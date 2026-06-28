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


# ──────────────────────────────────────────────
# 새벽 미국시장 뉴스 — 등락 '이유' 보강 (Google News RSS 검색)
# ──────────────────────────────────────────────

# Google News RSS 검색은 공개 피드. 한국어 '뉴욕증시' 기사는 간밤 등락의
# 원인(테크/반도체/금리/실적/관세 등)을 함께 담아, 브리핑에 '왜'를 채운다.
_GNEWS_RSS = "https://news.google.com/rss/search"
_US_QUERIES: tuple[str, ...] = ("뉴욕증시", "나스닥 반도체")

_US_CACHE: dict[str, object] = {"at": 0.0, "items": []}


def fetch_overnight_us_news(limit: int = 8, timeout: float = 5.0) -> list[dict]:
    """간밤 미국증시 한국어 헤드라인(등락 이유 포함). 실패 시 빈 리스트.

    Google News RSS 검색('뉴욕증시' 등)으로 최신 기사를 모은다. 헤드라인만 사용하며,
    브리핑 에이전트가 '근거 있을 때만' 원인을 1줄 덧붙이는 데 쓴다(추측 금지).
    """
    now = time.time()
    cached = _US_CACHE.get("items") or []
    if cached and (now - float(_US_CACHE.get("at", 0.0))) < _TTL_SEC:
        return list(cached)[:limit]

    items: list[dict] = []
    seen: set[str] = set()
    headers = {"User-Agent": "AxisResearch/1.0 (+https://axislytics.com)"}
    for q in _US_QUERIES:
        try:
            r = httpx.get(
                _GNEWS_RSS,
                params={"q": q, "hl": "ko", "gl": "KR", "ceid": "KR:ko"},
                timeout=timeout,
                headers=headers,
                follow_redirects=True,
            )
            if r.status_code != 200 or not r.content:
                continue
            root = ElementTree.fromstring(r.content)
            count = 0
            for item in root.iter("item"):
                title = (item.findtext("title") or "").strip()
                if not title or title in seen:
                    continue
                seen.add(title)
                # "제목 - 출처" 형태에서 출처 분리(있으면)
                src = "구글뉴스"
                if " - " in title:
                    head, _, tail = title.rpartition(" - ")
                    if head and tail:
                        title, src = head.strip(), tail.strip()
                items.append(
                    {
                        "headline": title,
                        "source": src,
                        "published_at": (item.findtext("pubDate") or "").strip(),
                        "link": (item.findtext("link") or "").strip(),
                    }
                )
                count += 1
                if count >= 6:  # 쿼리별 최대 6
                    break
        except Exception as e:
            logger.debug(f"[news_rss] US '{q}' 실패: {type(e).__name__}: {str(e)[:80]}")

    if items:
        _US_CACHE["at"] = now
        _US_CACHE["items"] = items
    return items[:limit]


# ──────────────────────────────────────────────
# 주말 브리핑 뉴스 — 주말 주요 소식 + 다음주 전망 (Google News RSS 검색)
# ──────────────────────────────────────────────

# 주말엔 시장이 닫혀 '데이터'가 아니라 '뉴스'가 핵심. 주말 새 글로벌 이슈 +
# 다가오는 주(週) 증시 전망 헤드라인을 모아, 주말 브리핑의 '무슨일/다음주 일정'을 채운다.
_WEEKEND_QUERIES: tuple[str, ...] = (
    "주말 증시",
    "이번주 증시 전망",
    "코스피 전망",
    "글로벌 경제",
)

_WEEKEND_CACHE: dict[str, object] = {"at": 0.0, "items": []}


def fetch_weekend_news(limit: int = 10, timeout: float = 5.0) -> list[dict]:
    """주말 주요 소식 + 다음주 증시 전망 한국어 헤드라인. 실패 시 빈 리스트.

    Google News RSS 검색('주말 증시', '이번주 증시 전망' 등)으로 모은다. 헤드라인만
    사용하며, 주말 브리핑 에이전트가 '근거 있을 때만' 원인·일정을 인용한다(추측 금지).
    """
    now = time.time()
    cached = _WEEKEND_CACHE.get("items") or []
    if cached and (now - float(_WEEKEND_CACHE.get("at", 0.0))) < _TTL_SEC:
        return list(cached)[:limit]

    items: list[dict] = []
    seen: set[str] = set()
    headers = {"User-Agent": "AxisResearch/1.0 (+https://axislytics.com)"}
    for q in _WEEKEND_QUERIES:
        try:
            r = httpx.get(
                _GNEWS_RSS,
                params={"q": q, "hl": "ko", "gl": "KR", "ceid": "KR:ko"},
                timeout=timeout,
                headers=headers,
                follow_redirects=True,
            )
            if r.status_code != 200 or not r.content:
                continue
            root = ElementTree.fromstring(r.content)
            count = 0
            for item in root.iter("item"):
                title = (item.findtext("title") or "").strip()
                if not title or title in seen:
                    continue
                seen.add(title)
                src = "구글뉴스"
                if " - " in title:
                    head, _, tail = title.rpartition(" - ")
                    if head and tail:
                        title, src = head.strip(), tail.strip()
                items.append(
                    {
                        "headline": title,
                        "source": src,
                        "published_at": (item.findtext("pubDate") or "").strip(),
                        "link": (item.findtext("link") or "").strip(),
                    }
                )
                count += 1
                if count >= 5:  # 쿼리별 최대 5
                    break
        except Exception as e:
            logger.debug(f"[news_rss] 주말 '{q}' 실패: {type(e).__name__}: {str(e)[:80]}")

    if items:
        _WEEKEND_CACHE["at"] = now
        _WEEKEND_CACHE["items"] = items
    return items[:limit]
