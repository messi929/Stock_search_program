"""yfinance 옵션 시장 시그널 수집 + 해석 모듈.

WEEK_C.md Day 1 산출물 (Event Analyst 페르소나용).

데이터 소스 (yfinance 1.x 검증):
  - Ticker.options                  → 만기일 튜플
  - Ticker.option_chain(date=None)  → calls/puts DataFrame (date가 첫 인자, tz는 keyword)
  - Ticker.info                     → currentPrice (ATM 기준)

⚠️ yfinance는 비공식 (Yahoo Finance 스크래핑) — 간헐 차단/지연 발생.
   → try/except + 30분 TTL 캐시로 graceful 처리.

산출:
  - put_call_ratio_volume / put_call_ratio_oi   (>1.2: Put 우세, <0.7: Call 우세)
  - atm_iv_pct                                   (현재가 ±5% strike 콜 IV 평균)
  - interpretation                               (한국어 한 줄 해석)

한국 시장:
  - KRX 개별 종목 옵션 거래량 미미 → 의미 없음 (명시적으로 제외).
  - VKOSPI(`^VKOSPI`) 시장 변동성 보조는 시도하되 yfinance 미지원 시 None 반환.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from loguru import logger


CACHE_TTL_SEC = 1800  # 30분
ATM_BAND_PCT = 0.05  # 현재가 ±5% strike 범위
PCR_PUT_DOMINANT = 1.2  # PCR > 1.2 → Put 우세 (헷징/하락 베팅)
PCR_CALL_DOMINANT = 0.7  # PCR < 0.7 → Call 우세 (강세 베팅)


@dataclass
class _Entry:
    value: dict[str, Any]
    expires_at: float


# 모듈 레벨 캐시 (프로세스 단위). 30분 TTL로 짧게 유지 — 옵션은 일중 변동.
_cache: dict[str, _Entry] = {}


def _cache_get(key: str) -> dict[str, Any] | None:
    e = _cache.get(key)
    if e is None:
        return None
    if e.expires_at < time.time():
        _cache.pop(key, None)
        return None
    return e.value


def _cache_set(key: str, value: dict[str, Any]) -> None:
    _cache[key] = _Entry(value=value, expires_at=time.time() + CACHE_TTL_SEC)


def _interpret(pcr_volume: float | None, atm_iv: float | None) -> str:
    """옵션 신호 한국어 해석 (단정 표현 회피 — LEGAL 정책)."""
    if pcr_volume is None or atm_iv is None:
        return "옵션 데이터 부족 — 해석 불가"

    if pcr_volume > PCR_PUT_DOMINANT:
        return (
            f"Put/Call 비율 {pcr_volume:.2f} (Put 우세) — "
            "헷징 또는 하락 베팅 우세 관찰. 역발상 가능 신호."
        )
    if pcr_volume < PCR_CALL_DOMINANT:
        return (
            f"Put/Call 비율 {pcr_volume:.2f} (Call 우세) — "
            "강세 베팅 우세 관찰. 정점 가능성 경계 필요."
        )
    return f"Put/Call 비율 {pcr_volume:.2f} — 균형, 명확한 방향성 신호 부재."


def calculate_options_signals(
    ticker: str,
    *,
    skip_cache: bool = False,
    yf_module: Any | None = None,
) -> dict[str, Any]:
    """미국 종목 옵션 시그널 계산.

    Args:
        ticker: 미국 종목 심볼 (예: "AAPL", "RKLB")
        skip_cache: True면 캐시 무시.
        yf_module: yfinance 모듈 (테스트용 mock 주입 가능).

    Returns:
        {
            "ticker": "AAPL",
            "available": bool,
            "reason": str | None,            # available=False 시 사유
            "expiration": "2026-01-19",
            "put_call_ratio_volume": float | None,
            "put_call_ratio_oi": float | None,
            "atm_iv_pct": float | None,      # 0~수백 % (소수 아닌 퍼센트)
            "current_price": float | None,
            "interpretation": str,
            "data_source": "yfinance",
            "collected_at": iso_str,
        }
    """
    ticker = (ticker or "").strip().upper()
    if not ticker:
        return {"available": False, "reason": "ticker 누락", "ticker": ticker}

    cache_key = f"options:{ticker}"
    if not skip_cache:
        cached = _cache_get(cache_key)
        if cached is not None:
            return {**cached, "from_cache": True}

    if yf_module is None:
        try:
            import yfinance as yf  # type: ignore

            yf_module = yf
        except ImportError:
            return {
                "available": False,
                "reason": "yfinance 미설치",
                "ticker": ticker,
            }

    try:
        yf_ticker = yf_module.Ticker(ticker)
        expirations = yf_ticker.options or ()
    except Exception as e:
        logger.warning(
            f"options_signals fetch 실패 ({ticker}): "
            f"{type(e).__name__}: {str(e)[:120]}"
        )
        return {
            "available": False,
            "reason": f"yfinance 호출 실패: {type(e).__name__}",
            "ticker": ticker,
        }

    if not expirations:
        result = {
            "ticker": ticker,
            "available": False,
            "reason": "옵션 거래 없음 (해당 종목 옵션 미상장)",
            "data_source": "yfinance",
            "collected_at": _iso_now(),
        }
        _cache_set(cache_key, result)
        return result

    nearest = expirations[0]

    try:
        chain = yf_ticker.option_chain(nearest)
    except Exception as e:
        logger.warning(
            f"option_chain({nearest}) 실패 ({ticker}): "
            f"{type(e).__name__}: {str(e)[:120]}"
        )
        return {
            "ticker": ticker,
            "available": False,
            "reason": f"option_chain 실패: {type(e).__name__}",
            "data_source": "yfinance",
            "collected_at": _iso_now(),
        }

    calls = getattr(chain, "calls", None)
    puts = getattr(chain, "puts", None)

    pcr_volume = _safe_ratio(_sum_col(puts, "volume"), _sum_col(calls, "volume"))
    pcr_oi = _safe_ratio(
        _sum_col(puts, "openInterest"), _sum_col(calls, "openInterest")
    )

    # 현재가 (info가 무거우면 fast_info 시도)
    current_price = _get_current_price(yf_ticker)

    atm_iv = _atm_iv(calls, current_price)
    atm_iv_pct = round(atm_iv * 100, 2) if atm_iv is not None else None

    result = {
        "ticker": ticker,
        "available": True,
        "expiration": str(nearest),
        "put_call_ratio_volume": _round_or_none(pcr_volume, 2),
        "put_call_ratio_oi": _round_or_none(pcr_oi, 2),
        "atm_iv_pct": atm_iv_pct,
        "current_price": _round_or_none(current_price, 4),
        "interpretation": _interpret(pcr_volume, atm_iv),
        "data_source": "yfinance",
        "collected_at": _iso_now(),
    }
    _cache_set(cache_key, result)
    return result


def calculate_vkospi_signal(
    *,
    skip_cache: bool = False,
    yf_module: Any | None = None,
) -> dict[str, Any]:
    """한국 시장 변동성 지수(VKOSPI) 보조 시그널.

    yfinance `^VKOSPI` 시도 — 미제공 시 graceful fallback.
    개별 한국 종목엔 옵션 신호가 의미 없으므로 시장 전체 지표로만 활용.
    """
    cache_key = "options:VKOSPI"
    if not skip_cache:
        cached = _cache_get(cache_key)
        if cached is not None:
            return {**cached, "from_cache": True}

    if yf_module is None:
        try:
            import yfinance as yf  # type: ignore

            yf_module = yf
        except ImportError:
            return {"available": False, "reason": "yfinance 미설치"}

    try:
        ticker = yf_module.Ticker("^VKOSPI")
        hist = ticker.history(period="5d")
    except Exception as e:
        logger.warning(f"VKOSPI 호출 실패: {type(e).__name__}: {str(e)[:120]}")
        return {
            "available": False,
            "reason": f"yfinance VKOSPI 미지원 또는 일시 오류: {type(e).__name__}",
        }

    if hist is None or len(hist) == 0:
        result = {
            "available": False,
            "reason": "VKOSPI 데이터 없음 (yfinance 미지원 가능)",
            "data_source": "yfinance",
            "collected_at": _iso_now(),
        }
        _cache_set(cache_key, result)
        return result

    last = hist.iloc[-1]
    last_close = float(last["Close"]) if "Close" in hist.columns else None
    result = {
        "available": True,
        "index": "VKOSPI",
        "last_close": _round_or_none(last_close, 2),
        "data_source": "yfinance",
        "collected_at": _iso_now(),
    }
    _cache_set(cache_key, result)
    return result


# ──────────────────────────────────────────────
# 헬퍼
# ──────────────────────────────────────────────


def _sum_col(df: Any, col: str) -> float:
    """DataFrame 컬럼 합 (NaN/None graceful)."""
    if df is None or len(df) == 0 or col not in getattr(df, "columns", []):
        return 0.0
    try:
        return float(df[col].fillna(0).sum())
    except Exception:
        return 0.0


def _safe_ratio(numer: float, denom: float) -> float | None:
    if denom is None or denom <= 0:
        return None
    return numer / denom


def _round_or_none(v: float | None, digits: int) -> float | None:
    return None if v is None else round(v, digits)


def _atm_iv(calls: Any, current_price: float | None) -> float | None:
    """현재가 ±5% 범위 콜 옵션의 평균 IV (소수, 0.65 = 65%)."""
    if calls is None or current_price is None or current_price <= 0:
        return None
    if "strike" not in getattr(calls, "columns", []):
        return None
    if "impliedVolatility" not in getattr(calls, "columns", []):
        return None
    lo = current_price * (1 - ATM_BAND_PCT)
    hi = current_price * (1 + ATM_BAND_PCT)
    try:
        atm = calls[(calls["strike"] >= lo) & (calls["strike"] <= hi)]
        iv = atm["impliedVolatility"].dropna()
        if len(iv) == 0:
            return None
        return float(iv.mean())
    except Exception:
        return None


def _get_current_price(yf_ticker: Any) -> float | None:
    """현재가 조회 — fast_info 우선, info fallback."""
    # fast_info는 가벼움 (1 호출), info는 무거움 (네트워크 다수)
    try:
        fast = getattr(yf_ticker, "fast_info", None)
        if fast is not None:
            # fast_info는 dict-like 또는 객체 — 양쪽 시도
            for attr in ("last_price", "lastPrice"):
                v = (
                    fast.get(attr) if hasattr(fast, "get") else getattr(fast, attr, None)
                )
                if v is not None:
                    return float(v)
    except Exception:
        pass

    try:
        info = yf_ticker.info or {}
        for key in ("currentPrice", "regularMarketPrice", "previousClose"):
            v = info.get(key)
            if v is not None:
                return float(v)
    except Exception:
        return None
    return None


def _iso_now() -> str:
    from datetime import datetime

    return datetime.now().isoformat(timespec="seconds")


def clear_cache() -> None:
    """테스트용 캐시 비우기."""
    _cache.clear()
