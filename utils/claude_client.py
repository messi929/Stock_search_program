"""Claude API 래퍼 — Anthropic SDK + 프롬프트 캐싱 + 비용 추적 + 재시도.

지원 모델 (CLAUDE.md 참조):
  Research   → MODEL_HAIKU   (저비용)
  Analyst    → MODEL_SONNET
  Validator  → MODEL_SONNET
  Strategist → MODEL_OPUS    (복잡 종합)

기본 동작:
  - System 프롬프트는 자동으로 ephemeral cache_control 적용 (1K+ 토큰 시 효과)
  - 1시간 응답 캐시 (ResponseCache, default_cache)
  - RateLimitError 재시도: 지수 백오프 (1s → 2s → 4s, 최대 3회)
  - 사용량은 ClaudeUsage로 반환, cost_tracker.log_usage()로 기록 가능

사용:
    client = ClaudeClient()
    result = await client.complete(
        agent="research",
        model=MODEL_HAIKU,
        system="당신은 시황 분석가입니다...",
        messages=[{"role": "user", "content": "삼성바이오 어때?"}],
        max_tokens=1024,
        uid="user-uid-or-empty",
    )
    print(result["content"], result["usage"])
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass

from loguru import logger

from utils.cache import default_cache


# ──────────────────────────────────────────────
# 모델 상수
# ──────────────────────────────────────────────

MODEL_HAIKU = "claude-haiku-4-5-20251001"
MODEL_SONNET = "claude-sonnet-4-6"
MODEL_OPUS = "claude-opus-4-7"


# ──────────────────────────────────────────────
# 사용량 데이터
# ──────────────────────────────────────────────

@dataclass
class ClaudeUsage:
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0


# ──────────────────────────────────────────────
# 예외
# ──────────────────────────────────────────────

class ClaudeAPIError(Exception):
    """Claude API 호출 실패 (재시도 후에도 실패)."""


# ──────────────────────────────────────────────
# 클라이언트
# ──────────────────────────────────────────────

class ClaudeClient:
    """Anthropic SDK 비동기 래퍼."""

    def __init__(
        self,
        api_key: str | None = None,
        max_retries: int = 3,
        cache_system_prompt: bool = True,
        use_response_cache: bool = True,
    ):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.max_retries = max_retries
        self.cache_system_prompt = cache_system_prompt
        self.use_response_cache = use_response_cache
        self._client = None  # 지연 초기화

    def _get_client(self):
        """anthropic.AsyncAnthropic 지연 초기화."""
        if self._client is None:
            if not self.api_key:
                raise ClaudeAPIError(
                    "ANTHROPIC_API_KEY가 설정되지 않았습니다. .env 또는 환경변수를 확인하세요."
                )
            try:
                from anthropic import AsyncAnthropic
            except ImportError as e:
                raise ClaudeAPIError(
                    "anthropic SDK 미설치. `pip install -r requirements.txt` 실행 필요."
                ) from e
            self._client = AsyncAnthropic(api_key=self.api_key)
        return self._client

    async def complete(
        self,
        agent: str,
        model: str,
        system: str,
        messages: list[dict],
        max_tokens: int = 4096,
        temperature: float = 1.0,
        uid: str = "",
        skip_cache: bool = False,
    ) -> dict:
        """Claude 호출.

        Args:
            agent: 비용 추적용 에이전트 이름 ("research" | "analyst" | "validator" | "strategist")
            model: MODEL_HAIKU / MODEL_SONNET / MODEL_OPUS
            system: 시스템 프롬프트 (cache_control 자동 적용)
            messages: [{"role": "user|assistant", "content": "..."}]
            max_tokens: 응답 최대 토큰
            temperature: 샘플링 온도
            uid: Firestore 비용 기록용 user uid (비어 있으면 익명)
            skip_cache: True면 응답 캐시 무시

        Returns:
            {"content": str, "usage": ClaudeUsage, "cached": bool, "stop_reason": str}
        """
        # 1) 응답 캐시 조회
        cache_key = default_cache.make_key(model, system, messages)
        if self.use_response_cache and not skip_cache:
            cached = default_cache.get(cache_key)
            if cached is not None:
                logger.debug(f"[Claude:{agent}] 캐시 히트 — API 호출 생략")
                return {**cached, "cached": True}

        # 2) 시스템 프롬프트 — 1K+ 토큰일 때만 cache_control 적용 (Anthropic 최소 단위)
        system_param = self._build_system_param(system)

        # 3) API 호출 (재시도 포함)
        client = self._get_client()
        last_err: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                response = await client.messages.create(
                    model=model,
                    system=system_param,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                break
            except Exception as e:
                last_err = e
                # SDK 예외 클래스가 변경될 수 있어 문자열 매칭으로 안전망
                err_name = type(e).__name__
                if err_name == "RateLimitError" or "429" in str(e):
                    backoff = 2 ** attempt
                    logger.warning(f"[Claude:{agent}] rate limit, {backoff}s 후 재시도 ({attempt + 1}/{self.max_retries})")
                    await asyncio.sleep(backoff)
                    continue
                if err_name in ("APIConnectionError", "APITimeoutError"):
                    backoff = 2 ** attempt
                    logger.warning(f"[Claude:{agent}] 연결 오류 {err_name}, {backoff}s 후 재시도")
                    await asyncio.sleep(backoff)
                    continue
                # 그 외 (4xx auth/validation, 5xx server)는 즉시 실패
                raise ClaudeAPIError(f"{err_name}: {e}") from e
        else:
            raise ClaudeAPIError(f"최대 재시도({self.max_retries}) 후 실패: {last_err}") from last_err

        # 4) 응답 파싱
        content = "".join(
            block.text for block in response.content if getattr(block, "type", None) == "text"
        )
        usage = self._extract_usage(response)
        result = {
            "content": content,
            "usage": usage,
            "cached": False,
            "stop_reason": getattr(response, "stop_reason", None),
        }

        # 5) 비용 기록 (실패해도 결과에는 영향 X)
        try:
            from utils.cost_tracker import log_usage
            log_usage(uid=uid, agent=agent, model=model, usage=usage)
        except Exception as e:
            logger.warning(f"[Claude:{agent}] 비용 기록 건너뜀: {e}")

        # 6) 응답 캐시 저장 (cached=False 형태로 저장하여 재방문 시 cached=True로 반환)
        if self.use_response_cache and not skip_cache:
            default_cache.set(cache_key, result)

        return result

    def _build_system_param(self, system: str):
        """시스템 프롬프트 구성. 충분히 길면 cache_control 적용."""
        if not self.cache_system_prompt or len(system) < 1024:
            return system
        return [
            {
                "type": "text",
                "text": system,
                "cache_control": {"type": "ephemeral"},
            }
        ]

    @staticmethod
    def _extract_usage(response) -> ClaudeUsage:
        """SDK 응답에서 토큰 사용량 추출."""
        u = getattr(response, "usage", None)
        if u is None:
            return ClaudeUsage(0, 0)
        return ClaudeUsage(
            input_tokens=getattr(u, "input_tokens", 0) or 0,
            output_tokens=getattr(u, "output_tokens", 0) or 0,
            cache_read_tokens=getattr(u, "cache_read_input_tokens", 0) or 0,
            cache_creation_tokens=getattr(u, "cache_creation_input_tokens", 0) or 0,
        )


# ──────────────────────────────────────────────
# 진입점: `py -m utils.claude_client --test`
# ──────────────────────────────────────────────

async def _smoke_test():
    """Week 1 Day 5 sanity check — '안녕하세요' 응답 확인."""
    client = ClaudeClient()
    result = await client.complete(
        agent="smoke",
        model=MODEL_HAIKU,
        system="당신은 인사를 짧게 받는 비서입니다. 한국어로 한 문장만 답하세요.",
        messages=[{"role": "user", "content": "안녕하세요"}],
        max_tokens=128,
    )
    print("=" * 60)
    print(f"Model: {MODEL_HAIKU}")
    print(f"Response: {result['content']}")
    print(f"Usage: in={result['usage'].input_tokens} out={result['usage'].output_tokens}")
    print(f"Cached: {result['cached']}, Stop: {result['stop_reason']}")
    print("=" * 60)


if __name__ == "__main__":
    import sys
    if "--test" in sys.argv:
        asyncio.run(_smoke_test())
    else:
        print("Usage: py -m utils.claude_client --test")
