"""utils/data_collectors/yfinance_event_collector.py 단위 테스트 (mock yfinance)."""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pandas as pd
import pytest

from utils.data_collectors.yfinance_event_collector import (
    fetch_yfinance_events,
)


def _make_yf_module(
    earnings_df: pd.DataFrame | None = None,
    dividends_series: pd.Series | None = None,
    quarterly_income: pd.DataFrame | None = None,
):
    ticker_obj = MagicMock()
    ticker_obj.earnings_dates = earnings_df
    ticker_obj.dividends = dividends_series
    ticker_obj.quarterly_income_stmt = quarterly_income
    yf_module = MagicMock()
    yf_module.Ticker = MagicMock(return_value=ticker_obj)
    return yf_module, ticker_obj


# ──────────────────────────────────────────────
# 1. 실적 발표
# ──────────────────────────────────────────────


def test_earnings_dates_parsed_with_new_columns():
    """현행 yfinance 컬럼 ('EPS Estimate', 'Reported EPS', 'Surprise(%)')."""
    df = pd.DataFrame(
        {
            "EPS Estimate": [1.20, 1.10],
            "Reported EPS": [1.35, 1.05],
            "Surprise(%)": [12.5, -4.5],
        },
        index=pd.to_datetime(["2026-04-25", "2026-01-25"]),
    )
    yf_mod, _ = _make_yf_module(earnings_df=df)
    out = fetch_yfinance_events("AAPL", yf_module=yf_mod)
    assert len(out["earnings_dates"]) == 2
    first = out["earnings_dates"][0]
    assert first["date"] == "2026-04-25"
    assert first["eps_estimate"] == 1.20
    assert first["eps_reported"] == 1.35
    assert first["surprise_pct"] == 12.5


def test_earnings_dates_parsed_with_legacy_columns():
    """저버전 yfinance 컬럼 ('epsEstimate' 등) graceful 매핑."""
    df = pd.DataFrame(
        {
            "epsEstimate": [1.20],
            "epsActual": [1.35],
            "surprise": [12.5],
        },
        index=pd.to_datetime(["2026-04-25"]),
    )
    yf_mod, _ = _make_yf_module(earnings_df=df)
    out = fetch_yfinance_events("AAPL", yf_module=yf_mod)
    rec = out["earnings_dates"][0]
    assert rec["eps_estimate"] == 1.20
    assert rec["eps_reported"] == 1.35
    assert rec["surprise_pct"] == 12.5


def test_next_earnings_picks_future():
    future = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    past = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    df = pd.DataFrame(
        {
            "EPS Estimate": [1.20, 1.30],
            "Reported EPS": [None, 1.05],
            "Surprise(%)": [None, -4.5],
        },
        index=pd.to_datetime([future, past]),
    )
    yf_mod, _ = _make_yf_module(earnings_df=df)
    out = fetch_yfinance_events("AAPL", yf_module=yf_mod)
    assert out["next_earnings"] is not None
    assert out["next_earnings"]["date"] == future
    assert out["next_earnings"]["is_future"] is True


def test_next_earnings_none_when_all_past():
    past1 = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
    past2 = (datetime.now() - timedelta(days=100)).strftime("%Y-%m-%d")
    df = pd.DataFrame(
        {"EPS Estimate": [1.0, 1.0]},
        index=pd.to_datetime([past1, past2]),
    )
    yf_mod, _ = _make_yf_module(earnings_df=df)
    out = fetch_yfinance_events("AAPL", yf_module=yf_mod)
    assert out["next_earnings"] is None


# ──────────────────────────────────────────────
# 2. 배당
# ──────────────────────────────────────────────


def test_dividends_parsed_to_records():
    s = pd.Series(
        [0.24, 0.25, 0.26],
        index=pd.to_datetime(["2026-02-10", "2026-05-10", "2026-08-10"]),
    )
    yf_mod, _ = _make_yf_module(dividends_series=s)
    out = fetch_yfinance_events("AAPL", yf_module=yf_mod)
    assert len(out["dividends"]) == 3
    assert out["dividends"][0]["ex_date"] == "2026-02-10"
    assert out["dividends"][0]["amount"] == 0.24


def test_next_ex_dividend_picks_future():
    future = (datetime.now() + timedelta(days=20)).strftime("%Y-%m-%d")
    past = (datetime.now() - timedelta(days=20)).strftime("%Y-%m-%d")
    s = pd.Series([0.24, 0.25], index=pd.to_datetime([past, future]))
    yf_mod, _ = _make_yf_module(dividends_series=s)
    out = fetch_yfinance_events("AAPL", yf_module=yf_mod)
    assert out["next_ex_dividend"]["ex_date"] == future


# ──────────────────────────────────────────────
# 3. quarterly_income_stmt 가용성
# ──────────────────────────────────────────────


def test_quarterly_income_available():
    qi = pd.DataFrame({"Q1": [1, 2], "Q2": [3, 4]})
    yf_mod, _ = _make_yf_module(quarterly_income=qi)
    out = fetch_yfinance_events("AAPL", yf_module=yf_mod)
    assert out["quarterly_income_available"] is True


def test_quarterly_income_unavailable_when_empty():
    yf_mod, _ = _make_yf_module(quarterly_income=pd.DataFrame())
    out = fetch_yfinance_events("AAPL", yf_module=yf_mod)
    assert out["quarterly_income_available"] is False


# ──────────────────────────────────────────────
# 4. graceful handling
# ──────────────────────────────────────────────


def test_empty_ticker_returns_error():
    out = fetch_yfinance_events("")
    assert out["error"] == "ticker 누락"


def test_no_data_graceful():
    """모든 필드가 None/empty인 종목 → 빈 리스트만 반환, error 없음."""
    yf_mod, _ = _make_yf_module(
        earnings_df=pd.DataFrame(),
        dividends_series=pd.Series(dtype=float),
        quarterly_income=pd.DataFrame(),
    )
    out = fetch_yfinance_events("NOTHING", yf_module=yf_mod)
    assert out["earnings_dates"] == []
    assert out["dividends"] == []
    assert out["next_earnings"] is None
    assert out["next_ex_dividend"] is None
    assert out["quarterly_income_available"] is False


def test_earnings_attr_raises_other_fields_still_collected():
    """earnings_dates 접근에서 예외가 나도 dividends는 정상 수집되어야 함."""
    s = pd.Series([0.24], index=pd.to_datetime(["2026-04-25"]))
    ticker_obj = MagicMock()
    type(ticker_obj).earnings_dates = property(
        lambda self: (_ for _ in ()).throw(RuntimeError("blocked"))
    )
    ticker_obj.dividends = s
    ticker_obj.quarterly_income_stmt = None
    yf_mod = MagicMock()
    yf_mod.Ticker = MagicMock(return_value=ticker_obj)

    out = fetch_yfinance_events("PARTIAL", yf_module=yf_mod)
    assert out["earnings_dates"] == []
    assert len(out["dividends"]) == 1


def test_ticker_creation_failure_returns_error():
    yf_mod = MagicMock()
    yf_mod.Ticker = MagicMock(side_effect=ValueError("invalid symbol"))
    out = fetch_yfinance_events("BAD!", yf_module=yf_mod)
    assert "ValueError" in (out["error"] or "")
