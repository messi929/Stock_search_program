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
import re
from typing import Awaitable, Callable, Optional

import httpx
from loguru import logger

THREADS_API = "https://graph.threads.net/v1.0"
THREADS_GRAPH = "https://graph.threads.net"  # 토큰 refresh용(버전 없음)

MAX_TEXT = 500   # 글 1개(=파트 1개)의 글자 수 상한
MAX_PARTS = 6    # 타래 파트 수 상한. 발행 실패 지점 수를 줄이려는 것(§7-3 롤백 불가)
PART_SEP = "---"  # 파트 경계 — 단독 줄. 생성 본문에는 등장하지 않는다(홍보 구분선은 '──')

_SEP_RE = re.compile(r"^[ \t]*-{3,}[ \t]*$", re.MULTILINE)


def _creds() -> tuple[str, str]:
    """(token, user_id). 미설정이면 빈 문자열."""
    return os.getenv("THREADS_ACCESS_TOKEN", ""), os.getenv("THREADS_USER_ID", "")


def is_enabled() -> bool:
    """발행 가능 여부 — 토큰 + user_id 둘 다 있어야 True."""
    token, uid = _creds()
    return bool(token and uid)


# ──────────────────────────────────────────────
# 성과 조회 (읽기) — 2026-08-09 추가
# ──────────────────────────────────────────────
#
# 배경: 이 클라이언트는 3주간 **쓰기 전용**이었다. 62편을 발행하고 반응을 한 번도
# 수집하지 않아서, 포맷 개편(THREADS_FORMAT.md §8)이 효과가 있었는지 원리적으로
# 알 수 없었다. 2026-08-09에 API로 직접 뽑아보니 평균 조회 27 / 외부 댓글 0이었고,
# 07-14 이전 발행 45편은 post_id조차 없어 영구 조회 불가다.
# → 같은 실수를 반복하지 않기 위한 읽기 경로다. 자세한 실측은 docs/axis/NAVER_PREMIUM.md §0.

INSIGHT_METRICS = "views,likes,replies,reposts,quotes"


async def fetch_insights(post_id: str, *, timeout: float = 20.0) -> Optional[dict]:
    """글 1개의 반응 지표. {views, likes, replies, reposts, quotes} 또는 None.

    ⚠️ `replies`는 **자기 답글도 포함한다.** 타래로 발행하면 파트 수 - 1 만큼이
    자동으로 잡히므로, 외부 반응을 보려면 호출부가 파트 수를 빼야 한다
    (`external_replies` 참고).
    """
    token, _ = _creds()
    if not (token and post_id):
        return None
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(
                f"{THREADS_API}/{post_id}/insights",
                params={"metric": INSIGHT_METRICS, "access_token": token},
            )
            body = _json(r)
    except Exception as e:
        logger.warning(f"[threads] insights 조회 실패 {post_id}: {e}")
        return None

    if r.status_code >= 400 or "data" not in body:
        logger.warning(f"[threads] insights 응답 오류 {post_id}: {_err(body, r)}")
        return None

    out: dict[str, int] = {}
    for item in body.get("data", []):
        name = item.get("name")
        vals = item.get("values") or [{}]
        try:
            out[str(name)] = int(vals[0].get("value", 0) or 0)
        except (TypeError, ValueError, IndexError):
            out[str(name)] = 0
    return out


def external_replies(insights: dict, part_count: int) -> int:
    """전체 답글에서 우리 자신의 타래 답글을 뺀 값 = 진짜 외부 반응.

    2026-08-09 실측에서 17편 전부 `replies == part_count - 1`이었다. 즉 외부 댓글이
    정확히 0이었는데, 이 보정 없이는 '댓글 1개씩 달렸다'로 오독하게 된다.
    """
    total = int(insights.get("replies", 0) or 0)
    return max(0, total - max(0, part_count - 1))


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
    if len(text) > MAX_TEXT:
        raise RuntimeError(f"본문이 {MAX_TEXT}자를 초과합니다({len(text)}자)")

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


# ──────────────────────────────────────────────
# 타래(thread) — 파트 배열
# ──────────────────────────────────────────────

def split_parts(text: str) -> list[str]:
    """본문 문자열 → 파트 배열. 단독 `---` 줄이 경계. 구분자가 없으면 1개짜리 배열."""
    chunks = _SEP_RE.split(text or "")
    return [c.strip() for c in chunks if c and c.strip()]


def join_parts(parts: list[str]) -> str:
    """파트 배열 → 검수/복사용 단일 문자열(구분자 삽입). split_parts의 역함수."""
    return f"\n\n{PART_SEP}\n\n".join(p.strip() for p in (parts or []) if p and p.strip())


def validate_parts(parts: list[str]) -> list[str]:
    """발행 전 전체 검증. 정규화된 파트 배열 반환, 문제가 있으면 RuntimeError.

    🚨 **발행을 시작하기 전에 전부 검증한다.** Threads는 API 글삭제를 지원하지 않아
    3번째 파트에서 길이 초과로 터지면 반쪽 타래가 영구히 박힌다. 되돌릴 수 없으므로
    "하나라도 이상하면 아무것도 발행하지 않는다"가 유일한 방어선이다.
    """
    norm = [p.strip() for p in (parts or []) if p and p.strip()]
    if not norm:
        raise RuntimeError("발행할 본문이 비어 있습니다")
    if len(norm) > MAX_PARTS:
        raise RuntimeError(f"파트가 {len(norm)}개입니다 — 최대 {MAX_PARTS}개까지 발행합니다")
    for i, p in enumerate(norm, 1):
        if len(p) > MAX_TEXT:
            raise RuntimeError(f"{i}번째 파트가 {MAX_TEXT}자를 초과합니다({len(p)}자)")
    return norm


async def publish_thread(
    parts: list[str],
    *,
    reply_to_id: Optional[str] = None,
    on_part: Optional[Callable[[int, dict], Awaitable[None]]] = None,
    timeout: float = 30.0,
) -> list[dict]:
    """파트 배열을 타래로 순차 발행. 각 파트를 **직전 파트에 답글로** 물린다.

    parts는 호출부에서 validate_parts()를 통과시킨 것이어야 한다.
    reply_to_id: 이어서 발행(복구) 시 마지막으로 성공한 파트의 id.
    on_part: 파트 하나가 발행될 때마다 await 호출(i, {"id","permalink"}). 부분 성공을
        호출부가 **즉시 영속화**하라고 있는 훅 — 중간에 죽어도 어디까지 나갔는지 남는다.

    실패 시 RuntimeError를 올린다. 그때까지 성공한 파트는 on_part로 이미 통보됐다.
    """
    results: list[dict] = []
    prev = reply_to_id
    for i, part in enumerate(parts):
        r = await publish_text(part, reply_to_id=prev, timeout=timeout)
        # ⚠️ 루트 id를 계속 쓰면 타래가 아니라 평면 댓글 더미가 된다. 반드시 직전 글에 체인.
        prev = r["id"]
        results.append(r)
        if on_part:
            await on_part(i, r)
    return results


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
