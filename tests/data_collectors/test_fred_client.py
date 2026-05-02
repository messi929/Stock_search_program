"""utils/data_collectors/fred_client.py 단위 테스트 (mock fredapi)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from utils.data_collectors.fred_client import (
    FRED_SERIES,
    FREDClient,
    _unit_label,
    mask_api_key_in_str,
)


# ──────────────────────────────────────────────
# 1. FRED_SERIES 정합성
# ──────────────────────────────────────────────


def test_fred_series_has_minimum_12_entries():
    assert len(FRED_SERIES) >= 12


def test_fred_series_required_categories_present():
    """4 카테고리 모두 최소 1개 이상."""
    cats = {meta["category"] for meta in FRED_SERIES.values()}
    assert "interest_rate" in cats
    assert "business_cycle" in cats
    assert "inflation" in cats
    assert "currency" in cats


@pytest.mark.parametrize(
    "axis_key,expected_series_id",
    [
        ("fed_funds_rate", "DFF"),
        ("treasury_10y", "DGS10"),
        ("yield_spread_10y_2y", "T10Y2Y"),
        ("industrial_production", "INDPRO"),
        ("cpi_all", "CPIAUCSL"),
        ("cpi_core", "CPILFESL"),
        ("pce_core", "PCEPILFE"),
        ("dxy_broad", "DTWEXBGS"),
    ],
)
def test_fred_series_correct_mapping(axis_key, expected_series_id):
    assert FRED_SERIES[axis_key]["series_id"] == expected_series_id


def test_fred_series_all_have_required_meta():
    for key, meta in FRED_SERIES.items():
        assert "series_id" in meta
        assert "category" in meta
        assert "frequency" in meta
        assert meta["frequency"] in ("D", "M", "Q", "A")
        assert "description" in meta


# ──────────────────────────────────────────────
# 2. mask_api_key_in_str (보안)
# ──────────────────────────────────────────────


def test_mask_api_key_basic():
    raw = "https://api.stlouisfed.org/...?api_key=c270656a6410dd4c7f6cc046dfc17a7f&series_id=DFF"
    masked = mask_api_key_in_str(raw)
    assert "c270656a6410dd4c7f6cc046dfc17a7f" not in masked
    assert "api_key=***" in masked
    assert "series_id=DFF" in masked


def test_mask_api_key_case_insensitive():
    raw = "API_KEY=ABCDEF0123456789ABCDEF0123456789"
    assert "ABCDEF" not in mask_api_key_in_str(raw)


# ──────────────────────────────────────────────
# 3. _unit_label
# ──────────────────────────────────────────────


@pytest.mark.parametrize(
    "category,expected",
    [
        ("interest_rate", "percent"),
        ("business_cycle", "index_or_count"),
        ("inflation", "index_yoy"),
        ("currency", "index"),
        ("commodity", "usd_per_barrel"),
        ("unknown_category", "raw"),
    ],
)
def test_unit_label(category, expected):
    assert _unit_label(category) == expected


# ──────────────────────────────────────────────
# 4. FREDClient.get_series
# ──────────────────────────────────────────────


def _mk_fred_with_series(series_data: pd.Series | None) -> MagicMock:
    fred = MagicMock()
    if series_data is None:
        fred.get_series.return_value = pd.Series(dtype=float)
    else:
        fred.get_series.return_value = series_data
    return fred


def test_get_series_normal_response():
    """fredapi가 pd.Series 반환 → NaN 제거 후 그대로."""
    series = pd.Series(
        [5.33, 5.32, 5.30, float("nan"), 5.25],
        index=pd.to_datetime(["2025-12-27", "2025-12-28", "2025-12-29", "2025-12-30", "2025-12-31"]),
    )
    fred = _mk_fred_with_series(series)
    client = FREDClient(api_key="x" * 32, fred_instance=fred, sleep_sec=0)

    result = client.get_series("DFF", observation_start="2025-12-27", observation_end="2025-12-31")

    assert len(result) == 4  # NaN 제거
    assert result.iloc[-1] == 5.25
    assert client.stats.successful_calls == 1
    # observation_start/end 정확히 전달되었는지 검증
    fred.get_series.assert_called_once_with(
        "DFF", observation_start="2025-12-27", observation_end="2025-12-31"
    )


def test_get_series_without_dates():
    """date 인자 None이면 fredapi에 전달 X."""
    fred = _mk_fred_with_series(pd.Series([5.0], index=pd.to_datetime(["2025-12-31"])))
    client = FREDClient(api_key="x" * 32, fred_instance=fred, sleep_sec=0)

    client.get_series("DFF")

    fred.get_series.assert_called_once_with("DFF")


def test_get_series_empty_response():
    fred = _mk_fred_with_series(None)
    client = FREDClient(api_key="x" * 32, fred_instance=fred, sleep_sec=0)

    result = client.get_series("DFF")

    assert result.empty
    assert client.stats.empty_responses == 1


def test_get_series_handles_exception():
    fred = MagicMock()
    fred.get_series.side_effect = ConnectionError("FRED timeout")
    client = FREDClient(api_key="x" * 32, fred_instance=fred, sleep_sec=0)

    result = client.get_series("DFF")

    assert result.empty
    assert client.stats.failed_calls == 1


def test_get_series_rate_limit_sleep_called():
    fred = _mk_fred_with_series(pd.Series([5.0], index=pd.to_datetime(["2025-12-31"])))
    client = FREDClient(api_key="x" * 32, fred_instance=fred, sleep_sec=0.3)

    with patch("utils.data_collectors.fred_client.time.sleep") as mock_sleep:
        client.get_series("DFF")

    mock_sleep.assert_called_once_with(0.3)


# ──────────────────────────────────────────────
# 5. FREDClient.get_latest_value
# ──────────────────────────────────────────────


def test_get_latest_value_normal():
    series = pd.Series([5.30, 5.33], index=pd.to_datetime(["2025-12-30", "2025-12-31"]))
    fred = MagicMock()
    fred.get_series_latest_release.return_value = series
    fred.get_series_info.return_value = {
        "title": "Federal Funds Effective Rate",
        "frequency": "Daily, 7-Day",
        "units": "Percent",
    }
    client = FREDClient(api_key="x" * 32, fred_instance=fred, sleep_sec=0)

    result = client.get_latest_value("DFF")

    assert result is not None
    assert result["series_id"] == "DFF"
    assert result["latest_value"] == 5.33
    assert result["latest_date"] == "2025-12-31"
    assert result["title"] == "Federal Funds Effective Rate"
    assert result["units"] == "Percent"


def test_get_latest_value_handles_empty():
    fred = MagicMock()
    fred.get_series_latest_release.return_value = pd.Series(dtype=float)
    fred.get_series_info.return_value = {}
    client = FREDClient(api_key="x" * 32, fred_instance=fred, sleep_sec=0)

    assert client.get_latest_value("DFF") is None
    assert client.stats.empty_responses == 1


def test_get_latest_value_handles_exception():
    fred = MagicMock()
    fred.get_series_latest_release.side_effect = RuntimeError("API error")
    client = FREDClient(api_key="x" * 32, fred_instance=fred, sleep_sec=0)

    assert client.get_latest_value("DFF") is None
    assert client.stats.failed_calls == 1


# ──────────────────────────────────────────────
# 6. FREDClient.get_multiple_series
# ──────────────────────────────────────────────


def test_get_multiple_series_default_returns_all_keys():
    fred = _mk_fred_with_series(pd.Series([1.0], index=pd.to_datetime(["2025-12-31"])))
    client = FREDClient(api_key="x" * 32, fred_instance=fred, sleep_sec=0)

    result = client.get_multiple_series()

    assert len(result) == len(FRED_SERIES)
    assert set(result.keys()) == set(FRED_SERIES.keys())
    assert fred.get_series.call_count == len(FRED_SERIES)


def test_get_multiple_series_specific_keys():
    fred = _mk_fred_with_series(pd.Series([5.33], index=pd.to_datetime(["2025-12-31"])))
    client = FREDClient(api_key="x" * 32, fred_instance=fred, sleep_sec=0)

    result = client.get_multiple_series(["fed_funds_rate", "treasury_10y"])

    assert set(result.keys()) == {"fed_funds_rate", "treasury_10y"}
    # 호출된 series_id 검증
    called_series = [c.args[0] for c in fred.get_series.call_args_list]
    assert "DFF" in called_series
    assert "DGS10" in called_series


def test_get_multiple_series_unknown_key_skipped():
    fred = _mk_fred_with_series(pd.Series([1.0], index=pd.to_datetime(["2025-12-31"])))
    client = FREDClient(api_key="x" * 32, fred_instance=fred, sleep_sec=0)

    result = client.get_multiple_series(["fed_funds_rate", "unknown_key"])

    assert "unknown_key" in result
    assert result["unknown_key"].empty
    # 알 수 없는 키는 fred.get_series 호출 X
    assert fred.get_series.call_count == 1


# ──────────────────────────────────────────────
# 7. normalize_to_records
# ──────────────────────────────────────────────


def test_normalize_to_records_normal():
    series = pd.Series(
        [5.30, 5.33], index=pd.to_datetime(["2025-12-30", "2025-12-31"])
    )
    fred = MagicMock()
    client = FREDClient(api_key="x" * 32, fred_instance=fred, sleep_sec=0)

    records = client.normalize_to_records("fed_funds_rate", series)

    assert len(records) == 2
    r0 = records[0]
    assert r0["indicator_key"] == "fed_funds_rate"
    assert r0["country"] == "US"
    assert r0["category"] == "interest_rate"
    assert r0["date"] == "20251230"
    assert r0["value"] == 5.30
    assert r0["unit"] == "percent"
    assert r0["frequency"] == "D"
    assert r0["source"] == "FRED"
    assert r0["source_series_id"] == "DFF"
    assert "collected_at" in r0


def test_normalize_to_records_skips_nan():
    series = pd.Series(
        [5.30, float("nan"), 5.33],
        index=pd.to_datetime(["2025-12-29", "2025-12-30", "2025-12-31"]),
    )
    client = FREDClient(api_key="x" * 32, fred_instance=MagicMock(), sleep_sec=0)

    records = client.normalize_to_records("fed_funds_rate", series)

    assert len(records) == 2
    dates = [r["date"] for r in records]
    assert "20251230" not in dates


def test_normalize_to_records_unknown_key():
    series = pd.Series([1.0], index=pd.to_datetime(["2025-12-31"]))
    client = FREDClient(api_key="x" * 32, fred_instance=MagicMock(), sleep_sec=0)

    records = client.normalize_to_records("unknown_key", series)

    assert records == []


def test_normalize_to_records_empty_series():
    client = FREDClient(api_key="x" * 32, fred_instance=MagicMock(), sleep_sec=0)
    assert client.normalize_to_records("fed_funds_rate", pd.Series(dtype=float)) == []


# ──────────────────────────────────────────────
# 8. lazy initialization
# ──────────────────────────────────────────────


def test_fred_lazy_init_only_when_accessed():
    """fred_instance 주입 안 하면 첫 access 전엔 fredapi import X."""
    client = FREDClient(api_key="x" * 32, sleep_sec=0)
    assert client._fred is None

    # property 접근 시 import (이 테스트는 실제 import 일어나는 검증, mock으로 회피 필요)
    with patch("fredapi.Fred") as MockFred:
        MockFred.return_value = MagicMock()
        _ = client.fred
        MockFred.assert_called_once_with(api_key="x" * 32)
