"""접근 제어 미들웨어 — Firebase Auth + 티어 시스템.

티어:
  free: surge, bluechip, recommend, watchlist + 기본 필터
  pro: 전체 카테고리 + 내보내기 + 알림 + 포트폴리오 + 백테스트

환경변수:
  AUTH_ENABLED: "true"로 설정 시 인증 필수 (기본: "false")
"""

import os
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from loguru import logger

AUTH_ENABLED = os.environ.get("AUTH_ENABLED", "false").lower() == "true"

# 인증 불필요 경로
PUBLIC_PATHS = {"/", "/api/status", "/api/categories", "/favicon.ico"}
PUBLIC_PREFIXES = ("/static/",)

# 무료 티어 허용 카테고리
FREE_CATEGORIES = {"surge", "bluechip", "recommend", "watchlist", "etf"}

# 유료 전용 엔드포인트
PRO_ENDPOINTS = {"/api/export", "/api/backtest", "/api/portfolio", "/api/sectors"}

# 무료 티어 결과 제한
FREE_RESULT_LIMIT = 20


def verify_firebase_token(token: str) -> dict | None:
    """Firebase ID 토큰 검증.

    Returns:
        {"uid": str, "email": str, "tier": str} or None
    """
    if not token:
        return None

    try:
        from firebase_admin import auth
        decoded = auth.verify_id_token(token)
        uid = decoded.get("uid", "")
        email = decoded.get("email", "")

        # 커스텀 클레임에서 tier 읽기 (없으면 free)
        tier = decoded.get("tier", "free")

        return {"uid": uid, "email": email, "tier": tier}
    except Exception as e:
        logger.debug(f"토큰 검증 실패: {e}")
        return None


class AuthMiddleware(BaseHTTPMiddleware):
    """Firebase Auth + 티어 접근 제어."""

    async def dispatch(self, request: Request, call_next):
        # 인증 비활성화 시 전체 허용 (개발/테스트)
        if not AUTH_ENABLED:
            request.state.user = {"uid": "", "email": "", "tier": "pro"}
            return await call_next(request)

        path = request.url.path

        # 공개 경로
        if path in PUBLIC_PATHS or any(path.startswith(p) for p in PUBLIC_PREFIXES):
            request.state.user = {"uid": "", "email": "", "tier": "free"}
            return await call_next(request)

        # WebSocket은 쿼리 파라미터로 토큰 전달
        if path == "/api/ws":
            request.state.user = {"uid": "", "email": "", "tier": "free"}
            return await call_next(request)

        # Authorization 헤더에서 토큰 추출
        auth_header = request.headers.get("Authorization", "")
        token = ""
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]

        user = verify_firebase_token(token)

        if not user:
            # 미인증 → free 티어로 제한 접근 허용
            user = {"uid": "", "email": "", "tier": "free"}

        request.state.user = user
        tier = user["tier"]

        # Pro 전용 엔드포인트
        if path in PRO_ENDPOINTS and tier != "pro":
            return JSONResponse(
                status_code=403,
                content={"detail": "Pro 기능입니다. 업그레이드해주세요.", "upgrade": True},
            )

        # 무료 티어: 카테고리 제한
        if tier == "free" and path == "/api/scan":
            category = request.query_params.get("category", "surge")
            if category not in FREE_CATEGORIES:
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": f"'{category}'은(는) Pro 기능입니다.",
                        "upgrade": True,
                        "free_categories": list(FREE_CATEGORIES),
                    },
                )

        response = await call_next(request)
        return response
