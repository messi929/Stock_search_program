"""관리자 대시보드 API — 사용자/구독/어뷰징 관리.

접근 제어:
  1. Firebase 로그인 필요
  2. 이메일이 ADMIN_EMAILS(env) 에 포함되어야 함
  3. 또는 X-Admin-Key 헤더가 ADMIN_KEY(env)와 일치
"""

import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Request
from loguru import logger
from starlette.responses import JSONResponse

from screener.middleware import ADMIN_EMAILS
from screener.services.subscription import _users_ref

router = APIRouter(prefix="/api/admin")

ADMIN_KEY = os.environ.get("ADMIN_KEY", "")


def _is_admin(request: Request) -> bool:
    user = getattr(request.state, "user", None) or {}
    if user.get("email", "").lower() in ADMIN_EMAILS:
        return True
    key = request.headers.get("x-admin-key", "")
    return bool(ADMIN_KEY) and key == ADMIN_KEY


def _forbid():
    return JSONResponse(status_code=403, content={"detail": "관리자 전용"})


def _serialize_user(uid: str, d: dict) -> dict:
    def _iso(v):
        if not v:
            return None
        if hasattr(v, "isoformat"):
            return v.isoformat()
        if hasattr(v, "timestamp"):
            return datetime.fromtimestamp(v.timestamp(), tz=timezone.utc).isoformat()
        return str(v)

    sub = d.get("subscription") or {}
    return {
        "uid": uid,
        "email": d.get("email", ""),
        "tier": d.get("tier", "free"),
        "created_at": _iso(d.get("created_at")),
        "trial_started": bool(d.get("trial_started")),
        "trial_ends_at": _iso(d.get("trial_ends_at")),
        "suspended": bool(d.get("suspended")),
        "suspicious": bool(d.get("suspicious")),
        "admin_note": d.get("admin_note", "") or "",
        "subscription_status": sub.get("status", ""),
        "subscription_plan": sub.get("plan", ""),
        "subscription_period_end": _iso(sub.get("current_period_end")),
        "lemon_customer_id": d.get("lemon_customer_id") or "",
    }


@router.get("/users")
async def list_users(request: Request, filter: str = "", limit: int = 100):
    """사용자 목록. filter: all|suspicious|suspended|trial|pro|free."""
    if not _is_admin(request):
        return _forbid()

    query = _users_ref()
    if filter == "suspicious":
        query = query.where("suspicious", "==", True)
    elif filter == "suspended":
        query = query.where("suspended", "==", True)
    elif filter == "pro":
        query = query.where("tier", "==", "pro")
    elif filter == "free":
        query = query.where("tier", "==", "free")

    docs = list(query.limit(max(1, min(limit, 500))).stream())
    users = [_serialize_user(d.id, d.to_dict()) for d in docs]

    # trial 필터는 클라이언트 측에서 처리 (trial_ends_at 존재 AND 미래)
    if filter == "trial":
        now = datetime.now(timezone.utc).isoformat()
        users = [u for u in users if u.get("trial_ends_at") and u["trial_ends_at"] > now]

    # suspicious 우선, 그다음 최신 가입순
    users.sort(key=lambda u: (
        0 if u["suspended"] else (1 if u["suspicious"] else 2),
        u.get("created_at") or "",
    ), reverse=False)
    return {"users": users, "count": len(users), "filter": filter}


@router.get("/users/{uid}")
async def user_detail(request: Request, uid: str):
    """사용자 상세 + 최근 로그인 이력 + 활성 세션."""
    if not _is_admin(request):
        return _forbid()

    doc = _users_ref().document(uid).get()
    if not doc.exists:
        return JSONResponse(status_code=404, content={"detail": "사용자 없음"})

    user = _serialize_user(uid, doc.to_dict())

    # 최근 로그인 30개
    logins = []
    try:
        cur = _users_ref().document(uid).collection("login_history").order_by("timestamp", direction="DESCENDING").limit(30).stream()
        for d in cur:
            dd = d.to_dict()
            ts = dd.get("timestamp")
            logins.append({
                "ip": dd.get("ip", ""),
                "user_agent": dd.get("user_agent", "")[:200],
                "timestamp": ts.isoformat() if hasattr(ts, "isoformat") else (datetime.fromtimestamp(ts.timestamp(), tz=timezone.utc).isoformat() if hasattr(ts, "timestamp") else str(ts)),
            })
    except Exception as e:
        logger.debug(f"login_history 조회 실패: {e}")

    # 활성 세션
    sessions = []
    try:
        for d in _users_ref().document(uid).collection("active_sessions").stream():
            dd = d.to_dict()
            last = dd.get("last_seen")
            sessions.append({
                "session_id": d.id,
                "ip": dd.get("ip", ""),
                "user_agent": dd.get("user_agent", "")[:200],
                "last_seen": last.isoformat() if hasattr(last, "isoformat") else str(last),
            })
    except Exception:
        pass

    # unique IP 집계 (30일)
    since = datetime.now(timezone.utc) - timedelta(days=30)
    unique_ips = set()
    for l in logins:
        unique_ips.add(l["ip"])

    return {
        "user": user,
        "login_history": logins,
        "active_sessions": sessions,
        "unique_ips_30d": len(unique_ips),
    }


async def _json_body(request: Request) -> dict:
    try:
        return await request.json()
    except Exception:
        return {}


def _log_admin_action(request: Request, uid: str, action: str, detail: dict) -> None:
    """관리자 액션을 users/{uid}/audit_log에 기록."""
    try:
        user = getattr(request.state, "user", None) or {}
        actor = user.get("email", "") or request.headers.get("x-admin-key", "")[:10] or "unknown"
        _users_ref().document(uid).collection("audit_log").add({
            "action": action,
            "actor": actor,
            "detail": detail or {},
            "timestamp": datetime.now(timezone.utc),
        })
    except Exception as e:
        logger.debug(f"audit log failed: {e}")


@router.post("/users/{uid}/suspend")
async def suspend_user(request: Request, uid: str):
    if not _is_admin(request):
        return _forbid()
    body = await _json_body(request)
    reason = (body.get("reason") or "").strip()[:500]
    _users_ref().document(uid).set({
        "suspended": True,
        "admin_note": reason or "정지 (관리자)",
    }, merge=True)
    try:
        for d in _users_ref().document(uid).collection("active_sessions").stream():
            d.reference.delete()
    except Exception:
        pass
    _log_admin_action(request, uid, "suspend", {"reason": reason})
    logger.warning(f"계정 정지: {uid} — {reason}")
    return {"ok": True, "suspended": True}


@router.post("/users/{uid}/unsuspend")
async def unsuspend_user(request: Request, uid: str):
    if not _is_admin(request):
        return _forbid()
    _users_ref().document(uid).set({
        "suspended": False,
        "suspicious": False,
        "admin_note": "",
    }, merge=True)
    _log_admin_action(request, uid, "unsuspend", {})
    return {"ok": True, "suspended": False}


@router.post("/users/{uid}/extend-trial")
async def extend_trial(request: Request, uid: str):
    """체험 기간 연장. body: {days: int}"""
    if not _is_admin(request):
        return _forbid()
    body = await _json_body(request)
    days = int(body.get("days", 7))
    if days <= 0 or days > 90:
        return JSONResponse(status_code=400, content={"detail": "1~90일"})

    doc = _users_ref().document(uid).get()
    if not doc.exists:
        return JSONResponse(status_code=404, content={"detail": "사용자 없음"})

    d = doc.to_dict()
    now = datetime.now(timezone.utc)
    base = d.get("trial_ends_at")
    if hasattr(base, "timestamp"):
        base = datetime.fromtimestamp(base.timestamp(), tz=timezone.utc)
    if not base or base < now:
        base = now
    new_end = base + timedelta(days=days)

    from firebase_admin import auth
    _users_ref().document(uid).set({
        "trial_ends_at": new_end,
        "tier": "pro",
        "trial_started": True,
    }, merge=True)
    try:
        auth.set_custom_user_claims(uid, {"tier": "pro", "trial": True})
    except Exception as e:
        logger.error(f"claims 실패: {e}")
    _log_admin_action(request, uid, "extend_trial", {"days": days, "new_end": new_end.isoformat()})
    return {"ok": True, "trial_ends_at": new_end.isoformat()}


@router.post("/users/{uid}/note")
async def set_note(request: Request, uid: str):
    if not _is_admin(request):
        return _forbid()
    body = await _json_body(request)
    note = (body.get("note") or "").strip()[:1000]
    _users_ref().document(uid).set({"admin_note": note}, merge=True)
    _log_admin_action(request, uid, "note", {"note_len": len(note)})
    return {"ok": True}


@router.get("/users/{uid}/audit-log")
async def get_audit_log(request: Request, uid: str):
    """관리자 액션 이력 조회."""
    if not _is_admin(request):
        return _forbid()
    logs = []
    try:
        cur = _users_ref().document(uid).collection("audit_log").order_by("timestamp", direction="DESCENDING").limit(50).stream()
        for d in cur:
            dd = d.to_dict()
            ts = dd.get("timestamp")
            logs.append({
                "action": dd.get("action", ""),
                "actor": dd.get("actor", ""),
                "detail": dd.get("detail", {}),
                "timestamp": ts.isoformat() if hasattr(ts, "isoformat") else (datetime.fromtimestamp(ts.timestamp(), tz=timezone.utc).isoformat() if hasattr(ts, "timestamp") else str(ts)),
            })
    except Exception:
        pass
    return {"logs": logs}


@router.get("/trial-expiring")
async def trial_expiring(request: Request, days: int = 2):
    """D-N일 이내 체험 만료 예정 사용자 조회. 이메일 알림 연동용.
    Cloud Scheduler에서 주기적으로 이 엔드포인트 호출 → 각 사용자에게 메일 발송.
    """
    if not _is_admin(request):
        return _forbid()
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(days=max(1, min(days, 30)))
    users_out = []
    try:
        cur = _users_ref().where("trial_started", "==", True).stream()
        for d in cur:
            dd = d.to_dict() or {}
            te = dd.get("trial_ends_at")
            if hasattr(te, "timestamp"):
                te = datetime.fromtimestamp(te.timestamp(), tz=timezone.utc)
            if not te:
                continue
            sub_status = (dd.get("subscription") or {}).get("status", "")
            if now < te <= cutoff and dd.get("tier") == "pro" and sub_status not in ("active", "on_trial", "cancelled"):
                users_out.append({
                    "uid": d.id,
                    "email": dd.get("email", ""),
                    "trial_ends_at": te.isoformat(),
                    "days_left": max(0, (te - now).days),
                })
    except Exception as e:
        logger.error(f"trial_expiring query failed: {e}")
    return {"users": users_out, "count": len(users_out), "cutoff_days": days}


@router.get("/stats")
async def admin_stats(request: Request):
    """대시보드 상단 지표."""
    if not _is_admin(request):
        return _forbid()

    now = datetime.now(timezone.utc)
    stats = {"total": 0, "pro": 0, "free": 0, "trial_active": 0,
             "suspicious": 0, "suspended": 0}

    for d in _users_ref().stream():
        dd = d.to_dict() or {}
        stats["total"] += 1
        if dd.get("tier") == "pro":
            stats["pro"] += 1
        else:
            stats["free"] += 1
        te = dd.get("trial_ends_at")
        if hasattr(te, "timestamp"):
            te = datetime.fromtimestamp(te.timestamp(), tz=timezone.utc)
        if te and te > now:
            stats["trial_active"] += 1
        if dd.get("suspicious"):
            stats["suspicious"] += 1
        if dd.get("suspended"):
            stats["suspended"] += 1

    return stats
