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

from agents.marketer import (
    DEFAULT_FORMATS,
    FORMATS,
    THREADS_MAX,
    generate_batch,
    pick_hot_tickers,
    recent_marketing_memory,
)
from screener.api.admin_routes import _forbid, _is_admin
from utils import threads_client

router = APIRouter(prefix="/api/admin/marketing")

_COLLECTION = "marketing_drafts"
# partial = 타래 중간에서 발행이 끊긴 상태. Threads는 글삭제 API가 없어 되돌릴 수 없으므로
# 복구는 '지우기'가 아니라 '이어서 발행'뿐이다(docs/axis/THREADS_FORMAT.md §7-3).
_VALID_STATUS = ("draft", "approved", "archived", "published", "partial")


def _parts_of(d: dict) -> list[str]:
    """초안 문서 → 발행할 파트 배열. parts가 없는 옛 초안은 text 1개짜리로 취급."""
    parts = [str(p) for p in (d.get("parts") or []) if str(p).strip()]
    if parts:
        return parts
    return threads_client.split_parts(str(d.get("text") or ""))


def _iso(v):
    if not v:
        return None
    if hasattr(v, "isoformat"):
        return v.isoformat()
    if hasattr(v, "timestamp"):
        return datetime.fromtimestamp(v.timestamp(), tz=timezone.utc).isoformat()
    return str(v)


def _serialize(doc_id: str, d: dict) -> dict:
    parts = _parts_of(d)
    return {
        "id": doc_id,
        "parts": parts,
        "part_count": len(parts),
        "published_upto": int(d.get("published_upto", 0) or 0),  # 이어서 발행 지점
        "published_ids": list(d.get("published_ids") or []),
        "kind": d.get("kind", "stock"),  # "stock"(종목글) | "briefing"(시황브리핑) | "index"(지수차트)
        "index_key": d.get("index_key", ""),
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
        "warnings": d.get("warnings", []) or [],   # 독자시점/길이 가드(하네스 v2)
        "score": int(d.get("score", 0) or 0),       # 편집 자가채점(0~30)
        "angle": d.get("angle", "") or "",          # 글의 핵심 긴장(하네스 v2)
        "archetype": d.get("archetype", "") or "",  # 앵글 유형(다양성 추적, point 2)
        "source": d.get("source", "haiku"),
        "permalink": d.get("permalink", ""),
        "published_at": _iso(d.get("published_at")),
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
    각 (종목 × 포맷) 조합마다 4단계 하네스(앵글→작가 best-of-N→편집→가드, 조합당
    ~5콜)로 초안 생성 후 Firestore에 status=draft로 저장.
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

    # 연속성 메모리(point 3): 최근 다룬 종목·과다 사용 앵글 유형을 회피.
    memory = recent_marketing_memory()

    if not tickers:
        hot_count = int(body.get("hot_count", 3) or 3)
        # 자동 선정 시에만 최근 종목 제외(관리자가 직접 입력하면 존중).
        tickers = pick_hot_tickers(limit=max(1, min(hot_count, 10)), exclude=memory["tickers"])
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

    posts = await generate_batch(
        tickers, formats, uid=uid, avoid_archetypes=memory["archetypes"]
    )
    if not posts:
        return JSONResponse(
            status_code=422,
            content={
                "detail": (
                    f"인용할 실수치가 있는 종목을 찾지 못했습니다(입력: {tickers}). "
                    "종목코드(예: 267260)나 적재된 정확한 종목명으로 입력하거나, "
                    "스크리너에 데이터가 있는 종목인지 확인하세요."
                )
            },
        )

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


@router.post("/briefing/generate")
async def generate_briefing_draft(request: Request):
    """새벽 미국시장 브리핑 초안 1건 생성 → Firestore 저장.

    간밤 미국 지수(FDR) + RSS 뉴스 → Haiku 1회. 종목 입력 불필요.
    """
    if not _is_admin(request):
        return _forbid()

    user = getattr(request.state, "user", None) or {}
    uid = user.get("uid", "") if isinstance(user, dict) else ""

    from agents.briefing import generate_briefing

    post = await generate_briefing(uid=uid)
    if not post:
        return JSONResponse(
            status_code=502,
            content={"detail": "브리핑 생성 실패(지수 데이터 또는 AI 응답 없음)"},
        )

    from firebase_admin import firestore

    from screener.db.firebase_client import get_db

    db = get_db()
    now = firestore.SERVER_TIMESTAMP
    try:
        ref = db.collection(_COLLECTION).document()
        ref.set({**post, "status": "draft", "created_at": now, "updated_at": now})
        doc = ref.get()
        serialized = _serialize(ref.id, doc.to_dict() or post)
    except Exception as e:
        logger.warning(f"[marketing] 브리핑 저장 실패: {e}")
        return JSONResponse(status_code=500, content={"detail": "초안 저장 실패"})

    logger.info(f"[marketing] 브리핑 초안 생성 by {user.get('email', '?')}")
    return {"created": [serialized], "count": 1}


@router.post("/weekend-briefing/generate")
async def generate_weekend_briefing_draft(request: Request):
    """주말 결산 브리핑 초안 1건 생성 → Firestore 저장.

    주말 주요 소식 + 지난 금요일 미국장 마감 → 다음 거래일(월요일) 국내장 관전.
    Sonnet 1회. 종목 입력 불필요.
    """
    if not _is_admin(request):
        return _forbid()

    user = getattr(request.state, "user", None) or {}
    uid = user.get("uid", "") if isinstance(user, dict) else ""

    from agents.weekend_briefing import generate_weekend_briefing

    post = await generate_weekend_briefing(uid=uid)
    if not post:
        return JSONResponse(
            status_code=502,
            content={"detail": "주말 브리핑 생성 실패(지수·뉴스 결손 또는 AI 응답 없음)"},
        )

    from firebase_admin import firestore

    from screener.db.firebase_client import get_db

    db = get_db()
    now = firestore.SERVER_TIMESTAMP
    try:
        ref = db.collection(_COLLECTION).document()
        ref.set({**post, "status": "draft", "created_at": now, "updated_at": now})
        doc = ref.get()
        serialized = _serialize(ref.id, doc.to_dict() or post)
    except Exception as e:
        logger.warning(f"[marketing] 주말 브리핑 저장 실패: {e}")
        return JSONResponse(status_code=500, content={"detail": "초안 저장 실패"})

    logger.info(f"[marketing] 주말 브리핑 초안 생성 by {user.get('email', '?')}")
    return {"created": [serialized], "count": 1}


@router.get("/index-chart/indices")
async def list_index_choices(request: Request):
    """지수 차트 글로 만들 수 있는 지수 목록(프론트 선택용)."""
    if not _is_admin(request):
        return _forbid()
    from agents.index_chart import list_indices

    return {"indices": list_indices()}


@router.post("/index-chart/generate")
async def generate_index_chart_drafts(request: Request):
    """지수 차트 글 초안 생성 → Firestore 저장. body: {keys: str[]}.

    keys = ['KS11','KQ11','IXIC',...] (지수별 개별 글). 각 지수마다 FDR 시계열에서
    차트 지표를 직접 계산 → marketer 4단계 하네스로 1편씩 생성.
    """
    if not _is_admin(request):
        return _forbid()

    try:
        body = await request.json()
    except Exception:
        body = {}

    user = getattr(request.state, "user", None) or {}
    uid = user.get("uid", "") if isinstance(user, dict) else ""

    from agents.index_chart import INDICES, generate_index_chart

    keys = [str(k).strip().upper() for k in (body.get("keys") or []) if str(k).strip()]
    keys = [k for k in keys if k in INDICES][:6]  # 과부하 방지 상한
    if not keys:
        return JSONResponse(
            status_code=400,
            content={"detail": "생성할 지수를 선택하세요(예: KS11, KQ11, IXIC)."},
        )

    import asyncio

    results = await asyncio.gather(
        *(generate_index_chart(k, uid=uid) for k in keys), return_exceptions=True
    )
    posts = []
    for k, r in zip(keys, results):
        if isinstance(r, dict):
            posts.append(r)
        elif isinstance(r, Exception):
            logger.warning(f"[marketing] 지수 차트 생성 예외 {k}: {r}")
    if not posts:
        return JSONResponse(
            status_code=502,
            content={"detail": "지수 차트 글 생성 실패(지수 데이터 또는 AI 응답 없음)"},
        )

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
            logger.warning(f"[marketing] 지수 초안 저장 실패 {p.get('name')}: {e}")

    logger.info(
        f"[marketing] 지수 차트 초안 {len(created)}건 생성 by {user.get('email', '?')} "
        f"(지수 {keys})"
    )
    return {"created": created, "count": len(created)}


@router.get("/publish-status")
async def publish_status(request: Request):
    """Threads 자동발행 가능 여부(토큰/USER_ID 설정 여부). 프론트 발행버튼 활성화용."""
    if not _is_admin(request):
        return _forbid()
    return {"enabled": threads_client.is_enabled()}


@router.post("/drafts/{draft_id}/publish")
async def publish_draft(request: Request, draft_id: str):
    """초안을 Threads에 발행. 파트가 여러 개면 **타래**로 순차 발행한다.

    - 발행 시작 전에 **전 파트를 검증**한다(길이·금지표현). 하나라도 걸리면 아무것도
      발행하지 않는다 — Threads는 글삭제 API가 없어 반쪽 타래를 되돌릴 수 없다.
    - 파트가 나갈 때마다 즉시 Firestore에 기록한다. 중간에 끊기면 status=partial이 되고,
      같은 엔드포인트를 다시 호출하면 끊긴 지점부터 **이어서 발행**한다.
    - 미설정(토큰 없음) 503 / 검증 실패 422 / 발행 실패 502.
    """
    if not _is_admin(request):
        return _forbid()
    if not threads_client.is_enabled():
        return JSONResponse(
            status_code=503,
            content={"detail": "Threads 자동발행 미설정(THREADS_ACCESS_TOKEN/USER_ID)"},
        )

    from firebase_admin import firestore

    from screener.db.firebase_client import get_db

    db = get_db()
    ref = db.collection(_COLLECTION).document(draft_id)
    snap = ref.get()
    if not snap.exists:
        return JSONResponse(status_code=404, content={"detail": "초안 없음"})
    data = snap.to_dict() or {}

    if data.get("status") == "published":
        return JSONResponse(status_code=409, content={"detail": "이미 발행된 초안입니다"})

    try:
        parts = threads_client.validate_parts(_parts_of(data))
    except Exception as e:
        return JSONResponse(status_code=400, content={"detail": str(e)})

    # 발행 직전 금지표현 재검증(이중 안전) — 전 파트를 본다.
    from agents.base import BaseAgent

    for i, p in enumerate(parts, 1):
        _filtered, found = BaseAgent.filter_forbidden(p)
        if found:
            return JSONResponse(
                status_code=422,
                content={"detail": f"{i}번째 파트에 금지표현({found}) — 수정 후 발행하세요"},
            )

    # 이어서 발행(복구): 앞서 나간 파트는 건너뛰고 마지막 글에 체인한다.
    done_ids = [str(x) for x in (data.get("published_ids") or []) if x]
    start = min(int(data.get("published_upto", 0) or 0), len(done_ids), len(parts))
    remaining = parts[start:]
    if not remaining:
        return JSONResponse(status_code=409, content={"detail": "이미 모든 파트가 발행됐습니다"})

    published: list[dict] = []

    async def _record(i: int, r: dict) -> None:
        """파트 하나가 나갈 때마다 즉시 영속화 — 여기서 죽어도 어디까지 갔는지 남는다."""
        published.append(r)
        patch = {
            "published_ids": firestore.ArrayUnion([r.get("id", "")]),
            "published_upto": start + i + 1,
            "updated_at": firestore.SERVER_TIMESTAMP,
        }
        if start == 0 and i == 0:  # 루트 = 타래의 대표 링크
            patch["permalink"] = r.get("permalink", "")
            patch["threads_post_id"] = r.get("id", "")
        try:
            ref.set(patch, merge=True)
        except Exception as e:  # 기록 실패가 발행을 막지는 않는다(이미 나갔다)
            logger.error(f"[marketing] 파트 기록 실패 {draft_id} part={start + i + 1}: {e}")

    try:
        await threads_client.publish_thread(
            remaining,
            reply_to_id=done_ids[-1] if start > 0 and done_ids else None,
            on_part=_record,
        )
    except Exception as e:
        done = start + len(published)
        logger.warning(f"[marketing] 발행 실패 {draft_id} ({done}/{len(parts)}파트): {e}")
        try:
            ref.set({"status": "partial", "updated_at": firestore.SERVER_TIMESTAMP}, merge=True)
        except Exception:
            pass
        return JSONResponse(
            status_code=502,
            content={
                "detail": (
                    f"{len(parts)}파트 중 {done}개까지 발행되고 끊겼습니다: {e} — "
                    "Threads는 글삭제 API가 없어 되돌릴 수 없습니다. "
                    "'이어서 발행'으로 남은 파트를 마저 보내세요."
                ),
                "published_upto": done,
                "part_count": len(parts),
            },
        )

    try:
        ref.set(
            {
                "status": "published",
                "published_at": firestore.SERVER_TIMESTAMP,
                "updated_at": firestore.SERVER_TIMESTAMP,
            },
            merge=True,
        )
        doc = ref.get()
    except Exception as e:
        logger.warning(f"[marketing] 발행 후 상태 저장 실패 {draft_id}: {e}")
        # 발행 자체는 성공했으므로 permalink는 반환
        return {
            "ok": True,
            "permalink": published[0].get("permalink", "") if published else "",
            "warning": "상태 저장 실패",
        }

    user = getattr(request.state, "user", {}) or {}
    logger.info(
        f"[marketing] 발행 완료 {draft_id} ({len(parts)}파트) by {user.get('email', '?')} "
        f"{(doc.to_dict() or {}).get('permalink', '')}"
    )
    return {"ok": True, "draft": _serialize(draft_id, doc.to_dict() or {})}


@router.patch("/drafts/{draft_id}")
async def update_draft(request: Request, draft_id: str):
    """초안 수정. body: {text?: str, parts?: str[], status?: str}.

    text는 `---` 단독 줄을 파트 경계로 보고 parts를 다시 만든다(검수 화면 textarea 그대로).
    parts를 직접 주면 그쪽이 우선. 둘은 항상 같이 갱신돼 어긋나지 않는다.
    """
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
    if "parts" in body or "text" in body:
        if body.get("parts"):
            parts = [str(p).strip() for p in body["parts"] if str(p).strip()]
        else:
            parts = threads_client.split_parts(str(body.get("text") or ""))
        patch["parts"] = parts
        patch["text"] = threads_client.join_parts(parts)
        patch["char_count"] = len(parts[0]) if parts else 0
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
