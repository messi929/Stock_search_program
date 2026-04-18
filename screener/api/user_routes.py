"""사용자 프로필·세션·어뷰징 방지 API."""

from fastapi import APIRouter, Request
from starlette.responses import JSONResponse

from screener.services.security import (
    end_session,
    get_client_ip,
    heartbeat_session,
    record_login,
    register_session,
)
from screener.services.subscription import (
    _users_ref,
    check_and_expire_trial,
    ensure_user_doc,
    start_trial,
)

router = APIRouter(prefix="/api")


@router.get("/user/profile")
async def user_profile(request: Request):
    """현재 로그인 사용자의 티어/체험 상태."""
    user = request.state.user
    uid = user.get("uid", "")
    if not uid:
        return {"authenticated": False}

    email = user.get("email", "")
    email_verified = bool(user.get("email_verified", False))
    is_admin = bool(user.get("is_admin"))
    ip = get_client_ip(request)

    # 관리자는 이메일 인증/체험 로직 건너뛰고 즉시 Pro
    if is_admin:
        ensure_user_doc(uid, email, email_verified=True, ip=ip)
        return {
            "authenticated": True,
            "uid": uid,
            "email": email,
            "email_verified": True,
            "is_admin": True,
            "tier": "pro",
            "trial_active": False,
            "trial_ends_at": None,
            "trial_days_left": 0,
            "trial_started": False,
            "can_start_trial": False,
            "trial_blocked_reason": "",
        }

    data = ensure_user_doc(uid, email, email_verified=email_verified, ip=ip) or {}
    trial = check_and_expire_trial(uid) or {}

    sub = (data.get("subscription") or {})
    has_paid = sub.get("status") in ("active", "on_trial", "cancelled")
    trial_started = bool(data.get("trial_started"))
    can_start_trial = (
        email_verified
        and not trial_started
        and not has_paid
    )

    return {
        "authenticated": True,
        "uid": uid,
        "email": email,
        "email_verified": email_verified,
        "is_admin": False,
        "tier": trial.get("tier", user.get("tier", "free")),
        "trial_active": trial.get("trial_active", False),
        "trial_ends_at": trial.get("trial_ends_at"),
        "trial_days_left": trial.get("days_left", 0),
        "trial_started": trial_started,
        "can_start_trial": can_start_trial,
        "trial_blocked_reason": data.get("trial_blocked_reason", "") if not trial.get("trial_active") else "",
    }


@router.post("/user/start-trial")
async def user_start_trial(request: Request):
    """사용자가 명시적으로 7일 무료 체험 시작."""
    user = request.state.user
    uid = user.get("uid", "")
    if not uid:
        return JSONResponse(status_code=401, content={"detail": "로그인 필요"})
    if not user.get("email_verified"):
        return JSONResponse(status_code=400, content={"ok": False, "reason": "not_verified",
                                                       "detail": "이메일 인증 후 시작할 수 있습니다."})

    email = user.get("email", "")
    ip = get_client_ip(request)
    # 문서 존재 보장
    ensure_user_doc(uid, email, email_verified=True, ip=ip)
    result = start_trial(uid, email, ip)
    return result


@router.post("/auth/session-start")
async def session_start(request: Request):
    """로그인 직후 호출. IP 기록 + 동시접속 분석 + 세션 ID 발급."""
    user = request.state.user
    uid = user.get("uid", "")
    if not uid:
        return JSONResponse(status_code=401, content={"detail": "로그인 필요"})

    ip = get_client_ip(request)
    ua = request.headers.get("user-agent", "")
    record_login(uid, ip, ua)
    result = register_session(uid, ip, ua)
    return result


@router.post("/auth/heartbeat")
async def session_heartbeat(request: Request):
    """세션 활성 유지. 세션이 무효하면 logout 지시."""
    user = request.state.user
    uid = user.get("uid", "")
    body = await request.json() if request.headers.get("content-length") else {}
    sid = (body or {}).get("session_id", "")
    ok = heartbeat_session(uid, sid) if uid and sid else False
    return {"valid": ok}


@router.post("/auth/session-end")
async def session_end(request: Request):
    """로그아웃 — 세션 제거."""
    user = request.state.user
    uid = user.get("uid", "")
    body = await request.json() if request.headers.get("content-length") else {}
    sid = (body or {}).get("session_id", "")
    if uid and sid:
        end_session(uid, sid)
    return {"ok": True}


# ── 관심종목 클라우드 동기화 ──

@router.get("/user/watchlist")
async def get_user_watchlist(request: Request):
    """현재 사용자 관심종목 (클라우드 저장분)."""
    user = request.state.user
    uid = user.get("uid", "")
    if not uid:
        return {"watchlist": []}
    try:
        doc = _users_ref().document(uid).get()
        if not doc.exists:
            return {"watchlist": []}
        d = doc.to_dict() or {}
        wl = d.get("watchlist") or []
        if not isinstance(wl, list):
            wl = []
        return {"watchlist": wl}
    except Exception:
        return {"watchlist": []}


@router.post("/user/watchlist")
async def set_user_watchlist(request: Request):
    """관심종목 저장. body: {watchlist: [ticker, ...]}"""
    user = request.state.user
    uid = user.get("uid", "")
    if not uid:
        return JSONResponse(status_code=401, content={"detail": "로그인 필요"})
    body = await request.json()
    wl = body.get("watchlist", [])
    if not isinstance(wl, list):
        return JSONResponse(status_code=400, content={"detail": "watchlist는 배열"})
    # sanitize: 문자열 ticker만, 중복 제거, 최대 500개, 길이 20
    cleaned = []
    seen = set()
    for t in wl:
        s = str(t or "").strip()[:20]
        if s and s not in seen:
            seen.add(s)
            cleaned.append(s)
        if len(cleaned) >= 500:
            break
    from datetime import datetime, timezone
    _users_ref().document(uid).set({
        "watchlist": cleaned,
        "watchlist_updated_at": datetime.now(timezone.utc),
    }, merge=True)
    return {"ok": True, "count": len(cleaned)}


@router.get("/user/holdings")
async def get_user_holdings(request: Request):
    """포트폴리오 보유 종목 (클라우드 저장분)."""
    user = request.state.user
    uid = user.get("uid", "")
    if not uid:
        return {"holdings": []}
    try:
        doc = _users_ref().document(uid).get()
        if not doc.exists:
            return {"holdings": []}
        d = doc.to_dict() or {}
        hs = d.get("holdings") or []
        if not isinstance(hs, list):
            hs = []
        return {"holdings": hs}
    except Exception:
        return {"holdings": []}


@router.get("/user/meta")
async def get_user_meta(request: Request):
    """사용자 메모/태그 통합 조회 — {notes: {ticker: text}, tags: {ticker: [tag, ...]}}"""
    user = request.state.user
    uid = user.get("uid", "")
    if not uid:
        return {"notes": {}, "tags": {}}
    try:
        doc = _users_ref().document(uid).get()
        if not doc.exists:
            return {"notes": {}, "tags": {}}
        d = doc.to_dict() or {}
        meta = d.get("wl_meta") or {}
        return {
            "notes": meta.get("notes") or {},
            "tags": meta.get("tags") or {},
        }
    except Exception:
        return {"notes": {}, "tags": {}}


@router.post("/user/meta")
async def set_user_meta(request: Request):
    """메모/태그 저장. body: {notes: {ticker: text}, tags: {ticker: [tag,...]}}"""
    user = request.state.user
    uid = user.get("uid", "")
    if not uid:
        return JSONResponse(status_code=401, content={"detail": "로그인 필요"})
    body = await request.json()
    raw_notes = body.get("notes") or {}
    raw_tags = body.get("tags") or {}
    if not isinstance(raw_notes, dict) or not isinstance(raw_tags, dict):
        return JSONResponse(status_code=400, content={"detail": "notes/tags는 딕셔너리"})
    # Sanitize notes
    notes = {}
    for t, txt in list(raw_notes.items())[:500]:
        t = str(t or "").strip()[:20]
        if not t:
            continue
        txt = str(txt or "")[:2000]
        if txt.strip():
            notes[t] = txt
    # Sanitize tags
    tags = {}
    for t, arr in list(raw_tags.items())[:500]:
        t = str(t or "").strip()[:20]
        if not t or not isinstance(arr, list):
            continue
        cleaned_tags = []
        seen = set()
        for tag in arr[:20]:
            s = str(tag or "").strip().replace("<", "").replace(">", "").replace(",", "")[:20]
            if s and s not in seen:
                seen.add(s)
                cleaned_tags.append(s)
        if cleaned_tags:
            tags[t] = cleaned_tags
    from datetime import datetime, timezone
    _users_ref().document(uid).set({
        "wl_meta": {"notes": notes, "tags": tags},
        "wl_meta_updated_at": datetime.now(timezone.utc),
    }, merge=True)
    return {"ok": True, "notes": len(notes), "tags": len(tags)}


def _generate_referral_code(uid: str) -> str:
    """UID 기반 짧은 리퍼럴 코드 (8자 영숫자)."""
    import hashlib
    import string
    h = hashlib.sha256(uid.encode()).digest()
    alphabet = string.ascii_uppercase + string.digits
    # 혼동 제거 (0/O, 1/I/L)
    alphabet = alphabet.replace("0", "").replace("O", "").replace("1", "").replace("I", "").replace("L", "")
    code = "".join(alphabet[b % len(alphabet)] for b in h[:8])
    return code


@router.get("/user/referral")
async def get_referral(request: Request):
    """내 리퍼럴 코드 + 사용 현황."""
    user = request.state.user
    uid = user.get("uid", "")
    if not uid:
        return JSONResponse(status_code=401, content={"detail": "로그인 필요"})
    doc = _users_ref().document(uid).get()
    d = doc.to_dict() if doc.exists else {}
    code = d.get("referral_code")
    if not code:
        code = _generate_referral_code(uid)
        _users_ref().document(uid).set({"referral_code": code}, merge=True)
    return {
        "referral_code": code,
        "referred_count": int(d.get("referral_count", 0) or 0),
        "used_code": d.get("used_referral_code") or "",  # 가입 시 사용한 코드
    }


@router.post("/user/referral/apply")
async def apply_referral(request: Request):
    """리퍼럴 코드 사용 — 피추천인 14일 체험 추가 + 추천인 30일 추가.
    body: {code: "XXXXXXXX"}
    """
    from datetime import datetime, timedelta, timezone
    from firebase_admin import auth

    user = request.state.user
    uid = user.get("uid", "")
    if not uid:
        return JSONResponse(status_code=401, content={"detail": "로그인 필요"})

    body = await request.json()
    code = str(body.get("code", "")).strip().upper()[:12]
    if not code:
        return JSONResponse(status_code=400, content={"detail": "코드 필요"})

    # 본인 코드 차단
    if code == _generate_referral_code(uid):
        return JSONResponse(status_code=400, content={"detail": "본인 코드는 사용 불가"})

    doc = _users_ref().document(uid).get()
    d = doc.to_dict() if doc.exists else {}
    if d.get("used_referral_code"):
        return JSONResponse(status_code=400, content={"detail": "이미 리퍼럴 코드를 사용했습니다"})

    # 추천인 찾기
    try:
        referrer = list(_users_ref().where("referral_code", "==", code).limit(1).stream())
    except Exception:
        referrer = []
    if not referrer:
        return JSONResponse(status_code=404, content={"detail": "유효하지 않은 코드"})

    referrer_doc = referrer[0]
    referrer_uid = referrer_doc.id
    if referrer_uid == uid:
        return JSONResponse(status_code=400, content={"detail": "본인 코드는 사용 불가"})

    now = datetime.now(timezone.utc)

    # 피추천인: 체험 14일 추가
    me_end = d.get("trial_ends_at")
    if hasattr(me_end, "timestamp"):
        me_end = datetime.fromtimestamp(me_end.timestamp(), tz=timezone.utc)
    if not me_end or me_end < now:
        me_end = now
    new_me_end = me_end + timedelta(days=14)
    _users_ref().document(uid).set({
        "tier": "pro",
        "trial_started": True,
        "trial_ends_at": new_me_end,
        "used_referral_code": code,
        "referred_by": referrer_uid,
    }, merge=True)
    try:
        auth.set_custom_user_claims(uid, {"tier": "pro", "trial": True})
    except Exception:
        pass

    # 추천인: 체험 30일 추가 + 카운트
    ref_data = referrer_doc.to_dict()
    ref_end = ref_data.get("trial_ends_at")
    if hasattr(ref_end, "timestamp"):
        ref_end = datetime.fromtimestamp(ref_end.timestamp(), tz=timezone.utc)
    if not ref_end or ref_end < now:
        ref_end = now
    new_ref_end = ref_end + timedelta(days=30)
    _users_ref().document(referrer_uid).set({
        "tier": "pro",
        "trial_started": True,
        "trial_ends_at": new_ref_end,
        "referral_count": int(ref_data.get("referral_count", 0) or 0) + 1,
    }, merge=True)
    try:
        auth.set_custom_user_claims(referrer_uid, {"tier": "pro", "trial": True})
    except Exception:
        pass

    return {
        "ok": True,
        "you_days_added": 14,
        "you_trial_ends_at": new_me_end.isoformat(),
        "referrer_uid": referrer_uid,
    }


@router.post("/user/holdings")
async def set_user_holdings(request: Request):
    """포트폴리오 저장. body: {holdings: [{ticker,buy_price,qty}, ...]}"""
    user = request.state.user
    uid = user.get("uid", "")
    if not uid:
        return JSONResponse(status_code=401, content={"detail": "로그인 필요"})
    body = await request.json()
    hs = body.get("holdings", [])
    if not isinstance(hs, list):
        return JSONResponse(status_code=400, content={"detail": "holdings는 배열"})
    cleaned = []
    for h in hs[:200]:
        if not isinstance(h, dict):
            continue
        try:
            t = str(h.get("ticker", "")).strip()[:20]
            bp = float(h.get("buy_price", 0) or 0)
            q = int(h.get("qty", 0) or 0)
        except Exception:
            continue
        if not t or bp <= 0 or q <= 0:
            continue
        cleaned.append({"ticker": t, "buy_price": bp, "qty": q})
    from datetime import datetime, timezone
    _users_ref().document(uid).set({
        "holdings": cleaned,
        "holdings_updated_at": datetime.now(timezone.utc),
    }, merge=True)
    return {"ok": True, "count": len(cleaned)}
