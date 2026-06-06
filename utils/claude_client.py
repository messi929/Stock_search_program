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
import json
import os
import re
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
# 구조화 출력(structured output) — 강제 tool use
# ──────────────────────────────────────────────
# 설계(2026-06-06): 텍스트로 JSON을 받아 파싱하던 방식은 모델이 ```펜스·설명문·
# escape 누락·필드 누락을 흘려 flaky했다(특히 event 페르소나, prod 확인). 대신
# Pydantic 스키마를 그대로 tool input_schema로 만들고 tool_choice로 그 tool 호출을
# 강제하면, API가 tool_use.input을 항상 유효한 JSON 객체로 보장한다 — 텍스트 파싱·
# json-repair·펜스 제거가 전부 불필요해지고 검증 실패가 사실상 0이 된다.
# (SDK 0.43.0은 tools/tool_choice를 네이티브 kwarg로 지원하므로 extra_body 불필요.)

_TOOL_NAME_RE = re.compile(r"[^a-zA-Z0-9_-]")


def _tool_name_for(schema) -> str:
    """Pydantic 스키마 클래스명 → tool 이름(^[a-zA-Z0-9_-]{1,64}$)."""
    raw = getattr(schema, "__name__", "output").strip("_") or "output"
    return ("emit_" + _TOOL_NAME_RE.sub("_", raw))[:64]


def build_tool_from_schema(schema) -> dict:
    """Pydantic BaseModel 서브클래스 → Anthropic tool 정의.

    input_schema는 Pydantic v2 model_json_schema()를 그대로 사용($defs/$ref 포함 —
    tool 스키마는 표준 JSON Schema를 허용). strict 모드가 아니라 optional 필드/추가
    제약이 있어도 거부되지 않는다(관대). 강제 호출이 구조를 보장한다.
    """
    return {
        "name": _tool_name_for(schema),
        "description": (
            "분석 결과를 이 도구의 스키마에 맞춰 구조화하여 제출합니다. "
            "모든 관련 필드를 빠짐없이 채우세요. 이 도구 호출이 유일한 출력 형식입니다."
        ),
        "input_schema": schema.model_json_schema(),
    }


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
        thinking_budget: int = 0,
        output_schema=None,
    ) -> dict:
        """Claude 호출.

        Args:
            agent: 비용 추적용 에이전트 이름 ("research" | "analyst" | "validator" | "strategist")
            model: MODEL_HAIKU / MODEL_SONNET / MODEL_OPUS
            system: 시스템 프롬프트 (cache_control 자동 적용)
            messages: [{"role": "user|assistant", "content": "..."}]
            max_tokens: 응답(출력) 최대 토큰. thinking 사용 시 budget은 별도 가산.
            temperature: 샘플링 온도 (thinking 활성 시 API가 1.0을 강제 → 자동 보정)
            uid: Firestore 비용 기록용 user uid (비어 있으면 익명)
            skip_cache: True면 응답 캐시 무시
            thinking_budget: >0이면 Extended Thinking 활성화 (추론 토큰 예산).
                복잡한 종합·검증에서 추론 품질↑. max_tokens와 별개로 가산되며,
                temperature는 1.0으로 강제된다.
            output_schema: Pydantic BaseModel 서브클래스. 지정하면 그 스키마로 tool을
                만들어 tool_choice로 호출을 강제한다(구조화 출력). content는 tool_use.input을
                직렬화한 유효 JSON 문자열로 반환되어, 호출부의 JSON 파싱이 항상 성공한다.
                thinking과는 동시 사용 불가(API 제약) — 지정 시 thinking은 무시된다.

        Returns:
            {"content": str, "usage": ClaudeUsage, "cached": bool, "stop_reason": str,
             "thinking": str}
        """
        use_structured = output_schema is not None
        use_thinking = (thinking_budget and thinking_budget > 0) and not use_structured
        if output_schema is not None and thinking_budget and thinking_budget > 0:
            logger.debug(
                f"[Claude:{agent}] output_schema 지정 — thinking 비활성화(API 제약상 "
                f"강제 tool_choice와 병행 불가)"
            )

        # 1) 응답 캐시 조회 (L1 메모리 → L2 Firestore). Firestore I/O는 to_thread로 비블로킹.
        #    캐시 키에 max_tokens·thinking을 포함 — 이 둘이 바뀌면 응답 형태가 달라지는데
        #    키에 없으면 옛 응답(예: 잘린 JSON)이 히트해 수정이 가려진다(prod 확인 2026-06-06).
        key_extra: dict = {"max_tokens": int(max_tokens)}
        if use_thinking:
            key_extra["thinking"] = int(thinking_budget)
        if use_structured:
            # 구조화 출력은 content 형식이 텍스트와 다르므로 키에 포함 — 안 그러면 옛
            # 텍스트 캐시가 히트해 구조화 전환이 가려진다(2026-06-06 max_tokens 버그 교훈).
            key_extra["structured"] = getattr(output_schema, "__name__", "schema")
        cache_key = default_cache.make_key(model, system, messages, key_extra)
        if self.use_response_cache and not skip_cache:
            cached = await asyncio.to_thread(default_cache.get, cache_key)
            if cached is not None:
                logger.debug(f"[Claude:{agent}] 캐시 히트 — API 호출 생략")
                return {
                    "content": cached["content"],
                    "usage": ClaudeUsage(**cached["usage"]),
                    "cached": True,
                    "stop_reason": cached.get("stop_reason"),
                    "thinking": cached.get("thinking", ""),
                }

        # 2) 시스템 프롬프트 — 1K+ 토큰일 때만 cache_control 적용 (Anthropic 최소 단위)
        system_param = self._build_system_param(system)

        # 2.5) thinking 파라미터 + 토큰/온도 보정
        create_kwargs: dict = {}
        effective_max_tokens = max_tokens
        effective_temperature = temperature
        if use_thinking:
            # extra_body로 주입 — SDK 버전 무관(0.43.0은 thinking 네이티브 kwarg 미지원,
            # extra_body는 요청 body에 그대로 병합돼 동작. 응답 text 파싱도 정상 확인).
            create_kwargs["extra_body"] = {
                "thinking": {
                    "type": "enabled",
                    "budget_tokens": int(thinking_budget),
                }
            }
            # max_tokens는 thinking + 출력 합계여야 하므로 budget을 가산
            effective_max_tokens = max_tokens + int(thinking_budget)
            # Extended Thinking은 temperature=1.0만 허용
            effective_temperature = 1.0

        # 2.6) 구조화 출력 — 스키마로 tool 생성 + 호출 강제
        structured_tool_name = ""
        if use_structured:
            tool = build_tool_from_schema(output_schema)
            structured_tool_name = tool["name"]
            create_kwargs["tools"] = [tool]
            create_kwargs["tool_choice"] = {"type": "tool", "name": structured_tool_name}

        # 3) API 호출 (재시도 포함)
        client = self._get_client()
        last_err: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                response = await client.messages.create(
                    model=model,
                    system=system_param,
                    messages=messages,
                    max_tokens=effective_max_tokens,
                    temperature=effective_temperature,
                    **create_kwargs,
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

        # 4) 응답 파싱 — text 블록만 content로, thinking 블록은 별도 보관(디버깅/로깅용)
        #    구조화 출력이면 tool_use.input을 유효 JSON 문자열로 직렬화해 content에 담는다
        #    (호출부의 extract_json + json.loads가 그대로 동작 → 파싱 실패 0).
        if use_structured:
            tool_input = next(
                (
                    block.input
                    for block in response.content
                    if getattr(block, "type", None) == "tool_use"
                    and getattr(block, "name", None) == structured_tool_name
                ),
                None,
            )
            if tool_input is not None:
                content = json.dumps(tool_input, ensure_ascii=False)
            else:
                # 강제 tool_choice에서는 거의 발생하지 않음 — 안전망으로 text 폴백
                logger.warning(
                    f"[Claude:{agent}] 구조화 출력인데 tool_use 블록 없음 — text 폴백"
                )
                content = "".join(
                    b.text for b in response.content
                    if getattr(b, "type", None) == "text"
                )
        else:
            content = "".join(
                block.text for block in response.content if getattr(block, "type", None) == "text"
            )
        thinking_text = "".join(
            getattr(block, "thinking", "") or ""
            for block in response.content
            if getattr(block, "type", None) == "thinking"
        )
        if use_thinking and thinking_text:
            logger.debug(
                f"[Claude:{agent}] thinking {len(thinking_text)}자 사용 "
                f"(budget={thinking_budget})"
            )
        usage = self._extract_usage(response)
        stop_reason = getattr(response, "stop_reason", None)
        if stop_reason == "max_tokens":
            # 출력이 max_tokens에 걸려 잘림 — JSON 파싱/스키마 검증 실패의 주원인.
            # 관측성: 어떤 에이전트가 한도를 넘는지 prod 로그로 추적.
            logger.warning(
                f"[Claude:{agent}] ⚠️ 출력이 max_tokens({effective_max_tokens})에 걸려 잘림 "
                f"(out={usage.output_tokens}) — max_tokens 상향 또는 입력 축소 필요"
            )
        result = {
            "content": content,
            "usage": usage,
            "cached": False,
            "stop_reason": stop_reason,
            "thinking": thinking_text,
        }

        # 5) 비용 기록 (실패해도 결과에는 영향 X)
        try:
            from utils.cost_tracker import log_usage
            log_usage(uid=uid, agent=agent, model=model, usage=usage)
        except Exception as e:
            logger.warning(f"[Claude:{agent}] 비용 기록 건너뜀: {e}")

        # 6) 응답 캐시 저장 — JSON-safe dict로 변환(L2 Firestore 직렬화 위함).
        #    Firestore I/O는 to_thread로 비블로킹.
        if self.use_response_cache and not skip_cache:
            cache_value = {
                "content": content,
                "usage": {
                    "input_tokens": usage.input_tokens,
                    "output_tokens": usage.output_tokens,
                    "cache_read_tokens": usage.cache_read_tokens,
                    "cache_creation_tokens": usage.cache_creation_tokens,
                },
                "stop_reason": result["stop_reason"],
                # thinking은 디버깅용 — 캐시 비대화 방지 위해 앞부분만 보관
                "thinking": thinking_text[:2000] if thinking_text else "",
            }
            await asyncio.to_thread(default_cache.set, cache_key, cache_value)

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
