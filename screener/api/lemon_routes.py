"""Lemon Squeezy 결제 + 구독 관리 API 라우터.

Lemon Squeezy는 Merchant of Record(MoR)로서 결제/세금/인보이스를 대행.
개인 개발자 친화적이며 한국 사업자등록 없이 해외 결제 가능.

Webhook 이벤트 처리:
  - subscription_created, subscription_updated, subscription_resumed: 구독 활성화
  - subscription_payment_success: 갱신 결제 성공
  - subscription_cancelled: 기간 종료 예약 해지 (기간 끝까지 유지)
  - subscription_expired: 구독 만료 (즉시 free 전환)
  - subscription_payment_failed: 결제 실패 (즉시 free 전환)
"""

import hashlib
import hmac
import json
import os

import httpx
from fastapi import APIRouter, Request
from loguru import logger
from starlette.responses import JSONResponse

from screener.services.subscription import (
    clear_subscription,
    ensure_user_doc,
    get_user_subscription,
    sync_subscription_to_firebase,
)

LS_API_KEY = os.environ.get("LEMONSQUEEZY_API_KEY", "")
LS_STORE_ID = os.environ.get("LEMONSQUEEZY_STORE_ID", "")
LS_VARIANT_MONTHLY = os.environ.get("LEMONSQUEEZY_VARIANT_MONTHLY", "")
LS_VARIANT_YEARLY = os.environ.get("LEMONSQUEEZY_VARIANT_YEARLY", "")
LS_WEBHOOK_SECRET = os.environ.get("LEMONSQUEEZY_WEBHOOK_SECRET", "")

LS_API = "https://api.lemonsqueezy.com/v1"

router = APIRouter(prefix="/api")


def _ls_headers() -> dict:
    return {
        "Accept": "application/vnd.api+json",
        "Content-Type": "application/vnd.api+json",
        "Authorization": f"Bearer {LS_API_KEY}",
    }


# ── 프론트엔드용 설정 ──

@router.get("/lemon-config")
async def lemon_config():
    """프론트엔드용 Lemon Squeezy 설정."""
    if not LS_API_KEY:
        return {}
    return {
        "enabled": True,
        "variantMonthly": LS_VARIANT_MONTHLY,
        "variantYearly": LS_VARIANT_YEARLY,
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

    # 미들웨어가 관리자 이메일에 pro 티어를 부여했으면 그대로 반환
    if user.get("tier") == "pro" and user.get("email"):
        from screener.middleware import ADMIN_EMAILS
        if user["email"].lower() in ADMIN_EMAILS:
            return {"tier": "pro", "subscription": {"plan": "admin", "status": "active", "current_period_end": None, "cancel_at_period_end": False}}

    data = get_user_subscription(user["uid"])
    if not data:
        return {"tier": "free", "subscription": None}

    sub = data.get("subscription")
    if sub and sub.get("current_period_end"):
        ts = sub["current_period_end"]
        if hasattr(ts, "isoformat"):
            sub["current_period_end"] = ts.isoformat()

    return {"tier": data.get("tier", "free"), "subscription": sub}


# ── Checkout 세션 생성 ──

@router.post("/checkout")
async def create_checkout(request: Request):
    """Lemon Squeezy Checkout 세션 생성 → 결제 페이지 URL 반환."""
    user = request.state.user
    if not user.get("uid"):
        return JSONResponse(status_code=401, content={"detail": "로그인 필요"})

    if not LS_API_KEY or not LS_STORE_ID:
        return JSONResponse(status_code=500, content={"detail": "결제 설정이 없습니다."})

    body = await request.json()
    plan = body.get("plan", "monthly")
    variant_id = LS_VARIANT_YEARLY if plan == "yearly" else LS_VARIANT_MONTHLY
    if not variant_id:
        return JSONResponse(status_code=500, content={"detail": "가격 설정이 없습니다."})

    origin = request.headers.get(
        "origin",
        f"{request.base_url.scheme}://{request.base_url.netloc}",
    )

    payload = {
        "data": {
            "type": "checkouts",
            "attributes": {
                "checkout_data": {
                    "email": user["email"],
                    "custom": {"firebase_uid": user["uid"]},
                },
                "product_options": {
                    "redirect_url": f"{origin}/dashboard?payment=success",
                    "receipt_button_text": "서비스로 돌아가기",
                    "receipt_link_url": f"{origin}/dashboard",
                },
                "checkout_options": {
                    "embed": False,
                    "dark": True,
                },
            },
            "relationships": {
                "store": {"data": {"type": "stores", "id": str(LS_STORE_ID)}},
                "variant": {"data": {"type": "variants", "id": str(variant_id)}},
            },
        }
    }

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.post(f"{LS_API}/checkouts", json=payload, headers=_ls_headers())
    except httpx.HTTPError as e:
        logger.error(f"LS 네트워크 오류: {e}")
        return JSONResponse(status_code=502, content={"detail": "결제 서비스 연결 실패"})

    if r.status_code >= 400:
        logger.error(f"LS checkout 생성 실패 ({r.status_code}): {r.text}")
        return JSONResponse(status_code=500, content={"detail": "결제 세션 생성 실패"})

    url = r.json().get("data", {}).get("attributes", {}).get("url")
    if not url:
        logger.error(f"LS checkout URL 누락: {r.text}")
        return JSONResponse(status_code=500, content={"detail": "결제 URL을 가져올 수 없습니다."})

    return {"url": url}


# ── 구독 해지 ──

@router.post("/subscription/cancel")
async def cancel_subscription(request: Request):
    """기간 종료 예약 해지."""
    user = request.state.user
    if not user.get("uid"):
        return JSONResponse(status_code=401, content={"detail": "로그인 필요"})

    data = get_user_subscription(user["uid"])
    sub = data.get("subscription") if data else None
    sub_id = sub.get("lemon_subscription_id") if sub else None
    if not sub_id:
        return JSONResponse(status_code=400, content={"detail": "활성 구독이 없습니다."})

    # LS: DELETE /subscriptions/{id} = 기간 종료 예약 해지
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.delete(f"{LS_API}/subscriptions/{sub_id}", headers=_ls_headers())
    except httpx.HTTPError as e:
        logger.error(f"LS 네트워크 오류: {e}")
        return JSONResponse(status_code=502, content={"detail": "결제 서비스 연결 실패"})

    if r.status_code >= 400:
        logger.error(f"LS 구독 해지 실패 ({r.status_code}): {r.text}")
        return JSONResponse(status_code=500, content={"detail": "해지 요청 실패"})

    return {"message": "구독이 기간 종료 후 해지됩니다."}


# ── 고객 포털 ──

@router.post("/billing-portal")
async def billing_portal(request: Request):
    """Lemon Squeezy 고객 포털 URL 반환 (결제수단 변경·영수증 등)."""
    user = request.state.user
    if not user.get("uid"):
        return JSONResponse(status_code=401, content={"detail": "로그인 필요"})

    data = get_user_subscription(user["uid"])
    sub = data.get("subscription") if data else None
    portal_url = sub.get("customer_portal_url") if sub else None

    # Firestore에 없으면 LS API에서 재조회
    if not portal_url:
        sub_id = sub.get("lemon_subscription_id") if sub else None
        if not sub_id:
            return JSONResponse(status_code=400, content={"detail": "결제 정보가 없습니다."})
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                r = await client.get(f"{LS_API}/subscriptions/{sub_id}", headers=_ls_headers())
            if r.status_code < 400:
                attrs = r.json().get("data", {}).get("attributes", {}) or {}
                portal_url = (attrs.get("urls") or {}).get("customer_portal")
        except httpx.HTTPError as e:
            logger.error(f"LS 네트워크 오류: {e}")

    if not portal_url:
        return JSONResponse(status_code=500, content={"detail": "고객 포털 URL을 가져올 수 없습니다."})

    return {"url": portal_url}


# ── Webhook ──

@router.post("/webhooks/lemonsqueezy")
async def webhook(request: Request):
    """LS 이벤트 수신 → Firestore/Firebase claims 동기화.

    LS는 X-Signature 헤더에 HMAC-SHA256(body, secret)의 hex를 담아 전송.
    """
    payload = await request.body()
    sig = request.headers.get("x-signature", "") or request.headers.get("X-Signature", "")

    if not LS_WEBHOOK_SECRET:
        logger.error("LEMONSQUEEZY_WEBHOOK_SECRET 미설정 — webhook 거부")
        return JSONResponse(status_code=500, content={"detail": "webhook 미설정"})

    expected = hmac.new(
        LS_WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(sig, expected):
        logger.warning("LS webhook 서명 검증 실패")
        return JSONResponse(status_code=400, content={"detail": "서명 검증 실패"})

    try:
        event = json.loads(payload)
    except json.JSONDecodeError:
        return JSONResponse(status_code=400, content={"detail": "잘못된 JSON"})

    meta = event.get("meta", {}) or {}
    event_name = meta.get("event_name", "")
    custom = meta.get("custom_data") or {}
    uid = custom.get("firebase_uid")
    data = event.get("data", {}) or {}

    logger.info(f"LS webhook 수신: {event_name} (uid={uid})")

    if not uid:
        # uid 없으면 customer_id로 역조회 (fallback)
        attrs = data.get("attributes", {}) or {}
        customer_id = str(attrs.get("customer_id", ""))
        uid = _resolve_uid_from_customer(customer_id)

    if not uid:
        logger.warning(f"LS webhook: firebase_uid 확인 불가 — 이벤트 무시 ({event_name})")
        return {"received": True}

    # 활성화·갱신 이벤트
    if event_name in (
        "subscription_created",
        "subscription_updated",
        "subscription_resumed",
        "subscription_payment_success",
        "subscription_cancelled",  # 예약 해지 — status는 active 유지, ends_at만 세팅
    ):
        sync_subscription_to_firebase(uid, data)

    # 만료·결제 실패·환불 이벤트 → 즉시 Free 강등
    elif event_name in (
        "subscription_expired",
        "subscription_payment_failed",
        "subscription_payment_refunded",  # 환불 시 Pro 박탈 (7일 환불 보장 대응)
    ):
        clear_subscription(uid)
        logger.warning(f"LS {event_name}: {uid} → free")

    return {"received": True}


def _resolve_uid_from_customer(customer_id: str) -> str | None:
    """Firestore에서 lemon_customer_id로 Firebase UID 역조회."""
    if not customer_id:
        return None
    try:
        from screener.db.firebase_client import get_db
        docs = (
            get_db()
            .collection("users")
            .where("lemon_customer_id", "==", customer_id)
            .limit(1)
            .stream()
        )
        for doc in docs:
            return doc.id
    except Exception as e:
        logger.error(f"customer_id 역조회 실패: {e}")
    return None
