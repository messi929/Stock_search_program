"""utils/data_collectors/us_ownership.py 단위 테스트 (mock yfinance)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd

from utils.data_collectors.us_ownership import fetch_us_institutional_ownership


def _make_yf_module(major_holders=None, institutional_holders=None, raise_on_ticker=False):
    ticker_obj = MagicMock()
    ticker_obj.major_holders = major_holders
    ticker_obj.institutional_holders = institutional_holders
    yf_module = MagicMock()
    if raise_on_ticker:
        yf_module.Ticker = MagicMock(side_effect=RuntimeError("boom"))
    else:
        yf_module.Ticker = MagicMock(return_value=ticker_obj)
    return yf_module


def _major_holders_df():
    # 신형 yfinance: index=Breakdown, 'Value' 컬럼 (fraction)
    return pd.DataFrame(
        {"Value": [0.01633, 0.65963, 0.67058, 7641.0]},
        index=[
            "insidersPercentHeld",
            "institutionsPercentHeld",
            "institutionsFloatPercentHeld",
            "institutionsCount",
        ],
    )


def _institutional_holders_df():
    return pd.DataFrame(
        {
            "Date Reported": ["2026-03-31", "2026-03-31", "2026-03-31"],
            "Holder": ["Blackrock Inc.", "Vanguard Capital Management LLC", "State Street Corporation"],
            "pctHeld": [0.0779, 0.0649, 0.0410],
            "Shares": [1144695425, 953847648, 602341409],
            "Value": [352943925019, 294099832499, 185719918548],
            "pctChange": [-0.0086, 1.0, -0.0028],
        }
    )


# ──────────────────────────────────────────────
# 1. 정상 파싱
# ──────────────────────────────────────────────


def test_full_parse():
    yf = _make_yf_module(_major_holders_df(), _institutional_holders_df())
    r = fetch_us_institutional_ownership("aapl", top_n=10, yf_module=yf)

    assert r["available"] is True
    assert r["ticker"] == "AAPL"  # 대문자 정규화
    # fraction → percent 변환
    assert r["institutions_pct"] == 65.96
    assert r["insiders_pct"] == 1.63
    assert r["institutions_float_pct"] == 67.06
    assert r["institutions_count"] == 7641
    assert r["as_of"] == "2026-03-31"
    assert len(r["top_holders"]) == 3
    top = r["top_holders"][0]
    assert top["holder"] == "Blackrock Inc."
    assert top["pct_held"] == 7.79
    assert top["shares"] == 1144695425
    assert top["date_reported"] == "2026-03-31"
    assert r["error"] is None
    # 정보 제공용 표시 — 신호 아님 명시
    assert "신호" in r["note"]


def test_top_n_limit():
    yf = _make_yf_module(_major_holders_df(), _institutional_holders_df())
    r = fetch_us_institutional_ownership("AAPL", top_n=2, yf_module=yf)
    assert len(r["top_holders"]) == 2


# ──────────────────────────────────────────────
# 2. 부분/빈 데이터 graceful
# ──────────────────────────────────────────────


def test_only_major_holders_available():
    yf = _make_yf_module(_major_holders_df(), None)
    r = fetch_us_institutional_ownership("AAPL", yf_module=yf)
    assert r["available"] is True  # 요약 비율만으로도 available
    assert r["institutions_pct"] == 65.96
    assert r["top_holders"] == []
    assert r["as_of"] is None


def test_only_holders_no_major():
    yf = _make_yf_module(None, _institutional_holders_df())
    r = fetch_us_institutional_ownership("AAPL", yf_module=yf)
    assert r["available"] is True  # 상위 기관만으로도 available
    assert r["institutions_pct"] is None
    assert len(r["top_holders"]) == 3


def test_all_empty_not_available():
    yf = _make_yf_module(None, None)
    r = fetch_us_institutional_ownership("AAPL", yf_module=yf)
    assert r["available"] is False
    assert r["top_holders"] == []


def test_empty_ticker():
    r = fetch_us_institutional_ownership("", yf_module=_make_yf_module())
    assert r["available"] is False
    assert r["error"] == "ticker 누락"


# ──────────────────────────────────────────────
# 3. 예외 graceful
# ──────────────────────────────────────────────


def test_ticker_creation_failure():
    yf = _make_yf_module(raise_on_ticker=True)
    r = fetch_us_institutional_ownership("AAPL", yf_module=yf)
    assert r["available"] is False
    assert r["error"] is not None
    assert "RuntimeError" in r["error"]


def test_attribute_access_raises_graceful():
    ticker_obj = MagicMock()
    type(ticker_obj).major_holders = property(
        lambda self: (_ for _ in ()).throw(RuntimeError("blocked"))
    )
    ticker_obj.institutional_holders = None
    yf = MagicMock()
    yf.Ticker = MagicMock(return_value=ticker_obj)
    r = fetch_us_institutional_ownership("AAPL", yf_module=yf)
    # major_holders 접근 실패해도 크래시 없이 dict 반환
    assert r["available"] is False
    assert r["ticker"] == "AAPL"
