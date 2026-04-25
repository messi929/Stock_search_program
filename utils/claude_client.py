"""Claude API 래퍼 — Week 1 Day 5 본격 구현 예정.

지원 모델:
  - claude-haiku-4-5-20251001  (Research, 저비용)
  - claude-sonnet-4-6           (Analyst, Validator)
  - claude-opus-4-7             (Strategist, 종합 분석)

기능 (Day 5에서 채움):
  - 모델별 호출 헬퍼
  - 토큰/비용 자동 로깅 (utils.cost_tracker)
  - 재시도 + 에러 핸들링
  - 응답 캐싱 (utils.cache, 1시간 TTL)
"""

from __future__ import annotations

import os
from dataclasses import dataclass


# ──────────────────────────────────────────────
# 모델 상수 — 4 에이전트 모델 차등 (CLAUDE.md 참조)
# ──────────────────────────────────────────────

MODEL_HAIKU = "claude-haiku-4-5-20251001"
MODEL_SONNET = "claude-sonnet-4-6"
MODEL_OPUS = "claude-opus-4-7"


@dataclass
class ClaudeUsage:
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0


class ClaudeClient:
    """Anthropic SDK 래퍼. Week 1 Day 5에 구현."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if not self.api_key:
            # 키가 없어도 임포트는 가능해야 함 (Week 1 스캐폴딩 단계)
            pass

    async def complete(
        self,
        model: str,
        system: str,
        messages: list[dict],
        max_tokens: int = 4096,
        response_format: str | None = None,
    ) -> dict:
        """Claude API 호출. Week 1 Day 5 구현."""
        raise NotImplementedError(
            "ClaudeClient.complete()는 Week 1 Day 5에 구현됩니다."
        )
