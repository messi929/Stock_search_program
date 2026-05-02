"""매크로 이벤트 메타 + 수동 IPO 캘린더 로더.

WEEK_C.md Day 3 산출물.

JSON 정적 파일을 한 번 로드 후 캐시 (모듈 단위).
스키마 무결성 최소 검증 + 사용자 친화 조회 헬퍼.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger


_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
_MACRO_META_FILE = _DATA_DIR / "macro_event_metadata.json"
_IPO_FILE = _DATA_DIR / "upcoming_ipo.json"


_macro_meta_cache: dict[str, Any] | None = None
_ipo_cache: dict[str, Any] | None = None


# ──────────────────────────────────────────────
# 매크로 이벤트 메타
# ──────────────────────────────────────────────


def load_macro_event_metadata(force_refresh: bool = False) -> dict[str, Any]:
    """data/macro_event_metadata.json 로드 + 캐시.

    Returns:
        {"_meta": {...}, "events": {"FOMC": {...}, ...}, "fabrication_warning": "..."}
    """
    global _macro_meta_cache
    if _macro_meta_cache is not None and not force_refresh:
        return _macro_meta_cache

    if not _MACRO_META_FILE.exists():
        logger.warning(f"macro_event_metadata.json 미존재: {_MACRO_META_FILE}")
        _macro_meta_cache = {"events": {}}
        return _macro_meta_cache

    try:
        with open(_MACRO_META_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"macro_event_metadata.json 파싱 실패: {e}")
        _macro_meta_cache = {"events": {}}
        return _macro_meta_cache

    if "events" not in data or not isinstance(data["events"], dict):
        logger.error("macro_event_metadata.json: 'events' 키 누락 또는 dict 아님")
        _macro_meta_cache = {"events": {}}
        return _macro_meta_cache

    _macro_meta_cache = data
    return data


def get_event_meta(event_type: str) -> dict[str, Any]:
    """이벤트 타입별 통계 메타 조회.

    Args:
        event_type: macro_calendar.json의 type 필드 값 (예: "FOMC", "US_CPI").

    Returns:
        메타 dict — 미등록 시 빈 dict.
    """
    data = load_macro_event_metadata()
    events = data.get("events", {})
    return dict(events.get(event_type, {}))


# ──────────────────────────────────────────────
# IPO 큐레이션
# ──────────────────────────────────────────────


def load_upcoming_ipos(force_refresh: bool = False) -> dict[str, Any]:
    global _ipo_cache
    if _ipo_cache is not None and not force_refresh:
        return _ipo_cache

    if not _IPO_FILE.exists():
        logger.warning(f"upcoming_ipo.json 미존재: {_IPO_FILE}")
        _ipo_cache = {"items": []}
        return _ipo_cache

    try:
        with open(_IPO_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"upcoming_ipo.json 파싱 실패: {e}")
        _ipo_cache = {"items": []}
        return _ipo_cache

    if "items" not in data or not isinstance(data["items"], list):
        logger.error("upcoming_ipo.json: 'items' 키 누락 또는 list 아님")
        _ipo_cache = {"items": []}
        return _ipo_cache

    _ipo_cache = data
    return data


def find_ipos_for_secondary(ticker: str) -> list[dict[str, Any]]:
    """주어진 티커가 2차 수혜로 매핑된 IPO 목록 반환.

    Args:
        ticker: 종목 티커 (대소문자 구분 — 한국 6자리 코드는 그대로, 미국은 upper)

    Returns:
        해당 IPO 항목 리스트.
    """
    data = load_upcoming_ipos()
    items = data.get("items", [])
    out: list[dict[str, Any]] = []
    for item in items:
        beneficiaries = item.get("secondary_beneficiaries") or []
        if ticker in beneficiaries or ticker.upper() in [b.upper() for b in beneficiaries]:
            out.append(item)
    return out


def get_high_certainty_ipos(min_score: int = 7) -> list[dict[str, Any]]:
    """certainty_score 임계 이상 IPO만 반환."""
    data = load_upcoming_ipos()
    items = data.get("items", [])
    return [it for it in items if int(it.get("certainty_score", 0)) >= min_score]


# ──────────────────────────────────────────────
# 캐시 클리어 (테스트용)
# ──────────────────────────────────────────────


def clear_cache() -> None:
    global _macro_meta_cache, _ipo_cache
    _macro_meta_cache = None
    _ipo_cache = None
