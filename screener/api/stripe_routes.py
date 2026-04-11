"""Stripe 결제 + 구독 관리 API 라우터."""

import os
import stripe
from fastapi import APIRouter, Request
from starlette.responses import JSONResponse
from loguru import logger

from screener.services.subscription import (
    ensure_user_doc,
    get_or_create_stripe_customer,
    sync_subscription_to_firebase,
    clear_subscription,
    get_user_subscription,
)

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_PRICE_MONTHLY = os.environ.get("STRIPE_PRICE_MONTHLY", "")
STRIPE_PRICE_YEARLY = os.environ.get("STRIPE_PRICE_YEARLY", "")

router = APIRouter(prefix="/api")


# ── Stripe 설정 (프론트에서 참조) ──

@router.get("/stripe-config")
async def stripe_config():
    """프론트엔드용 Stripe publishable key + 가격 ID."""
    if not STRIPE_PUBLISHABLE_KEY:
        return {}
    return {
        "publishableKey": STRIPE_PUBLISHABLE_KEY,
        "priceMonthly": STRIPE_PRICE_MONTHLY,
        "priceYearly": STRIPE_PRICE_YEARLY,
    }


# ── 사용자 문서 초기화 ──

@router.post("/user/init")
async def init_user(request: Request):
    """첫 로그인 시 Firestore 사용자 문서 생성."""
    user = request.state.user
    if not user.get("uid"):
        return JSONResponse(status_code=401, content={"detail": "로그인 필요"})
    data = ensure_user_doc(user["uid"], user["email"])
    return {"tier": data.get("tier", "free")}


# ── 구독 조회 ──

@router.get("/subscription")
async def get_subscription(request: Request):
    """현재 사용자의 구독 정보."""
    user = request.state.user
    if not user.get("uid"):
        return JSONResponse(status_code=401, content={"detail": "로그인 필요"})

    data = get_user_subscription(user["uid"])
    if not data:
        return {"tier": "free", "subscription": None}

    sub = data.get("subscription")
    # Firestore timestamp → ISO string 변환
    if sub and sub.get("current_period_end"):
        ts = sub["current_period_end"]
        if hasattr(ts, "isoformat"):
            sub["current_period_end"] = ts.isoformat()

    return {"tier": data.get("tier", "free"), "subscription": sub}


# ── Checkout 세션 생성 ──

@router.post("/checkout")
async def create_checkout(request: Request):
    """Stripe Checkout 세션 생성 → 결제 페이지 URL 반환."""
    user = request.state.user
    if not user.get("uid"):
        return JSONResponse(status_code=401, content={"detail": "로그인 필요"})

    body = await request.json()
    plan = body.get("plan", "monthly")

    price_id = STRIPE_PRICE_YEARLY if plan == "yearly" else STRIPE_PRICE_MONTHLY
    if not price_id:
        return JSONResponse(status_code=500, content={"detail": "가격 설정이 없습니다."})

    customer_id = get_or_create_stripe_customer(user["uid"], user["email"])

    # 기존 base_url 추출 (프론트에서 돌아올 URL)
    origin = request.headers.get("origin", request.base_url.scheme + "://" + request.base_url.netloc)

    session = stripe.checkout.Session.create(
        customer=customer_id,
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=f"{origin}/?payment=success",
        cancel_url=f"{origin}/?payment=cancel",
        metadata={"firebase_uid": user["uid"]},
        locale="ko",
    )
    return {"url": session.url}


# ── 구독 해지 ──

@router.post("/subscription/cancel")
async def cancel_subscription(request: Request):
    """구독을 기간 종료 시 해지 설정."""
    user = request.state.user
    if not user.get("uid"):
        return JSONResponse(status_code=401, content={"detail": "로그인 필요"})

    data = get_user_subscription(user["uid"])
    sub = data.get("subscription") if data else None
    if not sub or not sub.get("stripe_subscription_id"):
        return JSONResponse(status_code=400, content={"detail": "활성 구독이 없습니다."})

    stripe.Subscription.modify(
        sub["stripe_subscription_id"],
        cancel_at_period_end=True,
    )
    return {"message": "구독이 기간 종료 후 해지됩니다."}


# ── Stripe 고객 포털 ──

@router.post("/billing-portal")
async def billing_portal(request: Request):
    """Stripe 고객 포털 세션 → URL 반환."""
    user = request.state.user
    if not user.get("uid"):
        return JSONResponse(status_code=401, content={"detail": "로그인 필요"})

    data = get_user_subscription(user["uid"])
    customer_id = data.get("stripe_customer_id") if data else None
    if not customer_id:
        return JSONResponse(status_code=400, content={"detail": "결제 정보가 없습니다."})

    origin = request.headers.get("origin", request.base_url.scheme + "://" + request.base_url.netloc)
    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=origin,
    )
    return {"url": session.url}


# ── Stripe Webhook ──

@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request):
    """Stripe 이벤트 수신 → Firestore/Firebase claims 동기화."""
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
    except stripe.SignatureVerificationError:
        logger.warning("Stripe webhook 서명 검증 실패")
        return JSONResponse(status_code=400, content={"detail": "서명 검증 실패"})
    except Exception as e:
        logger.error(f"Stripe webhook 처리 오류: {e}")
        return JSONResponse(status_code=400, content={"detail": str(e)})

    event_type = event["type"]
    data_obj = event["data"]["object"]

    logger.info(f"Stripe webhook 수신: {event_type}")

    if event_type == "checkout.session.completed":
        uid = data_obj.get("metadata", {}).get("firebase_uid")
        sub_id = data_obj.get("subscription")
        if uid and sub_id:
            subscription = stripe.Subscription.retrieve(sub_id)
            sync_subscription_to_firebase(uid, subscription)

    elif event_type in ("customer.subscription.updated", "customer.subscription.deleted"):
        # 고객 metadata에서 uid 추출
        customer_id = data_obj.get("customer")
        uid = _resolve_uid_from_customer(customer_id)
        if uid:
            if event_type == "customer.subscription.deleted":
                clear_subscription(uid)
            else:
                sync_subscription_to_firebase(uid, data_obj)

    elif event_type == "invoice.payment_failed":
        customer_id = data_obj.get("customer")
        uid = _resolve_uid_from_customer(customer_id)
        if uid:
            clear_subscription(uid)
            logger.warning(f"결제 실패로 구독 해제: {uid}")

    return {"received": True}


def _resolve_uid_from_customer(customer_id: str) -> str | None:
    """Stripe customer_id로 Firebase UID 조회."""
    if not customer_id:
        return None
    try:
        customer = stripe.Customer.retrieve(customer_id)
        return customer.get("metadata", {}).get("firebase_uid")
    except Exception:
        return None
