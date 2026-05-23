"""관리자 본인 계정에 영구 Pro 부여 - Firebase 커스텀 클레임 + Firestore.

extend-trial는 임시 트라이얼이라, 운영자/관리자에겐 영구 Pro가 적합.

사용:
  py scripts/grant_admin_pro.py wogus711929@gmail.com
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone

from firebase_admin import auth as fb_auth

from screener.db.firebase_client import get_db


def main(email: str) -> int:
    email = email.strip().lower()
    # Firebase 초기화 - get_db 호출이 firebase_admin.initialize_app까지 수행
    db = get_db()

    try:
        user = fb_auth.get_user_by_email(email)
    except fb_auth.UserNotFoundError:
        print(f"[ERROR] 사용자 없음: {email}")
        return 1

    uid = user.uid
    print(f"[ok] uid={uid} email={user.email}")

    # 1) Firebase 커스텀 클레임: tier=pro (trial 플래그는 제거 - 영구)
    fb_auth.set_custom_user_claims(uid, {"tier": "pro"})
    print(f"[ok] custom claim set: tier=pro (trial flag 제거)")

    # 2) Firestore users/{uid}: 영구 Pro 표시 (merge로 다른 필드 보존)
    now = datetime.now(timezone.utc)
    db.collection("users").document(uid).set(
        {
            "tier": "pro",
            "subscription_status": "active",
            "admin_grant": True,
            "admin_grant_at": now,
            # 트라이얼 흔적 제거 (있을 경우 무시되고, 없으면 None 저장)
            "trial_started": False,
            "trial_ends_at": None,
        },
        merge=True,
    )
    print(f"[ok] Firestore users/{uid} 갱신 (tier=pro, subscription_status=active, admin_grant=True)")

    # 3) 토큰 강제 만료 - 다음 요청 시 새 클레임이 박힌 토큰을 발급받게.
    try:
        fb_auth.revoke_refresh_tokens(uid)
        print(f"[ok] refresh tokens revoked - 다음 요청 시 클레임 갱신 강제")
    except Exception as e:
        print(f"[warn] revoke 실패(영향 없음, 자동 갱신 시 반영됨): {e}")

    print("\n완료. 브라우저에서 로그아웃→로그인(또는 토큰 갱신) 후 Pro 권한 확인.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: py scripts/grant_admin_pro.py <email>")
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
