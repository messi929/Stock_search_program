"""BaseAgent.call_claude_json 단위 테스트.

핵심 검증: completeness_check 콜백이 default_factory로 검증을 통과한
빈 필드를 잡아내 1회 재요청을 유발하고, 재시도 후에도 누락이면
graceful하게 반환하는지.
"""

from __future__ import annotations

import asyncio
import json

import pytest
from pydantic import BaseModel, Field

from agents.base import BaseAgent


# ──────────────────────────────────────────────
# 테스트용 더블
# ──────────────────────────────────────────────


class _Schema(BaseModel):
    name: str = ""
    body: str = ""  # default_factory처럼 누락돼도 검증 통과


class _FakeClaude:
    """미리 정한 content 문자열을 순서대로 반환하는 가짜 ClaudeClient."""

    def __init__(self, responses: list[str]):
        self._responses = list(responses)
        self.call_count = 0
        self.last_kwargs: dict = {}

    async def complete(self, **kwargs):
        self.call_count += 1
        self.last_kwargs = kwargs
        content = self._responses.pop(0)
        return {"content": content, "usage": None, "cached": False}


class _DummyAgent(BaseAgent):
    async def run(self, input_data):  # pragma: no cover - 추상 메서드 충족용
        raise NotImplementedError


def _agent(responses: list[str]) -> tuple[_DummyAgent, _FakeClaude]:
    fake = _FakeClaude(responses)
    agent = _DummyAgent(
        agent_name="dummy",
        model="claude-sonnet-4-6",
        system_prompt="",
        claude=fake,
    )
    return agent, fake


def _check_body(model: _Schema) -> list[str]:
    return [] if model.body.strip() else ["body"]


# ──────────────────────────────────────────────
# completeness_check 미지정 — 기존 동작 보존
# ──────────────────────────────────────────────


def test_no_completeness_check_returns_first_response():
    """completeness_check 없으면 검증 통과 즉시 반환 (재시도 없음)."""
    agent, fake = _agent([json.dumps({"name": "A"})])

    async def run():
        return await agent.call_claude_json(
            user_message="x", schema=_Schema
        )

    model, _ = asyncio.run(run())
    assert model.name == "A"
    assert model.body == ""
    assert fake.call_count == 1


# ──────────────────────────────────────────────
# completeness_check — 누락 시 재요청
# ──────────────────────────────────────────────


def test_incomplete_response_triggers_retry():
    """1차 응답에 body 누락 → 2차 재요청에서 채워지면 완전한 모델 반환."""
    agent, fake = _agent(
        [
            json.dumps({"name": "A"}),  # body 누락
            json.dumps({"name": "A", "body": "채워짐"}),  # 재요청 응답
        ]
    )

    async def run():
        return await agent.call_claude_json(
            user_message="x",
            schema=_Schema,
            completeness_check=_check_body,
        )

    model, _ = asyncio.run(run())
    assert model.body == "채워짐"
    assert fake.call_count == 2


def test_complete_response_no_retry():
    """1차 응답이 완전하면 재요청 없음."""
    agent, fake = _agent([json.dumps({"name": "A", "body": "처음부터 채움"})])

    async def run():
        return await agent.call_claude_json(
            user_message="x",
            schema=_Schema,
            completeness_check=_check_body,
        )

    model, _ = asyncio.run(run())
    assert model.body == "처음부터 채움"
    assert fake.call_count == 1


# ──────────────────────────────────────────────
# structured_output — 강제 tool use 라우팅
# ──────────────────────────────────────────────


def test_structured_output_passes_schema_and_skips_json_instruction():
    """structured_output=True면 schema가 output_schema로 전달되고, 텍스트 JSON
    지시문은 user_message에 덧붙지 않는다 (tool 스키마가 형식을 강제하므로)."""
    agent, fake = _agent([json.dumps({"name": "A", "body": "구조화"})])

    async def run():
        return await agent.call_claude_json(
            user_message="원본 메시지",
            schema=_Schema,
            structured_output=True,
        )

    model, _ = asyncio.run(run())
    assert model.body == "구조화"
    assert fake.last_kwargs["output_schema"] is _Schema
    # 구조화 모드에서는 "JSON 출력 지시" 텍스트를 덧붙이지 않음
    sent = fake.last_kwargs["messages"][0]["content"]
    assert sent == "원본 메시지"


def test_non_structured_keeps_json_instruction_and_no_schema():
    """기본(비구조화) 경로는 output_schema=None이고 JSON 지시문을 덧붙인다 — 기존 동작 보존."""
    agent, fake = _agent([json.dumps({"name": "A"})])

    async def run():
        return await agent.call_claude_json(user_message="원본", schema=_Schema)

    asyncio.run(run())
    assert fake.last_kwargs["output_schema"] is None
    assert "JSON 출력 지시" in fake.last_kwargs["messages"][0]["content"]


def test_retry_exhausted_returns_gracefully():
    """재시도 후에도 누락이면 예외 없이 (default 채워진) 모델 반환."""
    agent, fake = _agent(
        [
            json.dumps({"name": "A"}),  # body 누락
            json.dumps({"name": "A"}),  # 재요청에도 누락
        ]
    )

    async def run():
        return await agent.call_claude_json(
            user_message="x",
            schema=_Schema,
            completeness_check=_check_body,
            max_retries=1,
        )

    model, _ = asyncio.run(run())
    assert model.name == "A"
    assert model.body == ""  # graceful — default 유지
    assert fake.call_count == 2
