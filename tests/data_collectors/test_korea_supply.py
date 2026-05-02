"""KoreaSupplyCollector 단위 테스트 (mock 기반).

테스트 대상:
  1. 컬럼 매핑: pykrx 한국어 컬럼 → Firestore 영문 필드
  2. Rate limit: N개 호출 시 N번 sleep
  3. Firestore batch: 1000 doc → 490+490+20 = 3 commit
  4. Doc ID 형식: {ticker}_{date}
  5. 빈 응답 / 예외 graceful 처리
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from utils.data_collectors.korea_supply import (
    CORE_INVESTORS,
    FIRESTORE_BATCH_LIMIT,
    MIN_DAYS_FOR_SIGNAL,
    KoreaSupplyAnalyzer,
    KoreaSupplyCollector,
    _safe_float,
    _safe_int,
    _to_date_str,
)


# ──────────────────────────────────────────────
# 헬퍼: pykrx 모듈 mock 생성
# ──────────────────────────────────────────────


def _mk_net_purchase_df(tickers: list[str], net_values: list[int]) -> pd.DataFrame:
    """pykrx get_market_net_purchases_of_equities_by_ticker 반환 흉내."""
    return pd.DataFrame(
        {
            "매도거래량": [1000] * len(tickers),
            "매수거래량": [1500] * len(tickers),
            "순매수거래량": [500] * len(tickers),
            "매도거래대금": [v // 2 for v in net_values],
            "매수거래대금": [v + v // 2 for v in net_values],
            "순매수거래대금": net_values,
        },
        index=tickers,
    )


def _mk_holding_df(dates: list[str], qtys: list[int], exhaustion_pcts: list[float]) -> pd.DataFrame:
    """pykrx get_exhaustion_rates_of_foreign_investment_by_date 반환 흉내."""
    return pd.DataFrame(
        {
            "상장주식수": [5_969_782_550] * len(dates),
            "보유수량": qtys,
            "지분율": [55.0] * len(dates),
            "한도수량": [5_969_782_550] * len(dates),
            "한도소진률": exhaustion_pcts,
        },
        index=pd.to_datetime(dates),
    )


def _mk_pykrx_mock(
    daily_responses: dict | None = None,
    holding_response: pd.DataFrame | None = None,
    daily_exception: Exception | None = None,
) -> MagicMock:
    """pykrx.stock 모듈 mock.

    daily_responses: {investor: DataFrame} — 투자자별 응답 매핑
    holding_response: 보유 시계열 응답 DataFrame
    daily_exception: 호출 시 raise할 예외 (예외 처리 테스트용)
    """
    pykrx = MagicMock()

    def _daily_side_effect(fromdate, todate, market, investor):
        if daily_exception is not None:
            raise daily_exception
        if daily_responses is None:
            return pd.DataFrame()
        return daily_responses.get(investor, pd.DataFrame())

    pykrx.get_market_net_purchases_of_equities_by_ticker.side_effect = _daily_side_effect

    if holding_response is not None:
        pykrx.get_exhaustion_rates_of_foreign_investment_by_date.return_value = holding_response
    else:
        pykrx.get_exhaustion_rates_of_foreign_investment_by_date.return_value = pd.DataFrame()

    return pykrx


# ──────────────────────────────────────────────
# 테스트 1: 컬럼 매핑 (방식 A)
# ──────────────────────────────────────────────


def test_collect_daily_snapshot_column_mapping():
    """4개 투자자 카테고리별 매매 데이터가 영문 prefix 필드로 정확히 매핑되어야 한다."""
    pykrx = _mk_pykrx_mock(
        daily_responses={
            "외국인합계": _mk_net_purchase_df(["005930", "000660"], [1_000_000_000, -500_000_000]),
            "기관합계": _mk_net_purchase_df(["005930", "000660"], [800_000_000, 200_000_000]),
            "연기금등": _mk_net_purchase_df(["005930", "000660"], [300_000_000, 100_000_000]),
            "개인": _mk_net_purchase_df(["005930", "000660"], [-700_000_000, 400_000_000]),
        }
    )

    collector = KoreaSupplyCollector(db=MagicMock(), pykrx_module=pykrx, sleep_sec=0)
    df = collector.collect_daily_snapshot("20251231", market="KOSPI")

    assert not df.empty
    assert len(df) == 2

    samsung = df[df["ticker"] == "005930"].iloc[0]
    assert samsung["date"] == "20251231"
    assert samsung["market"] == "KOSPI"
    # 외국인합계 → foreign_*
    assert samsung["foreign_net_buy_value"] == 1_000_000_000
    assert samsung["foreign_buy_value"] == 1_000_000_000 + 500_000_000
    assert samsung["foreign_sell_value"] == 500_000_000
    # 기관합계 → institution_*
    assert samsung["institution_net_buy_value"] == 800_000_000
    # 연기금등 → pension_*
    assert samsung["pension_net_buy_value"] == 300_000_000
    # 개인 → individual_*
    assert samsung["individual_net_buy_value"] == -700_000_000

    sk_hynix = df[df["ticker"] == "000660"].iloc[0]
    assert sk_hynix["foreign_net_buy_value"] == -500_000_000


def test_collect_daily_snapshot_empty_response_returns_empty_df():
    """모든 투자자 응답이 빈 DataFrame이면 결과도 빈 DataFrame (예외 X)."""
    pykrx = _mk_pykrx_mock(daily_responses={})
    collector = KoreaSupplyCollector(db=MagicMock(), pykrx_module=pykrx, sleep_sec=0)

    df = collector.collect_daily_snapshot("20251231", market="KOSPI")

    assert df.empty
    assert collector.stats.empty_responses == len(CORE_INVESTORS)


def test_collect_daily_snapshot_handles_pykrx_exception():
    """pykrx 예외는 graceful 처리 — 실패 카운트 증가, 빈 결과 반환."""
    pykrx = _mk_pykrx_mock(daily_exception=ConnectionError("KRX timeout"))
    collector = KoreaSupplyCollector(db=MagicMock(), pykrx_module=pykrx, sleep_sec=0)

    df = collector.collect_daily_snapshot("20251231", market="KOSPI")

    assert df.empty
    assert collector.stats.failed_calls == len(CORE_INVESTORS)
    assert collector.stats.successful_calls == 0


# ──────────────────────────────────────────────
# 테스트 2: 보유 시계열 (방식 B)
# ──────────────────────────────────────────────


def test_collect_ticker_holding_series_normalization():
    """보유 시계열 한국어 컬럼이 영문 필드로 정규화되어야 한다."""
    pykrx = _mk_pykrx_mock(
        holding_response=_mk_holding_df(
            dates=["2025-12-29", "2025-12-30"],
            qtys=[3_289_000_000, 3_289_500_000],
            exhaustion_pcts=[55.10, 55.12],
        )
    )
    collector = KoreaSupplyCollector(db=MagicMock(), pykrx_module=pykrx, sleep_sec=0)

    df = collector.collect_ticker_holding_series("005930", "20251229", "20251230")

    assert len(df) == 2
    assert list(df.columns) == [
        "ticker",
        "date",
        "foreign_holding_qty",
        "foreign_limit_qty",
        "foreign_exhaustion_pct",
    ]
    assert df.iloc[0]["ticker"] == "005930"
    assert df.iloc[0]["date"] == "20251229"
    assert df.iloc[0]["foreign_holding_qty"] == 3_289_000_000
    assert df.iloc[0]["foreign_exhaustion_pct"] == 55.10
    assert df.iloc[1]["date"] == "20251230"


# ──────────────────────────────────────────────
# 테스트 3: Rate limit
# ──────────────────────────────────────────────


def test_rate_limit_sleeps_per_call():
    """투자자별 호출마다 sleep이 1회씩 호출되어야 한다."""
    pykrx = _mk_pykrx_mock(daily_responses={})
    collector = KoreaSupplyCollector(db=MagicMock(), pykrx_module=pykrx, sleep_sec=0.7)

    with patch("utils.data_collectors.korea_supply.time.sleep") as mock_sleep:
        collector.collect_daily_snapshot("20251231", market="KOSPI")

    # 4 투자자 × 1회 sleep = 4번
    assert mock_sleep.call_count == len(CORE_INVESTORS)
    for call in mock_sleep.call_args_list:
        assert call.args[0] == 0.7


def test_holding_series_sleeps_once_per_call():
    """보유 시계열은 종목당 1회 호출 → 1회 sleep."""
    pykrx = _mk_pykrx_mock(
        holding_response=_mk_holding_df(["2025-12-30"], [3_000_000_000], [55.0])
    )
    collector = KoreaSupplyCollector(db=MagicMock(), pykrx_module=pykrx, sleep_sec=1.0)

    with patch("utils.data_collectors.korea_supply.time.sleep") as mock_sleep:
        collector.collect_ticker_holding_series("005930", "20251201", "20251231")

    assert mock_sleep.call_count == 1


# ──────────────────────────────────────────────
# 테스트 4: Firestore batch
# ──────────────────────────────────────────────


def test_save_to_firestore_batch_chunking():
    """1000개 record → 490 + 490 + 20 = 3 batch.commit()."""
    db = MagicMock()
    batch_mocks: list[MagicMock] = []

    def _new_batch():
        b = MagicMock()
        batch_mocks.append(b)
        return b

    db.batch.side_effect = _new_batch
    db.collection.return_value.document.side_effect = lambda doc_id: SimpleNamespace(id=doc_id)

    collector = KoreaSupplyCollector(db=db, pykrx_module=MagicMock(), sleep_sec=0)
    records = [{"ticker": f"00{i:04d}", "date": "20251231", "foreign_net_buy_value": i} for i in range(1000)]

    written = collector.save_to_firestore(records)

    assert written == 1000
    assert collector.stats.docs_written == 1000
    # 3개 batch.commit 호출 확인 (490 + 490 + 20)
    assert len(batch_mocks) == 3
    for b in batch_mocks:
        b.commit.assert_called_once()
    # batch별 set 호출 수 검증
    assert batch_mocks[0].set.call_count == FIRESTORE_BATCH_LIMIT
    assert batch_mocks[1].set.call_count == FIRESTORE_BATCH_LIMIT
    assert batch_mocks[2].set.call_count == 1000 - 2 * FIRESTORE_BATCH_LIMIT


def test_save_to_firestore_doc_id_format():
    """Doc ID = {ticker}_{date} 형식."""
    db = MagicMock()
    db.batch.return_value = MagicMock()
    captured_doc_ids: list[str] = []
    db.collection.return_value.document.side_effect = lambda doc_id: (
        captured_doc_ids.append(doc_id) or SimpleNamespace(id=doc_id)
    )

    collector = KoreaSupplyCollector(db=db, pykrx_module=MagicMock(), sleep_sec=0)
    records = [
        {"ticker": "005930", "date": "20251230", "foreign_net_buy_value": 100},
        {"ticker": "000660", "date": "20251230", "foreign_net_buy_value": -50},
    ]

    collector.save_to_firestore(records)

    assert captured_doc_ids == ["005930_20251230", "000660_20251230"]


def test_save_to_firestore_adds_metadata_fields():
    """저장 시 year/month/collected_at/data_source/collection_phase 자동 추가."""
    db = MagicMock()
    batch = MagicMock()
    db.batch.return_value = batch
    db.collection.return_value.document.return_value = SimpleNamespace(id="dummy")

    collector = KoreaSupplyCollector(db=db, pykrx_module=MagicMock(), sleep_sec=0)
    collector.save_to_firestore(
        [{"ticker": "005930", "date": "20251231"}], collection_phase="incremental"
    )

    assert batch.set.call_count == 1
    call_args = batch.set.call_args
    saved_doc = call_args.args[1]
    assert saved_doc["year"] == 2025
    assert saved_doc["month"] == 12
    assert saved_doc["collection_phase"] == "incremental"
    assert saved_doc["data_source"] == "pykrx_1.x"
    assert "collected_at" in saved_doc
    assert call_args.kwargs.get("merge") is True


def test_save_to_firestore_skips_records_missing_ticker_or_date():
    """ticker/date 누락 레코드는 skip (예외 X)."""
    db = MagicMock()
    batch = MagicMock()
    db.batch.return_value = batch
    db.collection.return_value.document.return_value = SimpleNamespace(id="dummy")

    collector = KoreaSupplyCollector(db=db, pykrx_module=MagicMock(), sleep_sec=0)
    records = [
        {"ticker": "005930", "date": "20251231"},  # 정상
        {"date": "20251231"},  # ticker 누락
        {"ticker": "000660"},  # date 누락
    ]
    collector.save_to_firestore(records)

    # 정상 1건만 batch.set
    assert batch.set.call_count == 1


def test_save_to_firestore_empty_records_returns_zero():
    """빈 리스트 입력 시 db 호출 0회, 0 반환."""
    db = MagicMock()
    collector = KoreaSupplyCollector(db=db, pykrx_module=MagicMock(), sleep_sec=0)

    written = collector.save_to_firestore([])

    assert written == 0
    db.batch.assert_not_called()


# ──────────────────────────────────────────────
# 테스트 5: 유틸 함수
# ──────────────────────────────────────────────


@pytest.mark.parametrize(
    "input_val,expected",
    [
        (123, 123),
        (123.7, 123),
        (None, 0),
        (float("nan"), 0),
        ("abc", 0),
        ("100", 100),
    ],
)
def test_safe_int(input_val, expected):
    assert _safe_int(input_val) == expected


@pytest.mark.parametrize(
    "input_val,expected",
    [
        (55.123456, 55.1235),
        (None, 0.0),
        (float("nan"), 0.0),
        ("abc", 0.0),
    ],
)
def test_safe_float(input_val, expected):
    assert _safe_float(input_val) == expected


def test_to_date_str_from_timestamp():
    ts = pd.Timestamp("2025-12-31")
    assert _to_date_str(ts) == "20251231"


def test_to_date_str_from_string():
    assert _to_date_str("2025-12-31") == "20251231"
    assert _to_date_str("20251231") == "20251231"


# ──────────────────────────────────────────────
# 테스트 6: KoreaSupplyAnalyzer (Day 2)
# ──────────────────────────────────────────────


def _mk_analyzer_with_records(records: list[dict]) -> KoreaSupplyAnalyzer:
    """Firestore mock 주입한 analyzer.

    records: load_supply_history가 반환할 dict 리스트.
    """
    db = MagicMock()
    fake_docs = [SimpleNamespace(to_dict=lambda r=r: r) for r in records]
    # .where(...).where(...).stream() 체인 흉내
    query_chain = MagicMock()
    query_chain.stream.return_value = iter(fake_docs)
    query_chain.where.return_value = query_chain
    db.collection.return_value.where.return_value = query_chain
    return KoreaSupplyAnalyzer(db=db)


def _generate_supply_records(
    ticker: str,
    days: int,
    foreign_pcts: list[float] | None = None,
    foreign_net_buys: list[int] | None = None,
    institution_net_buys: list[int] | None = None,
    start_date: str = "20250101",
) -> list[dict]:
    """테스트용 supply records 생성."""
    base = datetime.strptime(start_date, "%Y%m%d") if False else None
    from datetime import datetime as _dt
    from datetime import timedelta as _td

    base_dt = _dt.strptime(start_date, "%Y%m%d")
    records = []
    for i in range(days):
        d = base_dt + _td(days=i)
        records.append(
            {
                "ticker": ticker,
                "date": d.strftime("%Y%m%d"),
                "foreign_exhaustion_pct": (foreign_pcts[i] if foreign_pcts else 50.0),
                "foreign_net_buy_value": (foreign_net_buys[i] if foreign_net_buys else 0),
                "institution_net_buy_value": (
                    institution_net_buys[i] if institution_net_buys else 0
                ),
            }
        )
    return records


def test_analyzer_get_consecutive_buy_days_counts_recent_buys():
    """최근부터 거꾸로 양수만 카운트, 첫 음수에서 멈춰야 함."""
    # 7일치: [-100, +50, +100, -10, +200, +300, +400]
    # 가장 최근 4일이 양수 → 최근 3일(거꾸로 4 5 6 7)... 잠깐 [+200, +300, +400]은 양수, -10 멈춤 → 3
    nets = [-100, 50, 100, -10, 200, 300, 400]
    records = _generate_supply_records("005930", 7, foreign_net_buys=nets)
    analyzer = _mk_analyzer_with_records(records)

    assert analyzer.get_consecutive_buy_days("005930") == 3


def test_analyzer_get_consecutive_buy_days_returns_zero_if_latest_is_sell():
    """마지막 날 순매도면 0."""
    nets = [100, 200, 300, -50]
    records = _generate_supply_records("005930", 4, foreign_net_buys=nets)
    analyzer = _mk_analyzer_with_records(records)

    assert analyzer.get_consecutive_buy_days("005930") == 0


def test_analyzer_get_consecutive_buy_days_empty_history():
    analyzer = _mk_analyzer_with_records([])
    assert analyzer.get_consecutive_buy_days("005930") == 0


def test_analyzer_get_30d_net_buy_sums_correctly():
    nets = [100_000_000, -50_000_000, 200_000_000, -30_000_000]  # = 220M
    records = _generate_supply_records("005930", 4, foreign_net_buys=nets)
    analyzer = _mk_analyzer_with_records(records)

    assert analyzer.get_30d_net_buy("005930") == 220_000_000


def test_analyzer_get_30d_net_buy_handles_none():
    """None/NaN 값은 0 취급."""
    records = _generate_supply_records("005930", 3, foreign_net_buys=[100, 200, 300])
    # 의도적으로 한 record의 net_buy를 None으로 변경
    records[1]["foreign_net_buy_value"] = None
    analyzer = _mk_analyzer_with_records(records)

    assert analyzer.get_30d_net_buy("005930") == 400


def test_analyzer_get_dual_buy_signal_counts_both_positive_days():
    """외국인 + 기관 둘 다 양수인 날만 카운트."""
    foreigns = [100, 200, -50, 300, 400]
    insts = [50, -10, 200, 100, 50]  # 둘 다 양수: idx 0, 3, 4 = 3일
    records = _generate_supply_records(
        "005930", 5, foreign_net_buys=foreigns, institution_net_buys=insts
    )
    analyzer = _mk_analyzer_with_records(records)

    result = analyzer.get_dual_buy_signal("005930")
    assert result["days"] == 3
    assert result["window"] == 30
    assert result["ratio"] == round(3 / 5, 3)


def test_analyzer_get_foreign_5y_trend_full_signal():
    """충분한 데이터 + 매수 흐름 + 평균 초과 → increasing_above_avg."""
    # 25일 데이터: 보유 비중 50→55 (현재 55 > 평균 ~52)
    # 30일 net buy 양수 합계
    pcts = [50.0 + i * 0.2 for i in range(25)]  # 50.0, 50.2, ..., 54.8
    nets = [10_000_000_000] * 25  # 매일 100억 매수
    records = _generate_supply_records("005930", 25, foreign_pcts=pcts, foreign_net_buys=nets)
    analyzer = _mk_analyzer_with_records(records)

    trend = analyzer.get_foreign_5y_trend("005930")

    assert trend["ticker"] == "005930"
    assert trend["data_points"] == 25
    assert trend["current_holding_pct"] == 54.8
    assert trend["5y_max"] == 54.8
    assert trend["5y_min"] == 50.0
    assert trend["interpretation_signal"] == "increasing_above_avg"
    assert trend["consecutive_buy_days"] == 25  # 전부 양수
    assert trend["30d_net_buy"] == 25 * 10_000_000_000


def test_analyzer_get_foreign_5y_trend_decreasing_below_avg():
    """매도 흐름 + 평균 미만 → decreasing_below_avg."""
    # 보유 비중 60→50 하락 (현재 50 < 평균 ~55)
    pcts = [60.0 - i * 0.4 for i in range(25)]
    nets = [-5_000_000_000] * 25  # 매일 50억 매도
    records = _generate_supply_records("005930", 25, foreign_pcts=pcts, foreign_net_buys=nets)
    analyzer = _mk_analyzer_with_records(records)

    trend = analyzer.get_foreign_5y_trend("005930")

    assert trend["interpretation_signal"] == "decreasing_below_avg"
    assert trend["consecutive_buy_days"] == 0


def test_analyzer_get_foreign_5y_trend_neutral():
    """평균 차이 < 0.5%p + 30일 net buy < 1억 → neutral."""
    # 보유 비중이 거의 변동 없음
    pcts = [50.0] * 25
    nets = [10_000_000, -5_000_000, 8_000_000, -3_000_000] + [0] * 21  # 합 = 10M (1억 미만)
    records = _generate_supply_records("005930", 25, foreign_pcts=pcts, foreign_net_buys=nets)
    analyzer = _mk_analyzer_with_records(records)

    trend = analyzer.get_foreign_5y_trend("005930")

    assert trend["interpretation_signal"] == "neutral"


def test_analyzer_get_foreign_5y_trend_insufficient_data():
    """MIN_DAYS_FOR_SIGNAL 미만 → insufficient_data + 모든 값 0."""
    records = _generate_supply_records(
        "005930", MIN_DAYS_FOR_SIGNAL - 1, foreign_pcts=[50.0] * (MIN_DAYS_FOR_SIGNAL - 1)
    )
    analyzer = _mk_analyzer_with_records(records)

    trend = analyzer.get_foreign_5y_trend("005930")

    assert trend["interpretation_signal"] == "insufficient_data"
    assert trend["current_holding_pct"] == 0.0
    assert trend["data_points"] == MIN_DAYS_FOR_SIGNAL - 1


def test_analyzer_get_foreign_5y_trend_empty_history():
    analyzer = _mk_analyzer_with_records([])
    trend = analyzer.get_foreign_5y_trend("999999")

    assert trend["interpretation_signal"] == "insufficient_data"
    assert trend["data_points"] == 0


def test_analyzer_load_supply_history_handles_firestore_exception():
    """Firestore 에러는 graceful 처리 — 빈 DataFrame 반환."""
    db = MagicMock()
    db.collection.return_value.where.side_effect = ConnectionError("network error")
    analyzer = KoreaSupplyAnalyzer(db=db)

    df = analyzer.load_supply_history("005930", days=30)

    assert df.empty


def test_analyzer_load_supply_history_sorts_by_date_ascending():
    """date 컬럼이 오름차순 정렬되어 반환."""
    # 의도적으로 역순으로 records 작성
    records = [
        {"ticker": "005930", "date": "20251231", "foreign_net_buy_value": 100},
        {"ticker": "005930", "date": "20251229", "foreign_net_buy_value": 50},
        {"ticker": "005930", "date": "20251230", "foreign_net_buy_value": 75},
    ]
    analyzer = _mk_analyzer_with_records(records)

    df = analyzer.load_supply_history("005930", days=10)

    assert list(df["date"]) == ["20251229", "20251230", "20251231"]


# datetime import for record generators
from datetime import datetime  # noqa: E402
