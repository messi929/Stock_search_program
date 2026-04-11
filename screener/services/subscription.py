"""구독 서비스 — Stripe ↔ Firestore ↔ Firebase custom claims 동기화."""

import os
import stripe
from datetime import datetime, timezone
from loguru import logger

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")

STRIPE_PRICE_MONTHLY = os.environ.get("STRIPE_PRICE_MONTHLY", "")
STRIPE_PRICE_YEARLY = os.environ.get("STRIPE_PRICE_YEARLY", "")


def _users_ref():
    """Firestore users 컬렉션 참조."""
    from screener.db.firebase_client import get_db
    return get_db().collection("users")


def ensure_user_doc(uid: str, email: str) -> dict:
    """첫 로그인 시 users/{uid} 문서 생성. 이미 있으면 기존 반환."""
    ref = _users_ref().document(uid)
    doc = ref.get()
    if doc.exists:
        return doc.to_dict()

    data = {
        "email": email,
        "tier": "free",
        "created_at": datetime.now(timezone.utc),
        "stripe_customer_id": None,
        "subscription": None,
    }
    ref.set(data)
    logger.info(f"사용자 문서 생성: {uid} ({email})")
    return data


def get_or_create_stripe_customer(uid: str, email: str) -> str:
    """Firestore에서 stripe_customer_id 조회, 없으면 Stripe에서 생성."""
    ref = _users_ref().document(uid)
    doc = ref.get()
    user_data = doc.to_dict() if doc.exists else {}

    customer_id = user_data.get("stripe_customer_id")
    if customer_id:
        return customer_id

    customer = stripe.Customer.create(
        email=email,
        metadata={"firebase_uid": uid},
    )
    ref.set({"stripe_customer_id": customer.id}, merge=True)
    logger.info(f"Stripe 고객 생성: {uid} → {customer.id}")
    return customer.id


def sync_subscription_to_firebase(uid: str, subscription) -> None:
    """Stripe 구독 객체 → Firestore 저장 + Firebase custom claims 갱신."""
    from firebase_admin import auth

    status = subscription.get("status", "canceled") if isinstance(subscription, dict) else subscription.status
    is_active = status in ("active", "trialing")
    tier = "pro" if is_active else "free"

    # plan 판별
    plan = "monthly"
    if isinstance(subscription, dict):
        price_id = ""
        items = subscription.get("items", {})
        if isinstance(items, dict):
            data_list = items.get("data", [])
            if data_list:
                price_id = data_list[0].get("price", {}).get("id", "")
        period_end = subscription.get("current_period_end", 0)
        cancel_at = subscription.get("cancel_at_period_end", False)
        sub_id = subscription.get("id", "")
    else:
        price_id = subscription.items.data[0].price.id if subscription.items.data else ""
        period_end = subscription.current_period_end
        cancel_at = subscription.cancel_at_period_end
        sub_id = subscription.id

    if price_id == STRIPE_PRICE_YEARLY:
        plan = "yearly"

    sub_data = {
        "stripe_subscription_id": sub_id,
        "status": status,
        "plan": plan,
        "current_period_end": datetime.fromtimestamp(period_end, tz=timezone.utc) if period_end else None,
        "cancel_at_period_end": cancel_at,
    }

    ref = _users_ref().document(uid)
    ref.set({"tier": tier, "subscription": sub_data}, merge=True)

    # Firebase custom claims 갱신
    try:
        auth.set_custom_user_claims(uid, {"tier": tier})
        logger.info(f"티어 갱신: {uid} → {tier} (구독: {status})")
    except Exception as e:
        logger.error(f"custom claims 갱신 실패: {uid} — {e}")


def clear_subscription(uid: str) -> None:
    """구독 해지 시 tier=free로 초기화."""
    from firebase_admin import auth

    ref = _users_ref().document(uid)
    ref.set({"tier": "free", "subscription": None}, merge=True)

    try:
        auth.set_custom_user_claims(uid, {"tier": "free"})
        logger.info(f"구독 해지: {uid} → free")
    except Exception as e:
        logger.error(f"custom claims 초기화 실패: {uid} — {e}")


def get_user_subscription(uid: str) -> dict | None:
    """사용자 구독 정보 조회."""
    ref = _users_ref().document(uid)
    doc = ref.get()
    if not doc.exists:
        return None
    return doc.to_dict()
