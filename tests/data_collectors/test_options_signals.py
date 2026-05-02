"""utils/data_collectors/options_signals.py 단위 테스트 (mock yfinance)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pandas as pd
import pytest

from utils.data_collectors import options_signals as os_mod
from utils.data_collectors.options_signals import (
    PCR_CALL_DOMINANT,
    PCR_PUT_DOMINANT,
    calculate_options_signals,
    calculate_vkospi_signal,
    clear_cache,
)


# ──────────────────────────────────────────────
# fixtures
# ──────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_cache():
    clear_cache()
    yield
    clear_cache()


def _make_chain(calls_df: pd.DataFrame, puts_df: pd.DataFrame):
    """option_chain return 형태 mock."""
    return SimpleNamespace(calls=calls_df, puts=puts_df)


def _make_yf_module(
    expirations: tuple[str, ...],
    chain,
    current_price: float | None = 150.0,
):
    """yfinance.Ticker mock 모듈."""
    ticker_obj = MagicMock()
    ticker_obj.options = expirations
    ticker_obj.option_chain = MagicMock(return_value=chain)
    # fast_info 우선 경로 (객체 attribute)
    if current_price is None:
        ticker_obj.fast_info = SimpleNamespace()
        ticker_obj.info = {}
    else:
        ticker_obj.fast_info = SimpleNamespace(last_price=current_price)
        ticker_obj.info = {"currentPrice": current_price}

    yf_module = MagicMock()
    yf_module.Ticker = MagicMock(return_value=ticker_obj)
    return yf_module, ticker_obj


# ──────────────────────────────────────────────
# 1. PCR 계산 (volume + OI)
# ──────────────────────────────────────────────


def test_pcr_volume_and_oi_basic():
    """Put/Call 합이 정상 계산되는지."""
    calls = pd.DataFrame(
        {
            "strike": [145, 150, 155],
            "volume": [100, 200, 100],
            "openInterest": [500, 1000, 500],
            "impliedVolatility": [0.30, 0.32, 0.31],
        }
    )
    puts = pd.DataFrame(
        {
            "strike": [145, 150, 155],
            "volume": [50, 100, 50],
            "openInterest": [200, 400, 200],
            "impliedVolatility": [0.35, 0.36, 0.34],
        }
    )
    chain = _make_chain(calls, puts)
    yf_mod, _ = _make_yf_module(("2026-01-19",), chain, current_price=150.0)

    result = calculate_options_signals("AAPL", yf_module=yf_mod)

    assert result["available"] is True
    assert result["expiration"] == "2026-01-19"
    # vol: put 200 / call 400 = 0.5 → Call 우세
    assert result["put_call_ratio_volume"] == 0.5
    # oi: 800/2000 = 0.4
    assert result["put_call_ratio_oi"] == 0.4
    # ATM IV: ±5% = 142.5~157.5 → 모든 strike 포함, mean(0.30,0.32,0.31) = 0.31
    assert result["atm_iv_pct"] == pytest.approx(31.0, abs=0.01)
    assert result["current_price"] == 150.0


def test_pcr_call_volume_zero_returns_none():
    """call volume=0 → ratio None (0 division 회피)."""
    calls = pd.DataFrame(
        {
            "strike": [150],
            "volume": [0],
            "openInterest": [0],
            "impliedVolatility": [0.30],
        }
    )
    puts = pd.DataFrame(
        {
            "strike": [150],
            "volume": [10],
            "openInterest": [10],
            "impliedVolatility": [0.35],
        }
    )
    chain = _make_chain(calls, puts)
    yf_mod, _ = _make_yf_module(("2026-01-19",), chain)

    result = calculate_options_signals("LOWLIQ", yf_module=yf_mod)
    assert result["available"] is True
    assert result["put_call_ratio_volume"] is None
    assert result["put_call_ratio_oi"] is None


# ──────────────────────────────────────────────
# 2. ATM IV 계산
# ──────────────────────────────────────────────


def test_atm_iv_uses_only_in_band_strikes():
    """ATM band 외 strike는 IV 평균에서 제외."""
    calls = pd.DataFrame(
        {
            # 100 ±5% = 95~105 → 96, 100, 104만 포함, 80/120 제외
            "strike": [80, 96, 100, 104, 120],
            "volume": [10, 10, 10, 10, 10],
            "openInterest": [10, 10, 10, 10, 10],
            "impliedVolatility": [9.99, 0.40, 0.50, 0.60, 9.99],
        }
    )
    puts = pd.DataFrame(
        {
            "strike": [100],
            "volume": [10],
            "openInterest": [10],
            "impliedVolatility": [0.45],
        }
    )
    chain = _make_chain(calls, puts)
    yf_mod, _ = _make_yf_module(("2026-01-19",), chain, current_price=100.0)

    result = calculate_options_signals("X", yf_module=yf_mod)
    # 0.40, 0.50, 0.60 평균 = 0.50 → 50.0%
    assert result["atm_iv_pct"] == pytest.approx(50.0, abs=0.01)


def test_atm_iv_none_when_no_strikes_in_band():
    calls = pd.DataFrame(
        {
            "strike": [50, 200],
            "volume": [10, 10],
            "openInterest": [10, 10],
            "impliedVolatility": [0.40, 0.50],
        }
    )
    puts = pd.DataFrame(
        {
            "strike": [100],
            "volume": [10],
            "openInterest": [10],
            "impliedVolatility": [0.45],
        }
    )
    chain = _make_chain(calls, puts)
    yf_mod, _ = _make_yf_module(("2026-01-19",), chain, current_price=100.0)

    result = calculate_options_signals("Y", yf_module=yf_mod)
    assert result["atm_iv_pct"] is None


# ──────────────────────────────────────────────
# 3. 해석 분기 (Put 우세 / Call 우세 / 균형)
# ──────────────────────────────────────────────


def test_interpretation_put_dominant():
    # PCR > 1.2 → Put 우세
    calls = pd.DataFrame(
        {"strike": [100], "volume": [50], "openInterest": [50], "impliedVolatility": [0.4]}
    )
    puts = pd.DataFrame(
        {"strike": [100], "volume": [200], "openInterest": [200], "impliedVolatility": [0.4]}
    )
    chain = _make_chain(calls, puts)
    yf_mod, _ = _make_yf_module(("2026-01-19",), chain, current_price=100.0)

    result = calculate_options_signals("BEAR", yf_module=yf_mod)
    assert result["put_call_ratio_volume"] == 4.0
    assert "Put 우세" in result["interpretation"]


def test_interpretation_call_dominant():
    # PCR < 0.7 → Call 우세
    calls = pd.DataFrame(
        {"strike": [100], "volume": [200], "openInterest": [200], "impliedVolatility": [0.4]}
    )
    puts = pd.DataFrame(
        {"strike": [100], "volume": [100], "openInterest": [100], "impliedVolatility": [0.4]}
    )
    chain = _make_chain(calls, puts)
    yf_mod, _ = _make_yf_module(("2026-01-19",), chain, current_price=100.0)

    result = calculate_options_signals("BULL", yf_module=yf_mod)
    assert result["put_call_ratio_volume"] == 0.5
    assert "Call 우세" in result["interpretation"]


def test_interpretation_balanced():
    # 0.7 ≤ PCR ≤ 1.2 → 균형
    calls = pd.DataFrame(
        {"strike": [100], "volume": [100], "openInterest": [100], "impliedVolatility": [0.4]}
    )
    puts = pd.DataFrame(
        {"strike": [100], "volume": [100], "openInterest": [100], "impliedVolatility": [0.4]}
    )
    chain = _make_chain(calls, puts)
    yf_mod, _ = _make_yf_module(("2026-01-19",), chain, current_price=100.0)

    result = calculate_options_signals("EQ", yf_module=yf_mod)
    assert result["put_call_ratio_volume"] == 1.0
    assert "균형" in result["interpretation"]


# ──────────────────────────────────────────────
# 4. graceful handling
# ──────────────────────────────────────────────


def test_no_options_listed_graceful():
    """옵션 미상장 종목 → available=False + reason."""
    yf_mod, _ = _make_yf_module(expirations=(), chain=None)
    result = calculate_options_signals("NOOPT", yf_module=yf_mod)
    assert result["available"] is False
    assert "없음" in result["reason"] or "미상장" in result["reason"]


def test_options_attr_raises_returns_unavailable():
    """yf_ticker.options 접근에서 예외 → graceful False."""
    ticker_obj = MagicMock()
    type(ticker_obj).options = property(
        lambda self: (_ for _ in ()).throw(RuntimeError("network"))
    )
    yf_mod = MagicMock()
    yf_mod.Ticker = MagicMock(return_value=ticker_obj)
    result = calculate_options_signals("FAIL", yf_module=yf_mod)
    assert result["available"] is False
    assert "RuntimeError" in result["reason"]


def test_option_chain_raises_returns_unavailable():
    """option_chain 호출 자체가 throw → graceful False."""
    ticker_obj = MagicMock()
    ticker_obj.options = ("2026-01-19",)
    ticker_obj.option_chain = MagicMock(side_effect=ValueError("malformed"))
    yf_mod = MagicMock()
    yf_mod.Ticker = MagicMock(return_value=ticker_obj)
    result = calculate_options_signals("BAD", yf_module=yf_mod)
    assert result["available"] is False
    assert "ValueError" in result["reason"]


def test_empty_ticker_returns_unavailable():
    result = calculate_options_signals("")
    assert result["available"] is False


# ──────────────────────────────────────────────
# 5. option_chain(date=None, tz=None) 시그니처 정확
# ──────────────────────────────────────────────


def test_option_chain_called_with_date_positional():
    """option_chain은 첫 인자로 date(만기일)을 positional 전달해야 함."""
    calls = pd.DataFrame(
        {"strike": [100], "volume": [10], "openInterest": [10], "impliedVolatility": [0.3]}
    )
    puts = pd.DataFrame(
        {"strike": [100], "volume": [10], "openInterest": [10], "impliedVolatility": [0.3]}
    )
    chain = _make_chain(calls, puts)
    yf_mod, ticker_obj = _make_yf_module(("2026-02-16",), chain, current_price=100.0)
    calculate_options_signals("AAPL", yf_module=yf_mod)
    ticker_obj.option_chain.assert_called_once_with("2026-02-16")


# ──────────────────────────────────────────────
# 6. 캐싱 (30분 TTL)
# ──────────────────────────────────────────────


def test_cache_hit_avoids_second_call():
    calls = pd.DataFrame(
        {"strike": [100], "volume": [10], "openInterest": [10], "impliedVolatility": [0.3]}
    )
    puts = pd.DataFrame(
        {"strike": [100], "volume": [10], "openInterest": [10], "impliedVolatility": [0.3]}
    )
    chain = _make_chain(calls, puts)
    yf_mod, ticker_obj = _make_yf_module(("2026-01-19",), chain, current_price=100.0)

    r1 = calculate_options_signals("CACHE", yf_module=yf_mod)
    r2 = calculate_options_signals("CACHE", yf_module=yf_mod)

    assert r1["available"] is True
    assert r2.get("from_cache") is True
    # Ticker는 첫 호출에서만 생성
    assert yf_mod.Ticker.call_count == 1


def test_skip_cache_forces_refetch():
    calls = pd.DataFrame(
        {"strike": [100], "volume": [10], "openInterest": [10], "impliedVolatility": [0.3]}
    )
    puts = pd.DataFrame(
        {"strike": [100], "volume": [10], "openInterest": [10], "impliedVolatility": [0.3]}
    )
    chain = _make_chain(calls, puts)
    yf_mod, _ = _make_yf_module(("2026-01-19",), chain, current_price=100.0)

    calculate_options_signals("R", yf_module=yf_mod)
    calculate_options_signals("R", yf_module=yf_mod, skip_cache=True)
    assert yf_mod.Ticker.call_count == 2


# ──────────────────────────────────────────────
# 7. VKOSPI 보조 (yfinance 미지원 graceful)
# ──────────────────────────────────────────────


def test_vkospi_returns_unavailable_when_no_history():
    ticker_obj = MagicMock()
    ticker_obj.history = MagicMock(return_value=pd.DataFrame())
    yf_mod = MagicMock()
    yf_mod.Ticker = MagicMock(return_value=ticker_obj)

    result = calculate_vkospi_signal(yf_module=yf_mod)
    assert result["available"] is False


def test_vkospi_returns_close_when_history_present():
    hist = pd.DataFrame(
        {"Close": [25.3, 26.1, 24.9]},
        index=pd.to_datetime(["2026-04-29", "2026-04-30", "2026-05-02"]),
    )
    ticker_obj = MagicMock()
    ticker_obj.history = MagicMock(return_value=hist)
    yf_mod = MagicMock()
    yf_mod.Ticker = MagicMock(return_value=ticker_obj)

    result = calculate_vkospi_signal(yf_module=yf_mod)
    assert result["available"] is True
    assert result["last_close"] == 24.9


def test_vkospi_history_error_graceful():
    ticker_obj = MagicMock()
    ticker_obj.history = MagicMock(side_effect=RuntimeError("blocked"))
    yf_mod = MagicMock()
    yf_mod.Ticker = MagicMock(return_value=ticker_obj)

    result = calculate_vkospi_signal(yf_module=yf_mod)
    assert result["available"] is False
    assert "RuntimeError" in result["reason"]


# ──────────────────────────────────────────────
# 8. 임계값 상수
# ──────────────────────────────────────────────


def test_threshold_constants():
    assert PCR_PUT_DOMINANT > 1.0
    assert PCR_CALL_DOMINANT < 1.0
    assert PCR_PUT_DOMINANT > PCR_CALL_DOMINANT
