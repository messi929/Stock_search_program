"""utils/data_collectors/edgar_collector.py 단위 테스트 (mock httpx)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from utils.data_collectors.edgar_collector import (
    EIGHT_K_ITEM_CATEGORY,
    EdgarClient,
    decode_8k_items,
    has_material_event,
)


# ──────────────────────────────────────────────
# 1. decode_8k_items
# ──────────────────────────────────────────────


def test_decode_basic_two_items():
    out = decode_8k_items("2.02,9.01")
    assert out == [("2.02", "earnings_release"), ("9.01", "exhibits")]


def test_decode_with_spaces():
    out = decode_8k_items("2.02, 9.01,5.02")
    codes = [c for c, _ in out]
    assert codes == ["2.02", "9.01", "5.02"]


def test_decode_unknown_code_falls_back():
    out = decode_8k_items("2.02,9.99")
    assert ("2.02", "earnings_release") in out
    assert ("9.99", "unknown") in out


def test_decode_dedupe():
    out = decode_8k_items("2.02,2.02,2.02")
    assert out == [("2.02", "earnings_release")]


def test_decode_empty():
    assert decode_8k_items("") == []
    assert decode_8k_items(None) == []  # type: ignore[arg-type]


# ──────────────────────────────────────────────
# 2. has_material_event
# ──────────────────────────────────────────────


def test_material_event_true_when_substantive_item():
    items = [("2.01", "asset_acquisition_disposal"), ("9.01", "exhibits")]
    assert has_material_event(items) is True


def test_material_event_false_when_only_boilerplate():
    items = [("7.01", "reg_fd"), ("9.01", "exhibits")]
    assert has_material_event(items) is False


def test_material_event_false_for_empty():
    assert has_material_event([]) is False


# ──────────────────────────────────────────────
# 3. User-Agent 강제
# ──────────────────────────────────────────────


def test_missing_user_agent_raises(monkeypatch):
    monkeypatch.delenv("EDGAR_USER_AGENT", raising=False)
    with pytest.raises(ValueError, match="EDGAR_USER_AGENT"):
        EdgarClient()


def test_user_agent_passed_to_request():
    """fetch 시 User-Agent 헤더 포함되는지 확인."""
    captured = {}

    def fake_get(url, headers=None):
        captured["url"] = url
        captured["headers"] = headers
        resp = MagicMock()
        resp.status_code = 200
        resp.raise_for_status = MagicMock()
        resp.json = MagicMock(
            return_value={"cik": "320193", "name": "APPLE INC", "filings": {"recent": {}}}
        )
        return resp

    fake_http = MagicMock()
    fake_http.get = MagicMock(side_effect=fake_get)
    client = EdgarClient(
        user_agent="Axis Research <ops@example.com>",
        rate_limit_sec=0,
        http_client=fake_http,
    )
    client.fetch_submissions("320193")
    assert "User-Agent" in captured["headers"]
    assert "ops@example.com" in captured["headers"]["User-Agent"]


# ──────────────────────────────────────────────
# 4. CIK 정규화 (10자리 zero-padded)
# ──────────────────────────────────────────────


def test_cik_normalize_padding():
    assert EdgarClient._normalize_cik("320193") == "0000320193"
    assert EdgarClient._normalize_cik(320193) == "0000320193"
    assert EdgarClient._normalize_cik("CIK0000320193") == "0000320193"
    assert EdgarClient._normalize_cik("0000320193") == "0000320193"


def test_cik_normalize_bad_input():
    with pytest.raises(ValueError):
        EdgarClient._normalize_cik("not-a-cik")


# ──────────────────────────────────────────────
# 5. 8-K 추출 + Item 디코딩
# ──────────────────────────────────────────────


def _mock_response_json(payload: dict, status: int = 200):
    resp = MagicMock()
    resp.status_code = status
    resp.raise_for_status = MagicMock()
    resp.json = MagicMock(return_value=payload)
    return resp


def test_fetch_recent_8k_filters_form_and_decodes_items():
    payload = {
        "cik": "320193",
        "name": "APPLE INC",
        "tickers": ["AAPL"],
        "filings": {
            "recent": {
                "form": ["10-Q", "8-K", "8-K", "10-K"],
                "accessionNumber": ["acc1", "acc2", "acc3", "acc4"],
                "filingDate": [
                    "2026-04-30",
                    "2026-04-15",
                    "2026-03-01",
                    "2026-01-31",
                ],
                "items": ["", "2.02,9.01", "1.01", ""],
                "primaryDocument": ["10q.htm", "8k.htm", "8k2.htm", "10k.htm"],
            }
        },
    }
    fake_http = MagicMock()
    fake_http.get = MagicMock(return_value=_mock_response_json(payload))
    client = EdgarClient(
        user_agent="Axis <ops@example.com>", rate_limit_sec=0, http_client=fake_http
    )
    out = client.fetch_recent_8k("320193")
    # 8-K 2건만 남아야 함
    assert len(out) == 2
    # 첫 번째: 2.02 + 9.01
    items_0 = out[0]["items_decoded"]
    assert ("2.02", "earnings_release") in items_0
    assert ("9.01", "exhibits") in items_0


def test_fetch_recent_8k_since_date_filter():
    payload = {
        "cik": "320193",
        "name": "APPLE",
        "tickers": ["AAPL"],
        "filings": {
            "recent": {
                "form": ["8-K", "8-K"],
                "accessionNumber": ["a1", "a2"],
                "filingDate": ["2026-04-15", "2026-01-15"],
                "items": ["2.02", "5.02"],
                "primaryDocument": ["a.htm", "b.htm"],
            }
        },
    }
    fake_http = MagicMock()
    fake_http.get = MagicMock(return_value=_mock_response_json(payload))
    client = EdgarClient(
        user_agent="Axis <ops@example.com>", rate_limit_sec=0, http_client=fake_http
    )
    out = client.fetch_recent_8k("320193", since_date="2026-03-01")
    assert len(out) == 1
    assert out[0]["accessionNumber"] == "a1"


def test_fetch_recent_8k_handles_403():
    """User-Agent 차단 시 403 → 빈 리스트 + 로그."""
    resp = MagicMock()
    resp.status_code = 403
    resp.raise_for_status = MagicMock()
    fake_http = MagicMock()
    fake_http.get = MagicMock(return_value=resp)
    client = EdgarClient(
        user_agent="Axis <ops@example.com>", rate_limit_sec=0, http_client=fake_http
    )
    out = client.fetch_recent_8k("320193")
    assert out == []
    assert client.stats.failed_calls == 1


def test_fetch_recent_8k_handles_network_error():
    fake_http = MagicMock()
    fake_http.get = MagicMock(side_effect=RuntimeError("connection reset"))
    client = EdgarClient(
        user_agent="Axis <ops@example.com>", rate_limit_sec=0, http_client=fake_http
    )
    out = client.fetch_recent_8k("320193")
    assert out == []
    assert client.stats.failed_calls == 1


# ──────────────────────────────────────────────
# 6. EIGHT_K_ITEM_CATEGORY 정합성
# ──────────────────────────────────────────────


def test_critical_items_present():
    """주요 8-K 코드는 모두 분류되어야 함."""
    for code in ("1.01", "2.01", "2.02", "5.02", "8.01", "9.01"):
        assert code in EIGHT_K_ITEM_CATEGORY


# ──────────────────────────────────────────────
# 7. fetch_ticker_to_cik — SEC company_tickers.json
# ──────────────────────────────────────────────


_COMPANY_TICKERS_PAYLOAD = {
    "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
    "1": {"cik_str": 789019, "ticker": "MSFT", "title": "Microsoft Corp"},
    "2": {"cik_str": 1535527, "ticker": "RKLB", "title": "Rocket Lab USA"},
}


def _client_with(payload, status=200):
    fake_http = MagicMock()
    fake_http.get = MagicMock(return_value=_mock_response_json(payload, status))
    return EdgarClient(
        user_agent="Axis <ops@example.com>", rate_limit_sec=0, http_client=fake_http
    )


def test_fetch_ticker_to_cik_full_mapping():
    client = _client_with(_COMPANY_TICKERS_PAYLOAD)
    mapping = client.fetch_ticker_to_cik()
    assert mapping == {"AAPL": "320193", "MSFT": "789019", "RKLB": "1535527"}


def test_fetch_ticker_to_cik_filtered_case_insensitive():
    client = _client_with(_COMPANY_TICKERS_PAYLOAD)
    mapping = client.fetch_ticker_to_cik(["aapl", "RKLB"])
    assert mapping == {"AAPL": "320193", "RKLB": "1535527"}


def test_fetch_ticker_to_cik_missing_ticker_returns_others():
    """매핑에 없는 티커는 누락 — 나머지는 정상 반환."""
    client = _client_with(_COMPANY_TICKERS_PAYLOAD)
    mapping = client.fetch_ticker_to_cik(["AAPL", "NOTREAL"])
    assert mapping == {"AAPL": "320193"}


def test_fetch_ticker_to_cik_handles_403():
    client = _client_with({}, status=403)
    assert client.fetch_ticker_to_cik() == {}
    assert client.stats.failed_calls == 1


def test_fetch_ticker_to_cik_handles_network_error():
    fake_http = MagicMock()
    fake_http.get = MagicMock(side_effect=RuntimeError("connection reset"))
    client = EdgarClient(
        user_agent="Axis <ops@example.com>", rate_limit_sec=0, http_client=fake_http
    )
    assert client.fetch_ticker_to_cik(["AAPL"]) == {}
    assert client.stats.failed_calls == 1


def test_fetch_ticker_to_cik_cik_feeds_fetch_recent_8k():
    """fetch_ticker_to_cik가 돌려준 CIK가 fetch_recent_8k에 그대로 쓰일 수 있어야 함."""
    client = _client_with(_COMPANY_TICKERS_PAYLOAD)
    cik = client.fetch_ticker_to_cik(["AAPL"])["AAPL"]
    # _normalize_cik이 받아들이는 형식인지 (예외 없이 10자리 패딩)
    assert EdgarClient._normalize_cik(cik) == "0000320193"
