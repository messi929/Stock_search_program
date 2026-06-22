"""jobs/daily_macro_collect.py + jobs/monthly_regime_calc.py 단위 + 통합 테스트.

검증 범주:
  1. daily_macro_collect — 변동 감지, dry-run, FRED/ECOS 일괄 수집
  2. monthly_regime_calc — 사이클 입력 빌드, 국면 전환 감지
  3. End-to-end 통합 — Mock FRED+ECOS → 사이클 → 국면 시나리오
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from jobs import daily_macro_collect as dmc
from jobs import monthly_regime_calc as mrc


# ──────────────────────────────────────────────
# 1. detect_significant_change
# ──────────────────────────────────────────────


class TestSignificantChange:
    def test_interest_rate_significant_change(self):
        records = [
            {"date": "20260401", "value": 5.00},
            {"date": "20260501", "value": 5.25},  # +25bp = 임계 10bp 초과
        ]
        change = dmc.detect_significant_change("fed_funds_rate", "interest_rate", records)
        assert change is not None
        assert change["change"] == 0.25

    def test_no_change_below_threshold(self):
        records = [
            {"date": "20260401", "value": 5.00},
            {"date": "20260501", "value": 5.05},  # +5bp = 임계 미만
        ]
        change = dmc.detect_significant_change("fed_funds_rate", "interest_rate", records)
        assert change is None

    def test_currency_significant_change(self):
        records = [
            {"date": "20260401", "value": 100.0},
            {"date": "20260501", "value": 101.0},  # +1.0 = 임계 0.5 초과
        ]
        change = dmc.detect_significant_change("dxy_broad", "currency", records)
        assert change is not None

    def test_returns_none_for_single_record(self):
        records = [{"date": "20260501", "value": 5.0}]
        assert dmc.detect_significant_change("x", "interest_rate", records) is None

    def test_returns_none_for_unknown_category(self):
        records = [
            {"date": "20260401", "value": 1.0},
            {"date": "20260501", "value": 2.0},
        ]
        assert dmc.detect_significant_change("x", "unknown_category", records) is None

    def test_handles_none_values(self):
        records = [
            {"date": "20260401", "value": None},
            {"date": "20260501", "value": 5.0},
        ]
        assert dmc.detect_significant_change("x", "interest_rate", records) is None

    def test_usd_krw_uses_relative_pct_comparison(self):
        """USD/KRW는 절대값이 아닌 % 변화 임계 (DXY와 단위 다름)."""
        records = [
            {"date": "20260401", "value": 1400.0},
            {"date": "20260501", "value": 1420.0},  # +20원 = 1.43% > 1% 임계
        ]
        change = dmc.detect_significant_change("usd_krw", "currency", records)
        assert change is not None
        assert change["comparison"] == "relative_pct"
        assert change["change"] == round(20.0 / 1400.0 * 100, 4)

    def test_usd_krw_below_threshold(self):
        """USD/KRW 0.5% 미만 변동은 미미 (1% 임계 미만)."""
        records = [
            {"date": "20260401", "value": 1400.0},
            {"date": "20260501", "value": 1405.0},  # +5원 = 0.36%
        ]
        assert dmc.detect_significant_change("usd_krw", "currency", records) is None

    def test_oil_wti_uses_relative_pct(self):
        records = [
            {"date": "20260401", "value": 70.0},
            {"date": "20260501", "value": 74.0},  # +5.7% > 5%
        ]
        change = dmc.detect_significant_change("oil_wti", "commodity", records)
        assert change is not None
        assert change["comparison"] == "relative_pct"

    def test_relative_pct_handles_zero_prev(self):
        """이전값 0 → ZeroDivisionError 회피, None 반환."""
        records = [
            {"date": "20260401", "value": 0.0},
            {"date": "20260501", "value": 5.0},
        ]
        assert dmc.detect_significant_change("usd_krw", "currency", records) is None


# ──────────────────────────────────────────────
# 2. daily_macro_collect 흐름 (dry-run)
# ──────────────────────────────────────────────


def test_daily_collect_dry_run_no_firestore_writes(monkeypatch):
    """dry-run 모드는 Firestore 쓰기 없이 호출 흐름만 검증."""
    # FRED + ECOS 모두 mock
    mock_fred = MagicMock()
    mock_fred.get_series.return_value = pd.Series(
        [5.30, 5.31], index=pd.to_datetime(["2026-04-30", "2026-05-01"])
    )
    mock_fred.normalize_to_records.return_value = [
        {"indicator_key": "fed_funds_rate", "date": "20260501", "value": 5.31, "category": "interest_rate"}
    ]

    mock_ecos = MagicMock()
    mock_ecos.get_series_by_axis_key.return_value = [
        {"TIME": "202605", "DATA_VALUE": "3.0"}
    ]
    mock_ecos.normalize_to_records.return_value = [
        {"indicator_key": "base_rate", "date": "20260501", "value": 3.0, "category": "interest_rate"}
    ]

    monkeypatch.setattr(dmc, "FREDClient", lambda: mock_fred)
    monkeypatch.setattr(dmc, "ECOSClient", lambda: mock_ecos)

    summary = dmc.run_daily_collect(
        series_keys=["fed_funds_rate", "base_rate"],
        window_days=7,
        dry_run=True,
    )

    assert summary["dry_run"] is True
    assert "fred" in summary
    assert "ecos" in summary


def test_daily_collect_unknown_fred_key_skipped(monkeypatch):
    """FRED_SERIES에 없는 키는 skip + 경고."""
    mock_fred = MagicMock()
    mock_fred.get_series.return_value = pd.Series(dtype=float)

    mock_ecos = MagicMock()
    mock_ecos.get_series_by_axis_key.return_value = []

    monkeypatch.setattr(dmc, "FREDClient", lambda: mock_fred)
    monkeypatch.setattr(dmc, "ECOSClient", lambda: mock_ecos)

    summary = dmc.run_daily_collect(
        series_keys=["nonexistent_key"], window_days=7, dry_run=True,
    )
    # nonexistent는 ECOS verified에도 없어서 attempted=0 가능
    assert summary["dry_run"] is True


# ──────────────────────────────────────────────
# 3. monthly_regime_calc — build_cycle_inputs
# ──────────────────────────────────────────────


def _mk_indicator_db(values_by_key: dict[str, float]):
    """indicator_key별 단일 값 반환하는 mock db."""
    db = MagicMock()

    def _stream_factory(key_value):
        # date 내림차순 1건만 반환
        return iter([SimpleNamespace(to_dict=lambda: {"date": "20260501", "value": key_value})])

    def _query_chain(query_calls: list, key: str):
        chain = MagicMock()
        chain.where.return_value = chain
        chain.stream.return_value = _stream_factory(values_by_key.get(key, 0.0))
        return chain

    # collection.where().where().stream() 체인 흉내 — indicator_key 추적은 어렵지만
    # 단순화: 모든 query는 첫 호출의 indicator_key 기준
    call_log = {"key": None}

    def _collection_side_effect(name):
        col = MagicMock()
        outer_chain = MagicMock()

        def _where_side_effect(*args, **kwargs):
            f = kwargs.get("filter") or (args[0] if args else None)
            if f and hasattr(f, "field_path") and f.field_path == "indicator_key":
                call_log["key"] = f.value
            return outer_chain

        outer_chain.where.side_effect = _where_side_effect

        def _stream():
            k = call_log["key"]
            if k and k in values_by_key:
                return iter([SimpleNamespace(to_dict=lambda: {"date": "20260501", "value": values_by_key[k]})])
            return iter([])

        outer_chain.stream.side_effect = _stream
        col.where.side_effect = _where_side_effect
        return col

    db.collection.side_effect = _collection_side_effect
    return db


def test_build_cycle_inputs_unknown_country_returns_none():
    """미지원 country → (None, [])."""
    db = MagicMock()
    inputs, missing = mrc.build_cycle_inputs(db, "JP")
    assert inputs is None
    assert missing == []


def test_build_cycle_inputs_us_with_data():
    """US 입력 빌드 — 모든 indicator 값 있을 때."""
    with patch.object(mrc, "_fetch_latest_value") as mock_latest, patch.object(
        mrc, "_fetch_value_at_offset"
    ) as mock_offset:
        mock_latest.return_value = 5.0
        mock_offset.return_value = 4.0

        inputs, missing = mrc.build_cycle_inputs(MagicMock(), "US")

    assert inputs is not None
    assert inputs["rate_current"] == 5.0
    assert inputs["rate_3m_ago"] == 4.0
    assert inputs["rate_12m_ago"] == 4.0
    assert inputs["dxy_current"] == 5.0
    # 모든 데이터 있을 때 missing 0건
    assert missing == []


def test_build_cycle_inputs_falls_back_when_offset_missing():
    """offset 데이터 없으면 current 값으로 fallback + missing에 기록."""
    with patch.object(mrc, "_fetch_latest_value") as mock_latest, patch.object(
        mrc, "_fetch_value_at_offset"
    ) as mock_offset:
        mock_latest.return_value = 5.0
        mock_offset.return_value = None  # offset 데이터 없음

        inputs, missing = mrc.build_cycle_inputs(MagicMock(), "US")

    assert inputs["rate_3m_ago"] == 5.0
    assert inputs["rate_12m_ago"] == 5.0
    # offset 누락 필드들 missing에 기록
    assert any("rate_3m_ago" in f for f in missing)
    assert any("rate_12m_ago" in f for f in missing)


def test_build_cycle_inputs_quarterly_uses_wider_window():
    """gdp_yoy_us는 freq=Q → 분기 발표 지연 대응으로 days_back=200일."""
    with patch.object(mrc, "_fetch_latest_value") as mock_latest, patch.object(
        mrc, "_fetch_value_at_offset"
    ) as mock_offset:
        mock_latest.return_value = 2.5
        mock_offset.return_value = 2.0

        mrc.build_cycle_inputs(MagicMock(), "US")

    # gdp_yoy_us 호출 시 days_back=200(분기 윈도우)인지 확인
    gdp_calls = [c for c in mock_latest.call_args_list if "gdp_yoy_us" in str(c)]
    assert len(gdp_calls) > 0
    for call in gdp_calls:
        if "days_back" in call.kwargs:
            assert call.kwargs["days_back"] == 200


def test_data_quality_known_gaps_for_kr():
    """KR은 unemployment + gdp_yoy 미수집 명시."""
    gaps = mrc.DATA_QUALITY_KNOWN_GAPS.get("KR", [])
    assert len(gaps) >= 2
    assert any("unemployment" in g for g in gaps)
    assert any("gdp_yoy" in g for g in gaps)


def test_data_quality_us_no_gaps():
    """US는 알려진 gap 없음 (모두 FRED + ECOS verified)."""
    assert mrc.DATA_QUALITY_KNOWN_GAPS.get("US") == []


# ──────────────────────────────────────────────
# 4. detect_regime_transition
# ──────────────────────────────────────────────


def test_detect_regime_transition_no_history_returns_none():
    db = MagicMock()
    db.collection.return_value.where.return_value.stream.return_value = iter([])

    transition = mrc.detect_regime_transition(db, "US", "Late Cycle")
    assert transition is None


def test_detect_regime_transition_same_regime_returns_none():
    db = MagicMock()
    docs = [
        SimpleNamespace(to_dict=lambda: {"regime": "Late Cycle", "calculated_at": "2026-04-01T00:00:00"})
    ]
    db.collection.return_value.where.return_value.stream.return_value = iter(docs)

    transition = mrc.detect_regime_transition(db, "US", "Late Cycle")
    assert transition is None


def test_detect_regime_transition_change_detected():
    db = MagicMock()
    docs = [
        SimpleNamespace(to_dict=lambda: {"regime": "Goldilocks", "calculated_at": "2026-04-01T00:00:00"})
    ]
    db.collection.return_value.where.return_value.stream.return_value = iter(docs)

    transition = mrc.detect_regime_transition(db, "US", "Stagflation")
    assert transition is not None
    assert transition["previous_regime"] == "Goldilocks"
    assert transition["current_regime"] == "Stagflation"
    assert transition["country"] == "US"


# ──────────────────────────────────────────────
# 5. End-to-end 통합 시나리오 (dry-run)
# ──────────────────────────────────────────────


def test_end_to_end_dry_run_us(monkeypatch):
    """dry-run 모드 monthly_regime_calc — Firestore 인증 없이 동작.

    실제 Firestore 미연결 → build_cycle_inputs는 0.0 반환 → detect_all_cycles 실행 → 결과 저장 시도.
    """
    summary = mrc.run_monthly_regime_calc(countries=["US"], dry_run=True)
    assert summary["dry_run"] is True
    assert summary["countries_processed"] == 1
    # 모든 값이 0이어도 사이클 계산은 가능 (전환기 등으로 분류)
    assert summary["cycles_calculated"] == 1


def test_end_to_end_both_countries_dry_run():
    summary = mrc.run_monthly_regime_calc(countries=["US", "KR"], dry_run=True)
    assert summary["countries_processed"] == 2


# ──────────────────────────────────────────────
# 6. CLI 진입점
# ──────────────────────────────────────────────


def test_daily_macro_main_dry_run_returns_exit_code():
    """--dry-run 메인 함수 호출 → exit code 0 또는 1 (변동 감지 여부)."""
    code = dmc.main(["--dry-run", "--series", "nonexistent_key"])
    assert code in (0, 1)


def test_monthly_regime_main_dry_run_returns_exit_code():
    code = mrc.main(["--country", "US", "--dry-run"])
    assert code in (0, 1)
