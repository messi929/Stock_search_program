"""yfinance 기반 미국 종목 이벤트 (실적/배당) 수집 모듈.

WEEK_C.md Day 2 산출물 (Event Analyst 페르소나용).

데이터 소스 (yfinance 1.x 검증):
  - Ticker.earnings_dates                → DataFrame (Reported EPS, Estimate, Surprise)
  - Ticker.get_earnings_dates(limit=N)   → 동일, limit 인자
  - Ticker.dividends                     → Series (배당락일 → 금액)
  - Ticker.quarterly_income_stmt         → DataFrame (분기 손익 — 권장)
  - Ticker.calendar                      → dict (다음 실적/배당락)

⚠️ 비공식 라이브러리 — 간헐 차단/지연.
   → try/except + 부분 결과 반환. 빈 응답도 graceful.

⚠️ quarterly_earnings는 deprecated 가능 → quarterly_income_stmt 권장.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import pandas as pd
from loguru import logger


@dataclass
class YfEventResult:
    ticker: str
    earnings_dates: list[dict[str, Any]]
    dividends: list[dict[str, Any]]
    next_earnings: dict[str, Any] | None
    next_ex_dividend: dict[str, Any] | None
    quarterly_income_available: bool
    data_source: str = "yfinance"
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "earnings_dates": self.earnings_dates,
            "dividends": self.dividends,
            "next_earnings": self.next_earnings,
            "next_ex_dividend": self.next_ex_dividend,
            "quarterly_income_available": self.quarterly_income_available,
            "data_source": self.data_source,
            "error": self.error,
            "collected_at": datetime.now().isoformat(timespec="seconds"),
        }


def _to_iso_date(v: Any) -> str | None:
    """Timestamp/datetime/str 등을 YYYY-MM-DD ISO 문자열로 정규화."""
    if v is None:
        return None
    try:
        if isinstance(v, str):
            # 이미 ISO면 통과
            return v.split("T")[0]
        if hasattr(v, "isoformat"):
            return v.isoformat().split("T")[0]
        ts = pd.Timestamp(v)
        if pd.isna(ts):
            return None
        return ts.strftime("%Y-%m-%d")
    except Exception:
        return None


def _earnings_to_records(
    df: pd.DataFrame, limit: int = 12
) -> list[dict[str, Any]]:
    """earnings_dates DataFrame → 레코드 리스트.

    yfinance 컬럼은 버전에 따라 변동:
      - "EPS Estimate", "Reported EPS", "Surprise(%)"
      - 또는 "epsEstimate", "epsActual", "surprise" (저버전)
    양쪽 graceful 매핑.
    """
    if df is None or len(df) == 0:
        return []

    out: list[dict[str, Any]] = []
    # index = 발표일자 Timestamp
    for ts, row in df.iloc[:limit].iterrows():
        date_iso = _to_iso_date(ts)
        if date_iso is None:
            continue
        # 컬럼 매핑 (둘 다 시도)
        estimate = (
            row.get("EPS Estimate")
            if "EPS Estimate" in df.columns
            else row.get("epsEstimate")
        )
        reported = (
            row.get("Reported EPS")
            if "Reported EPS" in df.columns
            else row.get("epsActual")
        )
        surprise = (
            row.get("Surprise(%)")
            if "Surprise(%)" in df.columns
            else row.get("surprise")
        )

        out.append(
            {
                "date": date_iso,
                "eps_estimate": _safe_float(estimate),
                "eps_reported": _safe_float(reported),
                "surprise_pct": _safe_float(surprise),
                "is_future": _is_future(date_iso),
            }
        )
    return out


def _dividends_to_records(
    series: pd.Series, limit: int = 12
) -> list[dict[str, Any]]:
    if series is None or len(series) == 0:
        return []
    s = series.tail(limit)
    out: list[dict[str, Any]] = []
    for ts, amount in s.items():
        date_iso = _to_iso_date(ts)
        if date_iso is None:
            continue
        out.append({"ex_date": date_iso, "amount": _safe_float(amount)})
    return out


def _safe_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except Exception:
        pass
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _is_future(date_iso: str) -> bool:
    try:
        return datetime.strptime(date_iso, "%Y-%m-%d") > datetime.now()
    except Exception:
        return False


def _next_event_from_records(
    records: list[dict[str, Any]], date_key: str
) -> dict[str, Any] | None:
    """발표일이 미래인 가장 가까운 이벤트 1건."""
    future = [r for r in records if r.get(date_key) and _is_future(r[date_key])]
    if not future:
        return None
    future.sort(key=lambda r: r[date_key])
    return future[0]


def fetch_yfinance_events(
    ticker: str,
    *,
    earnings_limit: int = 12,
    dividend_limit: int = 12,
    yf_module: Any | None = None,
) -> dict[str, Any]:
    """미국 종목 실적/배당 이벤트 수집.

    Args:
        ticker: 미국 종목 심볼.
        earnings_limit: 실적 발표 이력 개수.
        dividend_limit: 배당 이력 개수.
        yf_module: yfinance 모듈 (테스트 mock).

    Returns:
        YfEventResult.to_dict() — 부분 실패도 가능 (필드별 graceful).
    """
    ticker = (ticker or "").strip().upper()
    if not ticker:
        return YfEventResult(
            ticker=ticker,
            earnings_dates=[],
            dividends=[],
            next_earnings=None,
            next_ex_dividend=None,
            quarterly_income_available=False,
            error="ticker 누락",
        ).to_dict()

    if yf_module is None:
        try:
            import yfinance as yf  # type: ignore

            yf_module = yf
        except ImportError:
            return YfEventResult(
                ticker=ticker,
                earnings_dates=[],
                dividends=[],
                next_earnings=None,
                next_ex_dividend=None,
                quarterly_income_available=False,
                error="yfinance 미설치",
            ).to_dict()

    try:
        yf_ticker = yf_module.Ticker(ticker)
    except Exception as e:
        return YfEventResult(
            ticker=ticker,
            earnings_dates=[],
            dividends=[],
            next_earnings=None,
            next_ex_dividend=None,
            quarterly_income_available=False,
            error=f"Ticker 생성 실패: {type(e).__name__}",
        ).to_dict()

    # 1) 실적 발표 (earnings_dates 우선, fallback get_earnings_dates)
    earnings_records: list[dict[str, Any]] = []
    try:
        ed = getattr(yf_ticker, "earnings_dates", None)
        if ed is None or (hasattr(ed, "empty") and ed.empty):
            getter = getattr(yf_ticker, "get_earnings_dates", None)
            if getter:
                ed = getter(limit=earnings_limit)
        if ed is not None and hasattr(ed, "iterrows"):
            earnings_records = _earnings_to_records(ed, limit=earnings_limit)
    except Exception as e:
        logger.warning(
            f"earnings_dates 조회 실패 ({ticker}): "
            f"{type(e).__name__}: {str(e)[:120]}"
        )

    # 2) 배당
    dividends_records: list[dict[str, Any]] = []
    try:
        div = getattr(yf_ticker, "dividends", None)
        if div is not None and hasattr(div, "items"):
            dividends_records = _dividends_to_records(div, limit=dividend_limit)
    except Exception as e:
        logger.warning(
            f"dividends 조회 실패 ({ticker}): "
            f"{type(e).__name__}: {str(e)[:120]}"
        )

    # 3) quarterly_income_stmt 사용 가능 여부 (단순 boolean — 본 모듈 산출물에서는 raw 미저장)
    quarterly_income_available = False
    try:
        qi = getattr(yf_ticker, "quarterly_income_stmt", None)
        if qi is not None and hasattr(qi, "empty"):
            quarterly_income_available = not qi.empty
    except Exception as e:
        logger.debug(
            f"quarterly_income_stmt 조회 실패 ({ticker}): "
            f"{type(e).__name__}: {str(e)[:120]}"
        )

    next_earnings = _next_event_from_records(earnings_records, "date")
    next_ex_dividend = _next_event_from_records(dividends_records, "ex_date")

    return YfEventResult(
        ticker=ticker,
        earnings_dates=earnings_records,
        dividends=dividends_records,
        next_earnings=next_earnings,
        next_ex_dividend=next_ex_dividend,
        quarterly_income_available=quarterly_income_available,
    ).to_dict()
