"""Extended Thinking 배선 단위 테스트 (API 호출 없음).

요청 형태(extra_body·max_tokens 가산·temperature 강제)와 캐시 키 분리를
mock으로 검증한다. 실제 추론 품질은 evals 하네스(--judge)가 측정.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from utils.cache import ResponseCache
from utils.claude_client import ClaudeClient


# ── 캐시 키 분리 ──

def test_make_key_thinking_namespaced():
    """thinking 예산이 다르면 캐시 키가 달라야 한다 (A/B 오염 방지)."""
    args = ("claude-sonnet-4-6", "sys", [{"role": "user", "content": "x"}])
    k_plain = ResponseCache.make_key(*args)
    k_think = ResponseCache.make_key(*args, {"thinking": 3200})
    assert k_plain != k_think
    # 동일 extra면 동일 키
    assert k_think == ResponseCache.make_key(*args, {"thinking": 3200})


# ── 요청 형태 ──

class _FakeMessages:
    def __init__(self):
        self.captured = None

    async def create(self, **kwargs):
        self.captured = kwargs
        return SimpleNamespace(
            content=[
                SimpleNamespace(type="thinking", thinking="...추론..."),
                SimpleNamespace(type="text", text='{"ok": true}'),
            ],
            usage=SimpleNamespace(
                input_tokens=10,
                output_tokens=5,
                cache_read_input_tokens=0,
                cache_creation_input_tokens=0,
            ),
            stop_reason="end_turn",
        )


class _FakeClient:
    def __init__(self):
        self.messages = _FakeMessages()


def _make_client(fake) -> ClaudeClient:
    c = ClaudeClient(api_key="test", use_response_cache=False)
    c._client = fake  # 지연 초기화 우회
    return c


def test_thinking_injects_extra_body_and_bumps_tokens():
    fake = _FakeClient()
    client = _make_client(fake)
    out = asyncio.run(
        client.complete(
            agent="t",
            model="claude-sonnet-4-6",
            system="s",
            messages=[{"role": "user", "content": "x"}],
            max_tokens=2560,
            temperature=0.3,  # thinking이면 1.0으로 강제돼야 함
            thinking_budget=3200,
        )
    )
    cap = fake.messages.captured
    assert cap["extra_body"]["thinking"] == {"type": "enabled", "budget_tokens": 3200}
    # max_tokens = 출력 + budget
    assert cap["max_tokens"] == 2560 + 3200
    # temperature 강제 1.0
    assert cap["temperature"] == 1.0
    # text만 content로, thinking은 별도 필드
    assert out["content"] == '{"ok": true}'
    assert "추론" in out["thinking"]


def test_no_thinking_keeps_original_shape():
    fake = _FakeClient()
    client = _make_client(fake)
    out = asyncio.run(
        client.complete(
            agent="t",
            model="claude-sonnet-4-6",
            system="s",
            messages=[{"role": "user", "content": "x"}],
            max_tokens=2048,
            temperature=0.5,
            thinking_budget=0,
        )
    )
    cap = fake.messages.captured
    assert "extra_body" not in cap  # thinking 미사용 시 주입 없음
    assert cap["max_tokens"] == 2048
    assert cap["temperature"] == 0.5  # 원래 온도 유지
    assert out["content"] == '{"ok": true}'
