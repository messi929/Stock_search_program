"""yfinance 기반 미국 종목 기관 보유 스냅샷 (정보 제공용 — 신호/점수 아님).

⚠️ 성격 명시:
  - 미국 기관 보유는 분기 13F 공시(분기말 + 약 45일 지연) 기반의 **정적 스냅샷**.
  - 한국 시장의 일별 외국인/기관 수급과 **다름** — 일별 흐름/모멘텀 신호로 해석 불가.
  - 본 모듈 산출물은 **정보 위젯(참고 표시)** 용도로만 사용. 매매 신호/점수로 쓰지 말 것.

데이터 소스 (yfinance 1.x 검증):
  - Ticker.major_holders        → DataFrame(index=Breakdown, col=Value)
        insidersPercentHeld / institutionsPercentHeld / institutionsCount (fraction)
  - Ticker.institutional_holders → DataFrame
        ['Date Reported','Holder','pctHeld','Shares','Value','pctChange']

⚠️ 비공식 라이브러리 — 간헐 차단/지연. try/except + 부분 결과(graceful).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd
from loguru import logger


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


def _safe_int(v: Any) -> int | None:
    f = _safe_float(v)
    return int(f) if f is not None else None


def _pct(frac: Any) -> float | None:
    """fraction(0.6596) → percent(65.96, 소수 2자리). 이미 percent(>1.5 다수)면 그대로 추정 X — yfinance는 fraction 고정."""
    f = _safe_float(frac)
    return round(f * 100, 2) if f is not None else None


def _to_iso_date(v: Any) -> str | None:
    if v is None:
        return None
    try:
        if isinstance(v, str):
            return v.split("T")[0]
        if hasattr(v, "isoformat"):
            return v.isoformat().split("T")[0]
        ts = pd.Timestamp(v)
        if pd.isna(ts):
            return None
        return ts.strftime("%Y-%m-%d")
    except Exception:
        return None


def _parse_major_holders(mh: Any) -> dict[str, Any]:
    """major_holders DataFrame → insiders/institutions 비율 + 기관 수.

    신형(yfinance ≥0.2): index=Breakdown 라벨, 'Value' 컬럼(fraction).
    graceful — 형식이 달라도 빈 dict 반환.
    """
    out: dict[str, Any] = {}
    if mh is None or not hasattr(mh, "index"):
        return out
    try:
        # 'Value' 컬럼 우선, 없으면 첫 컬럼
        col = "Value" if "Value" in getattr(mh, "columns", []) else (
            mh.columns[0] if len(getattr(mh, "columns", [])) else None
        )
        if col is None:
            return out
        idx = {str(k): v for k, v in mh[col].items()}
        if "insidersPercentHeld" in idx:
            out["insiders_pct"] = _pct(idx["insidersPercentHeld"])
        if "institutionsPercentHeld" in idx:
            out["institutions_pct"] = _pct(idx["institutionsPercentHeld"])
        if "institutionsFloatPercentHeld" in idx:
            out["institutions_float_pct"] = _pct(idx["institutionsFloatPercentHeld"])
        if "institutionsCount" in idx:
            out["institutions_count"] = _safe_int(idx["institutionsCount"])
    except Exception as e:
        logger.debug(f"major_holders 파싱 실패: {type(e).__name__}: {str(e)[:100]}")
    return out


def _parse_institutional_holders(ih: Any, top_n: int) -> list[dict[str, Any]]:
    """institutional_holders DataFrame → 상위 보유 기관 리스트."""
    if ih is None or not hasattr(ih, "iterrows"):
        return []
    cols = list(getattr(ih, "columns", []))
    holders: list[dict[str, Any]] = []
    try:
        for _, row in ih.head(top_n).iterrows():
            holder = row.get("Holder") if "Holder" in cols else None
            if not holder:
                continue
            holders.append(
                {
                    "holder": str(holder),
                    "pct_held": _pct(row.get("pctHeld")) if "pctHeld" in cols else None,
                    "shares": _safe_int(row.get("Shares")) if "Shares" in cols else None,
                    "value": _safe_int(row.get("Value")) if "Value" in cols else None,
                    "date_reported": _to_iso_date(row.get("Date Reported"))
                    if "Date Reported" in cols
                    else None,
                    "pct_change": _safe_float(row.get("pctChange")) if "pctChange" in cols else None,
                }
            )
    except Exception as e:
        logger.debug(f"institutional_holders 파싱 실패: {type(e).__name__}: {str(e)[:100]}")
    return holders


def fetch_us_institutional_ownership(
    ticker: str,
    *,
    top_n: int = 10,
    yf_module: Any | None = None,
) -> dict[str, Any]:
    """미국 종목 기관 보유 스냅샷 (정보 제공용).

    Args:
        ticker: 미국 종목 심볼.
        top_n: 상위 보유 기관 개수.
        yf_module: yfinance 모듈 (테스트 mock).

    Returns:
        dict — 항상 available 키 포함. 실패/빈 응답도 graceful.
        {
          available: bool,
          ticker, insiders_pct, institutions_pct, institutions_float_pct,
          institutions_count, top_holders[], as_of, data_source, note, error
        }
    """
    ticker = (ticker or "").strip().upper()
    base = {
        "available": False,
        "ticker": ticker,
        "insiders_pct": None,
        "institutions_pct": None,
        "institutions_float_pct": None,
        "institutions_count": None,
        "top_holders": [],
        "as_of": None,
        "data_source": "yfinance (13F 기반 분기 스냅샷)",
        "note": "분기 공시 기반 정적 스냅샷(약 45일 지연). 일별 수급/매매 신호가 아닌 참고 정보입니다.",
        "error": None,
        "collected_at": datetime.now().isoformat(timespec="seconds"),
    }

    if not ticker:
        base["error"] = "ticker 누락"
        return base

    if yf_module is None:
        try:
            import yfinance as yf  # type: ignore

            yf_module = yf
        except ImportError:
            base["error"] = "yfinance 미설치"
            return base

    try:
        yf_ticker = yf_module.Ticker(ticker)
    except Exception as e:
        base["error"] = f"Ticker 생성 실패: {type(e).__name__}"
        return base

    # 1) major_holders (요약 비율)
    try:
        mh = getattr(yf_ticker, "major_holders", None)
        base.update(_parse_major_holders(mh))
    except Exception as e:
        logger.warning(
            f"major_holders 조회 실패 ({ticker}): {type(e).__name__}: {str(e)[:120]}"
        )

    # 2) institutional_holders (상위 기관)
    try:
        ih = getattr(yf_ticker, "institutional_holders", None)
        holders = _parse_institutional_holders(ih, top_n)
        base["top_holders"] = holders
        # as_of = 보유 기관 보고일 중 최신
        dates = [h["date_reported"] for h in holders if h.get("date_reported")]
        if dates:
            base["as_of"] = max(dates)
    except Exception as e:
        logger.warning(
            f"institutional_holders 조회 실패 ({ticker}): {type(e).__name__}: {str(e)[:120]}"
        )

    # available = 요약 비율 또는 상위 기관 중 하나라도 확보
    base["available"] = bool(
        base.get("institutions_pct") is not None or base.get("top_holders")
    )
    return base
