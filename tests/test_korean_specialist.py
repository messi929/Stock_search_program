"""Korean Specialist Agent 단위 테스트 (mock 기반)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from agents.korean_specialist import (
    KoreaSpecificScore,
    KoreanSpecialistAgent,
    KoreanSpecialistInput,
    KoreanSpecialistResult,
    WEIGHTS,
    calculate_weighted_total,
)


# ──────────────────────────────────────────────
# 1. weighted_total 가중 평균
# ──────────────────────────────────────────────


def test_weights_sum_to_one():
    assert sum(WEIGHTS.values()) == pytest.approx(1.0)


def test_weighted_total_all_max():
    s = KoreaSpecificScore(
        foreign_supply=10, governance=10, valueup_alignment=10,
        theme_position=10, policy_friendliness=10,
    )
    assert calculate_weighted_total(s) == pytest.approx(10.0)


def test_weighted_total_all_zero():
    s = KoreaSpecificScore()
    assert calculate_weighted_total(s) == 0.0


def test_weighted_total_skewed_to_foreign():
    """외국인 수급 가중치가 가장 큼 (35%)."""
    s = KoreaSpecificScore(
        foreign_supply=10, governance=0, valueup_alignment=0,
        theme_position=0, policy_friendliness=0,
    )
    assert calculate_weighted_total(s) == pytest.approx(3.5, abs=0.01)


# ──────────────────────────────────────────────
# 2. 비한국 종목 거부
# ──────────────────────────────────────────────


def test_non_korean_ticker_returns_refused():
    agent = KoreanSpecialistAgent.__new__(KoreanSpecialistAgent)
    agent.agent_name = "korean_specialist"
    agent.system_prompt = ""
    agent.model = "claude-sonnet-4-6"

    async def run():
        return await agent.run(KoreanSpecialistInput(ticker="AAPL"))

    result = asyncio.run(run())
    assert "한국 종목이 아닙니다" in result.summary_neutral


def test_short_numeric_ticker_padded_and_run():
    """5자리 종목코드 → 6자리 zfill 후 정상 처리."""
    agent = KoreanSpecialistAgent.__new__(KoreanSpecialistAgent)
    agent.agent_name = "korean_specialist"
    agent.system_prompt = ""
    agent.model = "claude-sonnet-4-6"

    response = _minimal_korean_response()
    async def run():
        with patch.object(agent, "_collect_korea_bundle", return_value={"ticker": "005930"}), \
             patch.object(
                 agent,
                 "call_claude_json",
                 new=AsyncMock(return_value=(KoreanSpecialistResult.model_validate(response), {})),
             ):
            return await agent.run(KoreanSpecialistInput(ticker="5930"))

    result = asyncio.run(run())
    assert result.korea_specific_analysis["ticker"] == "005930"


# ──────────────────────────────────────────────
# 3. 데이터 수집 — 부분 실패 graceful
# ──────────────────────────────────────────────


def test_collect_korea_bundle_partial_failure():
    agent = KoreanSpecialistAgent.__new__(KoreanSpecialistAgent)
    agent.agent_name = "korean_specialist"

    with patch.object(agent, "_fetch_valueup", return_value={"included": True}), \
         patch.object(agent, "_fetch_chaebol", side_effect=RuntimeError("blocked")), \
         patch.object(agent, "_fetch_governance", return_value={"total_score": 7}), \
         patch.object(agent, "_fetch_buyback_summary", side_effect=ValueError("dart down")), \
         patch.object(agent, "_fetch_short_selling", return_value={"current_short_ratio_pct": 1.2}), \
         patch.object(agent, "_fetch_supply", return_value={"foreign_consecutive_buy_days": 3}):
        bundle = agent._collect_korea_bundle("005930")

    # 성공한 것은 정상 dict
    assert bundle["valueup"]["included"] is True
    assert bundle["governance"]["total_score"] == 7
    assert bundle["short_selling"]["current_short_ratio_pct"] == 1.2
    assert bundle["supply"]["foreign_consecutive_buy_days"] == 3
    # 실패한 것은 available=False 표시
    assert bundle["chaebol"]["available"] is False
    assert "RuntimeError" in bundle["chaebol"]["error"]
    assert bundle["buyback"]["available"] is False
    assert "ValueError" in bundle["buyback"]["error"]


# ──────────────────────────────────────────────
# 4. run() — 사후 일관성 (weighted_total 재계산, governance disclaimer 강제)
# ──────────────────────────────────────────────


def _minimal_korean_response() -> dict:
    return {
        "korea_specific_analysis": {
            "ticker": "005930",
            "name": "삼성전자",
            "group": "삼성",
            "kospi_kosdaq": "KOSPI",
        },
        "foreign_supply_analysis": {"foreign_consecutive_buy_days": 5, "interpretation": "강한 시그널"},
        "chaebol_structure_analysis": {
            "is_chaebol": True,
            "group_name": "삼성",
            "governance_score": 7,
            # governance_disclaimer 누락 — 강제 첨부 대상
        },
        "value_up_analysis": {"value_up_index_included": True, "valueup_score": 8, "interpretation": "..."},
        "theme_cycle_analysis": {"main_theme": "반도체", "cycle_stage": "Expansion", "stage_rationale": "..."},
        "policy_risk_analysis": {"short_selling_status": "재개", "policy_implications": "..."},
        "korea_specific_score": {
            "foreign_supply": 9,
            "governance": 7,
            "valueup_alignment": 8,
            "theme_position": 7,
            "policy_friendliness": 6,
            "weighted_total": 0.0,  # 0으로 와도 시스템 후처리에서 재계산
            "interpretation": "...",
        },
        "what_to_watch_korea_specific": [],
        "summary_neutral": "삼성전자는 외국인 5일 연속 순매수 패턴 관찰.",
    }


def test_run_recalculates_weighted_total():
    agent = KoreanSpecialistAgent.__new__(KoreanSpecialistAgent)
    agent.agent_name = "korean_specialist"
    agent.system_prompt = ""
    agent.model = "claude-sonnet-4-6"

    response = _minimal_korean_response()

    async def run():
        with patch.object(agent, "_collect_korea_bundle", return_value={"ticker": "005930"}), \
             patch.object(
                 agent,
                 "call_claude_json",
                 new=AsyncMock(return_value=(KoreanSpecialistResult.model_validate(response), {})),
             ):
            return await agent.run(KoreanSpecialistInput(ticker="005930"))

    result = asyncio.run(run())
    s = result.korea_specific_score
    # 9*0.35 + 7*0.20 + 8*0.20 + 7*0.15 + 6*0.10 = 3.15 + 1.4 + 1.6 + 1.05 + 0.6 = 7.8
    assert s.weighted_total == pytest.approx(7.8, abs=0.01)


def test_run_attaches_governance_disclaimer_when_missing():
    agent = KoreanSpecialistAgent.__new__(KoreanSpecialistAgent)
    agent.agent_name = "korean_specialist"
    agent.system_prompt = ""
    agent.model = "claude-sonnet-4-6"

    response = _minimal_korean_response()
    # 명시적으로 disclaimer 누락
    response["chaebol_structure_analysis"].pop("governance_disclaimer", None)

    async def run():
        with patch.object(agent, "_collect_korea_bundle", return_value={"ticker": "005930"}), \
             patch.object(
                 agent,
                 "call_claude_json",
                 new=AsyncMock(return_value=(KoreanSpecialistResult.model_validate(response), {})),
             ):
            return await agent.run(KoreanSpecialistInput(ticker="005930"))

    result = asyncio.run(run())
    disclaimer = result.chaebol_structure_analysis.get("governance_disclaimer", "")
    assert "외부 평가기관" in disclaimer or "자체" in disclaimer


def test_run_filters_forbidden_in_summary():
    agent = KoreanSpecialistAgent.__new__(KoreanSpecialistAgent)
    agent.agent_name = "korean_specialist"
    agent.system_prompt = ""
    agent.model = "claude-sonnet-4-6"

    response = _minimal_korean_response()
    response["summary_neutral"] = "외국인이 사니까 사세요."

    async def run():
        with patch.object(agent, "_collect_korea_bundle", return_value={"ticker": "005930"}), \
             patch.object(
                 agent,
                 "call_claude_json",
                 new=AsyncMock(return_value=(KoreanSpecialistResult.model_validate(response), {})),
             ):
            return await agent.run(KoreanSpecialistInput(ticker="005930"))

    result = asyncio.run(run())
    assert "사세요" not in result.summary_neutral
    assert "[필터링됨]" in result.summary_neutral


def test_persona_md_loads():
    agent = KoreanSpecialistAgent()
    assert "Korean Market Specialist" in agent.system_prompt
    assert "외국인" in agent.system_prompt
    assert "밸류업" in agent.system_prompt
