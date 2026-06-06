"""관리자 에러 모니터링 싱크 — 실패를 Firestore `admin_errors`에 적재.

배경(2026-06-07): 에러 저장소가 전무했고 Cloud Run 로그만 휘발성으로 존재했다.
관리자가 에러를 조회·집계할 수 있도록, 의미 있는 실패(AI 에이전트 실패, 미처리 5xx,
웹훅 실패 등)를 best-effort로 Firestore에 적재한다.

원칙(utils/cost_tracker.log_to_firestore와 동일):
  - 전부 try/except로 감싸 **절대 예외를 전파하지 않는다** (에러 기록이 본 흐름을 막으면 안 됨).
  - 동기 함수. async 핸들러에서는 `asyncio.to_thread(log_error, ...)`로 감싸 호출(이벤트 루프 블로킹 방지).
  - 4xx/quota 등 정상적 클라이언트 거부는 적재하지 않는다(노이즈 방지) — 호출부에서 선별.

볼륨 관리: `admin_errors.created_at`에 Firestore TTL(90일) 정책 적용 권장(콘솔 설정, 코드 외).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from loguru import logger

_MAX_MSG = 500


def log_error(
    error_type: str,
    message: str,
    *,
    uid: str = "",
    ticker: str = "",
    agent: str = "",
    context: Optional[dict[str, Any]] = None,
) -> None:
    """실패 1건을 `admin_errors` 컬렉션에 적재. best-effort — 실패해도 조용히 넘어감.

    Args:
        error_type: 분류 키 (예: "agent_failure", "ai_error", "webhook_failure", "unhandled_5xx").
        message: 사람이 읽을 에러 메시지 (앞 500자만 저장).
        uid: 관련 사용자 uid (있으면).
        ticker: 관련 종목 (있으면).
        agent: 관련 에이전트/노드 이름 (있으면).
        context: 추가 메타(요청 경로, 상태코드 등). 직렬화 가능한 값만.
    """
    try:
        from firebase_admin import firestore

        db = firestore.client()
        doc = {
            "type": str(error_type)[:60],
            "message": str(message)[:_MAX_MSG],
            "uid": uid or "",
            "ticker": ticker or "",
            "agent": agent or "",
            "created_at": firestore.SERVER_TIMESTAMP,
        }
        if context:
            # 직렬화 불가 값이 섞여도 add가 실패하지 않도록 문자열화 폴백
            try:
                doc["context"] = {k: v for k, v in context.items()}
            except Exception:
                doc["context"] = {"_repr": str(context)[:_MAX_MSG]}
        db.collection("admin_errors").add(doc)
    except Exception as e:
        # 에러 기록 실패가 본 흐름을 막아서는 안 됨
        logger.debug(f"admin_errors 적재 실패 ({error_type}): {e}")


def iso_ts(v: Any) -> Optional[str]:
    """Firestore 타임스탬프/ datetime → ISO 문자열 (admin 응답 직렬화 공통 헬퍼)."""
    if not v:
        return None
    if hasattr(v, "isoformat"):
        return v.isoformat()
    if hasattr(v, "timestamp"):
        return datetime.fromtimestamp(v.timestamp(), tz=timezone.utc).isoformat()
    return str(v)
