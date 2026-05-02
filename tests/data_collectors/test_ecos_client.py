"""utils/data_collectors/ecos_client.py 단위 테스트 (mock httpx)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from utils.data_collectors.ecos_client import (
    ECOS_CODES,
    DEFAULT_PAGE_SIZE,
    ECOSClient,
    _normalize_ecos_date,
    get_unverified_codes,
    get_verified_codes,
    mask_api_key_in_str,
    to_ecos_date_format,
)


# ──────────────────────────────────────────────
# 1. ECOS_CODES 정합성
# ──────────────────────────────────────────────


def test_ecos_codes_has_minimum_8_entries():
    assert len(ECOS_CODES) >= 8


def test_ecos_codes_required_categories_present():
    cats = {meta["category"] for meta in ECOS_CODES.values()}
    assert "interest_rate" in cats
    assert "business_cycle" in cats
    assert "inflation" in cats
    assert "currency" in cats


@pytest.mark.parametrize(
    "axis_key,expected_stat,expected_freq",
    [
        ("base_rate", "722Y001", "M"),
        # treasury는 일별 시장금리 통계(817Y002)로 정정 (2026-05-02 검증)
        ("treasury_3y", "817Y002", "D"),
        ("treasury_10y", "817Y002", "D"),
        ("gdp_yoy", "200Y002", "Q"),
        # 광공업생산은 AB00 코드 (I31AA → 미존재)
        ("industrial_production", "901Y033", "M"),
        ("cpi_total", "901Y009", "M"),
        ("cpi_core", "901Y009", "M"),
        ("usd_krw", "731Y001", "D"),
    ],
)
def test_ecos_codes_correct_mapping(axis_key, expected_stat, expected_freq):
    assert ECOS_CODES[axis_key]["stat_code"] == expected_stat
    assert ECOS_CODES[axis_key]["freq"] == expected_freq


def test_ecos_codes_treasury_uses_correct_item_codes():
    """817Y002의 010200000=국고채(3년), 010210000=국고채(10년) 정확히 매핑."""
    assert ECOS_CODES["treasury_3y"]["item_code1"] == "010200000"
    assert ECOS_CODES["treasury_10y"]["item_code1"] == "010210000"


def test_ecos_codes_industrial_production_uses_ab00_with_원계열():
    """광공업생산은 AB00(광공업) + item_code2='1'(원계열)."""
    meta = ECOS_CODES["industrial_production"]
    assert meta["item_code1"] == "AB00"
    assert meta["item_code2"] == "1"


def test_get_verified_codes_returns_subset():
    """verified=True 항목만 반환 (현재 6개: base_rate, treasury_3y/10y, industrial_production, cpi_total, usd_krw)."""
    verified = get_verified_codes()
    assert len(verified) == 6
    assert "base_rate" in verified
    assert "treasury_3y" in verified
    assert "treasury_10y" in verified
    assert "industrial_production" in verified
    assert "cpi_total" in verified
    assert "usd_krw" in verified


def test_get_unverified_codes_marks_pending_updates():
    """verified=False 항목 (gdp_yoy, cpi_core) — 한국은행 개편으로 코드 갱신 필요."""
    unverified = get_unverified_codes()
    assert "gdp_yoy" in unverified
    assert "cpi_core" in unverified
    for meta in unverified.values():
        assert "verified_note" in meta


def test_ecos_codes_all_have_required_meta():
    for key, meta in ECOS_CODES.items():
        assert "stat_code" in meta
        assert "item_code1" in meta
        assert meta["freq"] in ("D", "M", "Q", "A")
        assert "category" in meta
        assert "description" in meta


# ──────────────────────────────────────────────
# 2. mask_api_key_in_str (보안)
# ──────────────────────────────────────────────


def test_mask_api_key_bare_pattern():
    """bare 20자 영숫자 키 마스킹."""
    raw = "Failed with key 8P4FF1L7AS9ILQ2KX62K — try again"
    masked = mask_api_key_in_str(raw)
    assert "8P4FF1L7AS9ILQ2KX62K" not in masked
    assert "***" in masked


def test_mask_api_key_url_pattern():
    """URL 경로의 키 마스킹."""
    raw = "https://ecos.bok.or.kr/api/StatisticSearch/8P4FF1L7AS9ILQ2KX62K/json/kr/1/100/722Y001/M/202401/202412/0101000"
    masked = mask_api_key_in_str(raw)
    assert "8P4FF1L7AS9ILQ2KX62K" not in masked
    assert "/StatisticSearch/***/" in masked
    assert "722Y001" in masked  # 통계 코드는 보존


def test_mask_api_key_preserves_short_codes():
    """짧은 stat_code (4자리)나 freq는 마스킹되지 않아야."""
    raw = "722Y001 M 20240101"
    masked = mask_api_key_in_str(raw)
    assert "722Y001" in masked


# ──────────────────────────────────────────────
# 3. to_ecos_date_format
# ──────────────────────────────────────────────


@pytest.mark.parametrize(
    "input_date,freq,expected",
    [
        # D: YYYYMMDD
        ("2025-12-31", "D", "20251231"),
        ("20251231", "D", "20251231"),
        # M: YYYYMM
        ("2025-12", "M", "202512"),
        ("202512", "M", "202512"),
        ("2025-12-31", "M", "202512"),
        # Q: YYYY+분기
        ("2024-Q3", "Q", "20243"),
        ("2024Q3", "Q", "20243"),
        ("20243", "Q", "20243"),
        ("2024", "Q", "20241"),  # 기본 Q1
        # A: YYYY
        ("2024", "A", "2024"),
        ("2024-12-31", "A", "2024"),
    ],
)
def test_to_ecos_date_format(input_date, freq, expected):
    assert to_ecos_date_format(input_date, freq) == expected


def test_to_ecos_date_format_invalid_freq():
    with pytest.raises(ValueError, match="freq"):
        to_ecos_date_format("20240101", "X")


def test_to_ecos_date_format_invalid_quarter_raises():
    """분기 5+는 ValueError (1~4만 유효)."""
    with pytest.raises(ValueError, match="분기"):
        to_ecos_date_format("2024-Q5", "Q")
    with pytest.raises(ValueError, match="분기"):
        to_ecos_date_format("20245", "Q")


# ──────────────────────────────────────────────
# 4. _normalize_ecos_date (Firestore Doc ID용)
# ──────────────────────────────────────────────


@pytest.mark.parametrize(
    "input_time,freq,expected",
    [
        ("20251231", "D", "20251231"),
        ("202512", "M", "20251201"),  # 월초로 정규화
        ("20243", "Q", "20240930"),  # Q3 → 9월말
        ("20244", "Q", "20241231"),  # Q4 → 12월말
        ("20241", "Q", "20240331"),  # Q1 → 3월말
        ("2024", "A", "20241231"),  # 연말로 정규화
    ],
)
def test_normalize_ecos_date(input_time, freq, expected):
    assert _normalize_ecos_date(input_time, freq) == expected


# ──────────────────────────────────────────────
# 5. ECOSClient.get_statistic_search
# ──────────────────────────────────────────────


def _mk_response(json_data: dict) -> MagicMock:
    r = MagicMock()
    r.json.return_value = json_data
    r.raise_for_status.return_value = None
    return r


def test_get_statistic_search_single_page():
    http = MagicMock()
    http.get.return_value = _mk_response(
        {
            "StatisticSearch": {
                "list_total_count": 3,
                "row": [
                    {"TIME": "202401", "DATA_VALUE": "3.5", "ITEM_NAME1": "한국은행 기준금리"},
                    {"TIME": "202402", "DATA_VALUE": "3.5", "ITEM_NAME1": "한국은행 기준금리"},
                    {"TIME": "202403", "DATA_VALUE": "3.5", "ITEM_NAME1": "한국은행 기준금리"},
                ],
            }
        }
    )
    client = ECOSClient(api_key="X" * 20, http_client=http, sleep_sec=0)

    rows = client.get_statistic_search("722Y001", "M", "202401", "202403", "0101000")

    assert len(rows) == 3
    assert client.stats.successful_calls == 1
    assert http.get.call_count == 1


def test_get_statistic_search_multi_page():
    """list_total_count > page_size이면 여러 번 호출."""
    http = MagicMock()
    # page 1: 1000건, page 2: 500건
    pages = [
        {"StatisticSearch": {"list_total_count": 1500, "row": [{"TIME": f"2024010{i}", "DATA_VALUE": f"{i}"} for i in range(10)] * 100}},
        {"StatisticSearch": {"list_total_count": 1500, "row": [{"TIME": f"2024010{i}", "DATA_VALUE": f"{i}"} for i in range(5)] * 100}},
    ]
    http.get.side_effect = [_mk_response(p) for p in pages]
    client = ECOSClient(api_key="X" * 20, http_client=http, sleep_sec=0, page_size=1000)

    rows = client.get_statistic_search("722Y001", "M", "202001", "202412")

    assert len(rows) == 1500
    assert http.get.call_count == 2


def test_get_statistic_search_info_200_no_data():
    """RESULT INFO-200 = 조회 결과 없음 → 빈 list (failed_calls 증가 안 함)."""
    http = MagicMock()
    http.get.return_value = _mk_response(
        {"RESULT": {"CODE": "INFO-200", "MESSAGE": "조회된 데이터가 없습니다."}}
    )
    client = ECOSClient(api_key="X" * 20, http_client=http, sleep_sec=0)

    rows = client.get_statistic_search("999X999", "M", "202401", "202412")

    assert rows == []
    assert client.stats.failed_calls == 0  # no_data는 failed가 아님


def test_get_statistic_search_info_100_auth_error_marked_failed():
    """RESULT INFO-100 = 인증키 미입력 → failed_calls + error log."""
    http = MagicMock()
    http.get.return_value = _mk_response(
        {"RESULT": {"CODE": "INFO-100", "MESSAGE": "인증키가 유효하지 않습니다 (key=ABCD1234EFGH5678IJKL)"}}
    )
    client = ECOSClient(api_key="X" * 20, http_client=http, sleep_sec=0)

    rows = client.get_statistic_search("722Y001", "M", "202401", "202412")

    assert rows == []
    assert client.stats.failed_calls == 1


def test_get_statistic_search_info_150_auth_error_marked_failed():
    http = MagicMock()
    http.get.return_value = _mk_response(
        {"RESULT": {"CODE": "INFO-150", "MESSAGE": "인증키 형식 오류"}}
    )
    client = ECOSClient(api_key="X" * 20, http_client=http, sleep_sec=0)

    rows = client.get_statistic_search("722Y001", "M", "202401", "202412")
    assert rows == []
    assert client.stats.failed_calls == 1


def test_get_statistic_search_other_result_code_warned_not_failed():
    """INFO-300 같은 다른 코드 → warning, failed 아님 (no data 케이스)."""
    http = MagicMock()
    http.get.return_value = _mk_response(
        {"RESULT": {"CODE": "INFO-300", "MESSAGE": "필수 파라미터 누락"}}
    )
    client = ECOSClient(api_key="X" * 20, http_client=http, sleep_sec=0)

    rows = client.get_statistic_search("722Y001", "M", "202401", "202412")
    assert rows == []
    # INFO-300은 사용자 호출 오류라 별도 분류 — 현재는 warning만 (failed는 아님)
    # 향후 정책 강화 가능


def test_get_statistic_search_handles_exception():
    http = MagicMock()
    http.get.side_effect = ConnectionError("ECOS network")
    client = ECOSClient(api_key="X" * 20, http_client=http, sleep_sec=0)

    rows = client.get_statistic_search("722Y001", "M", "202401", "202412")

    assert rows == []
    assert client.stats.failed_calls == 1


def test_get_statistic_search_no_api_key_returns_empty():
    """API 키 없으면 즉시 빈 list."""
    client = ECOSClient(api_key="", http_client=MagicMock(), sleep_sec=0)
    rows = client.get_statistic_search("722Y001", "M", "202401", "202412")
    assert rows == []


def test_get_statistic_search_url_construction():
    """URL이 ECOS 형식 (StatisticSearch/{key}/json/kr/{start}/{end}/{stat}/{freq}/{from}/{to}/{item})으로 구성."""
    http = MagicMock()
    http.get.return_value = _mk_response({"StatisticSearch": {"list_total_count": 0, "row": []}})
    client = ECOSClient(api_key="MYKEY", http_client=http, sleep_sec=0, page_size=100)

    client.get_statistic_search("722Y001", "M", "202401", "202412", "0101000")

    called_url = http.get.call_args.args[0]
    assert "/StatisticSearch/MYKEY/json/kr/" in called_url
    assert "/722Y001/M/202401/202412/" in called_url
    assert "0101000" in called_url


def test_get_statistic_search_max_pages_safety():
    """무한 응답에도 max_pages 도달 시 종료."""
    http = MagicMock()
    # 항상 list_total_count > 페이지 끝 (무한)
    http.get.return_value = _mk_response(
        {
            "StatisticSearch": {
                "list_total_count": 999_999,
                "row": [{"TIME": "20240101", "DATA_VALUE": "1.0"}],
            }
        }
    )
    client = ECOSClient(api_key="X" * 20, http_client=http, sleep_sec=0)

    client.get_statistic_search("722Y001", "M", "202401", "202412", max_pages=3)

    assert http.get.call_count == 3


# ──────────────────────────────────────────────
# 6. ECOSClient.get_series_by_axis_key
# ──────────────────────────────────────────────


def test_get_series_by_axis_key_unknown_returns_empty():
    client = ECOSClient(api_key="X" * 20, http_client=MagicMock(), sleep_sec=0)
    rows = client.get_series_by_axis_key("unknown_key", "2024-01-01", "2024-12-31")
    assert rows == []


def test_get_series_by_axis_key_converts_dates_to_ecos_format():
    """ISO 날짜 → ECOS freq 형식 자동 변환."""
    http = MagicMock()
    http.get.return_value = _mk_response({"StatisticSearch": {"list_total_count": 0, "row": []}})
    client = ECOSClient(api_key="X" * 20, http_client=http, sleep_sec=0)

    # base_rate freq=M → YYYYMM 형식으로 변환되어야
    client.get_series_by_axis_key("base_rate", "2024-01-31", "2024-12-31")

    called_url = http.get.call_args.args[0]
    # /722Y001/M/202401/202412/
    assert "/722Y001/M/202401/202412/" in called_url


def test_get_series_by_axis_key_quarterly_format():
    """gdp_yoy (Q) → YYYY+분기 형식으로 변환."""
    http = MagicMock()
    http.get.return_value = _mk_response({"StatisticSearch": {"list_total_count": 0, "row": []}})
    client = ECOSClient(api_key="X" * 20, http_client=http, sleep_sec=0)

    client.get_series_by_axis_key("gdp_yoy", "2024-Q1", "2024-Q4")

    called_url = http.get.call_args.args[0]
    assert "/200Y002/Q/20241/20244/" in called_url


# ──────────────────────────────────────────────
# 7. normalize_to_records
# ──────────────────────────────────────────────


def test_normalize_to_records_monthly():
    rows = [
        {"TIME": "202401", "DATA_VALUE": "3.5", "ITEM_NAME1": "한국은행 기준금리", "UNIT_NAME": "%"},
        {"TIME": "202402", "DATA_VALUE": "3.5", "ITEM_NAME1": "한국은행 기준금리", "UNIT_NAME": "%"},
    ]
    client = ECOSClient(api_key="X" * 20, http_client=MagicMock(), sleep_sec=0)

    records = client.normalize_to_records("base_rate", rows)

    assert len(records) == 2
    r0 = records[0]
    assert r0["indicator_key"] == "base_rate"
    assert r0["country"] == "KR"
    assert r0["category"] == "interest_rate"
    assert r0["date"] == "20240101"  # 월초 정규화
    assert r0["value"] == 3.5
    assert r0["unit_raw"] == "%"
    assert r0["frequency"] == "M"
    assert r0["source"] == "ECOS"
    assert r0["source_stat_code"] == "722Y001"
    assert r0["source_item_code1"] == "0101000"
    assert r0["source_item_code2"] == "?"  # base_rate는 단일 차원


def test_normalize_to_records_daily():
    rows = [
        {"TIME": "20240115", "DATA_VALUE": "1320.5", "UNIT_NAME": "원"},
    ]
    client = ECOSClient(api_key="X" * 20, http_client=MagicMock(), sleep_sec=0)

    records = client.normalize_to_records("usd_krw", rows)

    assert len(records) == 1
    assert records[0]["date"] == "20240115"
    assert records[0]["value"] == 1320.5
    assert records[0]["frequency"] == "D"


def test_normalize_to_records_quarterly():
    rows = [
        {"TIME": "20243", "DATA_VALUE": "2.1", "UNIT_NAME": "%"},
    ]
    client = ECOSClient(api_key="X" * 20, http_client=MagicMock(), sleep_sec=0)

    records = client.normalize_to_records("gdp_yoy", rows)

    assert records[0]["date"] == "20240930"  # Q3 → 9월말


def test_normalize_to_records_skips_invalid_value():
    """DATA_VALUE가 변환 불가하면 skip."""
    rows = [
        {"TIME": "202401", "DATA_VALUE": "3.5"},
        {"TIME": "202402", "DATA_VALUE": "-"},  # 공시 없음 표기
        {"TIME": "202403", "DATA_VALUE": ""},
        {"TIME": "202404", "DATA_VALUE": None},
    ]
    client = ECOSClient(api_key="X" * 20, http_client=MagicMock(), sleep_sec=0)

    records = client.normalize_to_records("base_rate", rows)
    assert len(records) == 1
    assert records[0]["date"] == "20240101"


def test_normalize_to_records_unknown_key():
    client = ECOSClient(api_key="X" * 20, http_client=MagicMock(), sleep_sec=0)
    assert client.normalize_to_records("unknown", [{"TIME": "202401", "DATA_VALUE": "1.0"}]) == []


def test_normalize_to_records_empty_rows():
    client = ECOSClient(api_key="X" * 20, http_client=MagicMock(), sleep_sec=0)
    assert client.normalize_to_records("base_rate", []) == []


# ──────────────────────────────────────────────
# 8. Rate limit
# ──────────────────────────────────────────────


def test_rate_limit_sleep_called():
    http = MagicMock()
    http.get.return_value = _mk_response({"StatisticSearch": {"list_total_count": 0, "row": []}})
    client = ECOSClient(api_key="X" * 20, http_client=http, sleep_sec=0.4)

    with patch("utils.data_collectors.ecos_client.time.sleep") as mock_sleep:
        client.get_statistic_search("722Y001", "M", "202401", "202412")

    mock_sleep.assert_called_with(0.4)
