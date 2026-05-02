"""utils/data_collectors/event_inference_cache.py 단위 테스트."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from utils.data_collectors import event_inference_cache as eic
from utils.data_collectors.event_inference_cache import (
    SAMPLE_SIZE_LOW,
    SAMPLE_SIZE_OK,
    _classify_sample_reliability,
    _post_process,
    _scrub_forbidden,
    _strip_to_json,
    clear_cache,
    get_similar_events_cached,
)


@pytest.fixture(autouse=True)
def _reset_cache():
    clear_cache()
    yield
    clear_cache()


# ──────────────────────────────────────────────
# 1. 표본 신뢰도 분류
# ──────────────────────────────────────────────


def test_sample_reliability_low():
    assert "정성 분석" in _classify_sample_reliability(0)
    assert "정성 분석" in _classify_sample_reliability(SAMPLE_SIZE_LOW - 1)


def test_sample_reliability_medium():
    assert "참고용" in _classify_sample_reliability(SAMPLE_SIZE_LOW)
    assert "참고용" in _classify_sample_reliability(SAMPLE_SIZE_OK - 1)


def test_sample_reliability_high():
    assert "신뢰" in _classify_sample_reliability(SAMPLE_SIZE_OK)
    assert "신뢰" in _classify_sample_reliability(50)


# ──────────────────────────────────────────────
# 2. JSON 추출 (코드펜스 처리)
# ──────────────────────────────────────────────


def test_strip_json_with_fence():
    raw = "```json\n{\"a\": 1}\n```"
    assert _strip_to_json(raw) == '{"a": 1}'


def test_strip_json_without_fence():
    raw = '   {"a": 1, "b": 2}   '
    assert _strip_to_json(raw) == '{"a": 1, "b": 2}'


def test_strip_json_with_prefix_text():
    """LLM이 'Here is the JSON:' 같은 prefix 붙여도 첫 { ~ 마지막 }만 추출."""
    raw = 'Here is your answer:\n{"a": 1}\nThanks!'
    assert _strip_to_json(raw) == '{"a": 1}'


def test_strip_json_no_braces_returns_empty():
    assert _strip_to_json("no json here") == "{}"
    assert _strip_to_json("") == "{}"


# ──────────────────────────────────────────────
# 3. 단정 표현 차단
# ──────────────────────────────────────────────


@pytest.mark.parametrize(
    "term",
    ["추천합니다", "사세요", "매수 신호", "매도 신호", "목표가", "손절가"],
)
def test_scrub_forbidden_detects_terms(term):
    out, found = _scrub_forbidden(f"이 종목은 {term}.")
    assert term in found
    assert term not in out
    assert "[중립표현 필요]" in out


def test_scrub_forbidden_clean_text_unchanged():
    text = "관찰 구간에서 멀티플 비교 가능."
    out, found = _scrub_forbidden(text)
    assert out == text
    assert found == []


# ──────────────────────────────────────────────
# 4. 안전망 자동 첨부 (_attach_safety via _post_process)
# ──────────────────────────────────────────────


def test_post_process_attaches_safety_fields():
    raw = json.dumps(
        {
            "comparable_events": [
                {"event": "Uber IPO 2019", "data_confidence": "medium"}
            ],
            "sample_size": 8,
            "qualitative_summary": "비교 사례 다수.",
        }
    )
    out = _post_process(raw)
    assert out["sample_size"] == 8
    assert "참고용" in out["sample_reliability"]
    assert "fabrication_warning" in out
    assert "verification_needed" in out
    assert "no_recommendation_disclaimer" in out
    assert "추천이 아닙니다" in out["no_recommendation_disclaimer"]


def test_post_process_low_sample_suppresses_statistics():
    raw = json.dumps(
        {
            "comparable_events": [{"event": "A"}, {"event": "B"}],
            "sample_size": 2,
        }
    )
    out = _post_process(raw)
    assert out["statistical_summary_suppressed"] is True
    assert "정성" in out["sample_reliability"]


def test_post_process_high_sample_no_suppression():
    raw = json.dumps(
        {"comparable_events": [], "sample_size": 12, "qualitative_summary": "x"}
    )
    out = _post_process(raw)
    assert "statistical_summary_suppressed" not in out
    assert "신뢰" in out["sample_reliability"]


def test_post_process_handles_invalid_json():
    """braces가 있지만 내부가 깨진 경우 → parse_error + 안전망."""
    raw = "{not valid json at all,,}"
    out = _post_process(raw)
    assert out["parse_error"] is True
    assert "fabrication_warning" in out
    assert out["sample_size"] == 0


def test_post_process_handles_empty_text():
    """braces 자체가 없는 경우 → 빈 dict로 시작, 안전망 첨부."""
    out = _post_process("not json here")
    # 깨끗한 빈 JSON은 parse_error로 표시되지 않지만 안전망은 첨부됨
    assert "fabrication_warning" in out
    assert out["sample_size"] == 0
    assert out["comparable_events"] == []


def test_post_process_scrubs_forbidden_in_response():
    """LLM이 단정어를 포함해도 응답에서 마스킹 + 발견 목록 표시."""
    # Claude는 한국어를 raw UTF-8로 응답 (escape 안 함). ensure_ascii=False 필수.
    raw = json.dumps(
        {
            "comparable_events": [],
            "sample_size": 5,
            "qualitative_summary": "이 종목은 매수 신호입니다.",
        },
        ensure_ascii=False,
    )
    out = _post_process(raw)
    assert "forbidden_terms_scrubbed" in out
    assert "매수 신호" in out["forbidden_terms_scrubbed"]


# ──────────────────────────────────────────────
# 5. 캐시 동작 (24h TTL, 동일 입력 → 1회만 호출)
# ──────────────────────────────────────────────


def _make_mock_client(content_str: str):
    client = MagicMock()
    client.complete = AsyncMock(return_value={"content": content_str})
    return client


def test_cache_hit_skips_second_api_call():
    raw = json.dumps({"comparable_events": [], "sample_size": 11})
    client = _make_mock_client(raw)

    async def run():
        r1 = await get_similar_events_cached(
            "IPO", "SpaceX IPO 2026 Q4", "SPACEX", "RKLB", claude_client=client
        )
        r2 = await get_similar_events_cached(
            "IPO", "SpaceX IPO 2026 Q4", "SPACEX", "RKLB", claude_client=client
        )
        return r1, r2

    r1, r2 = asyncio.run(run())
    assert r1["sample_size"] == 11
    assert r2.get("from_cache") is True
    assert client.complete.await_count == 1


def test_cache_miss_for_different_inputs():
    raw = json.dumps({"comparable_events": [], "sample_size": 11})
    client = _make_mock_client(raw)

    async def run():
        await get_similar_events_cached("IPO", "X", "P1", "S1", claude_client=client)
        await get_similar_events_cached("IPO", "Y", "P1", "S1", claude_client=client)

    asyncio.run(run())
    assert client.complete.await_count == 2


def test_cache_key_case_insensitive_for_tickers():
    """RKLB / rklb는 같은 캐시 키로 매핑 (대소문자 차이 무시)."""
    raw = json.dumps({"comparable_events": [], "sample_size": 11})
    client = _make_mock_client(raw)

    async def run():
        await get_similar_events_cached("IPO", "X", "spacex", "RKLB", claude_client=client)
        await get_similar_events_cached("IPO", "X", "SPACEX", "rklb", claude_client=client)

    asyncio.run(run())
    assert client.complete.await_count == 1


def test_skip_cache_forces_recall():
    raw = json.dumps({"comparable_events": [], "sample_size": 11})
    client = _make_mock_client(raw)

    async def run():
        await get_similar_events_cached("IPO", "X", "P", "S", claude_client=client)
        await get_similar_events_cached(
            "IPO", "X", "P", "S", claude_client=client, skip_cache=True
        )

    asyncio.run(run())
    assert client.complete.await_count == 2


# ──────────────────────────────────────────────
# 6. API 실패 graceful
# ──────────────────────────────────────────────


def test_api_failure_returns_safe_fallback():
    client = MagicMock()
    client.complete = AsyncMock(side_effect=RuntimeError("network down"))

    async def run():
        return await get_similar_events_cached(
            "IPO", "X", "P", "S", claude_client=client
        )

    out = asyncio.run(run())
    assert out["sample_size"] == 0
    assert "api_error" in out
    assert "RuntimeError" in out["api_error"]
    # 안전망은 여전히 첨부됨
    assert "fabrication_warning" in out
    assert "no_recommendation_disclaimer" in out


# ──────────────────────────────────────────────
# 7. SpaceX → RKLB 시나리오 (Day 4 검증 항목)
# ──────────────────────────────────────────────


def test_spacex_rklb_scenario_with_strong_sample():
    raw = json.dumps(
        {
            "comparable_events": [
                {
                    "event": "Uber IPO 2019.05",
                    "primary": "UBER",
                    "secondary": "LYFT",
                    "secondary_d_minus_60_to_d_day_return_pct": "+22%",
                    "data_confidence": "medium",
                }
            ]
            * 11,
            "sample_size": 11,
            "qualitative_summary": "동종업계 IPO 시 비교 종목 멀티플 리레이팅 관찰 다수.",
        }
    )
    client = _make_mock_client(raw)

    async def run():
        return await get_similar_events_cached(
            "IPO",
            "SpaceX IPO 2026 Q4",
            "SPACEX",
            "RKLB",
            claude_client=client,
        )

    out = asyncio.run(run())
    assert out["sample_size"] == 11
    assert "신뢰" in out["sample_reliability"]
    assert "fabrication_warning" in out
    assert "verification_needed" in out
    # 단정어 X
    full_text = json.dumps(out, ensure_ascii=False)
    for term in ("추천합니다", "매수 신호", "사세요"):
        assert term not in full_text
