"""Firebase/Firestore 클라이언트 초기화.

인증 우선순위:
  1. FIREBASE_CREDENTIALS 환경변수 (JSON 문자열) — Cloud Run 등 컨테이너 환경
  2. FIREBASE_KEY_PATH 환경변수 (파일 경로)
  3. 프로젝트 루트 *-adminsdk-*.json 자동 탐색 — 로컬 개발
  4. Google Cloud 기본 인증 (ADC) — GCP 환경에서 키 없이 동작
"""

import json
import os
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, firestore
from loguru import logger

_db = None


def get_db():
    """Firestore 클라이언트 반환 (싱글톤)."""
    global _db
    if _db is not None:
        return _db

    cred = None

    # 1) 환경변수 JSON 문자열 (Cloud Run Secret 등)
    cred_json = os.environ.get("FIREBASE_CREDENTIALS")
    if cred_json:
        cred = credentials.Certificate(json.loads(cred_json))
        logger.info("Firebase 인증: FIREBASE_CREDENTIALS 환경변수")

    # 2) 키 파일 경로
    if cred is None:
        key_path = os.environ.get("FIREBASE_KEY_PATH")
        if not key_path:
            project_root = Path(__file__).parent.parent.parent
            for f in project_root.glob("*-adminsdk-*.json"):
                key_path = str(f)
                break
        if key_path:
            cred = credentials.Certificate(key_path)
            logger.info(f"Firebase 인증: 키 파일 ({key_path})")

    # 3) GCP 기본 인증 (Application Default Credentials)
    if cred is None:
        try:
            firebase_admin.initialize_app()
            _db = firestore.client()
            logger.info("Firebase 인증: Application Default Credentials (ADC)")
            return _db
        except Exception:
            raise FileNotFoundError(
                "Firebase 인증 수단을 찾을 수 없습니다. "
                "FIREBASE_CREDENTIALS(JSON), FIREBASE_KEY_PATH(파일경로), "
                "또는 프로젝트 루트에 키 파일을 배치하세요."
            )

    firebase_admin.initialize_app(cred)
    _db = firestore.client()
    logger.info(f"Firestore 연결 완료 (프로젝트: {cred.project_id})")
    return _db
