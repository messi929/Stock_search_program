"""Axis 에이전트 공통 베이스 — Week 2 구현 예정.

모든 에이전트는 BaseAgent를 상속하여 다음을 공유합니다:
  - Claude API 클라이언트 (utils.claude_client)
  - 토큰 비용 추적 (utils.cost_tracker)
  - 면책 문구 자동 삽입 (LEGAL.md)
  - 금지 단어 후처리 검증
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


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


class BaseAgent(ABC):
    """모든 에이전트의 공통 베이스. Week 2 본격 구현."""

    model: str  # claude-haiku-4-5-20251001 / claude-sonnet-4-6 / claude-opus-4-7
    system_prompt: str

    @abstractmethod
    async def run(self, input_data: BaseModel) -> BaseModel:
        """에이전트 실행. 하위 클래스가 입출력 타입을 구체화."""
        raise NotImplementedError

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
