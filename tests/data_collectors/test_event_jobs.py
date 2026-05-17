"""Day 5 — daily_options_collect, weekly_event_calendar_sync Job 테스트."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from jobs import daily_options_collect, weekly_event_calendar_sync
from jobs.daily_options_collect import _DryRunDb, run_daily_options
from jobs.weekly_event_calendar_sync import (
    _DryRunDb as _WeeklyDryRunDb,
    build_cik_lookup,
    run_weekly_sync,
)


# ──────────────────────────────────────────────
# 1. daily_options_collect — 기본 흐름
# ──────────────────────────────────────────────


def test_daily_options_dry_run_no_options_listed():
    """옵션 미상장 종목 — Firestore skip + stats 정확."""
    with patch.object(daily_options_collect, "calculate_options_signals") as m_signal, \
         patch.object(daily_options_collect, "calculate_vkospi_signal") as m_vkospi:
        m_signal.return_value = {"available": False, "reason": "옵션 거래 없음"}
        m_vkospi.return_value = {"available": False}

        summary = run_daily_options(["NOOPT1", "NOOPT2"], dry_run=True)
        assert summary["dry_run"] is True
        assert summary["no_options"] == 2
        # tickers: succeeded/attempted == "0/2"
        assert summary["tickers"] == "0/2"
        assert summary["docs_written"] == 0


def test_daily_options_writes_records_for_available():
    """옵션 가용 종목 — 도큐먼트 1개 + VKOSPI 1개."""
    with patch.object(daily_options_collect, "calculate_options_signals") as m_signal, \
         patch.object(daily_options_collect, "calculate_vkospi_signal") as m_vkospi:
        m_signal.side_effect = lambda t: {
            "ticker": t,
            "available": True,
            "expiration": "2026-06-19",
            "put_call_ratio_volume": 0.85,
            "atm_iv_pct": 32.1,
            "interpretation": "균형",
            "data_source": "yfinance",
            "collected_at": "2026-05-03T06:30:00",
        }
        m_vkospi.return_value = {
            "available": True,
            "index": "VKOSPI",
            "last_close": 24.5,
            "data_source": "yfinance",
        }

        summary = run_daily_options(["AAPL", "RKLB"], dry_run=True)
        # 2 종목 + VKOSPI = 3 docs
        assert summary["docs_written"] == 3
        assert summary["tickers"] == "2/2"
        assert summary["vkospi"] is True


def test_daily_options_partial_failure_graceful():
    """일부 종목 실패해도 다른 종목은 정상 수집."""
    def fake_signal(ticker):
        if ticker == "FAIL":
            return {"available": False, "reason": "yfinance error"}
        return {
            "ticker": ticker,
            "available": True,
            "expiration": "2026-06-19",
            "put_call_ratio_volume": 1.0,
            "atm_iv_pct": 30.0,
            "interpretation": "균형",
            "data_source": "yfinance",
            "collected_at": "2026-05-03T06:30:00",
        }

    with patch.object(daily_options_collect, "calculate_options_signals", side_effect=fake_signal), \
         patch.object(daily_options_collect, "calculate_vkospi_signal", return_value={"available": False}):
        summary = run_daily_options(["AAPL", "FAIL", "RKLB"], dry_run=True)
        assert summary["tickers"] == "2/3"
        assert summary["no_options"] == 1


# ──────────────────────────────────────────────
# 2. weekly_event_calendar_sync — KR/US 분리 + 누락 시 skip
# ──────────────────────────────────────────────


def test_weekly_sync_skips_kr_when_no_dart_key(monkeypatch):
    """DART_API_KEY 미설정 → KR skip + US만 수집."""
    monkeypatch.delenv("DART_API_KEY", raising=False)
    monkeypatch.delenv("EDGAR_USER_AGENT", raising=False)

    with patch.object(weekly_event_calendar_sync, "fetch_yfinance_events", create=True) as m_yf:
        # weekly_event_calendar_sync는 collect_us_events 내부에서 yfinance import
        pass

    with patch(
        "utils.data_collectors.yfinance_event_collector.fetch_yfinance_events"
    ) as m_yf:
        m_yf.return_value = {
            "ticker": "AAPL",
            "earnings_dates": [{"date": "2026-05-15", "is_future": True}],
            "dividends": [],
            "next_earnings": {"date": "2026-05-15", "is_future": True},
            "next_ex_dividend": None,
            "quarterly_income_available": True,
        }

        summary = run_weekly_sync(
            kr_tickers=["005930"],
            us_tickers=["AAPL"],
            window_days=14,
            dry_run=True,
        )
        assert summary["kr_tickers"] == 0  # skip 되어 0
        assert summary["us_tickers"] == 1
        assert summary["us_yfinance_events"] >= 1


def test_weekly_sync_us_only_when_no_cik_lookup(monkeypatch):
    """cik_lookup 없으면 EDGAR skip, yfinance만."""
    monkeypatch.delenv("DART_API_KEY", raising=False)
    monkeypatch.setenv("EDGAR_USER_AGENT", "Axis <ops@example.com>")

    with patch(
        "utils.data_collectors.yfinance_event_collector.fetch_yfinance_events"
    ) as m_yf:
        m_yf.return_value = {
            "ticker": "AAPL",
            "earnings_dates": [{"date": "2026-05-15", "is_future": True}],
            "dividends": [{"ex_date": "2026-05-10", "amount": 0.24}],
            "next_earnings": None,
            "next_ex_dividend": None,
            "quarterly_income_available": False,
        }
        summary = run_weekly_sync(
            kr_tickers=[],
            us_tickers=["AAPL"],
            window_days=7,
            cik_lookup=None,  # EDGAR skip
            dry_run=True,
        )
        assert summary["us_8k_events"] == 0
        assert summary["us_yfinance_events"] >= 1


def test_weekly_sync_includes_edgar_when_lookup_present(monkeypatch):
    """cik_lookup + EDGAR_USER_AGENT 모두 있을 때 8-K 수집."""
    monkeypatch.delenv("DART_API_KEY", raising=False)
    monkeypatch.setenv("EDGAR_USER_AGENT", "Axis <ops@example.com>")

    fake_edgar_client = MagicMock()
    fake_edgar_client.fetch_recent_8k = MagicMock(
        return_value=[
            {
                "accessionNumber": "0001-25-000001",
                "filingDate": "2026-04-25",
                "form": "8-K",
                "items": "2.02,9.01",
                "items_decoded": [("2.02", "earnings_release")],
                "primaryDocument": "8k.htm",
                "cik": "320193",
                "name": "APPLE INC",
                "tickers": ["AAPL"],
            }
        ]
    )

    with patch(
        "utils.data_collectors.yfinance_event_collector.fetch_yfinance_events"
    ) as m_yf, patch(
        "utils.data_collectors.edgar_collector.EdgarClient",
        return_value=fake_edgar_client,
    ):
        m_yf.return_value = {
            "ticker": "AAPL",
            "earnings_dates": [],
            "dividends": [],
            "next_earnings": None,
            "next_ex_dividend": None,
            "quarterly_income_available": False,
        }
        summary = run_weekly_sync(
            kr_tickers=[],
            us_tickers=["AAPL"],
            window_days=14,
            cik_lookup={"AAPL": "320193"},
            dry_run=True,
        )
        assert summary["us_8k_events"] == 1


def test_weekly_sync_dry_run_no_db_writes():
    """dry_run=True면 _DryRunDb 사용 + 실제 Firestore 호출 없음."""
    summary = run_weekly_sync(
        kr_tickers=[],
        us_tickers=[],
        window_days=7,
        dry_run=True,
    )
    assert summary["dry_run"] is True
    assert summary["docs_written"] == 0


# ──────────────────────────────────────────────
# 3. build_cik_lookup — SEC company_tickers.json 자동 매핑
# ──────────────────────────────────────────────


def test_build_cik_lookup_skips_when_no_user_agent(monkeypatch):
    """EDGAR_USER_AGENT 미설정 → 빈 dict (graceful skip)."""
    monkeypatch.delenv("EDGAR_USER_AGENT", raising=False)
    assert build_cik_lookup(["AAPL", "MSFT"]) == {}


def test_build_cik_lookup_empty_tickers(monkeypatch):
    """us_tickers 비어있으면 네트워크 호출 없이 빈 dict."""
    monkeypatch.setenv("EDGAR_USER_AGENT", "Axis <ops@example.com>")
    assert build_cik_lookup([]) == {}


def test_build_cik_lookup_uses_edgar_client(monkeypatch):
    """EDGAR_USER_AGENT 있으면 EdgarClient.fetch_ticker_to_cik 결과 반환."""
    monkeypatch.setenv("EDGAR_USER_AGENT", "Axis <ops@example.com>")

    fake_client = MagicMock()
    fake_client.fetch_ticker_to_cik = MagicMock(
        return_value={"AAPL": "320193", "RKLB": "1535527"}
    )
    with patch(
        "utils.data_collectors.edgar_collector.EdgarClient",
        return_value=fake_client,
    ):
        lookup = build_cik_lookup(["AAPL", "RKLB"])

    assert lookup == {"AAPL": "320193", "RKLB": "1535527"}
    fake_client.fetch_ticker_to_cik.assert_called_once_with(["AAPL", "RKLB"])


def test_build_cik_lookup_graceful_on_error(monkeypatch):
    """EdgarClient 예외 발생 시 빈 dict (8-K 단계만 skip, Job은 계속)."""
    monkeypatch.setenv("EDGAR_USER_AGENT", "Axis <ops@example.com>")
    with patch(
        "utils.data_collectors.edgar_collector.EdgarClient",
        side_effect=RuntimeError("network down"),
    ):
        assert build_cik_lookup(["AAPL"]) == {}
