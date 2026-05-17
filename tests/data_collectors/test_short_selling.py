"""utils/data_collectors/short_selling.py 단위 테스트."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pandas as pd
import pytest

from utils.data_collectors import short_selling as ss


@pytest.fixture(autouse=True)
def _reset_policy_cache():
    ss.reset_policy_cache()
    yield
    ss.reset_policy_cache()


# ──────────────────────────────────────────────
# 1. 정책 이력 (정적 데이터)
# ──────────────────────────────────────────────


def test_get_current_policy_status_has_required_fields():
    status = ss.get_current_policy_status()
    assert "status" in status
    assert "since" in status
    assert "scope" in status


def test_get_current_policy_status_is_resumed():
    """2025-03-31 전면 재개 후이므로 현재 상태도 재개."""
    status = ss.get_current_policy_status()
    assert "재개" in status["status"]


def test_get_policy_history_sorted_ascending():
    history = ss.get_policy_history()
    dates = [r["date"] for r in history]
    assert dates == sorted(dates)
    assert len(history) >= 5  # 주요 정책 변동 5건 이상


def test_get_policy_history_includes_2020_covid():
    history = ss.get_policy_history()
    covid = next((r for r in history if r["date"] == "2020-03-16"), None)
    assert covid is not None
    assert "코로나" in covid["reason"]


# ──────────────────────────────────────────────
# 2. _classify_short_ratio
# ──────────────────────────────────────────────


@pytest.mark.parametrize(
    "ratio,expected_prefix",
    [
        (0.5, "매우 낮음"),
        (1.5, "낮음"),
        (3.5, "중간"),
        (7.0, "높음"),
        (15.0, "매우 높음"),
    ],
)
def test_classify_short_ratio(ratio, expected_prefix):
    assert ss._classify_short_ratio(ratio).startswith(expected_prefix)


# ──────────────────────────────────────────────
# 3. _interpret_short_trend
# ──────────────────────────────────────────────


def test_interpret_short_trend_insufficient_data():
    """1~4일치 데이터는 '표본 부족'."""
    assert "표본 부족" in ss._interpret_short_trend(-1_000_000, current_qty=10_000_000, data_points=3)


def test_interpret_short_trend_zero_data():
    """0일치는 '수집된 데이터 없음'으로 명확히 구분."""
    assert ss._interpret_short_trend(0, current_qty=0, data_points=0) == "수집된 데이터 없음"


def test_interpret_short_trend_neutral_change_relative():
    """현재 잔고 대비 5% 미만 변화 → '변화 미미' (대형주 noise 보정)."""
    # 1억주 잔고 + 100만주 변화 = 1% → 미미
    assert ss._interpret_short_trend(1_000_000, current_qty=100_000_000, data_points=20) == "변화 미미"
    assert ss._interpret_short_trend(-1_000_000, current_qty=100_000_000, data_points=20) == "변화 미미"


def test_interpret_short_trend_significant_relative_change():
    """현재 잔고 대비 5% 이상 변화 → 추세 라벨."""
    # 1억주 잔고 + 1천만주 감소 = 10% → 의미있는 감소
    label = ss._interpret_short_trend(-10_000_000, current_qty=100_000_000, data_points=20)
    assert "감소" in label and "커버링" in label


def test_interpret_short_trend_decreasing_is_covering():
    """잔고 5% 이상 감소 → 숏 커버링 가능성."""
    label = ss._interpret_short_trend(-1_000_000, current_qty=10_000_000, data_points=20)
    assert "커버링" in label


def test_interpret_short_trend_increasing_is_betting():
    """잔고 5% 이상 증가 → 숏 베팅 확대 가능성."""
    label = ss._interpret_short_trend(2_000_000, current_qty=10_000_000, data_points=20)
    assert "베팅" in label or "확대" in label


def test_interpret_short_trend_zero_balance_uses_fallback():
    """현재 잔고 0인 종목 → 절대 임계 fallback."""
    # 50K 변화 (절대 임계 100K 미만) → 미미
    assert ss._interpret_short_trend(50_000, current_qty=0, data_points=20) == "변화 미미"


# ──────────────────────────────────────────────
# 4. KoreaShortSellingCollector — collect/normalize
# ──────────────────────────────────────────────


def _mk_short_balance_df(dates: list[str], qtys: list[int], ratios: list[float]) -> pd.DataFrame:
    """pykrx get_shorting_balance_by_date 반환 흉내."""
    return pd.DataFrame(
        {
            "공매도잔고": qtys,
            "공매도금액": [q * 70_000 for q in qtys],
            "상장주식수": [5_969_782_550] * len(dates),
            "시가총액": [400_000_000_000_000] * len(dates),
            "비중": ratios,
        },
        index=pd.to_datetime(dates),
    )


def test_collect_ticker_short_series_normalization():
    """한국어 컬럼 → 영문 필드 매핑."""
    pykrx = MagicMock()
    pykrx.get_shorting_balance_by_date.return_value = _mk_short_balance_df(
        ["2025-04-28", "2025-04-29"], [12_500_000, 12_000_000], [1.20, 1.18]
    )
    collector = ss.KoreaShortSellingCollector(
        db=MagicMock(), pykrx_module=pykrx, sleep_sec=0
    )

    df = collector.collect_ticker_short_series("005930", "20250428", "20250429")

    assert len(df) == 2
    assert list(df.columns) == [
        "ticker",
        "date",
        "short_balance_qty",
        "short_balance_value",
        "listed_shares",
        "market_cap",
        "short_ratio_pct",
    ]
    assert df.iloc[0]["ticker"] == "005930"
    assert df.iloc[0]["date"] == "20250428"
    assert df.iloc[0]["short_balance_qty"] == 12_500_000
    assert df.iloc[0]["short_ratio_pct"] == 1.20


def test_collect_ticker_short_series_empty_response():
    pykrx = MagicMock()
    pykrx.get_shorting_balance_by_date.return_value = pd.DataFrame()
    collector = ss.KoreaShortSellingCollector(
        db=MagicMock(), pykrx_module=pykrx, sleep_sec=0
    )

    df = collector.collect_ticker_short_series("005930", "20250428", "20250429")

    assert df.empty
    assert collector.stats.empty_responses == 1


def test_collect_ticker_short_series_handles_exception():
    pykrx = MagicMock()
    pykrx.get_shorting_balance_by_date.side_effect = ConnectionError("KRX timeout")
    collector = ss.KoreaShortSellingCollector(
        db=MagicMock(), pykrx_module=pykrx, sleep_sec=0
    )

    df = collector.collect_ticker_short_series("005930", "20250428", "20250429")

    assert df.empty
    assert collector.stats.failed_calls == 1


def test_save_to_firestore_doc_id_and_metadata():
    db = MagicMock()
    batch = MagicMock()
    db.batch.return_value = batch
    captured: list[str] = []
    db.collection.return_value.document.side_effect = lambda doc_id: (
        captured.append(doc_id) or SimpleNamespace(id=doc_id)
    )

    collector = ss.KoreaShortSellingCollector(db=db, pykrx_module=MagicMock(), sleep_sec=0)
    collector.save_to_firestore(
        [{"ticker": "005930", "date": "20250428", "short_balance_qty": 12_500_000}]
    )

    assert captured == ["005930_20250428"]
    saved_doc = batch.set.call_args.args[1]
    assert saved_doc["data_source"] == "pykrx_1.x"
    assert "collected_at" in saved_doc


# ──────────────────────────────────────────────
# 5. KoreaShortSellingAnalyzer.analyze_short_signals
# ──────────────────────────────────────────────


def _mk_analyzer_with_history(records: list[dict]) -> ss.KoreaShortSellingAnalyzer:
    db = MagicMock()
    fake_docs = [SimpleNamespace(to_dict=lambda r=r: r) for r in records]
    query_chain = MagicMock()
    query_chain.stream.return_value = iter(fake_docs)
    query_chain.where.return_value = query_chain
    db.collection.return_value.where.return_value = query_chain
    return ss.KoreaShortSellingAnalyzer(db=db)


def test_analyze_short_signals_covering():
    """잔고 12.5M → 12.0M (감소) → 숏 커버링."""
    records = [
        {"ticker": "005930", "date": "20250401", "short_balance_qty": 13_000_000, "short_ratio_pct": 1.30},
        {"ticker": "005930", "date": "20250410", "short_balance_qty": 12_700_000, "short_ratio_pct": 1.25},
        {"ticker": "005930", "date": "20250415", "short_balance_qty": 12_300_000, "short_ratio_pct": 1.22},
        {"ticker": "005930", "date": "20250420", "short_balance_qty": 12_100_000, "short_ratio_pct": 1.20},
        {"ticker": "005930", "date": "20250425", "short_balance_qty": 12_000_000, "short_ratio_pct": 1.18},
        {"ticker": "005930", "date": "20250428", "short_balance_qty": 11_500_000, "short_ratio_pct": 1.15},
    ]
    analyzer = _mk_analyzer_with_history(records)

    result = analyzer.analyze_short_signals("005930")

    assert result["current_short_balance_qty"] == 11_500_000
    assert result["current_short_ratio_pct"] == 1.15
    assert result["change_qty"] == 11_500_000 - 13_000_000  # -1.5M
    assert result["change_pct_points"] == round(1.15 - 1.30, 2)
    assert "커버링" in result["interpretation"]
    assert result["ratio_classification"].startswith("낮음")
    assert result["data_points"] == 6
    assert result["actual_window_days"] >= 25  # 20250401 ~ 20250428 = 27일
    assert result["requested_window_days"] == 30
    assert "interpretation_note" in result
    assert "policy_status" in result


def test_analyze_short_signals_increasing():
    """잔고 50% 증가 (10M → 15M) → 베팅/확대 라벨."""
    records = [
        {"ticker": "005930", "date": "20250401", "short_balance_qty": 10_000_000, "short_ratio_pct": 1.00},
        {"ticker": "005930", "date": "20250410", "short_balance_qty": 11_000_000, "short_ratio_pct": 1.10},
        {"ticker": "005930", "date": "20250415", "short_balance_qty": 12_000_000, "short_ratio_pct": 1.20},
        {"ticker": "005930", "date": "20250420", "short_balance_qty": 13_000_000, "short_ratio_pct": 1.30},
        {"ticker": "005930", "date": "20250425", "short_balance_qty": 14_000_000, "short_ratio_pct": 1.40},
        {"ticker": "005930", "date": "20250428", "short_balance_qty": 15_000_000, "short_ratio_pct": 1.50},
    ]
    analyzer = _mk_analyzer_with_history(records)

    result = analyzer.analyze_short_signals("005930")
    assert ("베팅" in result["interpretation"]) or ("확대" in result["interpretation"])


def test_analyze_short_signals_neutral_change():
    """현재 잔고 대비 변화 5% 미만이면 '변화 미미' (12M 기준 60K = 0.5%)."""
    records = [
        {"ticker": "005930", "date": f"2025040{i}", "short_balance_qty": 12_000_000 + i * 10_000,
         "short_ratio_pct": 1.20}
        for i in range(1, 7)
    ]
    analyzer = _mk_analyzer_with_history(records)

    result = analyzer.analyze_short_signals("005930")
    assert result["interpretation"] == "변화 미미"


def test_analyze_short_signals_empty_history():
    analyzer = _mk_analyzer_with_history([])
    result = analyzer.analyze_short_signals("999999")

    assert result["current_short_balance_qty"] == 0
    assert result["interpretation"] == "수집된 데이터 없음"
    assert result["data_points"] == 0
    assert result["actual_window_days"] == 0
    assert result["requested_window_days"] == 30


def test_analyze_short_signals_includes_policy_status():
    """결과에 항상 정책 상태 포함."""
    analyzer = _mk_analyzer_with_history([])
    result = analyzer.analyze_short_signals("005930")
    assert "재개" in result["policy_status"].get("status", "")


def test_analyze_short_signals_includes_interpretation_note():
    """LEGAL: 추세 ≠ 매매 신호 명시."""
    analyzer = _mk_analyzer_with_history([])
    result = analyzer.analyze_short_signals("005930")
    assert result["interpretation_note"] == "추세 ≠ 매매 신호 (정보 제공 목적)"


def test_analyze_short_signals_handles_firestore_exception():
    db = MagicMock()
    db.collection.return_value.where.side_effect = ConnectionError("network")
    analyzer = ss.KoreaShortSellingAnalyzer(db=db)

    result = analyzer.analyze_short_signals("005930")

    assert result["data_points"] == 0
    assert result["interpretation"] == "수집된 데이터 없음"
