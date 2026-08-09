"""네이버 프리미엄콘텐츠 발행 워크스페이스 API — 관리자 전용.

2026-08-09 신설. 근거: `docs/axis/NAVER_PREMIUM.md`

## 🚨 "발행"이라는 말의 의미가 스레드와 다르다

**프리미엄콘텐츠에는 발행 API가 없다.** 스튜디오(studio.premium.naver.com) 웹 에디터에
사람이 직접 붙여넣는 수밖에 없다. 따라서 여기서 `publish`는 **발행 행위가 아니라 발행
사실의 기록**이다:

    초안 생성 → 검수·수정 → [전문 복사] → 스튜디오에 붙여넣기(사람) → 발행 URL 회수 →
    `POST /drafts/{id}/publish {url}` 로 기록

스레드처럼 버튼 하나로 나가지 않는다. 이걸 헷갈리면 "발행했는데 왜 안 올라갔지"가 된다.

접근 제어: `admin_routes._is_admin` 재사용(ADMIN_EMAILS 또는 X-Admin-Key).
저장소: Firestore `premium_drafts/{id}`.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Request
from loguru import logger
from starlette.responses import JSONResponse

from agents.premium_style import (
    COLUMN_MAX_CHARS,
    COLUMN_MIN_CHARS,
    COLUMN_TARGET_CHARS,
    guard_column,
)
from screener.api.admin_routes import _forbid, _is_admin

router = APIRouter(prefix="/api/admin/premium")

_COLLECTION = "premium_drafts"
_VALID_STATUS = ("draft", "approved", "published", "archived")

# 생성 가능한 콘텐츠 종류. weekly부터 시작하고 education/deepdive는 뼈대만 잡아둔다
# (docs/axis/NAVER_PREMIUM.md §5 착수 순서 — A1 주간 리포트 → A3 교육 연재).
KINDS: dict[str, dict] = {
    "weekly": {
        "label": "주간 시그널 리포트",
        "desc": "업종·규모별·종목 기여·거래대금 귀속을 교차한 주간 컬럼",
        "ready": True,
    },
    "education": {
        "label": "교육 연재",
        "desc": "투자심리 함정 7 + 지표읽기 10 커리큘럼의 장문판",
        "ready": False,
    },
    "deepdive": {
        "label": "종목 딥다이브",
        "desc": "단일 종목 수급·밸류·섹터 상대 위치 심층",
        "ready": False,
    },
}

STUDIO_URL = "https://studio.premium.naver.com/home"


def _iso(v):
    if not v:
        return None
    if hasattr(v, "isoformat"):
        return v.isoformat()
    if hasattr(v, "timestamp"):
        return datetime.fromtimestamp(v.timestamp(), tz=timezone.utc).isoformat()
    return str(v)


def _serialize(doc_id: str, d: dict) -> dict:
    body = str(d.get("body") or "")
    return {
        "id": doc_id,
        "kind": d.get("kind", "weekly"),
        "title": d.get("title", ""),
        "body": body,
        "char_count": int(d.get("char_count", len(body)) or 0),
        "section_count": int(d.get("section_count", 0) or 0),
        "week_label": d.get("week_label", ""),
        "period_start": d.get("period_start", ""),
        "period_end": d.get("period_end", ""),
        "facts": d.get("facts", ""),       # 검수자가 수치를 대조하는 원본
        "warnings": d.get("warnings", []) or [],
        "filtered": d.get("filtered", []) or [],
        "status": d.get("status", "draft"),
        "published_url": d.get("published_url", ""),
        "published_at": _iso(d.get("published_at")),
        "source": d.get("source", ""),
        "created_at": _iso(d.get("created_at")),
        "updated_at": _iso(d.get("updated_at")),
    }


@router.get("/meta")
async def meta(request: Request):
    """프론트 초기화용 — 종류 목록, 분량 기준, 스튜디오 링크."""
    if not _is_admin(request):
        return _forbid()
    return {
        "kinds": [{"key": k, **v} for k, v in KINDS.items()],
        "min_chars": COLUMN_MIN_CHARS,
        "target_chars": COLUMN_TARGET_CHARS,
        "max_chars": COLUMN_MAX_CHARS,
        "studio_url": STUDIO_URL,
        # 발행 API가 없다는 사실을 프론트가 문구로 노출하도록 명시적으로 내려준다.
        "manual_publish": True,
    }


@router.get("/drafts")
async def list_drafts(request: Request, status: str = "", limit: int = 50):
    """초안 목록 — 최신순. 목록에서는 body를 잘라 보낸다(전문은 상세에서)."""
    if not _is_admin(request):
        return _forbid()

    from firebase_admin import firestore

    from screener.db.firebase_client import get_db

    out = []
    try:
        q = (
            get_db()
            .collection(_COLLECTION)
            .order_by("created_at", direction=firestore.Query.DESCENDING)
            .limit(max(1, min(limit, 200)))
        )
        for d in q.stream():
            dd = d.to_dict() or {}
            if status and dd.get("status", "draft") != status:
                continue
            item = _serialize(d.id, dd)
            item["body"] = item["body"][:400]  # 목록 미리보기
            item["facts"] = ""
            out.append(item)
    except Exception as e:
        logger.warning(f"[premium] 초안 목록 조회 실패: {e}")
    return {"drafts": out, "count": len(out)}


@router.get("/drafts/{draft_id}")
async def get_draft(request: Request, draft_id: str):
    """초안 전문 — 복사·검수용."""
    if not _is_admin(request):
        return _forbid()
    from screener.db.firebase_client import get_db

    try:
        snap = get_db().collection(_COLLECTION).document(draft_id).get()
    except Exception as e:
        logger.warning(f"[premium] 초안 조회 실패 {draft_id}: {e}")
        return JSONResponse(status_code=500, content={"detail": "조회 실패"})
    if not snap.exists:
        return JSONResponse(status_code=404, content={"detail": "초안 없음"})
    return {"draft": _serialize(draft_id, snap.to_dict() or {})}


@router.post("/generate")
async def generate(request: Request):
    """초안 생성. body: {kind?: "weekly", end?: "YYYY-MM-DD"}.

    데이터가 부족하면 생성하지 않고 422를 준다 — 헛글을 큐에 쌓지 않는다.
    """
    if not _is_admin(request):
        return _forbid()

    try:
        body = await request.json()
    except Exception:
        body = {}

    kind = str(body.get("kind") or "weekly")
    spec = KINDS.get(kind)
    if not spec:
        return JSONResponse(status_code=400, content={"detail": f"알 수 없는 종류: {kind}"})
    if not spec.get("ready"):
        return JSONResponse(
            status_code=400, content={"detail": f"{spec['label']}은 아직 미구현입니다"}
        )

    end = None
    if body.get("end"):
        try:
            end = datetime.fromisoformat(str(body["end"])).date()
        except ValueError:
            return JSONResponse(status_code=400, content={"detail": "end는 YYYY-MM-DD"})

    from agents.premium_weekly import generate_weekly_column

    try:
        doc = await generate_weekly_column(end=end)
    except Exception as e:
        logger.warning(f"[premium] 생성 실패: {e}")
        return JSONResponse(status_code=500, content={"detail": "생성 실패"})

    if not doc:
        return JSONResponse(
            status_code=422,
            content={"detail": "주간 데이터가 부족해 생성을 건너뛰었습니다(헛글 방지)."},
        )

    from firebase_admin import firestore

    from screener.db.firebase_client import get_db

    try:
        doc["created_at"] = firestore.SERVER_TIMESTAMP
        doc["updated_at"] = firestore.SERVER_TIMESTAMP
        ref = get_db().collection(_COLLECTION).document()
        ref.set(doc)
        saved = ref.get()
    except Exception as e:
        logger.warning(f"[premium] 초안 저장 실패: {e}")
        return JSONResponse(status_code=500, content={"detail": "저장 실패"})

    return {"ok": True, "draft": _serialize(ref.id, saved.to_dict() or {})}


@router.patch("/drafts/{draft_id}")
async def update_draft(request: Request, draft_id: str):
    """초안 수정. body: {title?, body?, status?}.

    body를 고치면 가드를 **다시 돌린다.** 사람이 손댄 뒤 길이가 무너지거나 반말이
    섞이는 걸 잡기 위해서다(검수 화면에서 바로 보인다).
    """
    if not _is_admin(request):
        return _forbid()

    try:
        payload = await request.json()
    except Exception:
        payload = {}

    from firebase_admin import firestore

    from screener.db.firebase_client import get_db

    db = get_db()
    ref = db.collection(_COLLECTION).document(draft_id)
    snap = ref.get()
    if not snap.exists:
        return JSONResponse(status_code=404, content={"detail": "초안 없음"})
    cur = snap.to_dict() or {}

    patch: dict = {"updated_at": firestore.SERVER_TIMESTAMP}
    if "title" in payload:
        patch["title"] = str(payload.get("title") or "").strip()
    if "body" in payload:
        text = str(payload.get("body") or "")
        patch["body"] = text
        patch["char_count"] = len(text)
        patch["warnings"] = guard_column(text, str(cur.get("facts") or ""))
    if "status" in payload:
        st = str(payload.get("status") or "")
        if st not in _VALID_STATUS:
            return JSONResponse(status_code=400, content={"detail": f"status는 {_VALID_STATUS}"})
        patch["status"] = st

    try:
        ref.set(patch, merge=True)
        doc = ref.get()
    except Exception as e:
        logger.warning(f"[premium] 초안 수정 실패 {draft_id}: {e}")
        return JSONResponse(status_code=500, content={"detail": "수정 실패"})
    return {"ok": True, "draft": _serialize(draft_id, doc.to_dict() or {})}


@router.post("/drafts/{draft_id}/publish")
async def mark_published(request: Request, draft_id: str):
    """**발행 사실 기록** — 실제 발행은 사람이 스튜디오에서 한다. body: {url}.

    URL을 요구하는 이유: 나중에 검색 유입을 계측하려면 발행물의 실제 주소가 있어야 한다.
    스레드는 API가 post_id를 돌려줬지만 여기선 사람이 물어다 줘야 한다.
    """
    if not _is_admin(request):
        return _forbid()

    try:
        payload = await request.json()
    except Exception:
        payload = {}

    url = str(payload.get("url") or "").strip()
    if not url.startswith("http"):
        return JSONResponse(
            status_code=400,
            content={"detail": "발행된 콘텐츠 URL이 필요합니다(스튜디오에서 복사)."},
        )

    from firebase_admin import firestore

    from screener.db.firebase_client import get_db

    ref = get_db().collection(_COLLECTION).document(draft_id)
    if not ref.get().exists:
        return JSONResponse(status_code=404, content={"detail": "초안 없음"})

    try:
        ref.set(
            {
                "status": "published",
                "published_url": url,
                "published_at": firestore.SERVER_TIMESTAMP,
                "updated_at": firestore.SERVER_TIMESTAMP,
            },
            merge=True,
        )
        doc = ref.get()
    except Exception as e:
        logger.warning(f"[premium] 발행 기록 실패 {draft_id}: {e}")
        return JSONResponse(status_code=500, content={"detail": "기록 실패"})
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
        logger.warning(f"[premium] 초안 삭제 실패 {draft_id}: {e}")
        return JSONResponse(status_code=500, content={"detail": "삭제 실패"})
    return {"ok": True}
