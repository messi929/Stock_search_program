"""카카오 OAuth 로그인 — Firebase Custom Token 발급.

Firebase는 카카오를 native 지원하지 않으므로 custom token 흐름을 쓴다:
  1) 프론트가 카카오 인가 페이지로 보내 인가코드(code)를 받음
  2) 프론트가 code를 이 엔드포인트로 POST
  3) 백엔드가 카카오 토큰·사용자정보 조회 → Firebase Admin으로 custom token 발급
  4) 프론트가 signInWithCustomToken(auth, token)로 Firebase 세션 생성

환경변수:
  KAKAO_REST_API_KEY  — 카카오 디벨로퍼 앱 REST API 키 (필수, 없으면 503)
  KAKAO_CLIENT_SECRET — (선택) 카카오 앱 보안 → client secret 사용 설정 시 필수
"""

import os

import httpx
from loguru import logger

from fastapi import APIRouter, Request
from starlette.responses import JSONResponse

router = APIRouter(prefix="/api/auth")

KAKAO_TOKEN_URL = "https://kauth.kakao.com/oauth/token"
KAKAO_USER_URL = "https://kapi.kakao.com/v2/user/me"


@router.post("/kakao")
async def kakao_login(request: Request):
    """카카오 인가코드 → Firebase Custom Token 교환."""
    rest_key = os.environ.get("KAKAO_REST_API_KEY", "")
    if not rest_key:
        # 키 미설정 = 기능 비활성. 프론트는 버튼을 "준비 중"으로 둠.
        return JSONResponse(
            status_code=503,
            content={"detail": "카카오 로그인이 아직 활성화되지 않았습니다."},
        )

    try:
        body = await request.json()
    except Exception:
        body = {}
    code = (body or {}).get("code", "")
    redirect_uri = (body or {}).get("redirect_uri", "")
    if not code or not redirect_uri:
        return JSONResponse(
            status_code=400,
            content={"detail": "code·redirect_uri가 필요합니다."},
        )

    token_data = {
        "grant_type": "authorization_code",
        "client_id": rest_key,
        "redirect_uri": redirect_uri,
        "code": code,
    }
    client_secret = os.environ.get("KAKAO_CLIENT_SECRET", "")
    if client_secret:
        token_data["client_secret"] = client_secret

    # 1) 인가코드 → 카카오 access_token, 2) access_token → 사용자 정보
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            tok = await client.post(
                KAKAO_TOKEN_URL,
                data=token_data,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded;charset=utf-8"
                },
            )
            if tok.status_code != 200:
                logger.warning(f"[kakao] token 실패 {tok.status_code}: {tok.text[:200]}")
                return JSONResponse(
                    status_code=401,
                    content={"detail": "카카오 인증에 실패했습니다. 다시 시도해주세요."},
                )
            access_token = tok.json().get("access_token", "")
            if not access_token:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "카카오 토큰을 받지 못했습니다."},
                )

            me = await client.get(
                KAKAO_USER_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if me.status_code != 200:
                logger.warning(f"[kakao] user 실패 {me.status_code}: {me.text[:200]}")
                return JSONResponse(
                    status_code=401,
                    content={"detail": "카카오 사용자 정보를 가져오지 못했습니다."},
                )
            me_json = me.json()
    except Exception as e:
        logger.error(f"[kakao] 외부 호출 오류: {type(e).__name__}: {e}")
        return JSONResponse(status_code=502, content={"detail": "카카오 서버 통신 오류"})

    kakao_id = me_json.get("id")
    if not kakao_id:
        return JSONResponse(
            status_code=401, content={"detail": "카카오 ID를 확인할 수 없습니다."}
        )

    account = me_json.get("kakao_account", {}) or {}
    profile = account.get("profile", {}) or {}
    # 이메일 동의를 안 한 사용자는 빈 값(선택 동의 항목).
    email = account.get("email", "") if account.get("is_email_valid", True) else ""
    nickname = profile.get("nickname", "")

    # Google(자동 uid)과 분리하기 위해 카카오는 "kakao:{id}" 네임스페이스 uid.
    uid = f"kakao:{kakao_id}"

    from firebase_admin import auth as fb_auth

    # Firebase Auth 레코드 동기화(없으면 생성). custom token 발급에 필수는 아니나
    # 계정 관리·삭제(/api/user/account) 일관성을 위해 생성해 둔다.
    try:
        try:
            fb_auth.update_user(uid, **({"display_name": nickname} if nickname else {}))
        except fb_auth.UserNotFoundError:
            fb_auth.create_user(uid=uid, display_name=nickname or None)
    except Exception as e:
        logger.warning(
            f"[kakao] user record 동기화 실패(uid={uid}): {type(e).__name__}: {e}"
        )

    # ID 토큰에 email/provider가 실리도록 developer claims에 포함
    # (미들웨어가 email로 ADMIN_EMAILS·tier 판정).
    claims = {"provider": "kakao"}
    if email:
        claims["email"] = email

    try:
        custom_token = fb_auth.create_custom_token(uid, claims)
    except Exception as e:
        logger.error(f"[kakao] custom token 발급 실패(uid={uid}): {type(e).__name__}: {e}")
        return JSONResponse(
            status_code=500, content={"detail": "로그인 토큰 발급에 실패했습니다."}
        )

    logger.info(f"[kakao] 로그인 성공 uid={uid} email={email or '-'}")
    token_str = (
        custom_token.decode("utf-8")
        if isinstance(custom_token, bytes)
        else custom_token
    )
    return {"token": token_str, "email": email, "nickname": nickname}
