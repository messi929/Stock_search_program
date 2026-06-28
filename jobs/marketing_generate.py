"""마케팅 글 일괄 생성 CLI (jobs.marketing_generate).

스레드용 종목 글을 로컬에서 Haiku로 일괄 생성 → 콘솔 출력 + Firestore
`marketing_drafts`에 status=draft로 저장(웹 /admin/marketing 검수탭에 그대로 뜸).

웹 생성 버튼과 동일 로직(agents.marketer)을 쓰되, 잡 컨텍스트엔 in-memory 스냅샷이
없으므로 cache_warm.prime_name_store와 같은 방식으로 load_stocks(Firestore) → set_data해
build_instant_snapshot이 실제 수치(PER/RSI/등락 등)를 읽게 한다.

필요 env: ANTHROPIC_API_KEY, Firebase 자격증명(adminsdk json 또는 FIREBASE_CREDENTIALS).

실행:
  python -m jobs.marketing_generate                          # 오늘 화제종목 자동 × 기본 3포맷
  python -m jobs.marketing_generate --tickers 005930,000660  # 특정 종목
  python -m jobs.marketing_generate --formats curiosity,cta  # 특정 포맷
  python -m jobs.marketing_generate --hot 5                   # 자동 선정 개수
  python -m jobs.marketing_generate --dry-run                # 생성·출력만, 저장 X
"""

from __future__ import annotations

import argparse
import asyncio
from typing import Optional

from loguru import logger


def _prime_name_store() -> int:
    """load_stocks(Firestore) → screener _data_store 적재.

    build_instant_snapshot이 읽는 _get_combined_df를 채워, 잡에서도 실제 수치가
    들어간 글이 나오게 한다. (cache_warm.prime_name_store와 동일 패턴)
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
            logger.warning("[marketing] load_stocks 비어 있음 — 수치 없이 진행")
            return 0
        snapshot = pd.concat(frames, ignore_index=True)
        set_data(snapshot, etf_df=etf if (etf is not None and not etf.empty) else None)
        n = len(snapshot)
        logger.info(f"[marketing] 종목 store 적재: {n}종목 (실수치 활성)")
        return n
    except Exception as e:
        logger.warning(f"[marketing] store 적재 실패(graceful): {type(e).__name__}: {e}")
        return 0


def _save_drafts(posts: list[dict]) -> int:
    """생성된 초안을 Firestore marketing_drafts에 status=draft로 저장. 저장 수 반환."""
    try:
        from firebase_admin import firestore

        from screener.db.firebase_client import get_db

        db = get_db()
        now = firestore.SERVER_TIMESTAMP
        saved = 0
        for p in posts:
            try:
                # status가 이미 지정돼 있으면 존중(자동발행 경로의 published 등), 없으면 draft
                status = p.get("status") or "draft"
                doc = {**p, "status": status, "created_at": now, "updated_at": now}
                if status == "published" and "published_at" not in doc:
                    doc["published_at"] = now
                db.collection("marketing_drafts").document().set(doc)
                saved += 1
            except Exception as e:
                logger.warning(f"[marketing] 저장 실패 {p.get('ticker')}: {e}")
        return saved
    except Exception as e:
        logger.error(f"[marketing] Firestore 저장 불가: {e}")
        return 0


async def run_generate(
    tickers: Optional[list[str]] = None,
    formats: Optional[list[str]] = None,
    hot: int = 3,
    dry_run: bool = False,
) -> dict:
    """일괄 생성 메인."""
    from agents.marketer import (
        DEFAULT_FORMATS,
        FORMATS,
        generate_batch,
        pick_hot_tickers,
        recent_marketing_memory,
    )

    _prime_name_store()

    # 연속성 메모리(point 3): 최근 다룬 종목·과다 사용 앵글 유형을 회피.
    memory = recent_marketing_memory()

    fmts = [f for f in (formats or []) if f in FORMATS] or list(DEFAULT_FORMATS)
    tks = [t.strip().upper() for t in (tickers or []) if t.strip()]
    if not tks:
        tks = pick_hot_tickers(limit=max(1, min(hot, 10)), exclude=memory["tickers"])
    if not tks:
        logger.error("생성할 종목이 없습니다(스냅샷 미적재). --tickers로 직접 지정하세요.")
        return {"created": 0}

    tks = tks[:10]
    logger.info(f"마케팅 글 생성 — 종목 {tks} × 포맷 {fmts} (dry_run={dry_run}, 회피유형={memory['archetypes']})")
    posts = await generate_batch(tks, fmts, avoid_archetypes=memory["archetypes"])

    # 콘솔 출력 (.bat에서 chcp 65001 + PYTHONUTF8=1로 이모지 안전)
    for p in posts:
        print("\n" + "=" * 64)
        flagged = f" ⚠필터:{p['filtered']}" if p.get("filtered") else ""
        print(f"[{p['fmt_label']}] {p['name']} ({p['ticker']}) · {p['char_count']}자{flagged}")
        print("-" * 64)
        print(p["text"])

    saved = 0
    if not dry_run and posts:
        saved = _save_drafts(posts)

    print("\n" + "=" * 64)
    print(f"✅ 생성 {len(posts)}건" + (f" · 저장 {saved}건 (웹 /admin/marketing 검수탭 확인)" if not dry_run else " · 저장 안 함(dry-run)"))
    print("=" * 64)
    return {"created": len(posts), "saved": saved}


def main(argv: list[str] | None = None) -> int:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:
        pass

    parser = argparse.ArgumentParser(description="마케팅(스레드) 글 일괄 생성")
    parser.add_argument("--tickers", type=str, default="", help="쉼표 구분 티커. 비우면 자동")
    parser.add_argument("--formats", type=str, default="", help="쉼표 구분 포맷(curiosity,contrarian,trust,cta)")
    parser.add_argument("--hot", type=int, default=3, help="자동 선정 종목 수")
    parser.add_argument("--dry-run", action="store_true", help="생성·출력만, 저장 X")
    args = parser.parse_args(argv)

    tickers = [t for t in args.tickers.replace(" ", ",").split(",") if t.strip()]
    formats = [f for f in args.formats.replace(" ", ",").split(",") if f.strip()]

    asyncio.run(run_generate(tickers=tickers, formats=formats, hot=args.hot, dry_run=args.dry_run))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
