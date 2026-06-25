"""마케팅 콘텐츠 공장 API (Phase 1) — 관리자 전용.

스레드(Threads)용 종목 글을 Haiku로 생성 → Firestore에 초안 적재 →
관리자 콘솔에서 검수·수정·복사. (Phase 2에서 Threads API 자동 발행 예정)

접근 제어: admin_routes._is_admin 재사용(ADMIN_EMAILS 또는 X-Admin-Key).
저장소: Firestore `marketing_drafts/{id}`.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Request
from loguru import logger
from starlette.responses import JSONResponse

from agents.marketer import DEFAULT_FORMATS, FORMATS, THREADS_MAX, generate_batch, pick_hot_tickers
from screener.api.admin_routes import _forbid, _is_admin

router = APIRouter(prefix="/api/admin/marketing")

_COLLECTION = "marketing_drafts"
_VALID_STATUS = ("draft", "approved", "archived")


def _iso(v):
    if not v:
        return None
    if hasattr(v, "isoformat"):
        return v.isoformat()
    if hasattr(v, "timestamp"):
        return datetime.fromtimestamp(v.timestamp(), tz=timezone.utc).isoformat()
    return str(v)


def _serialize(doc_id: str, d: dict) -> dict:
    return {
        "id": doc_id,
        "ticker": d.get("ticker", ""),
        "name": d.get("name", ""),
        "market": d.get("market", ""),
        "is_kr": bool(d.get("is_kr")),
        "fmt": d.get("fmt", ""),
        "fmt_label": d.get("fmt_label", ""),
        "text": d.get("text", ""),
        "char_count": int(d.get("char_count", len(d.get("text", "")) or 0)),
        "status": d.get("status", "draft"),
        "filtered": d.get("filtered", []) or [],
        "source": d.get("source", "haiku"),
        "created_at": _iso(d.get("created_at")),
        "updated_at": _iso(d.get("updated_at")),
    }


@router.get("/formats")
async def list_formats(request: Request):
    """사용 가능한 글 포맷 목록(프론트 체크박스용)."""
    if not _is_admin(request):
        return _forbid()
    return {
        "formats": [{"key": k, "label": v["label"]} for k, v in FORMATS.items()],
        "default": list(DEFAULT_FORMATS),
        "max_chars": THREADS_MAX,
    }


@router.get("/drafts")
async def list_drafts(request: Request, status: str = "", limit: int = 100):
    """초안 목록. status 필터(draft|approved|archived), 최신순."""
    if not _is_admin(request):
        return _forbid()

    from firebase_admin import firestore

    from screener.db.firebase_client import get_db

    db = get_db()
    drafts = []
    try:
        q = db.collection(_COLLECTION).order_by(
            "created_at", direction=firestore.Query.DESCENDING
        ).limit(max(1, min(limit, 300)))
        for d in q.stream():
            dd = d.to_dict() or {}
            if status and dd.get("status", "draft") != status:
                continue
            drafts.append(_serialize(d.id, dd))
    except Exception as e:
        logger.warning(f"[marketing] 초안 목록 조회 실패: {e}")
    return {"drafts": drafts, "count": len(drafts)}


@router.post("/generate")
async def generate_drafts(request: Request):
    """초안 생성. body: {tickers?: str[], formats?: str[], hot_count?: int}.

    tickers 비우면 스크리너 스냅샷에서 '오늘 화제 종목'을 hot_count개 자동 선정.
    각 (종목 × 포맷) 조합마다 Haiku 1회 생성 후 Firestore에 status=draft로 저장.
    """
    if not _is_admin(request):
        return _forbid()

    try:
        body = await request.json()
    except Exception:
        body = {}

    user = getattr(request.state, "user", None) or {}
    uid = user.get("uid", "") if isinstance(user, dict) else ""

    tickers = [str(t).strip().upper() for t in (body.get("tickers") or []) if str(t).strip()]
    formats = [f for f in (body.get("formats") or []) if f in FORMATS]
    if not formats:
        formats = list(DEFAULT_FORMATS)
    if not tickers:
        hot_count = int(body.get("hot_count", 3) or 3)
        tickers = pick_hot_tickers(limit=max(1, min(hot_count, 10)))
    if not tickers:
        return JSONResponse(
            status_code=400,
            content={"detail": "생성할 종목이 없습니다(스냅샷 미적재). 종목을 직접 입력하세요."},
        )

    # 과부하 방지: 조합 수 상한
    tickers = tickers[:10]
    formats = formats[:len(FORMATS)]
    if len(tickers) * len(formats) > 30:
        tickers = tickers[: max(1, 30 // max(1, len(formats)))]

    posts = await generate_batch(tickers, formats, uid=uid)
    if not posts:
        return JSONResponse(status_code=502, content={"detail": "생성 실패(AI 응답 없음)"})

    from firebase_admin import firestore

    from screener.db.firebase_client import get_db

    db = get_db()
    now = firestore.SERVER_TIMESTAMP
    created = []
    for p in posts:
        try:
            ref = db.collection(_COLLECTION).document()
            ref.set({**p, "status": "draft", "created_at": now, "updated_at": now})
            doc = ref.get()
            created.append(_serialize(ref.id, doc.to_dict() or p))
        except Exception as e:
            logger.warning(f"[marketing] 초안 저장 실패 {p.get('ticker')}: {e}")

    logger.info(
        f"[marketing] 초안 {len(created)}건 생성 by {user.get('email', '?')} "
        f"(종목 {tickers}, 포맷 {formats})"
    )
    return {"created": created, "count": len(created)}


@router.patch("/drafts/{draft_id}")
async def update_draft(request: Request, draft_id: str):
    """초안 수정. body: {text?: str, status?: str}."""
    if not _is_admin(request):
        return _forbid()

    try:
        body = await request.json()
    except Exception:
        body = {}

    from firebase_admin import firestore

    from screener.db.firebase_client import get_db

    db = get_db()
    ref = db.collection(_COLLECTION).document(draft_id)
    snap = ref.get()
    if not snap.exists:
        return JSONResponse(status_code=404, content={"detail": "초안 없음"})

    patch: dict = {"updated_at": firestore.SERVER_TIMESTAMP}
    if "text" in body:
        text = str(body.get("text") or "")
        patch["text"] = text
        patch["char_count"] = len(text)
    if "status" in body:
        st = str(body.get("status") or "")
        if st not in _VALID_STATUS:
            return JSONResponse(status_code=400, content={"detail": f"status는 {_VALID_STATUS}"})
        patch["status"] = st

    try:
        ref.set(patch, merge=True)
        doc = ref.get()
    except Exception as e:
        logger.warning(f"[marketing] 초안 수정 실패 {draft_id}: {e}")
        return JSONResponse(status_code=500, content={"detail": "수정 실패"})
    return {"ok": True, "draft": _serialize(draft_id, doc.to_dict() or {})}


@router.delete("/drafts/{draft_id}")
async def delete_draft(request: Request, draft_id: str):
    """초안 삭제."""
    if not _is_admin(request):
        return _forbid()
    from screener.db.firebase_client import get_db

    try:
        get_db().collection(_COLLECTION).document(draft_id).delete()
    except Exception as e:
        logger.warning(f"[marketing] 초안 삭제 실패 {draft_id}: {e}")
        return JSONResponse(status_code=500, content={"detail": "삭제 실패"})
    return {"ok": True}
