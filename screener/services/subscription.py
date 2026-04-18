"""구독 서비스 — Lemon Squeezy ↔ Firestore ↔ Firebase custom claims 동기화.

LS 구독 객체 구조 (webhook/API 공통):
  {"type": "subscriptions", "id": "...",
   "attributes": {
     "status": "active|on_trial|paused|past_due|unpaid|cancelled|expired",
     "variant_id": int,
     "customer_id": int,
     "renews_at": ISO8601 | null,
     "ends_at": ISO8601 | null,  # 해지 예약 또는 만료 시점
     "urls": {"customer_portal": "...", "update_payment_method": "..."}
   }}
"""

import os
from datetime import datetime, timedelta, timezone

from loguru import logger

LS_VARIANT_MONTHLY = os.environ.get("LEMONSQUEEZY_VARIANT_MONTHLY", "")
LS_VARIANT_YEARLY = os.environ.get("LEMONSQUEEZY_VARIANT_YEARLY", "")
TRIAL_DAYS = int(os.environ.get("TRIAL_DAYS", "7"))


def _users_ref():
    """Firestore users 컬렉션 참조."""
    from screener.db.firebase_client import get_db
    return get_db().collection("users")


def ensure_user_doc(uid: str, email: str, email_verified: bool = True, ip: str = "") -> dict:
    """첫 로그인 시 users/{uid} 문서 생성. 가입 시점엔 trial 부여 안함.

    Trial은 사용자가 `start_trial()` 을 명시적으로 호출해야 시작됨.
    """
    import hashlib

    from screener.services.security import normalize_email

    ref = _users_ref().document(uid)
    doc = ref.get()
    now = datetime.now(timezone.utc)
    norm = normalize_email(email)

    if doc.exists:
        d = doc.to_dict()
        patch = {}
        if email_verified and not d.get("email_verified"):
            patch["email_verified"] = True
        if not d.get("normalized_email"):
            patch["normalized_email"] = norm
        if patch:
            ref.set(patch, merge=True)
            d.update(patch)
        return d

    # 관리자 이메일이면 즉시 Pro (인증/체험 로직 우회)
    from screener.middleware import ADMIN_EMAILS
    is_admin_email = (email or "").lower() in ADMIN_EMAILS

    # 신규 사용자 — tier=free로 생성, trial은 별도 start_trial() 호출로 시작
    data = {
        "email": email,
        "normalized_email": norm,
        "email_verified": True if is_admin_email else bool(email_verified),
        "tier": "pro" if is_admin_email else "free",
        "created_at": now,
        "trial_started": False,
        "trial_ends_at": None,
        "trial_claimed_at": None,
        "trial_blocked_reason": "",
        "signup_ip_hash": hashlib.sha256(ip.encode()).hexdigest()[:16] if ip else "",
        "lemon_customer_id": None,
        "subscription": None,
        "suspended": False,
        "suspicious": False,
        "admin_note": "admin" if is_admin_email else "",
        "is_admin_role": is_admin_email,
    }
    ref.set(data)
    logger.info(f"사용자 생성 (tier={'pro(admin)' if is_admin_email else 'free'}): {uid} ({email})")
    return data


def start_trial(uid: str, email: str, ip: str) -> dict:
    """사용자가 명시적으로 7일 무료 체험 시작.

    악용 체크 (일회용 메일 / 정규화 이메일 중복 / 24h IP 중복) 후 부여.

    Returns:
        {"ok": bool, "reason": str, "trial_ends_at": iso | None, "days_left": int}
        reason: ok | already_pro | already_used | not_verified | disposable_email | duplicate_email | ip_limit
    """
    from firebase_admin import auth
    from screener.services.security import (
        check_trial_abuse, normalize_email, record_trial_grant,
    )

    ref = _users_ref().document(uid)
    doc = ref.get()
    if not doc.exists:
        return {"ok": False, "reason": "no_user", "trial_ends_at": None, "days_left": 0}

    d = doc.to_dict()
    sub = d.get("subscription") or {}
    # 이미 Pro (유료 구독)
    if sub and sub.get("status") in ("active", "on_trial", "cancelled"):
        return {"ok": False, "reason": "already_pro", "trial_ends_at": None, "days_left": 0}
    # 이미 trial 사용
    if d.get("trial_started"):
        return {"ok": False, "reason": "already_used", "trial_ends_at": None, "days_left": 0}
    # 이메일 미인증
    if not d.get("email_verified"):
        return {"ok": False, "reason": "not_verified", "trial_ends_at": None, "days_left": 0}

    abuse = check_trial_abuse(uid, email, ip)
    if not abuse["grant_trial"]:
        ref.set({"trial_blocked_reason": abuse["reason"]}, merge=True)
        return {"ok": False, "reason": abuse["reason"], "trial_ends_at": None, "days_left": 0}

    now = datetime.now(timezone.utc)
    trial_end = now + timedelta(days=TRIAL_DAYS)
    ref.set({
        "tier": "pro",
        "trial_started": True,
        "trial_claimed_at": now,
        "trial_ends_at": trial_end,
        "trial_blocked_reason": "",
    }, merge=True)
    try:
        auth.set_custom_user_claims(uid, {"tier": "pro", "trial": True})
    except Exception as e:
        logger.error(f"start_trial claims 실패: {uid} — {e}")
    record_trial_grant(uid, email, ip)
    logger.info(f"trial 시작: {uid} ({email}) → {trial_end.isoformat()}")
    return {
        "ok": True,
        "reason": "ok",
        "trial_ends_at": trial_end.isoformat(),
        "days_left": TRIAL_DAYS,
    }


def check_and_expire_trial(uid: str) -> dict | None:
    """현재 사용자 trial 상태 확인. 만료됐으면 free로 전환.

    Returns:
        {"trial_active": bool, "trial_ends_at": iso, "days_left": int, "tier": str}
    """
    from firebase_admin import auth

    ref = _users_ref().document(uid)
    doc = ref.get()
    if not doc.exists:
        return None

    d = doc.to_dict()
    trial_end = d.get("trial_ends_at")
    if hasattr(trial_end, "timestamp"):  # Firestore Timestamp
        trial_end = datetime.fromtimestamp(trial_end.timestamp(), tz=timezone.utc)
    now = datetime.now(timezone.utc)

    has_paid_sub = d.get("subscription") and (d.get("subscription") or {}).get("status") in ("active", "on_trial", "cancelled")

    if not trial_end or has_paid_sub:
        return {
            "trial_active": False,
            "trial_ends_at": None,
            "days_left": 0,
            "tier": d.get("tier", "free"),
        }

    if now < trial_end:
        return {
            "trial_active": True,
            "trial_ends_at": trial_end.isoformat(),
            "days_left": max(0, (trial_end - now).days + (1 if (trial_end - now).seconds > 0 else 0)),
            "tier": "pro",
        }

    # 만료 처리
    if d.get("tier") == "pro" and not has_paid_sub:
        ref.set({"tier": "free"}, merge=True)
        try:
            auth.set_custom_user_claims(uid, {"tier": "free", "trial": False})
        except Exception as e:
            logger.error(f"trial 만료 claims 실패: {uid} — {e}")
        logger.info(f"trial 만료 → free: {uid}")
    return {
        "trial_active": False,
        "trial_ends_at": trial_end.isoformat(),
        "days_left": 0,
        "tier": "free",
    }


def _parse_iso(ts):
    """ISO8601 문자열 → datetime (UTC)."""
    if not ts:
        return None
    if hasattr(ts, "isoformat"):  # 이미 datetime
        return ts
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except Exception:
        return None


def sync_subscription_to_firebase(uid: str, data: dict) -> None:
    """LS subscription data → Firestore + Firebase custom claims.

    Args:
        uid: Firebase UID
        data: LS subscription 객체 (webhook event.data 또는 API 응답의 data)
    """
    from firebase_admin import auth

    sub_id = str(data.get("id", ""))
    attrs = data.get("attributes", {}) or {}

    status = attrs.get("status", "cancelled")
    # LS 활성 상태: active, on_trial (cancelled는 ends_at까지 pro 유지 — 별도 처리)
    is_active = status in ("active", "on_trial", "cancelled")
    tier = "pro" if is_active else "free"

    variant_id = str(attrs.get("variant_id", ""))
    plan = "yearly" if variant_id == LS_VARIANT_YEARLY else "monthly"

    renews_at = _parse_iso(attrs.get("renews_at"))
    ends_at = _parse_iso(attrs.get("ends_at"))
    period_end = ends_at or renews_at  # 해지 예약 시 ends_at 우선

    customer_id = str(attrs.get("customer_id", ""))
    urls = attrs.get("urls") or {}
    portal_url = urls.get("customer_portal", "")

    sub_data = {
        "lemon_subscription_id": sub_id,
        "lemon_customer_id": customer_id,
        "status": status,
        "plan": plan,
        "variant_id": variant_id,
        "current_period_end": period_end,
        "cancel_at_period_end": bool(ends_at) and status in ("active", "on_trial", "cancelled"),
        "customer_portal_url": portal_url,
    }

    ref = _users_ref().document(uid)
    ref.set(
        {"tier": tier, "lemon_customer_id": customer_id, "subscription": sub_data},
        merge=True,
    )

    try:
        auth.set_custom_user_claims(uid, {"tier": tier})
        logger.info(f"티어 갱신: {uid} → {tier} (plan={plan}, status={status})")
    except Exception as e:
        logger.error(f"custom claims 갱신 실패: {uid} — {e}")


def clear_subscription(uid: str) -> None:
    """구독 만료/결제 실패 시 tier=free로 초기화."""
    from firebase_admin import auth

    ref = _users_ref().document(uid)
    ref.set({"tier": "free", "subscription": None}, merge=True)

    try:
        auth.set_custom_user_claims(uid, {"tier": "free"})
        logger.info(f"구독 만료: {uid} → free")
    except Exception as e:
        logger.error(f"custom claims 초기화 실패: {uid} — {e}")


def get_user_subscription(uid: str) -> dict | None:
    """사용자 구독 정보 조회."""
    ref = _users_ref().document(uid)
    doc = ref.get()
    if not doc.exists:
        return None
    return doc.to_dict()
