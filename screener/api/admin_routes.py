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


def _iter_trial_expiring(days: int):
    """트라이얼 D-N일 이내 + 미결제 사용자 순회.
    yields (doc_id, data_dict, trial_ends_at_utc, days_left)
    """
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(days=max(1, min(days, 30)))
    try:
        cur = _users_ref().where("trial_started", "==", True).stream()
    except Exception as e:
        logger.error(f"trial_expiring query failed: {e}")
        return
    for d in cur:
        dd = d.to_dict() or {}
        te = dd.get("trial_ends_at")
        if hasattr(te, "timestamp"):
            te = datetime.fromtimestamp(te.timestamp(), tz=timezone.utc)
        if not te:
            continue
        sub_status = (dd.get("subscription") or {}).get("status", "")
        if not (now < te <= cutoff and dd.get("tier") == "pro" and sub_status not in ("active", "on_trial", "cancelled")):
            continue
        yield d.id, dd, te, max(0, (te - now).days)


@router.get("/trial-expiring")
async def trial_expiring(request: Request, days: int = 2):
    """D-N일 이내 체험 만료 예정 사용자 조회 (발송 없음)."""
    if not _is_admin(request):
        return _forbid()
    users_out = [
        {"uid": uid, "email": dd.get("email", ""), "trial_ends_at": te.isoformat(), "days_left": left}
        for uid, dd, te, left in _iter_trial_expiring(days)
    ]
    return {"users": users_out, "count": len(users_out), "cutoff_days": days}


def _trial_reminder_html(days_left: int, ends_at: datetime, pricing_url: str) -> str:
    ends_str = ends_at.astimezone(timezone.utc).strftime("%Y-%m-%d")
    urgency = "오늘 만료됩니다" if days_left == 0 else f"{days_left}일 남았습니다"
    return f"""<!DOCTYPE html>
<html lang="ko"><body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:600px;margin:0 auto;padding:40px 20px;color:#1e293b;background:#f8fafc;">
<div style="background:white;padding:32px;border-radius:12px;box-shadow:0 1px 3px rgba(0,0,0,.08);">
<h1 style="color:#2563eb;margin:0 0 16px;font-size:22px;">⏰ 체험판 {urgency}</h1>
<p style="font-size:15px;line-height:1.7;">Axis Pro 체험판이 <b>{ends_str}</b>에 만료됩니다.</p>
<p style="font-size:15px;line-height:1.7;">계속 Pro 기능(전문가 포트폴리오, 관찰 포인트, 백테스트 등)을 사용하시려면 아래 버튼에서 결제를 진행해주세요.</p>
<p style="margin:32px 0;text-align:center;">
<a href="{pricing_url}" style="background:#2563eb;color:white;padding:14px 28px;text-decoration:none;border-radius:8px;font-weight:600;display:inline-block;">Pro 결제하기 →</a>
</p>
<p style="color:#64748b;font-size:13px;margin-top:40px;border-top:1px solid #e2e8f0;padding-top:16px;">
체험판 만료 알림은 자동 발송되며, 사용자당 1회만 발송됩니다.
</p></div></body></html>"""


def _trial_reminder_text(days_left: int, ends_at: datetime, pricing_url: str) -> str:
    ends_str = ends_at.astimezone(timezone.utc).strftime("%Y-%m-%d")
    urgency = "오늘 만료됩니다" if days_left == 0 else f"{days_left}일 남았습니다"
    return (
        f"Axis Pro 체험판 {urgency}\n\n"
        f"체험판 만료일: {ends_str}\n\n"
        f"계속 Pro 기능을 사용하시려면 아래 링크에서 결제해주세요:\n{pricing_url}\n\n"
        f"--\nAxis"
    )


@router.post("/send-trial-reminders")
async def send_trial_reminders(request: Request, days: int = 2):
    """D-N일 체험 만료 예정 사용자에게 Mailgun으로 리마인더 메일 발송.

    Cloud Scheduler에서 매일 호출. x-admin-key 헤더로 인증.
    사용자당 1회만 발송 (trial_reminder_sent_at 필드로 중복 방지).
    """
    if not _is_admin(request):
        return _forbid()
    from screener.services.mailer import send_email, is_configured
    if not is_configured():
        return JSONResponse(status_code=503, content={"detail": "Mailgun 미설정"})

    base_url = os.environ.get("CLOUD_RUN_URL", "").rstrip("/")
    pricing_url = f"{base_url}/pricing" if base_url else "/pricing"
    now = datetime.now(timezone.utc)
    sent, skipped = 0, 0
    failed: list[str] = []

    for uid, dd, te, days_left in _iter_trial_expiring(days):
        email = (dd.get("email") or "").strip()
        if not email:
            continue
        if dd.get("trial_reminder_sent_at"):
            skipped += 1
            continue
        subject = f"[Axis] Pro 체험판 {days_left}일 남았습니다"
        ok = send_email(
            email,
            subject,
            _trial_reminder_html(days_left, te, pricing_url),
            _trial_reminder_text(days_left, te, pricing_url),
        )
        if ok:
            sent += 1
            try:
                _users_ref().document(uid).update({"trial_reminder_sent_at": now})
            except Exception as e:
                logger.debug(f"mark reminder failed for {uid}: {e}")
        else:
            failed.append(email)

    logger.info(f"trial reminders: sent={sent} skipped={skipped} failed={len(failed)}")
    return {"sent": sent, "skipped": skipped, "failed": failed, "cutoff_days": days}


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
