"""Axis Screener 라우트 — v7.5 CATEGORIES를 Smart Lists로 노출.

기존 /api/scan, /api/categories는 v7.5에 그대로 두고, Axis는 별도
/api/screener/smart-lists 엔드포인트로 카테고리 메타 정보만 노출합니다.
실제 스크리닝은 v7.5 /api/scan을 호출하면 됩니다.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/screener", tags=["axis-screener"])


@router.get("/smart-lists")
async def smart_lists(request: Request) -> dict:
    """v7.5 CATEGORIES를 그룹별로 정리해 반환.

    각 항목: id, name, group, desc, icon, requires_phase, columns
    실제 종목 조회는 클라이언트가 v7.5 /api/scan?category={id} 를 호출.
    """
    from screener.core.screener import CATEGORIES

    user = getattr(request.state, "user", None) or {}
    user_tier = (user.get("tier") or "free").lower()

    # Free tier가 접근 가능한 카테고리 (v7.5 middleware 기준 동일)
    FREE_CATEGORIES = {"surge", "bluechip", "recommend", "watchlist", "etf", "foreign_inst"}

    items: list[dict] = []
    for cat_id, meta in CATEGORIES.items():
        items.append(
            {
                "id": cat_id,
                "name": meta.get("name", cat_id),
                "group": meta.get("group", "etc"),
                "desc": meta.get("desc", ""),
                "icon": meta.get("icon", "list"),
                "columns": meta.get("columns", []),
                "requires_phase": meta.get("requires_phase", 0),
                "available_to_free": cat_id in FREE_CATEGORIES,
            }
        )

    # 그룹별로 정렬 (strategy → 기타)
    group_order = {"strategy": 0, "fundamental": 1, "supply": 2, "technical": 3}
    items.sort(key=lambda x: (group_order.get(x["group"], 99), x["name"]))

    return {
        "categories": items,
        "user_plan": user_tier,
        "scan_endpoint": "/api/scan",  # 클라이언트가 사용할 v7.5 엔드포인트
    }
