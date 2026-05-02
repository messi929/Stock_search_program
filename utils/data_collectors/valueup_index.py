"""KRX 코리아 밸류업 지수 종목 수집/조회 모듈.

WEEK_A.md Day 5 산출물.

데이터 소스:
  - 1차: KRX 공식 발표 (data/valueup_index.json 정적 — 분기 갱신 수동)
  - 2차 (fallback): KODEX 코리아밸류업 ETF (379800) 보유 종목

분기 리밸런싱: 3/6/9/12월 마지막 거래일.
ETF fallback은 운용사 사이트의 일별 PDF 다운로드가 필요하므로 본 모듈에서는 schema/엔트리포인트만 제공.

Korean Specialist 페르소나가 활용하는 함수:
  - is_in_valueup_index(ticker) → bool + 메타
  - get_valueup_constituents(rebalancing_date) → 100종목 list
  - get_added/removed_companies() → 리밸런싱 변동
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger


# data/valueup_index.json 위치
DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "valueup_index.json"


# ──────────────────────────────────────────────
# 데이터 로드 (1회 캐시)
# ──────────────────────────────────────────────


_cache: dict[str, Any] | None = None


def _load_data(force_refresh: bool = False) -> dict[str, Any]:
    """data/valueup_index.json 로드 + 메모리 캐시."""
    global _cache
    if _cache is not None and not force_refresh:
        return _cache

    if not DATA_FILE.exists():
        logger.warning(f"valueup_index.json 미존재: {DATA_FILE}")
        _cache = {"_meta": {}, "rebalancing_history": []}
        return _cache

    try:
        with open(DATA_FILE, encoding="utf-8") as f:
            _cache = json.load(f)
    except Exception as e:
        logger.error(f"valueup_index.json 파싱 실패: {type(e).__name__}: {e}")
        _cache = {"_meta": {}, "rebalancing_history": []}

    return _cache


def reset_cache() -> None:
    """테스트용: 캐시 강제 초기화."""
    global _cache
    _cache = None


# ──────────────────────────────────────────────
# 조회 함수
# ──────────────────────────────────────────────


def get_latest_rebalancing() -> dict[str, Any] | None:
    """가장 최근 리밸런싱 정보."""
    data = _load_data()
    history = data.get("rebalancing_history") or []
    if not history:
        return None
    # rebalancing_date 가장 늦은 것
    return max(history, key=lambda r: r.get("rebalancing_date", ""))


def get_valueup_constituents(rebalancing_date: str | None = None) -> list[dict[str, Any]]:
    """특정 리밸런싱 시점의 구성 종목 list.

    Args:
        rebalancing_date: YYYY-MM-DD. None이면 가장 최근.

    Returns:
        [{"ticker", "name", "sector"}, ...] 또는 빈 list.
    """
    data = _load_data()
    history = data.get("rebalancing_history") or []
    if not history:
        return []

    if rebalancing_date is None:
        target = max(history, key=lambda r: r.get("rebalancing_date", ""))
    else:
        target = next(
            (r for r in history if r.get("rebalancing_date") == rebalancing_date),
            None,
        )
        if target is None:
            return []

    return target.get("constituents") or []


def is_in_valueup_index(ticker: str) -> dict[str, Any]:
    """종목의 밸류업 인덱스 편입 여부.

    Returns:
        {
            "ticker": "005930",
            "included": True,
            "name": "삼성전자",
            "sector": "반도체",
            "rebalancing_date": "2024-09-30",
            "data_completeness": "partial" | "full",
            "newly_added": False,
            "since": "2024-09-30",
        }
        편입 안 됨 또는 데이터 없음:
        {"ticker": "...", "included": False, ...}
    """
    ticker = str(ticker).zfill(6)
    data = _load_data()
    meta = data.get("_meta") or {}
    completeness = meta.get("data_completeness", "unknown")

    history = data.get("rebalancing_history") or []
    if not history:
        return {
            "ticker": ticker,
            "included": False,
            "data_completeness": completeness,
            "note": "valueup_index.json 데이터 없음",
        }

    latest = max(history, key=lambda r: r.get("rebalancing_date", ""))
    constituents = latest.get("constituents") or []

    matched = next((c for c in constituents if c.get("ticker") == ticker), None)
    if matched is None:
        # data_completeness가 partial이면 "편입 안 됨"이라고 단정 X
        if completeness != "full":
            return {
                "ticker": ticker,
                "included": False,
                "rebalancing_date": latest.get("rebalancing_date"),
                "data_completeness": completeness,
                "note": "현재 등록 데이터에 없음 — 전체 100종목 미커버 가능 (분기 갱신 필요)",
            }
        return {
            "ticker": ticker,
            "included": False,
            "rebalancing_date": latest.get("rebalancing_date"),
            "data_completeness": completeness,
        }

    # 편입 시점 추적
    first_seen = _find_first_inclusion(ticker, history)
    added_companies = latest.get("added_companies") or []
    newly_added = any(a.get("ticker") == ticker for a in added_companies)

    return {
        "ticker": ticker,
        "included": True,
        "name": matched.get("name"),
        "sector": matched.get("sector"),
        "rebalancing_date": latest.get("rebalancing_date"),
        "newly_added": newly_added,
        "since": first_seen,
        "data_completeness": completeness,
    }


def _find_first_inclusion(ticker: str, history: list[dict]) -> str | None:
    """ticker가 처음 등장한 rebalancing_date."""
    sorted_hist = sorted(history, key=lambda r: r.get("rebalancing_date", ""))
    for r in sorted_hist:
        for c in r.get("constituents") or []:
            if c.get("ticker") == ticker:
                return r.get("rebalancing_date")
    return None


def get_recent_changes() -> dict[str, list[dict[str, Any]]]:
    """가장 최근 리밸런싱의 added/removed 종목."""
    latest = get_latest_rebalancing()
    if latest is None:
        return {"added": [], "removed": []}
    return {
        "added": latest.get("added_companies") or [],
        "removed": latest.get("removed_companies") or [],
        "rebalancing_date": latest.get("rebalancing_date"),
    }


def get_metadata() -> dict[str, Any]:
    """schema_version/as_of/data_completeness 등 메타 정보."""
    return _load_data().get("_meta") or {}
