"""인기종목 사전 분석 → L2 응답 캐시 워밍 (jobs.cache_warm).

collector 데이터 갱신(08:00/17:30 KST) 직후 실행. 인기종목 N개를 기본 페르소나로
미리 run_analysis → utils.cache.default_cache(L2 Firestore)에 적재. 사용자 첫 분석이
**동일 데이터 스냅샷**에서 cache hit → ~12s를 ~3-5s로 단축한다.

■ 캐시 키 정합성 (핵심)
  라이브 /analyze와 바이트 단위로 동일한 messages를 만들어야 hit한다. 유일한 분기점은
  종목명 주입(graph._resolve_stock_name → screener _get_combined_df / _data_store)이다.
  잡 컨텍스트엔 그 in-memory store가 비어 있으므로, 시작 시 load_stocks(Firestore)로
  ticker→name 맵을 set_data해 라이브와 동일하게 맞춘다. Analyst 등 나머지 노드는
  애초에 load_stocks(Firestore 공유)를 직접 쓰므로 자동 일치한다.

■ 인기종목 산출
  1. analysis_history collection_group 최근 활동 ticker (실사용 신호, best-effort)
  2. 부족분은 스크리너 snapshot 거래대금 상위로 보충
  이미 더운 종목은 재실행해도 전부 cache hit → Claude 미호출 → 비용 0. 콜드만 과금.

■ 비용
  콜드 딥다이브 1건 ~175원(Strategist Sonnet). WARM_TICKER_COUNT(기본 12)로 조절.
  예: 12종목 × 평일 2회 ≈ 4,200원/일. 전부 더우면 0원.

env:
  WARM_TICKER_COUNT (기본 12)        — 워밍 대상 종목 수
  WARM_PERSONA      (기본 blackrock) — 워밍 페르소나(무료 기본)
  WARM_MARKET       (기본 kr)        — 후보 풀 시장 (load_stocks source)
  WARM_HISTORY_DAYS (기본 14)        — 인기 산출 활동 윈도우(일)

실행:
  python -m jobs.cache_warm
  python -m jobs.cache_warm --dry-run        # 종목 선정만 출력, 분석 X
  python -m jobs.cache_warm --count 5
"""

from __future__ import annotations

import argparse
import asyncio
import os
import time
from typing import Any, Optional

from loguru import logger


# ──────────────────────────────────────────────
# env
# ──────────────────────────────────────────────

def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "") or default)
    except (TypeError, ValueError):
        return default


WARM_TICKER_COUNT = _env_int("WARM_TICKER_COUNT", 12)
WARM_PERSONA = os.environ.get("WARM_PERSONA", "blackrock").strip() or "blackrock"
WARM_MARKET = (os.environ.get("WARM_MARKET", "kr").strip() or "kr").lower()
WARM_HISTORY_DAYS = _env_int("WARM_HISTORY_DAYS", 14)

# 워밍 비용은 익명 버킷(ai_usage_anonymous)에 기록 — 실사용자/관리자 스캔과 분리.
WARM_UID = ""


# ──────────────────────────────────────────────
# 종목명 맵 적재 (라이브 _data_store와 정합)
# ──────────────────────────────────────────────

def prime_name_store() -> int:
    """load_stocks(Firestore) → screener _data_store 적재 (종목명 주입 정합용).

    _resolve_stock_name이 읽는 _get_combined_df를 라이브 API 서버와 동일하게 채운다.
    name 컬럼만 사용되므로 buy_score/기술지표 재계산은 불필요. 반환: 적재 종목 수.
    """
    try:
        import pandas as pd

        from screener.api.routes import set_data
        from screener.db.repository import load_stocks

        kr = load_stocks("kr")
        us = load_stocks("us")
        etf = load_stocks("etf")
        frames = [d for d in (kr, us) if d is not None and not d.empty]
        if not frames:
            logger.warning("[warm] load_stocks 결과 비어 있음 — 종목명 주입 생략")
            return 0
        snapshot = pd.concat(frames, ignore_index=True)
        set_data(snapshot, etf_df=etf if (etf is not None and not etf.empty) else None)
        n = len(snapshot) + (len(etf) if etf is not None and not etf.empty else 0)
        logger.info(f"[warm] 종목명 store 적재: {n}종목")
        return n
    except Exception as e:
        logger.warning(f"[warm] 종목명 store 적재 실패(graceful): {type(e).__name__}: {e}")
        return 0


# ──────────────────────────────────────────────
# 인기종목 산출
# ──────────────────────────────────────────────

def popular_from_history(db: Any, days: int, cap: int) -> list[str]:
    """analysis_history collection_group 최근 활동 최다 ticker (best-effort).

    인덱스 미존재/오류 시 빈 리스트(graceful). order_by created_at desc로 최근 N건만
    훑어 kind=analysis ticker 빈도 집계 — cutoff 필터는 코드에서 적용(복합 인덱스 회피).
    """
    try:
        from datetime import datetime, timedelta, timezone

        from firebase_admin import firestore

        cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, days))
        docs = (
            db.collection_group("analysis_history")
            .order_by("created_at", direction=firestore.Query.DESCENDING)
            .limit(800)
            .stream()
        )
        counts: dict[str, int] = {}
        for d in docs:
            x = d.to_dict() or {}
            if x.get("kind") != "analysis":
                continue
            ca = x.get("created_at")
            try:
                if ca is not None and hasattr(ca, "timestamp") and ca < cutoff:
                    continue
            except Exception:
                pass
            tk = (x.get("ticker") or "").upper()
            if tk:
                counts[tk] = counts.get(tk, 0) + 1
        ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
        out = [tk for tk, _ in ranked[:cap]]
        if out:
            logger.info(f"[warm] 이력 기반 인기종목 {len(out)}개: {out}")
        return out
    except Exception as e:
        logger.info(f"[warm] 이력 기반 인기종목 산출 skip(graceful): {type(e).__name__}: {e}")
        return []


def popular_from_screener(market: str, cap: int) -> list[str]:
    """스크리너 snapshot 거래대금 상위 ticker (인덱스 불필요·결정적)."""
    try:
        from screener.db.repository import load_stocks

        df = load_stocks(market)
        if df is None or df.empty:
            return []
        col = "trading_value" if "trading_value" in df.columns else "market_cap"
        if col not in df.columns:
            return []
        ranked = (
            df[["ticker", col]]
            .dropna(subset=["ticker"])
            .sort_values(col, ascending=False)
        )
        out = [str(t).strip() for t in ranked["ticker"].tolist() if str(t).strip()]
        return out[:cap]
    except Exception as e:
        logger.warning(f"[warm] 스크리너 인기종목 산출 실패: {type(e).__name__}: {e}")
        return []


def select_tickers(db: Any, count: int, market: str, history_days: int) -> list[str]:
    """이력(실수요) 우선 + 스크리너 거래대금 보충 → dedup, count개."""
    ordered: list[str] = []
    seen: set[str] = set()

    def _add(tickers: list[str]) -> None:
        for t in tickers:
            u = t.upper()
            if u in seen:
                continue
            seen.add(u)
            ordered.append(t)
            if len(ordered) >= count:
                break

    _add(popular_from_history(db, history_days, count))
    if len(ordered) < count:
        _add(popular_from_screener(market, count * 2))
    return ordered[:count]


# ──────────────────────────────────────────────
# 워밍 실행
# ──────────────────────────────────────────────

async def warm_one(ticker: str, persona: str) -> dict[str, Any]:
    """종목 1개 사전 분석 → L2 캐시 적재. 콜드면 과금, 더우면 cache hit(비용 0)."""
    from agents.graph import run_analysis

    t0 = time.time()
    try:
        await run_analysis(ticker=ticker, query=f"{ticker} 분석", persona=persona, user_uid=WARM_UID)
        elapsed = round(time.time() - t0, 2)
        # 5초 미만이면 전부 cache hit(Claude 미호출)일 가능성↑ → 신규 과금 없음.
        cached = elapsed < 5.0
        logger.info(f"[warm] {ticker} {'HIT(비용0)' if cached else 'COLD(과금)'} {elapsed}s")
        return {"ticker": ticker, "elapsed": elapsed, "likely_cached": cached, "ok": True}
    except Exception as e:
        logger.warning(f"[warm] {ticker} 실패: {type(e).__name__}: {e}")
        return {"ticker": ticker, "elapsed": round(time.time() - t0, 2), "ok": False, "error": str(e)}


async def run_warm(
    dry_run: bool = False, count: Optional[int] = None, persona: Optional[str] = None
) -> dict[str, Any]:
    """인기종목 사전 캐시 워밍 메인."""
    from screener.db.firebase_client import get_db

    t0 = time.time()
    n = count or WARM_TICKER_COUNT
    pers = (persona or WARM_PERSONA).strip() or "blackrock"
    db = get_db()

    # 종목명 주입 정합 (cache 키 일치 필수)
    prime_name_store()

    tickers = select_tickers(db, n, WARM_MARKET, WARM_HISTORY_DAYS)
    logger.info("=" * 56)
    logger.info(f"캐시 워밍 시작 — {len(tickers)}종목 · persona={pers} · dry_run={dry_run}")
    logger.info(f"  대상: {tickers}")
    logger.info("=" * 56)

    if dry_run:
        return {"selected": tickers, "dry_run": True, "elapsed_sec": round(time.time() - t0, 1)}

    results: list[dict[str, Any]] = []
    for tk in tickers:  # 순차 — Claude rate limit + Cloud Run max=1 보호
        results.append(await warm_one(tk, pers))

    cold = sum(1 for r in results if r.get("ok") and not r.get("likely_cached"))
    hit = sum(1 for r in results if r.get("ok") and r.get("likely_cached"))
    failed = sum(1 for r in results if not r.get("ok"))
    summary = {
        "selected": len(tickers),
        "warmed_cold": cold,   # 신규 분석(과금)
        "already_hot": hit,    # 이미 캐시(비용 0)
        "failed": failed,
        "persona": pers,
        "dry_run": dry_run,
        "elapsed_sec": round(time.time() - t0, 1),
    }
    logger.info("=" * 56)
    logger.info("캐시 워밍 완료")
    for k, v in summary.items():
        logger.info(f"  {k}: {v}")
    logger.info("=" * 56)
    return summary


def main(argv: list[str] | None = None) -> int:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:
        pass

    parser = argparse.ArgumentParser(description="인기종목 사전 캐시 워밍")
    parser.add_argument("--dry-run", action="store_true", help="종목 선정만 출력, 분석 X")
    parser.add_argument("--count", type=int, default=None, help="워밍 종목 수(기본 WARM_TICKER_COUNT)")
    parser.add_argument("--persona", type=str, default=None, help="워밍 페르소나(기본 WARM_PERSONA)")
    args = parser.parse_args(argv)

    asyncio.run(run_warm(dry_run=args.dry_run, count=args.count, persona=args.persona))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
