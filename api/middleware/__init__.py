"""Axis 인증/권한 — screener.middleware 재사용 진입점.

신규 미들웨어를 만들지 않고 기존 v7.5 인프라를 그대로 사용합니다.
Axis 라우트는 screener/main.py에 마운트되므로 AuthMiddleware가 자동 적용됩니다.
"""

from screener.middleware import AuthMiddleware, verify_firebase_token

__all__ = ["AuthMiddleware", "verify_firebase_token"]
