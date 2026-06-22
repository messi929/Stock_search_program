"""KIS OpenAPI 시세 라우트 (Phase 3A — REST).

엔드포인트:
  GET /api/kis/price/{ticker}          — 현재가
  GET /api/kis/chart/{ticker}/daily    — 일봉
  GET /api/kis/chart/{ticker}/minute   — 분봉
  GET /api/kis/orderbook/{ticker}      — 10호가
  GET /api/kis/investor/{ticker}       — 투자자별 매매동향

⚠️ KIS 정책 보호: 모든 응답을 백엔드 in-memory TTL 캐시.
   - 현재가 / 호가: 5초
   - 분봉: 30초
   - 일봉 / 투자자: 5분
   클라이언트가 폭주해도 KIS에는 캐시 무효화 주기마다만 호출.

⚠️ KisClient는 token 캐시 활용 위해 싱글톤 사용.
   KisClient.get_*는 sync → run_in_threadpool로 이벤트 루프 보호.
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, HTTPException, Path, Query, Request
from fastapi.concurrency import run_in_threadpool
from loguru import logger

from utils.data_collectors.kis_client import KisClient


router = APIRouter(prefix="/api/kis", tags=["axis-kis"])


# ──────────────────────────────────────────────
# 싱글톤 KisClient + 캐시
# ──────────────────────────────────────────────


_client: KisClient | None = None


def _kis() -> KisClient:
    """싱글톤 KisClient. KIS_APP_KEY 없으면 503."""
    global _client
    if _client is None:
        try:
            _client = KisClient()
        except Exception as e:
            logger.warning(f"KisClient 초기화 실패: {type(e).__name__}: {e}")
            raise HTTPException(status_code=503, detail="KIS 클라이언트 사용 불가")
    if not _client.app_key:
        raise HTTPException(status_code=503, detail="KIS_APP_KEY 미설정")
    return _client


_cache: dict[str, tuple[float, Any]] = {}


def _cached_or_fetch(key: str, ttl: float, fetcher) -> Any:
    """간단한 TTL in-memory 캐시. 동기 fetcher 호출."""
    now = time.time()
    entry = _cache.get(key)
    if entry and now - entry[0] < ttl:
        return entry[1]
    value = fetcher()
    _cache[key] = (now, value)
    return value


async def _async_cached(key: str, ttl: float, fetcher) -> Any:
    """비동기 wrap. fetcher는 sync.

    KIS 장애(특히 토큰 발급 1분 락 EGW00133)가 분석 페이지 전체를 unhandled 500으로
    죽이던 문제를 차단: fetch 실패 시 ① 만료된 캐시라도 있으면 그것을 반환(stale-on-error)
    ② 없으면 503(일시 불가)로 degrade — 시세 위젯만 비고 분석 본문은 진행되도록.
    """
    now = time.time()
    entry = _cache.get(key)
    if entry and now - entry[0] < ttl:
        return entry[1]
    try:
        value = await run_in_threadpool(fetcher)
    except HTTPException:
        raise
    except Exception as e:
        if entry is not None:
            logger.warning(
                f"[kis] {key} fetch 실패 → stale 캐시 반환: {type(e).__name__}: {str(e)[:140]}"
            )
            return entry[1]
        logger.warning(
            f"[kis] {key} fetch 실패(캐시 없음) → 503 degrade: "
            f"{type(e).__name__}: {str(e)[:140]}"
        )
        raise HTTPException(
            status_code=503,
            detail={"code": "KIS_UNAVAILABLE", "message": "시세를 일시적으로 가져올 수 없습니다 (잠시 후 재시도)"},
        )
    _cache[key] = (now, value)
    return value


# ──────────────────────────────────────────────
# 엔드포인트
# ──────────────────────────────────────────────


def _validate_ticker(ticker: str) -> str:
    """6자리 숫자만 허용. 자릿수 부족하면 zfill."""
    t = ticker.strip()
    if not t.isdigit() or len(t) > 6:
        raise HTTPException(status_code=400, detail="ticker는 6자리 숫자만 허용")
    return t.zfill(6)


@router.get("/price/{ticker}")
async def get_price(
    request: Request,
    ticker: str = Path(..., description="6자리 종목코드"),
) -> dict:
    """현재가 + 등락 + 거래량."""
    ticker = _validate_ticker(ticker)
    kis = _kis()
    data = await _async_cached(
        f"price:{ticker}", 5.0, lambda: kis.get_current_price(ticker)
    )
    if not data:
        raise HTTPException(status_code=502, detail="KIS 현재가 응답 없음")
    return {"ticker": ticker, "data": data, "source": "kis"}


@router.get("/chart/{ticker}/daily")
async def get_daily_chart(
    request: Request,
    ticker: str = Path(..., description="6자리 종목코드"),
    period: str = Query("D", regex="^[DWMY]$", description="D|W|M|Y"),
    adjusted: bool = Query(True, description="수정주가 여부"),
) -> dict:
    """일/주/월/년봉. 기본 D, 수정주가."""
    ticker = _validate_ticker(ticker)
    kis = _kis()
    cache_key = f"chart:{ticker}:{period}:{int(adjusted)}"
    bars = await _async_cached(
        cache_key,
        300.0,  # 5분
        lambda: kis.get_daily_chart(ticker, period=period, adjusted=adjusted),  # type: ignore[arg-type]
    )
    return {"ticker": ticker, "period": period, "bars": bars, "source": "kis"}


@router.get("/chart/{ticker}/minute")
async def get_minute_chart(
    request: Request,
    ticker: str = Path(..., description="6자리 종목코드"),
    time_hhmmss: str | None = Query(
        None, regex="^\\d{6}$", description="기준 시각 HHMMSS, None=현재"
    ),
) -> dict:
    """당일 1분봉 최근 30개."""
    ticker = _validate_ticker(ticker)
    kis = _kis()
    cache_key = f"minute:{ticker}:{time_hhmmss or 'now'}"
    bars = await _async_cached(
        cache_key,
        30.0,
        lambda: kis.get_minute_chart(ticker, time_hhmmss=time_hhmmss),
    )
    return {"ticker": ticker, "bars": bars, "source": "kis"}


@router.get("/orderbook/{ticker}")
async def get_orderbook(
    request: Request,
    ticker: str = Path(..., description="6자리 종목코드"),
) -> dict:
    """10호가 + 예상체결."""
    ticker = _validate_ticker(ticker)
    kis = _kis()
    data = await _async_cached(
        f"orderbook:{ticker}", 5.0, lambda: kis.get_orderbook(ticker)
    )
    if not data:
        raise HTTPException(status_code=502, detail="KIS 호가 응답 없음")
    return {"ticker": ticker, **data, "source": "kis"}


@router.get("/investor/{ticker}")
async def get_investor(
    request: Request,
    ticker: str = Path(..., description="6자리 종목코드"),
) -> dict:
    """투자자별 매매동향 (외국인/기관/개인) 최근 30일."""
    ticker = _validate_ticker(ticker)
    kis = _kis()
    rows = await _async_cached(
        f"investor:{ticker}", 300.0, lambda: kis.get_investor_trend(ticker)
    )
    return {"ticker": ticker, "trend": rows, "source": "kis"}


@router.get("/health")
async def kis_health(request: Request) -> dict:
    """KIS 라우트 헬스 — 키 존재 + token 캐시 상태."""
    try:
        kis = _kis()
    except HTTPException as e:
        return {"ok": False, "reason": e.detail}
    has_token = bool(kis._access_token) and time.time() < kis._token_expires_at
    return {
        "ok": True,
        "env": kis.env,
        "app_key_prefix": kis.app_key[:6] + "***" if kis.app_key else None,
        "token_in_memory": has_token,
        "stats": kis.stats.summary(),
        "cache_size": len(_cache),
    }
