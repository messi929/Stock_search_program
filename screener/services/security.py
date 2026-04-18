"""계정 어뷰징 방지 — IP/세션 추적 + Trial 악용 감지.

동시접속 감지 + 월 unique IP 한도 초과 시 자동 플래그.
이메일 정규화 + 일회용 도메인 차단 + IP당 trial 1회 제한.
"""

import hashlib
import os
import uuid
from datetime import datetime, timedelta, timezone

from loguru import logger

# 일회용 메일 서비스 (대표 100개 + 키워드 매칭)
DISPOSABLE_DOMAINS = {
    "tempmail.com", "temp-mail.org", "temp-mail.io", "tempail.com",
    "10minutemail.com", "10minutemail.net", "10minutemail.co.uk",
    "guerrillamail.com", "guerrillamail.info", "guerrillamail.biz", "grr.la",
    "mailinator.com", "mailinator.net", "mailinator2.com", "mailnesia.com",
    "throwaway.email", "throwawaymail.com", "throwawaymailgenerator.com",
    "yopmail.com", "yopmail.net", "yopmail.fr",
    "trashmail.com", "trashmail.de", "trashmail.net", "trashmail.me",
    "maildrop.cc", "mailnull.com", "sharklasers.com", "getnada.com",
    "spam4.me", "spamgourmet.com", "fakeinbox.com", "burnermail.io",
    "dispostable.com", "discard.email", "mohmal.com", "emailondeck.com",
    "tempinbox.com", "tempmailo.com", "tempr.email", "tempemail.net",
    "minutemail.com", "mailtemp.info", "mailcatch.com", "mytemp.email",
    "airmail.cc", "getairmail.com", "mvrht.com", "inboxbear.com",
    "boun.cr", "mt2014.com", "mt2015.com", "mailexpire.com",
    "anonmail.me", "anonbox.net", "fakemail.net", "fakermail.com",
    "harakirimail.com", "mailbox.in.ua", "sbox.live", "sogetthis.com",
    "tempmailaddress.com", "temp-mail.ru", "tempmail.us", "tempymail.com",
    "mailnesia.com", "mailsac.com", "mailzilla.com", "moakt.cc",
    "moakt.com", "mytrashmail.com", "nowmymail.com", "proxymail.eu",
    "rcpt.at", "safetymail.info", "selfdestructingmail.com",
    "tempinbox.co.uk", "vomoto.com", "wegwerfmail.de", "wegwerfmail.net",
    "wh4f.org", "whyspam.me", "willselfdestruct.com", "wronghead.com",
    "fakeinformation.com", "jetable.org", "noclickemail.com",
    "no-spam.ws", "spamhereplease.com", "spamslicer.com", "sroff.com",
    "trash-mail.at", "tyldd.com", "kurzepost.de", "objectmail.com",
    "receiveee.com", "rmqkr.net", "tempmailer.de", "tempsky.com",
    "emailfake.com", "emailfake.info", "emailfake.net",
}
DISPOSABLE_KEYWORDS = (
    "tempmail", "tempemail", "10minute", "disposable", "throwaway",
    "trashmail", "wegwerf", "selfdestruct", "mailnull", "anon-mail",
)

MAX_ACTIVE_SESSIONS = int(os.environ.get("MAX_ACTIVE_SESSIONS", "2"))  # 동시 접속 허용
UNIQUE_IP_WARN = int(os.environ.get("UNIQUE_IP_WARN", "4"))   # 월 unique IP 경고선
UNIQUE_IP_FLAG = int(os.environ.get("UNIQUE_IP_FLAG", "5"))   # 월 unique IP 플래그선 (의심)
SESSION_STALE_MIN = 15  # 분. heartbeat 끊긴 세션 자동 정리


def _users_ref():
    from screener.db.firebase_client import get_db
    return get_db().collection("users")


def _trial_ips_ref():
    """Trial 부여 이력 (IP·이메일 기반)."""
    from screener.db.firebase_client import get_db
    return get_db().collection("trial_ips")


def _hash_ip(ip: str) -> str:
    """IP 해시 (저장은 해시로, 분석은 원본으로 비교 시 같은 IP 같은 해시)."""
    return hashlib.sha256(ip.encode()).hexdigest()[:16]


def is_disposable_email(email: str) -> bool:
    """일회용 메일 도메인 감지."""
    if not email or "@" not in email:
        return False
    domain = email.lower().split("@")[-1].strip()
    if domain in DISPOSABLE_DOMAINS:
        return True
    return any(kw in domain for kw in DISPOSABLE_KEYWORDS)


def normalize_email(email: str) -> str:
    """Gmail +alias/점 제거 등 이메일 정규화.

    - Gmail/Googlemail: 점 제거 + +alias 제거, googlemail.com → gmail.com
    - 기타: +alias 제거 (대부분 공급자가 alias로 취급)
    - 소문자 통일
    """
    if not email or "@" not in email:
        return (email or "").strip().lower()
    email = email.strip().lower()
    local, domain = email.split("@", 1)
    if domain in ("gmail.com", "googlemail.com"):
        local = local.split("+")[0].replace(".", "")
        domain = "gmail.com"
    else:
        local = local.split("+")[0]
    return f"{local}@{domain}"


def check_trial_abuse(uid: str, email: str, ip: str) -> dict:
    """Trial 부여 전 악용 여부 체크.

    Returns:
        {"grant_trial": bool, "reason": str}
        - reason: ok | disposable_email | duplicate_email | ip_limit
    """
    norm = normalize_email(email)

    # 1. 일회용 도메인
    if is_disposable_email(email):
        return {"grant_trial": False, "reason": "disposable_email"}

    # 2. 정규화 이메일 중복 (이미 trial 받은 계정 존재)
    try:
        existing = _users_ref().where("normalized_email", "==", norm).limit(2).stream()
        others = [d for d in existing if d.id != uid]
        if others:
            return {"grant_trial": False, "reason": "duplicate_email"}
    except Exception as e:
        logger.debug(f"정규화 이메일 조회 실패: {e}")

    # 3. 24시간 내 같은 IP로 다른 계정이 trial 받았는지
    if ip:
        ip_h = _hash_ip(ip)
        day_ago = datetime.now(timezone.utc) - timedelta(hours=24)
        try:
            recent = _trial_ips_ref().where("ip_hash", "==", ip_h).where("created_at", ">=", day_ago).limit(5).stream()
            for d in recent:
                data = d.to_dict() or {}
                if data.get("uid") and data.get("uid") != uid:
                    return {"grant_trial": False, "reason": "ip_limit"}
        except Exception as e:
            logger.debug(f"trial_ips 조회 실패: {e}")

    return {"grant_trial": True, "reason": "ok"}


def record_trial_grant(uid: str, email: str, ip: str) -> None:
    """Trial 부여 기록 — IP·정규화 이메일 저장."""
    try:
        _trial_ips_ref().add({
            "uid": uid,
            "email": email,
            "normalized_email": normalize_email(email),
            "ip_hash": _hash_ip(ip) if ip else "",
            "created_at": datetime.now(timezone.utc),
        })
    except Exception as e:
        logger.debug(f"trial_ips 기록 실패: {e}")


def record_login(uid: str, ip: str, user_agent: str) -> None:
    """로그인 시 이력 기록 (login_history 서브컬렉션)."""
    if not uid or not ip:
        return
    try:
        ref = _users_ref().document(uid).collection("login_history").document()
        ref.set({
            "ip": ip,
            "ip_hash": _hash_ip(ip),
            "user_agent": (user_agent or "")[:300],
            "timestamp": datetime.now(timezone.utc),
        })
    except Exception as e:
        logger.debug(f"login history 저장 실패: {e}")


def register_session(uid: str, ip: str, user_agent: str) -> dict:
    """활성 세션 등록 + 동시접속/IP 변경 분석.

    Returns:
        {"session_id": str, "concurrent": int, "unique_ips_30d": int,
         "warning": str | None, "forced_others_out": bool}
    """
    if not uid:
        return {"session_id": "", "concurrent": 0, "unique_ips_30d": 0,
                "warning": None, "forced_others_out": False}

    sid = uuid.uuid4().hex
    now = datetime.now(timezone.utc)
    stale_before = now - timedelta(minutes=SESSION_STALE_MIN)

    sessions_col = _users_ref().document(uid).collection("active_sessions")
    try:
        # 만료 세션 정리
        stale_docs = sessions_col.where("last_seen", "<", stale_before).stream()
        for d in stale_docs:
            d.reference.delete()

        # 현재 활성 세션
        current = list(sessions_col.stream())
        forced_out = False

        # 동시접속 초과 시 오래된 세션 제거
        if len(current) >= MAX_ACTIVE_SESSIONS:
            current.sort(key=lambda d: d.to_dict().get("last_seen") or now)
            to_kill = len(current) - MAX_ACTIVE_SESSIONS + 1
            for d in current[:to_kill]:
                d.reference.delete()
            forced_out = True

        sessions_col.document(sid).set({
            "ip": ip,
            "ip_hash": _hash_ip(ip),
            "user_agent": (user_agent or "")[:300],
            "created_at": now,
            "last_seen": now,
        })

        # 30일 내 unique IP 개수
        since = now - timedelta(days=30)
        hist = _users_ref().document(uid).collection("login_history").where("timestamp", ">=", since).stream()
        ip_hashes = {d.to_dict().get("ip_hash") for d in hist if d.to_dict().get("ip_hash")}
        unique_n = len(ip_hashes)

        warning = None
        if unique_n >= UNIQUE_IP_FLAG:
            # 의심 플래그 세팅
            try:
                _users_ref().document(uid).set({"suspicious": True}, merge=True)
            except Exception:
                pass
            warning = f"이 계정은 최근 30일간 {unique_n}개 IP에서 사용되었습니다. 공유 의심 시 관리자가 검토할 수 있습니다."
        elif unique_n >= UNIQUE_IP_WARN:
            warning = f"여러 위치에서 로그인 감지 (최근 30일 {unique_n}곳). 본인 외 사용 시 비밀번호를 변경해주세요."

        concurrent_after = len(list(sessions_col.stream()))
        return {
            "session_id": sid,
            "concurrent": concurrent_after,
            "unique_ips_30d": unique_n,
            "warning": warning,
            "forced_others_out": forced_out,
        }
    except Exception as e:
        logger.error(f"세션 등록 실패 uid={uid}: {e}")
        return {"session_id": sid, "concurrent": 1, "unique_ips_30d": 0,
                "warning": None, "forced_others_out": False}


def heartbeat_session(uid: str, sid: str) -> bool:
    """세션 활성 유지 (주기 호출). 세션 없으면 False 반환 → 클라이언트 로그아웃."""
    if not uid or not sid:
        return False
    try:
        ref = _users_ref().document(uid).collection("active_sessions").document(sid)
        doc = ref.get()
        if not doc.exists:
            return False
        ref.set({"last_seen": datetime.now(timezone.utc)}, merge=True)
        return True
    except Exception as e:
        logger.debug(f"heartbeat 실패: {e}")
        return False


def end_session(uid: str, sid: str) -> None:
    """로그아웃 — 세션 제거."""
    if not uid or not sid:
        return
    try:
        _users_ref().document(uid).collection("active_sessions").document(sid).delete()
    except Exception:
        pass


def get_client_ip(request) -> str:
    """프록시 경유 실제 IP 추출."""
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else ""
