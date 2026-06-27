"""매일 스레드 콘텐츠 자동 생성 잡 (jobs.daily_threads_content).

마케팅 콘텐츠 공장의 일일 엔진. 매일 아침 1회 실행하여:
  1) 🌙 새벽 미국시장 브리핑 1편 (FDR 지수 + RSS → Haiku)
  2) 📊 오늘 화제 종목 '양쪽 관점' N편 (marketer contrarian 포맷)
를 생성해 Firestore `marketing_drafts`에 status=draft로 적재한다(검수 큐).

기본은 **검수 큐**(생성만, 발행 X) — 관리자가 /admin/marketing에서 보고 발행.
`--publish` 플래그를 주면 생성 직후 Threads 자동 발행까지 수행(THREADS_* 필요).

필요 env: ANTHROPIC_API_KEY, Firebase 자격증명. (자동발행 시 THREADS_ACCESS_TOKEN/USER_ID)

실행:
  python -m jobs.daily_threads_content                 # 브리핑 + 종목2, 저장만(검수큐)
  python -m jobs.daily_threads_content --stocks 3      # 종목 글 개수
  python -m jobs.daily_threads_content --no-briefing   # 브리핑 생략
  python -m jobs.daily_threads_content --publish       # 생성 후 즉시 자동발행
  python -m jobs.daily_threads_content --dry-run       # 생성·출력만, 저장 X
"""

from __future__ import annotations

import argparse
import asyncio
from typing import Optional

from loguru import logger


async def _publish_posts(posts: list[dict]) -> int:
    """생성된 글을 Threads에 순차 발행. 발행 성공 수 반환. (검수 없이 자동발행 모드)"""
    from utils import threads_client

    if not threads_client.is_enabled():
        logger.warning("[daily] --publish 지정됐으나 Threads 미설정 — 발행 건너뜀")
        return 0

    published = 0
    for p in posts:
        text = (p.get("text") or "").strip()
        if not text or len(text) > 500:
            logger.warning(f"[daily] 발행 스킵(본문 길이 {len(text)}): {p.get('name')}")
            continue
        try:
            res = await threads_client.publish_text(text)
            p["status"] = "published"
            p["permalink"] = res.get("permalink", "")
            p["threads_post_id"] = res.get("id", "")
            published += 1
            logger.info(f"[daily] 발행: {p.get('name')} {res.get('permalink', '')}")
            await asyncio.sleep(3)  # 레이트리밋 여유
        except Exception as e:
            logger.warning(f"[daily] 발행 실패 {p.get('name')}: {e}")
    return published


async def run_daily(
    stocks: int = 1,
    briefing: bool = True,
    publish: bool = False,
    dry_run: bool = False,
) -> dict:
    """일일 콘텐츠 생성 메인."""
    from agents.briefing import generate_briefing
    from agents.marketer import generate_batch, pick_hot_tickers
    from jobs.marketing_generate import _prime_name_store, _save_drafts

    # 종목 글은 실수치가 필요 → store 적재 (브리핑은 FDR이라 불필요)
    _prime_name_store()

    posts: list[dict] = []

    # 1) 새벽 미국시장 브리핑
    if briefing:
        b = await generate_briefing()
        if b:
            posts.append(b)
            logger.info(f"[daily] 브리핑 생성: {b['char_count']}자, 필터 {b['filtered']}")
        else:
            logger.warning("[daily] 브리핑 생성 실패(지수/AI)")

    # 2) 화제 종목 '양쪽 관점'(contrarian)
    if stocks > 0:
        tickers = pick_hot_tickers(limit=max(1, min(stocks, 5)))
        if tickers:
            stock_posts = await generate_batch(tickers, ["contrarian"])
            posts.extend(stock_posts)
            logger.info(f"[daily] 종목 글 {len(stock_posts)}편 생성: {tickers}")
        else:
            logger.warning("[daily] 화제 종목 선정 실패(스냅샷 미적재)")

    if not posts:
        logger.error("[daily] 생성된 글이 없습니다")
        return {"created": 0, "published": 0, "saved": 0}

    # 콘솔 출력
    for p in posts:
        print("\n" + "=" * 64)
        flagged = f" ⚠필터:{p['filtered']}" if p.get("filtered") else ""
        print(f"[{p.get('fmt_label', '?')}] {p.get('name', '')} · {p.get('char_count', 0)}자{flagged}")
        print("-" * 64)
        print(p.get("text", ""))

    published = 0
    if publish and not dry_run:
        published = await _publish_posts(posts)

    saved = 0
    if not dry_run:
        # 발행된 글은 status=published로 저장되도록 _save_drafts가 p의 status를 존중하게
        saved = _save_drafts(posts)

    print("\n" + "=" * 64)
    summary = f"✅ 생성 {len(posts)}편"
    if publish:
        summary += f" · 발행 {published}편"
    summary += f" · 저장 {saved}편" if not dry_run else " · 저장 안 함(dry-run)"
    print(summary)
    print("=" * 64)
    return {"created": len(posts), "published": published, "saved": saved}


def main(argv: Optional[list[str]] = None) -> int:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:
        pass

    parser = argparse.ArgumentParser(description="매일 스레드 콘텐츠 자동 생성")
    parser.add_argument("--stocks", type=int, default=1, help="양쪽관점 종목 글 개수(0=생략)")
    parser.add_argument("--no-briefing", action="store_true", help="새벽 미국장 브리핑 생략")
    parser.add_argument("--publish", action="store_true", help="생성 후 Threads 즉시 자동발행")
    parser.add_argument("--dry-run", action="store_true", help="생성·출력만, 저장/발행 X")
    args = parser.parse_args(argv)

    asyncio.run(
        run_daily(
            stocks=args.stocks,
            briefing=not args.no_briefing,
            publish=args.publish,
            dry_run=args.dry_run,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
