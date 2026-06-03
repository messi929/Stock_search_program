"""공식 RSS 경제 뉴스 수집 — Research 에이전트 시황 보강.

회색지대 크롤링 대신 공개 RSS 피드만 사용(합법·안정). 종목별 정밀도는 낮지만
시황/매크로 맥락 제공에 충분. 실패는 무시(빈 리스트 → research가 일반 지식 추론).
모듈 레벨 TTL 캐시(5분)로 분석마다 재호출 방지.
"""

from __future__ import annotations

import time
from xml.etree import ElementTree

import httpx
from loguru import logger

# (출처명, RSS URL) — 공개 경제 피드. 일부 실패해도 나머지로 graceful.
RSS_FEEDS: list[tuple[str, str]] = [
    ("연합뉴스", "https://www.yna.co.kr/rss/economy.xml"),
    ("한국경제", "https://www.hankyung.com/feed/economy"),
    ("매일경제", "https://www.mk.co.kr/rss/30100041/"),
]

_CACHE: dict[str, object] = {"at": 0.0, "items": []}
_TTL_SEC = 300.0


def fetch_market_news(limit: int = 8, timeout: float = 4.0) -> list[dict]:
    """공개 RSS에서 최근 경제 헤드라인 수집 (TTL 캐시). 실패 시 빈 리스트."""
    now = time.time()
    cached = _CACHE.get("items") or []
    if cached and (now - float(_CACHE.get("at", 0.0))) < _TTL_SEC:
        return list(cached)[:limit]

    items: list[dict] = []
    headers = {"User-Agent": "AxisResearch/1.0 (+https://axislytics.com)"}
    for source, url in RSS_FEEDS:
        try:
            r = httpx.get(url, timeout=timeout, headers=headers, follow_redirects=True)
            if r.status_code != 200 or not r.content:
                continue
            root = ElementTree.fromstring(r.content)
            for item in root.iter("item"):
                title = (item.findtext("title") or "").strip()
                if not title:
                    continue
                items.append(
                    {
                        "headline": title,
                        "source": source,
                        "published_at": (item.findtext("pubDate") or "").strip(),
                        "link": (item.findtext("link") or "").strip(),
                    }
                )
                if len([x for x in items if x["source"] == source]) >= 6:
                    break  # 출처별 최대 6
        except Exception as e:
            logger.debug(f"[news_rss] {source} 실패: {type(e).__name__}: {str(e)[:80]}")

    if items:
        _CACHE["at"] = now
        _CACHE["items"] = items
    return items[:limit]
