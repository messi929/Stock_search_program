"""Axis 에이전트 공통 베이스.

모든 에이전트는 BaseAgent를 상속하여 다음을 공유합니다:
  - ClaudeClient (utils.claude_client)
  - 면책 문구 자동 삽입 (LEGAL.md)
  - 금지 단어 후처리 검증
  - JSON 응답 파싱 헬퍼
"""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from typing import Any

from loguru import logger
from pydantic import BaseModel

from utils.claude_client import ClaudeClient


# ──────────────────────────────────────────────
# LEGAL: 면책 문구 — 모든 응답에 자동 삽입 (docs/axis/LEGAL.md)
# ──────────────────────────────────────────────

DISCLAIMER = (
    "📌 본 분석은 투자 권유가 아닌 정보 제공입니다.\n"
    "   최종 투자 판단은 사용자 본인의 책임입니다.\n"
    "   Axis는 자본시장법상 투자자문업 면허가 없으며,\n"
    "   특정 종목의 매매를 권유하지 않습니다."
)

# 응답 후처리 시 검출할 금지 단어 — 발견되면 [필터링됨]으로 치환 + 로그
FORBIDDEN_WORDS: tuple[str, ...] = (
    "추천합니다", "추천드립니다", "추천드려요",
    "사세요", "매수하세요", "매도하세요",
    "매수 신호", "매도 신호", "진입 신호",
    "유망합니다", "유망주",
    "목표가", "매수가", "적정가",
    "사야 합니다", "팔아야 합니다",
)


# ──────────────────────────────────────────────
# JSON 파싱 헬퍼
# ──────────────────────────────────────────────

_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def extract_json(text: str) -> str:
    """Claude 응답에서 JSON 본체만 추출.

    처리 케이스:
      - ```json ... ``` 코드 블록
      - ``` ... ``` 일반 블록
      - JSON 앞뒤 공백/설명 텍스트
      - 그냥 raw JSON
    """
    text = text.strip()
    text = _JSON_FENCE_RE.sub("", text).strip()

    # 첫 { 부터 마지막 } 까지만 추출 (앞뒤 설명 컷)
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]
    return text


# ──────────────────────────────────────────────
# Base Agent
# ──────────────────────────────────────────────

class BaseAgent(ABC):
    """모든 에이전트의 공통 베이스."""

    def __init__(
        self,
        agent_name: str,
        model: str,
        system_prompt: str,
        claude: ClaudeClient | None = None,
    ):
        self.agent_name = agent_name
        self.model = model
        self.system_prompt = system_prompt
        self.claude = claude or ClaudeClient()

    @abstractmethod
    async def run(self, input_data: BaseModel) -> BaseModel:
        """에이전트 실행. 하위 클래스가 입출력 타입을 구체화."""
        raise NotImplementedError

    async def call_claude(
        self,
        user_message: str,
        max_tokens: int = 4096,
        temperature: float = 1.0,
        uid: str = "",
        prefill: str | None = None,
    ) -> dict:
        """Claude 호출 헬퍼. prefill이 지정되면 응답이 그것으로 시작하도록 강제."""
        messages: list[dict] = [{"role": "user", "content": user_message}]
        if prefill is not None:
            messages.append({"role": "assistant", "content": prefill})

        result = await self.claude.complete(
            agent=self.agent_name,
            model=self.model,
            system=self.system_prompt,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            uid=uid,
        )

        # prefill이 있으면 응답 앞에 prefill 복원
        if prefill is not None:
            result["content"] = prefill + result["content"]
        return result

    async def call_claude_json(
        self,
        user_message: str,
        schema: type[BaseModel],
        max_tokens: int = 4096,
        uid: str = "",
        max_retries: int = 1,
    ) -> tuple[BaseModel, dict]:
        """Claude 호출 + JSON 파싱 + Pydantic 검증.

        Returns:
            (parsed_model, raw_result) — raw_result는 usage/cached 등 메타.
        """
        last_err: Exception | None = None
        for attempt in range(max_retries + 1):
            # JSON prefill로 응답을 { 로 시작하도록 강제 → 파싱 안정성↑
            result = await self.call_claude(
                user_message=user_message,
                max_tokens=max_tokens,
                uid=uid,
                prefill="{",
            )
            try:
                json_str = extract_json(result["content"])
                data = json.loads(json_str)
                model = schema.model_validate(data)
                return model, result
            except (json.JSONDecodeError, ValueError) as e:
                last_err = e
                logger.warning(
                    f"[{self.agent_name}] JSON 파싱 실패 (시도 {attempt + 1}/{max_retries + 1}): {e}"
                )
                if attempt < max_retries:
                    user_message = (
                        f"{user_message}\n\n"
                        f"⚠️ 직전 응답 JSON 파싱 실패. 반드시 {schema.__name__} 스키마에 정확히 맞춰 JSON만 출력하세요."
                    )
        raise ValueError(f"[{self.agent_name}] JSON 파싱 재시도 후에도 실패: {last_err}")

    @staticmethod
    def append_disclaimer(text: str) -> str:
        """응답 끝에 면책 문구 삽입."""
        return f"{text.rstrip()}\n\n{DISCLAIMER}"

    @staticmethod
    def filter_forbidden(text: str) -> tuple[str, list[str]]:
        """금지 단어 검출 + 치환. (필터링된 텍스트, 발견된 단어 리스트) 반환."""
        found: list[str] = []
        for word in FORBIDDEN_WORDS:
            if word in text:
                found.append(word)
                text = text.replace(word, "[필터링됨]")
        return text, found
