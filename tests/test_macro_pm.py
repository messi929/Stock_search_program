"""Macro PM Agent 단위 테스트 (mock 기반)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.macro_pm import (
    CycleAnalysis,
    CycleStage,
    MacroPmAgent,
    MacroPmInput,
    MacroPmResult,
    MacroRegime,
    StockMacroAlignment,
    WeightingUsed,
    check_macro_completeness,
    determine_weights,
)


# ──────────────────────────────────────────────
# 1. 동적 가중치
# ──────────────────────────────────────────────


@pytest.mark.parametrize(
    "market,qtype,us_w,kr_w",
    [
        ("KR", "stock", 0.4, 0.6),
        ("US", "stock", 0.9, 0.1),
        (None, "etf", 0.7, 0.3),
        (None, "macro_only", 0.7, 0.3),
        (None, "stock", 0.7, 0.3),  # market 미상 fallback
    ],
)
def test_determine_weights(market, qtype, us_w, kr_w):
    actual_us, actual_kr, _ = determine_weights(market, qtype)
    assert actual_us == pytest.approx(us_w)
    assert actual_kr == pytest.approx(kr_w)
    # 합 1.0 검증
    assert (actual_us + actual_kr) == pytest.approx(1.0)


# ──────────────────────────────────────────────
# 2. fetch_macro_bundle — 데이터 부재 graceful
# ──────────────────────────────────────────────


def test_macro_bundle_returns_unavailable_when_inputs_empty():
    agent = MacroPmAgent.__new__(MacroPmAgent)
    agent.agent_name = "macro_pm"
    agent.system_prompt = ""

    with patch.object(agent, "_load_macro_inputs", return_value={}):
        bundle = agent._fetch_macro_bundle(country="US")
    assert bundle["available"] is False
    assert "데이터 없음" in bundle.get("reason", "")


def test_macro_bundle_handles_load_exception():
    agent = MacroPmAgent.__new__(MacroPmAgent)
    agent.agent_name = "macro_pm"
    with patch.object(agent, "_load_macro_inputs", side_effect=RuntimeError("firestore down")):
        bundle = agent._fetch_macro_bundle(country="US")
    assert bundle["available"] is False
    assert "firestore down" in bundle.get("error", "")


def test_macro_bundle_returns_cycles_and_regime_when_inputs_complete():
    """완전한 inputs → cycle_detector + regime_detector 정상 호출."""
    agent = MacroPmAgent.__new__(MacroPmAgent)
    agent.agent_name = "macro_pm"

    # 완전한 입력 (cycle_detector REQUIRED_INPUTS 만족)
    inputs = {
        "rate_current": 4.0,
        "rate_3m_ago": 4.5,
        "rate_12m_ago": 5.5,
        "spread_10y_2y": 0.5,
        "gdp_yoy": 2.5,
        "industrial_production_yoy": 2.0,
        "unemployment_current": 3.8,
        "unemployment_12m_ago": 3.6,
        "cpi_yoy": 2.4,
        "core_cpi_yoy": 2.2,
        "cpi_3m_avg_change": -0.1,
        "dxy_current": 100.0,
        "dxy_3m_ago": 102.0,
        "dxy_12m_ago": 104.0,
    }
    with patch.object(agent, "_load_macro_inputs", return_value=inputs):
        bundle = agent._fetch_macro_bundle(country="US")
    assert bundle["available"] is True
    assert "cycles" in bundle
    assert "regime" in bundle
    # 4 사이클 모두 포함
    for axis in ("interest_rate", "business_cycle", "currency", "inflation"):
        assert axis in bundle["cycles"]


# ──────────────────────────────────────────────
# 3. run() — 가중치 + regime 강제 일관성 보정
# ──────────────────────────────────────────────


def _minimal_macro_response(regime_name: str = "Goldilocks", confidence: float = 0.75) -> dict:
    return {
        "macro_regime": {
            "current_regime": regime_name,
            "transition_to": None,
            "regime_confidence": confidence,
        },
        "cycle_analysis": {
            "interest_rate": {"stage": "인하 후반", "key_indicators": {}, "rationale": "..."},
            "business_cycle": {"stage": "확장 후기", "key_indicators": {}, "rationale": "..."},
            "currency_cycle": {"stage": "달러 약세", "key_indicators": {}, "rationale": "..."},
            "inflation_cycle": {"stage": "저인플레", "key_indicators": {}, "rationale": "..."},
        },
        "regime_implications": {"favored_assets_historically": ["성장주"]},
        "transition_signals_to_monitor": [],
        "stock_specific_analysis": {
            "ticker": "AAPL",
            "sector": "기술",
            "macro_alignment": "✅ 강세",
            "alignment_score": 8,
            "interpretation": "Goldilocks에서 기술주 강세 패턴",
        },
        "weighting_used": {
            "us_weight": 0.5,  # 보정 대상 — 입력 KR이면 0.4로 강제됨
            "kr_weight": 0.5,
            "rationale": "WRONG",
        },
        "summary_neutral": "AAPL은 Goldilocks 국면 통상 강세 자산.",
    }


def test_run_forces_correct_weights_for_kr_ticker():
    """입력 market=KR이면 us_weight=0.4, kr_weight=0.6 강제."""
    agent = MacroPmAgent.__new__(MacroPmAgent)
    agent.agent_name = "macro_pm"
    agent.system_prompt = ""
    agent.model = "claude-sonnet-4-6"

    response = _minimal_macro_response()

    async def run():
        with patch.object(agent, "_fetch_macro_bundle", return_value={"available": False}), \
             patch.object(
                 agent,
                 "call_claude_json",
                 new=AsyncMock(return_value=(MacroPmResult.model_validate(response), {})),
             ):
            return await agent.run(MacroPmInput(ticker="005930", market="KR", question_type="stock"))

    result = asyncio.run(run())
    assert result.weighting_used.us_weight == pytest.approx(0.4)
    assert result.weighting_used.kr_weight == pytest.approx(0.6)
    assert "한국" in result.weighting_used.rationale


def test_run_forces_quantitative_regime_when_llm_disagrees():
    """LLM이 'Reflation'이라 해도 정량 결과가 'Goldilocks'면 Goldilocks 강제."""
    agent = MacroPmAgent.__new__(MacroPmAgent)
    agent.agent_name = "macro_pm"
    agent.system_prompt = ""
    agent.model = "claude-sonnet-4-6"

    response = _minimal_macro_response(regime_name="Reflation", confidence=0.5)
    bundle = {
        "available": True,
        "regime": {
            "regime": "Goldilocks",
            "regime_confidence": 0.85,
            "transition_to": "Late Cycle",
        },
        "cycles": {},
    }

    async def run():
        with patch.object(agent, "_fetch_macro_bundle", return_value=bundle), \
             patch.object(
                 agent,
                 "call_claude_json",
                 new=AsyncMock(return_value=(MacroPmResult.model_validate(response), {})),
             ):
            return await agent.run(MacroPmInput(ticker="AAPL", market="US", question_type="stock"))

    result = asyncio.run(run())
    assert result.macro_regime.current_regime == "Goldilocks"  # 정량 강제
    assert result.macro_regime.regime_confidence == pytest.approx(0.85)
    assert result.macro_regime.transition_to == "Late Cycle"


def test_run_filters_forbidden_in_summary():
    agent = MacroPmAgent.__new__(MacroPmAgent)
    agent.agent_name = "macro_pm"
    agent.system_prompt = ""
    agent.model = "claude-sonnet-4-6"

    response = _minimal_macro_response()
    response["summary_neutral"] = "Goldilocks 진입했으니 매수하세요."

    async def run():
        with patch.object(agent, "_fetch_macro_bundle", return_value={"available": False}), \
             patch.object(
                 agent,
                 "call_claude_json",
                 new=AsyncMock(return_value=(MacroPmResult.model_validate(response), {})),
             ):
            return await agent.run(MacroPmInput(ticker="AAPL", market="US"))

    result = asyncio.run(run())
    assert "매수하세요" not in result.summary_neutral
    assert "[필터링됨]" in result.summary_neutral


def test_persona_md_loads():
    agent = MacroPmAgent()
    assert "Macro PM" in agent.system_prompt
    assert "Goldilocks" in agent.system_prompt
    assert "절대 금지" in agent.system_prompt
    # 필수 필드 누락 금지 섹션 (B 작업)
    assert "필수 필드" in agent.system_prompt


# ──────────────────────────────────────────────
# 4. 완전성 검사 — check_macro_completeness
# ──────────────────────────────────────────────


def test_completeness_full_response_returns_empty():
    result = MacroPmResult.model_validate(_minimal_macro_response())
    assert check_macro_completeness(result) == []


def test_completeness_detects_missing_summary():
    response = _minimal_macro_response()
    response["summary_neutral"] = ""
    result = MacroPmResult.model_validate(response)
    assert "summary_neutral" in check_macro_completeness(result)


def test_completeness_detects_missing_cycle_analysis():
    """cycle_analysis 통째 누락 — default_factory로 검증은 통과하나 빈 카드."""
    response = _minimal_macro_response()
    del response["cycle_analysis"]
    result = MacroPmResult.model_validate(response)
    assert "cycle_analysis" in check_macro_completeness(result)
