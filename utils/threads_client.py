"""Threads(Meta) 자동 발행 클라이언트 — 마케팅 콘텐츠 공장 Phase 2.

graph.threads.net/v1.0, **2단계 발행**(컨테이너 생성 → publish). 한글은 반드시
UTF-8 폼 인코딩으로 전송(httpx가 처리). 자격증명은 환경변수:
  - THREADS_ACCESS_TOKEN : 장기 토큰(60일, refresh 필요)
  - THREADS_USER_ID      : 숫자 user_id

미설정 시 is_enabled()=False → 호출부에서 graceful(검수 큐만 동작, 발행 버튼 비활성).

발급 절차 전체: docs/axis/THREADS_PUBLISHING.md
제약: 텍스트 500자, 하루 250개. API 글삭제는 미지원(앱에서 수동).
"""

from __future__ import annotations

import asyncio
import os
from typing import Optional

import httpx
from loguru import logger

THREADS_API = "https://graph.threads.net/v1.0"
THREADS_GRAPH = "https://graph.threads.net"  # 토큰 refresh용(버전 없음)


def _creds() -> tuple[str, str]:
    """(token, user_id). 미설정이면 빈 문자열."""
    return os.getenv("THREADS_ACCESS_TOKEN", ""), os.getenv("THREADS_USER_ID", "")


def is_enabled() -> bool:
    """발행 가능 여부 — 토큰 + user_id 둘 다 있어야 True."""
    token, uid = _creds()
    return bool(token and uid)


async def publish_text(
    text: str,
    *,
    reply_to_id: Optional[str] = None,
    timeout: float = 30.0,
) -> dict:
    """텍스트 글 발행. 성공 시 {"id", "permalink"}.

    실패 시 RuntimeError. 호출부에서 try/except로 사용자 메시지 처리.
    """
    token, uid = _creds()
    if not (token and uid):
        raise RuntimeError("Threads 자격증명 미설정(THREADS_ACCESS_TOKEN/USER_ID)")

    text = (text or "").strip()
    if not text:
        raise RuntimeError("발행할 본문이 비어 있습니다")
    if len(text) > 500:
        raise RuntimeError(f"본문이 500자를 초과합니다({len(text)}자)")

    async with httpx.AsyncClient(timeout=timeout) as client:
        # ── 1) 컨테이너 생성 ──
        create_params = {"media_type": "TEXT", "text": text, "access_token": token}
        if reply_to_id:
            create_params["reply_to_id"] = reply_to_id
        r = await client.post(f"{THREADS_API}/{uid}/threads", data=create_params)
        body = _json(r)
        if r.status_code >= 400 or "id" not in body:
            raise RuntimeError(f"컨테이너 생성 실패: {_err(body, r)}")
        creation_id = body["id"]

        # ── 2) 발행 (컨테이너가 즉시 준비 안 됐을 수 있어 짧게 재시도) ──
        last_err = ""
        post_id = ""
        for attempt in range(3):
            r2 = await client.post(
                f"{THREADS_API}/{uid}/threads_publish",
                data={"creation_id": creation_id, "access_token": token},
            )
            b2 = _json(r2)
            if r2.status_code < 400 and "id" in b2:
                post_id = b2["id"]
                break
            last_err = _err(b2, r2)
            await asyncio.sleep(2 * (attempt + 1))
        if not post_id:
            raise RuntimeError(f"발행 실패: {last_err}")

        # ── 3) permalink 조회(실패해도 발행 자체는 성공) ──
        permalink = ""
        try:
            r3 = await client.get(
                f"{THREADS_API}/{post_id}",
                params={"fields": "permalink", "access_token": token},
            )
            permalink = (_json(r3) or {}).get("permalink", "")
        except Exception:
            pass

    logger.info(f"[threads] 발행 완료 id={post_id} {permalink}")
    return {"id": post_id, "permalink": permalink}


async def get_me(timeout: float = 15.0) -> dict:
    """연결된 계정 정보(id, username) — 토큰 헬스체크용."""
    token, _uid = _creds()
    if not token:
        raise RuntimeError("THREADS_ACCESS_TOKEN 미설정")
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.get(
            f"{THREADS_API}/me",
            params={"fields": "id,username", "access_token": token},
        )
        body = _json(r)
        if r.status_code >= 400:
            raise RuntimeError(f"/me 실패: {_err(body, r)}")
        return body


async def refresh_token(timeout: float = 15.0) -> dict:
    """장기 토큰 60일 연장. 새 access_token + expires_in 반환.

    스케줄 잡에서 호출 후 Secret Manager 새 버전 등록에 사용.
    """
    token, _uid = _creds()
    if not token:
        raise RuntimeError("THREADS_ACCESS_TOKEN 미설정")
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.get(
            f"{THREADS_GRAPH}/refresh_access_token",
            params={"grant_type": "th_refresh_token", "access_token": token},
        )
        body = _json(r)
        if r.status_code >= 400 or "access_token" not in body:
            raise RuntimeError(f"토큰 refresh 실패: {_err(body, r)}")
        return body


# ──────────────────────────────────────────────
# 내부 헬퍼
# ──────────────────────────────────────────────

def _json(r: httpx.Response) -> dict:
    try:
        return r.json()
    except Exception:
        return {}


def _err(body: dict, r: httpx.Response) -> str:
    err = (body or {}).get("error") or {}
    msg = err.get("message") or (r.text[:200] if r.text else f"HTTP {r.status_code}")
    code = err.get("code")
    return f"{msg} (code={code}, http={r.status_code})" if code else f"{msg} (http={r.status_code})"
