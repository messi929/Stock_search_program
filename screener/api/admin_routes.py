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


# ──────────────────────────────────────────────
# 신규: 가입·전환 퍼널 (2026-06-12)
# ──────────────────────────────────────────────

_KST = timezone(timedelta(hours=9))


def _as_utc(v):
    """Firestore Timestamp/datetime/None → aware UTC datetime 또는 None."""
    if v is None:
        return None
    if hasattr(v, "timestamp"):
        try:
            return datetime.fromtimestamp(v.timestamp(), tz=timezone.utc)
        except Exception:
            return None
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    return None


def _kst_day(dt: datetime) -> str:
    """UTC datetime → KST 날짜 문자열(YYYY-MM-DD). 창업자가 생각하는 '하루' 기준."""
    return dt.astimezone(_KST).strftime("%Y-%m-%d")


@router.get("/funnel")
async def admin_funnel(request: Request, days: int = 30):
    """가입→활성화→체험→결제 퍼널 + 일별 가입 추이.

    어디서 새는지 진단용. 두 번의 전량 스캔(users + collection_group(analysis_history)).
    현 사용자 규모에선 무리 없음(/usage·/stats와 동일 패턴).

    단계 정의:
      - 가입(signup): users 문서 존재
      - 활성화(activated): analysis_history에 kind=analysis 1건 이상(딥다이브 경험)
      - 체험(trial): trial_started == True
      - 결제(paid): subscription.status in (active, cancelled)  # cancelled=기간말까지 유료
    """
    if not _is_admin(request):
        return _forbid()

    from screener.db.firebase_client import get_db

    db = get_db()
    days = max(1, min(days, 365))
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days)

    # 1) analysis_history 전량 스캔 → 활성화된 uid 집합 + uid별 최초 분석 시각
    activated_first: dict[str, datetime] = {}      # kind=analysis 최초 시각
    engaged_uids: set[str] = set()                 # 모든 활동(분석/검증/발견)
    try:
        for doc in db.collection_group("analysis_history").stream():
            parent = doc.reference.parent.parent
            uid = parent.id if parent is not None else ""
            if not uid:
                continue
            engaged_uids.add(uid)
            dd = doc.to_dict() or {}
            if dd.get("kind", "analysis") != "analysis":
                continue
            ca = _as_utc(dd.get("created_at"))
            if ca is None:
                continue
            prev = activated_first.get(uid)
            if prev is None or ca < prev:
                activated_first[uid] = ca
    except Exception as e:
        logger.warning(f"funnel: analysis_history 스캔 실패: {e}")

    activated_uids = set(activated_first.keys())

    # 2) users 전량 스캔 → 일별 가입 + 코호트 퍼널 + 전체 활성화율
    signups_by_day: dict[str, int] = {}
    # 코호트 = 기간 내 신규 가입자
    cohort = {"signups": 0, "activated": 0, "trial": 0, "paid": 0}
    # 전체(all-time)
    overall = {"total": 0, "activated": 0, "trial": 0, "paid": 0}
    ttf_hours: list[float] = []   # 가입→첫분석 소요시간(코호트, 시간)

    # 차트용 날짜 버킷 미리 0으로 채움(빈 날도 보이게)
    for i in range(days):
        d_kst = (since + timedelta(days=i)).astimezone(_KST).strftime("%Y-%m-%d")
        signups_by_day.setdefault(d_kst, 0)
    signups_by_day.setdefault(_kst_day(now), 0)

    try:
        for d in _users_ref().stream():
            dd = d.to_dict() or {}
            uid = d.id
            # 관리자 계정은 퍼널에서 제외(자기 자신 노이즈)
            if dd.get("is_admin_role"):
                continue
            created = _as_utc(dd.get("created_at"))
            sub = dd.get("subscription") or {}
            status = sub.get("status", "")
            is_paid = status in ("active", "cancelled")
            is_trial = bool(dd.get("trial_started"))
            is_activated = uid in activated_uids

            overall["total"] += 1
            if is_activated:
                overall["activated"] += 1
            if is_trial:
                overall["trial"] += 1
            if is_paid:
                overall["paid"] += 1

            if created is not None:
                signups_by_day[_kst_day(created)] = signups_by_day.get(_kst_day(created), 0) + 1
                if created >= since:
                    cohort["signups"] += 1
                    if is_activated:
                        cohort["activated"] += 1
                        fa = activated_first.get(uid)
                        if fa is not None and fa >= created:
                            ttf_hours.append((fa - created).total_seconds() / 3600.0)
                    if is_trial:
                        cohort["trial"] += 1
                    if is_paid:
                        cohort["paid"] += 1
    except Exception as e:
        logger.warning(f"funnel: users 스캔 실패: {e}")

    # 일별 추이 정렬(오름차순) — 기간 내 + 가입 있던 날만
    trend = [
        {"date": k, "signups": v}
        for k, v in sorted(signups_by_day.items())
        if k >= _kst_day(since)
    ]

    def _rate(num: int, den: int) -> float:
        return round(num / den * 100, 1) if den else 0.0

    ttf_median = 0.0
    if ttf_hours:
        s = sorted(ttf_hours)
        mid = len(s) // 2
        ttf_median = round(s[mid] if len(s) % 2 else (s[mid - 1] + s[mid]) / 2, 1)

    return {
        "period_days": days,
        "cohort": {
            **cohort,
            "activation_rate": _rate(cohort["activated"], cohort["signups"]),
            "trial_rate": _rate(cohort["trial"], cohort["signups"]),
            "paid_rate": _rate(cohort["paid"], cohort["signups"]),
            # 활성화한 사람 중 결제 전환 — 첫경험이 결제로 이어지나
            "activated_to_paid_rate": _rate(cohort["paid"], cohort["activated"]),
            "median_hours_to_activate": ttf_median,
        },
        "overall": {
            **overall,
            "activation_rate": _rate(overall["activated"], overall["total"]),
        },
        "trend": trend,
        "engaged_total": len(engaged_uids),
    }


# ──────────────────────────────────────────────
# 신규: 수입 / 사용량 / 에러 모니터링 (2026-06-07)
# ──────────────────────────────────────────────

# 분석으로 카운트되는 에이전트 (api/routes/ai.py:_ANALYSIS_AGENTS와 동일하게 유지)
_ANALYSIS_AGENTS = ("strategist", "event_analyst", "macro_pm", "korean_specialist")


@router.get("/me")
async def admin_me(request: Request):
    """프론트 관리자 게이트용 경량 체크. 관리자면 200, 아니면 403."""
    if not _is_admin(request):
        return _forbid()
    user = getattr(request.state, "user", None) or {}
    return {"is_admin": True, "email": user.get("email", "")}


@router.get("/revenue")
async def admin_revenue(request: Request):
    """수입(MRR/ARR) 추정 + 활성 구독 집계. 가격은 코드 상수 기반(추정)."""
    if not _is_admin(request):
        return _forbid()

    from screener.services.error_log import iso_ts
    from screener.services.pricing import (
        PRO_MONTHLY_KRW,
        PRO_YEARLY_KRW,
        monthly_recurring_krw,
    )

    now = datetime.now(timezone.utc)
    soon = now + timedelta(days=30)
    by_plan = {"monthly": 0, "yearly": 0}
    active = 0          # status active|on_trial|cancelled (기간 끝까지 pro)
    trial_active = 0    # on_trial
    cancel_scheduled = 0
    upcoming = []       # 30일 내 갱신/만료 예정

    for d in _users_ref().stream():
        dd = d.to_dict() or {}
        sub = dd.get("subscription") or {}
        status = sub.get("status", "")
        if status not in ("active", "on_trial", "cancelled"):
            continue
        active += 1
        if status == "on_trial":
            trial_active += 1
        plan = sub.get("plan", "")
        if plan in by_plan:
            by_plan[plan] += 1
        if sub.get("cancel_at_period_end"):
            cancel_scheduled += 1
        pe = sub.get("current_period_end")
        pe_dt = pe
        if hasattr(pe, "timestamp"):
            pe_dt = datetime.fromtimestamp(pe.timestamp(), tz=timezone.utc)
        elif isinstance(pe, str):
            try:
                pe_dt = datetime.fromisoformat(pe.replace("Z", "+00:00"))
            except Exception:
                pe_dt = None
        if isinstance(pe_dt, datetime) and now <= pe_dt <= soon:
            upcoming.append({
                "uid": d.id,
                "email": dd.get("email", ""),
                "plan": plan,
                "period_end": iso_ts(pe),
                "cancel_at_period_end": bool(sub.get("cancel_at_period_end")),
            })

    upcoming.sort(key=lambda x: x.get("period_end") or "")
    mrr = round(monthly_recurring_krw(by_plan["monthly"], by_plan["yearly"]))
    return {
        "active_subscriptions": active,
        "by_plan": by_plan,
        "trial_active": trial_active,
        "cancel_scheduled": cancel_scheduled,
        "mrr_krw": mrr,
        "arr_krw": mrr * 12,
        "upcoming_renewals": upcoming,
        "prices": {"monthly": PRO_MONTHLY_KRW, "yearly": PRO_YEARLY_KRW},
        "estimated": True,
    }


def _parse_usage_doc(data: dict, acc: dict) -> None:
    """ai_usage 일별 문서(평면 키)를 acc에 누적. acc는 호출자가 초기화."""
    acc["krw"] += float(data.get("total.krw", 0) or 0)
    acc["usd"] += float(data.get("total.usd", 0) or 0)
    for agent in _ANALYSIS_AGENTS:
        c = int(data.get(f"agents.{agent}.calls", 0) or 0)
        acc["analyses"] += c
        acc["by_agent"][agent] = acc["by_agent"].get(agent, 0) + c
    v = int(data.get("agents.validator.calls", 0) or 0)
    acc["validations"] += v
    acc["by_agent"]["validator"] = acc["by_agent"].get("validator", 0) + v
    disc = int(data.get("agents.discoverer.calls", 0) or 0)
    acc["discoveries"] += disc
    acc["by_agent"]["discoverer"] = acc["by_agent"].get("discoverer", 0) + disc


def _new_usage_acc() -> dict:
    return {"krw": 0.0, "usd": 0.0, "analyses": 0, "validations": 0,
            "discoveries": 0, "by_agent": {}}


@router.get("/usage")
async def admin_usage(request: Request, month: str = "", top: int = 50):
    """전체 + 고객별 AI 사용량 집계. month=YYYY-MM (기본 현재월, UTC).

    cost_tracker가 users/{uid}/ai_usage/{YYYY-MM-DD}에 평면 키로 기록한 것을
    collection_group으로 전량 스캔해 집계한다(현 사용자 규모에선 무리 없음).
    """
    if not _is_admin(request):
        return _forbid()

    from screener.db.firebase_client import get_db

    db = get_db()
    if not month:
        month = datetime.now(timezone.utc).strftime("%Y-%m")

    totals = _new_usage_acc()
    per_uid: dict[str, dict] = {}

    try:
        for doc in db.collection_group("ai_usage").stream():
            if not doc.id.startswith(month):
                continue
            uid_ref = doc.reference.parent.parent
            uid = uid_ref.id if uid_ref is not None else ""
            data = doc.to_dict() or {}
            _parse_usage_doc(data, totals)
            acc = per_uid.setdefault(uid, _new_usage_acc())
            _parse_usage_doc(data, acc)
    except Exception as e:
        logger.warning(f"admin_usage 집계 실패: {e}")

    # uid→email 매핑 (Top N만 조회)
    ranked = sorted(per_uid.items(), key=lambda kv: kv[1]["krw"], reverse=True)
    ranked = ranked[: max(1, min(top, 200))]
    by_user = []
    for uid, acc in ranked:
        email = ""
        try:
            snap = _users_ref().document(uid).get()
            if snap.exists:
                email = (snap.to_dict() or {}).get("email", "")
        except Exception:
            pass
        by_user.append({
            "uid": uid,
            "email": email,
            "krw": round(acc["krw"]),
            "usd": round(acc["usd"], 2),
            "analyses": acc["analyses"],
            "validations": acc["validations"],
            "discoveries": acc["discoveries"],
        })

    return {
        "month": month,
        "totals": {
            "krw": round(totals["krw"]),
            "usd": round(totals["usd"], 2),
            "analyses": totals["analyses"],
            "validations": totals["validations"],
            "discoveries": totals["discoveries"],
            "active_users": len(per_uid),
        },
        "by_agent": totals["by_agent"],
        "by_user": by_user,
    }


@router.get("/errors")
async def admin_errors(request: Request, limit: int = 100, type: str = "", days: int = 0):
    """최근 에러 목록. type 필터, days(최근 N일) 필터 옵션."""
    if not _is_admin(request):
        return _forbid()

    from firebase_admin import firestore

    from screener.db.firebase_client import get_db
    from screener.services.error_log import iso_ts

    db = get_db()
    errors = []
    try:
        q = db.collection("admin_errors").order_by(
            "created_at", direction=firestore.Query.DESCENDING
        ).limit(max(1, min(limit, 500)))
        since = None
        if days and days > 0:
            since = datetime.now(timezone.utc) - timedelta(days=days)
        for d in q.stream():
            dd = d.to_dict() or {}
            ca = dd.get("created_at")
            ca_dt = ca
            if hasattr(ca, "timestamp"):
                ca_dt = datetime.fromtimestamp(ca.timestamp(), tz=timezone.utc)
            if since and isinstance(ca_dt, datetime) and ca_dt < since:
                continue
            if type and dd.get("type") != type:
                continue
            errors.append({
                "id": d.id,
                "type": dd.get("type", ""),
                "message": dd.get("message", ""),
                "uid": dd.get("uid", ""),
                "ticker": dd.get("ticker", ""),
                "agent": dd.get("agent", ""),
                "context": dd.get("context", {}),
                "created_at": iso_ts(ca),
            })
    except Exception as e:
        logger.warning(f"admin_errors 조회 실패: {e}")
    return {"errors": errors, "count": len(errors)}


@router.get("/errors/summary")
async def admin_errors_summary(request: Request, days: int = 7):
    """최근 N일 에러 유형별/일별 빈도 집계."""
    if not _is_admin(request):
        return _forbid()

    from firebase_admin import firestore

    from screener.db.firebase_client import get_db

    db = get_db()
    days = max(1, min(days, 90))
    since = datetime.now(timezone.utc) - timedelta(days=days)
    by_type: dict[str, int] = {}
    by_day: dict[str, int] = {}
    total = 0
    try:
        q = db.collection("admin_errors").order_by(
            "created_at", direction=firestore.Query.DESCENDING
        ).limit(2000)
        for d in q.stream():
            dd = d.to_dict() or {}
            ca = dd.get("created_at")
            ca_dt = ca
            if hasattr(ca, "timestamp"):
                ca_dt = datetime.fromtimestamp(ca.timestamp(), tz=timezone.utc)
            if not isinstance(ca_dt, datetime) or ca_dt < since:
                continue
            total += 1
            t = dd.get("type", "unknown")
            by_type[t] = by_type.get(t, 0) + 1
            day = ca_dt.strftime("%Y-%m-%d")
            by_day[day] = by_day.get(day, 0) + 1
    except Exception as e:
        logger.warning(f"admin_errors_summary 집계 실패: {e}")
    return {"days": days, "total": total, "by_type": by_type, "by_day": by_day}


# ──────────────────────────────────────────────
# 점검 공지(maintenance) — config/maintenance 문서. 공개 조회는 /api/maintenance.
# ──────────────────────────────────────────────

@router.put("/maintenance")
async def set_maintenance(request: Request):
    """점검 공지 설정(켜기/끄기, 시작·종료 시각, 메시지). 관리자 전용. 즉시 반영."""
    if not _is_admin(request):
        return _forbid()
    try:
        body = await request.json()
    except Exception:
        body = {}
    cfg = {
        "enabled": bool(body.get("enabled")),
        "starts_at": str(body.get("starts_at") or "")[:40],  # ISO 또는 빈값
        "ends_at": str(body.get("ends_at") or "")[:40],
        "message": str(body.get("message") or "")[:500],
    }
    try:
        from firebase_admin import firestore

        from screener.db.firebase_client import get_db

        get_db().collection("config").document("maintenance").set(
            {**cfg, "updated_at": firestore.SERVER_TIMESTAMP}
        )
    except Exception as e:
        logger.warning(f"maintenance 저장 실패: {e}")
        return JSONResponse(status_code=500, content={"detail": "저장 실패"})

    user = getattr(request.state, "user", None) or {}
    logger.info(f"[admin] 점검 공지 설정 by {user.get('email', '?')}: {cfg}")
    return {"ok": True, **cfg}
