"""주말 결산 브리핑 자동 생성 잡 (jobs.weekend_briefing).

일요일 밤(22~23시 KST) 1회 실행. 주말 주요 소식 + 지난 금요일 미국장 마감을 정리한
'주말 결산 브리핑' 1편을 생성해 Firestore `marketing_drafts`에 status=draft로 적재한다
(검수 큐). 다음 거래일(월요일) 한국장 준비용 — 새벽 미국시장 브리핑의 자매 콘텐츠.

기본은 **검수 큐**(생성만, 발행 X) — 관리자가 /admin/marketing에서 보고 발행.
`--publish` 플래그를 주면 생성 직후 Threads 자동 발행까지 수행(THREADS_* 필요).

필요 env: ANTHROPIC_API_KEY, Firebase 자격증명. (자동발행 시 THREADS_ACCESS_TOKEN/USER_ID)

실행:
  python -m jobs.weekend_briefing             # 생성 → 검수 큐 저장
  python -m jobs.weekend_briefing --publish   # 생성 후 즉시 자동발행
  python -m jobs.weekend_briefing --dry-run   # 생성·출력만, 저장 X
"""

from __future__ import annotations

import argparse
import asyncio
from typing import Optional

from loguru import logger


async def run_weekend(publish: bool = False, dry_run: bool = False) -> dict:
    """주말 브리핑 생성 메인."""
    from agents.weekend_briefing import generate_weekend_briefing
    from jobs.marketing_generate import _save_drafts

    post = await generate_weekend_briefing()
    if not post:
        logger.error("[weekend] 생성된 브리핑이 없습니다(지수·뉴스 결손/AI 실패)")
        return {"created": 0, "published": 0, "saved": 0}

    # 콘솔 출력
    print("\n" + "=" * 64)
    flagged = f" ⚠필터:{post['filtered']}" if post.get("filtered") else ""
    print(f"[{post.get('fmt_label', '?')}] · {post.get('char_count', 0)}자{flagged}")
    print("-" * 64)
    print(post.get("text", ""))

    published = 0
    if publish and not dry_run:
        from utils import threads_client

        if not threads_client.is_enabled():
            logger.warning("[weekend] --publish 지정됐으나 Threads 미설정 — 발행 건너뜀")
        else:
            text = (post.get("text") or "").strip()
            if text and len(text) <= 500:
                try:
                    res = await threads_client.publish_text(text)
                    post["status"] = "published"
                    post["permalink"] = res.get("permalink", "")
                    post["threads_post_id"] = res.get("id", "")
                    published = 1
                    logger.info(f"[weekend] 발행: {res.get('permalink', '')}")
                except Exception as e:
                    logger.warning(f"[weekend] 발행 실패: {e}")
            else:
                logger.warning(f"[weekend] 발행 스킵(본문 길이 {len(text)})")

    saved = 0
    if not dry_run:
        saved = _save_drafts([post])  # status(published/draft) 존중

    print("\n" + "=" * 64)
    summary = "✅ 생성 1편"
    if publish:
        summary += f" · 발행 {published}편"
    summary += f" · 저장 {saved}편" if not dry_run else " · 저장 안 함(dry-run)"
    print(summary)
    print("=" * 64)
    return {"created": 1, "published": published, "saved": saved}


def main(argv: Optional[list[str]] = None) -> int:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:
        pass

    parser = argparse.ArgumentParser(description="주말 결산 브리핑 자동 생성")
    parser.add_argument("--publish", action="store_true", help="생성 후 Threads 즉시 자동발행")
    parser.add_argument("--dry-run", action="store_true", help="생성·출력만, 저장/발행 X")
    args = parser.parse_args(argv)

    asyncio.run(run_weekend(publish=args.publish, dry_run=args.dry_run))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
