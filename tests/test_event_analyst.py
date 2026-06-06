"""Event Analyst Agent 단위 테스트 (mock 기반).

실 Claude 호출은 별도 통합 테스트. 본 파일은 데이터 수집 + 모드 분기 +
사후 일관성 보정 + LEGAL 후처리를 mock으로 검증.

2026-06-06: event는 LLM이 단순 평탄 스키마(_EventLLMOutput)를 채우고 코드가
EventAnalystResult로 조립(_assemble)하는 구조로 단순화됨. run/completeness 테스트는
_EventLLMOutput 기준.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from agents.event_analyst import (
    EventAnalystAgent,
    EventAnalystInput,
    _EventLLMOutput,
    calculate_final_score,
    check_event_completeness,
    determine_mode,
    is_kr_ticker,
)


# ──────────────────────────────────────────────
# 1. 4차원 가중 평균 + 모드 분기
# ──────────────────────────────────────────────


@pytest.mark.parametrize(
    "src,tim,prob,imp,expected",
    [
        (10, 10, 10, 10, 10.0),
        (0, 0, 0, 0, 0.0),
        (10, 10, 0, 0, 7.0),
        (5, 5, 5, 5, 5.0),
        (8, 6, 4, 2, 0.4 * 8 + 0.3 * 6 + 0.2 * 4 + 0.1 * 2),
    ],
)
def test_calculate_final_score(src, tim, prob, imp, expected):
    assert calculate_final_score(src, tim, prob, imp) == pytest.approx(expected)


@pytest.mark.parametrize(
    "score,mode_expect,badge_contains",
    [
        (10.0, "Full Analysis", "확정"),
        (9.0, "Full Analysis", "확정"),
        (8.5, "Full Analysis", "신뢰"),
        (7.0, "Full Analysis", "신뢰"),
        (6.5, "Cautious", "추정"),
        (5.0, "Cautious", "추정"),
        (4.5, "Probabilistic Only", "추측"),
        (3.0, "Probabilistic Only", "추측"),
        (2.5, "Refused", "거부"),
        (0.0, "Refused", "거부"),
    ],
)
def test_determine_mode(score, mode_expect, badge_contains):
    mode, badge = determine_mode(score)
    assert mode == mode_expect
    assert badge_contains in badge


# ──────────────────────────────────────────────
# 2. ticker 시장 자동 추론
# ──────────────────────────────────────────────


def test_is_kr_ticker_six_digit():
    assert is_kr_ticker("005930") is True
    assert is_kr_ticker("373220") is True


def test_is_kr_ticker_us_symbol():
    assert is_kr_ticker("AAPL") is False
    assert is_kr_ticker("RKLB") is False


def test_is_kr_ticker_invalid():
    assert is_kr_ticker("12345") is False
    assert is_kr_ticker("0059300") is False
    assert is_kr_ticker("") is False


# ──────────────────────────────────────────────
# 3. 데이터 수집 분기 (KR/US)
# ──────────────────────────────────────────────


def test_us_ticker_collects_options_yfinance_not_short():
    agent = EventAnalystAgent.__new__(EventAnalystAgent)
    agent.agent_name = "event_analyst"
    agent.system_prompt = ""

    with patch.object(agent, "_fetch_options", return_value={"available": True, "expiration": "2026-06-19"}), \
         patch.object(agent, "_fetch_yfinance_events", return_value={"earnings_dates": [], "dividends": [], "next_earnings": None, "next_ex_dividend": None, "quarterly_income_available": True}), \
         patch.object(agent, "_fetch_short_selling") as m_short:
        async def run():
            return await agent._collect_data_bundle(
                EventAnalystInput(ticker="AAPL", market="US")
            )

        bundle = asyncio.run(run())
        assert bundle["options"]["available"] is True
        assert "short_selling" not in bundle
        m_short.assert_not_called()


def test_kr_ticker_collects_short_not_options():
    agent = EventAnalystAgent.__new__(EventAnalystAgent)
    agent.agent_name = "event_analyst"

    with patch.object(agent, "_fetch_short_selling", return_value={"current_short_ratio_pct": 1.2}) as m_short, \
         patch.object(agent, "_fetch_options") as m_opt, \
         patch.object(agent, "_fetch_yfinance_events") as m_yf:
        async def run():
            return await agent._collect_data_bundle(
                EventAnalystInput(ticker="005930", market="KR")
            )

        bundle = asyncio.run(run())
        assert "short_selling" in bundle
        assert bundle["options"]["available"] is False
        assert "한국 개별 종목 옵션" in bundle["options"]["reason"]
        m_short.assert_called_once()
        m_opt.assert_not_called()
        m_yf.assert_not_called()


def test_collect_data_bundle_handles_module_failures():
    agent = EventAnalystAgent.__new__(EventAnalystAgent)
    agent.agent_name = "event_analyst"

    with patch.object(agent, "_fetch_options", side_effect=RuntimeError("yfinance blocked")), \
         patch.object(agent, "_fetch_yfinance_events", return_value={"earnings_dates": [], "dividends": []}):
        async def run():
            return await agent._collect_data_bundle(
                EventAnalystInput(ticker="RKLB", market="US")
            )

        bundle = asyncio.run(run())
        assert bundle["options"]["available"] is False
        assert bundle["options"]["error"] == "RuntimeError"
        assert "yfinance_events" in bundle


def test_ipo_secondary_lookup_when_event_type():
    agent = EventAnalystAgent.__new__(EventAnalystAgent)
    agent.agent_name = "event_analyst"

    with patch.object(agent, "_fetch_options", return_value={"available": False}), \
         patch.object(agent, "_fetch_yfinance_events", return_value={"earnings_dates": [], "dividends": []}), \
         patch("utils.data_collectors.event_metadata.find_ipos_for_secondary") as m_find:
        m_find.return_value = [{"company": "SpaceX", "secondary_beneficiaries": ["RKLB"]}]

        async def run():
            return await agent._collect_data_bundle(
                EventAnalystInput(
                    ticker="RKLB",
                    market="US",
                    event_type="ipo_secondary",
                    primary_ticker="SPACEX",
                )
            )

        bundle = asyncio.run(run())
        assert "ipo_secondary" in bundle
        assert bundle["ipo_secondary"][0]["company"] == "SpaceX"


# ──────────────────────────────────────────────
# 4. LLM 단순 출력 → 조립(_assemble) 사후 일관성 보정
# ──────────────────────────────────────────────


def _llm_dict() -> dict:
    """LLM이 채우는 단순 스키마(_EventLLMOutput)용 dict."""
    return {
        "source": 9, "timing": 9, "probability": 10, "impact": 8,
        "certainty_rationale": "공식 발표 + 일자 확정",
        "direct_beneficiary": {"ticker": "AAPL", "rationale": "직접 수혜"},
        "secondary_beneficiaries": [{"ticker": "X", "rationale": "2차"}],
        "comparable_events_count": 12,
        "current_position_vs_history": "현재가 +5%는 1σ 이내",
        "vol_lower_1sigma": "-8%",
        "vol_upper_1sigma": "+12%",
        "bullish_case": {"trigger": "a", "historical_pattern": "b", "probability": "30%"},
        "base_case": {"trigger": "c", "historical_pattern": "d", "probability": "50%"},
        "bearish_case": {"trigger": "e", "historical_pattern": "f", "probability": "20%"},
        "key_risks": ["리스크1"],
        "what_to_watch": ["관전1"],
        "summary_neutral": "AAPL 실적 관찰 구간으로 분류됩니다.",
    }


def _run_with_llm(llm: dict):
    agent = EventAnalystAgent.__new__(EventAnalystAgent)
    agent.agent_name = "event_analyst"
    agent.system_prompt = ""
    agent.model = "claude-sonnet-4-6"

    async def run():
        with patch.object(agent, "_collect_data_bundle", return_value={"market": "US", "ticker": "AAPL"}), \
             patch.object(
                 agent, "call_claude_json",
                 new=AsyncMock(return_value=(_EventLLMOutput.model_validate(llm), {})),
             ):
            return await agent.run(EventAnalystInput(ticker="AAPL", market="US"))

    return asyncio.run(run())


def test_assemble_recalculates_final_score_and_mode():
    """LLM 4차원 점수 → 코드가 final_score/mode/badge 계산."""
    result = _run_with_llm(_llm_dict())
    cb = result.event_summary.certainty_breakdown
    # 9,9,10,8 → 0.4*9+0.3*9+0.2*10+0.1*8 = 9.1
    assert cb.final_score == pytest.approx(9.1, abs=0.01)
    assert cb.mode == "Full Analysis"
    assert "확정" in result.event_summary.badge


def test_assemble_fills_event_type_target_from_input():
    """event_type/target은 입력에서 강제 주입."""
    result = _run_with_llm(_llm_dict())
    assert result.event_summary.event_type  # 비어있지 않음
    assert result.event_summary.event_target


def test_assemble_classifies_sample_reliability_high():
    llm = _llm_dict()
    llm["comparable_events_count"] = 12
    result = _run_with_llm(llm)
    assert "신뢰 가능" in result.historical_statistics.sample_reliability


def test_assemble_low_sample_marks_uncertain():
    llm = _llm_dict()
    llm["comparable_events_count"] = 3
    result = _run_with_llm(llm)
    assert "미제시" in result.historical_statistics.sample_reliability


def test_assemble_attaches_fabrication_warning():
    result = _run_with_llm(_llm_dict())
    assert "외부 검증" in result.historical_statistics.fabrication_warning


def test_assemble_filters_forbidden_in_summary():
    llm = _llm_dict()
    llm["summary_neutral"] = "AAPL 실적 발표일 매수하세요."
    result = _run_with_llm(llm)
    assert "매수하세요" not in result.summary_neutral
    assert "[필터링됨]" in result.summary_neutral


def test_assemble_maps_scenarios_and_beneficiaries():
    """단순 출력의 시나리오/수혜가 EventAnalystResult 구조로 매핑."""
    result = _run_with_llm(_llm_dict())
    assert result.scenario_analysis.bullish_case.trigger == "a"
    assert result.scenario_analysis.bearish_case.probability == "20%"
    assert result.impact_mapping.direct_beneficiary.get("ticker") == "AAPL"
    assert result.impact_mapping.secondary_beneficiaries[0].get("ticker") == "X"


# ──────────────────────────────────────────────
# 5. Refused 모드 — 사전 차단
# ──────────────────────────────────────────────


def test_refused_mode_skips_claude_call():
    agent = EventAnalystAgent.__new__(EventAnalystAgent)
    agent.agent_name = "event_analyst"
    agent.system_prompt = ""
    agent.model = "claude-sonnet-4-6"

    bundle = {"market": "KR", "ticker": "005930", "certainty_pre_check": 1}

    async def run():
        with patch.object(agent, "_collect_data_bundle", return_value=bundle), \
             patch.object(agent, "call_claude_json"):
            return await agent.run(EventAnalystInput(ticker="005930", market="KR"))

    result = asyncio.run(run())
    assert result.event_summary.certainty_breakdown.mode == "Refused"
    assert "거부" in result.event_summary.badge


def test_graceful_fallback_on_parse_failure():
    """call_claude_json이 최종 실패해도 raw 에러 대신 유효 구조 반환."""
    agent = EventAnalystAgent.__new__(EventAnalystAgent)
    agent.agent_name = "event_analyst"
    agent.system_prompt = ""
    agent.model = "claude-sonnet-4-6"

    async def run():
        with patch.object(agent, "_collect_data_bundle", return_value={"market": "US", "ticker": "AAPL"}), \
             patch.object(
                 agent, "call_claude_json",
                 new=AsyncMock(side_effect=ValueError("parse fail")),
             ):
            return await agent.run(EventAnalystInput(ticker="AAPL", market="US"))

    result = asyncio.run(run())
    assert result.persona == "event"
    assert result.summary_neutral  # 비어있지 않은 친화 메시지
    assert "ValueError" not in result.summary_neutral  # raw 에러 노출 금지


# ──────────────────────────────────────────────
# 6. 시스템 프롬프트 로딩
# ──────────────────────────────────────────────


def test_persona_md_loads_with_legal_rules():
    agent = EventAnalystAgent()
    assert "LEGAL Hard Rules" in agent.system_prompt or "절대 금지" in agent.system_prompt
    assert "summary_neutral" in agent.system_prompt
    assert "scenario_analysis" in agent.system_prompt
    assert "current_position_vs_history" in agent.system_prompt


# ──────────────────────────────────────────────
# 7. 완전성 검사 — check_event_completeness(_EventLLMOutput)
# ──────────────────────────────────────────────


def test_completeness_full_response_returns_empty():
    out = _EventLLMOutput.model_validate(_llm_dict())
    assert check_event_completeness(out) == []


def test_completeness_detects_missing_summary():
    llm = _llm_dict()
    llm["summary_neutral"] = "   "
    out = _EventLLMOutput.model_validate(llm)
    assert "summary_neutral" in check_event_completeness(out)


def test_completeness_detects_missing_scenarios():
    llm = _llm_dict()
    llm["bullish_case"] = {}
    llm["base_case"] = {}
    llm["bearish_case"] = {}
    out = _EventLLMOutput.model_validate(llm)
    assert "scenario_analysis" in check_event_completeness(out)


def test_completeness_detects_zero_certainty():
    llm = _llm_dict()
    llm["source"] = llm["timing"] = llm["probability"] = llm["impact"] = 0
    out = _EventLLMOutput.model_validate(llm)
    assert "certainty_scores" in check_event_completeness(out)
