"""임시 — 관리자 UX 검증용 custom token 발급. 사용 후 삭제."""
import sys
import firebase_admin
from firebase_admin import credentials, auth

cred = credentials.Certificate("stock-search-program-firebase-adminsdk-fbsvc-739cbe9df9.json")
firebase_admin.initialize_app(cred)

email = "wogus711929@gmail.com"
try:
    user = auth.get_user_by_email(email)
    print(f"UID: {user.uid}")
    print(f"Email: {user.email}")
    print(f"Display: {user.display_name}")
    token = auth.create_custom_token(user.uid).decode("utf-8")
    print(f"TOKEN: {token}")
except auth.UserNotFoundError:
    print(f"NOT_FOUND: {email}", file=sys.stderr)
    sys.exit(2)
except Exception as e:
    print(f"ERROR: {e}", file=sys.stderr)
    sys.exit(1)
