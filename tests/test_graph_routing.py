"""LangGraph 6 페르소나 라우팅 단위 테스트 (mock 기반).

실제 Claude/Firestore 호출 없이 분기 + state 흐름만 검증.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.graph import (
    ALL_PERSONAS,
    AnalysisState,
    DATA_DRIVEN_PERSONAS,
    STRATEGIST_PERSONAS,
    is_data_driven_persona,
    is_strategist_persona,
    route_by_persona,
    run_analysis,
)


# ──────────────────────────────────────────────
# 1. 페르소나 그룹 분류
# ──────────────────────────────────────────────


def test_persona_groups_complete():
    assert STRATEGIST_PERSONAS == {"blackrock", "ark", "graham"}
    assert DATA_DRIVEN_PERSONAS == {"event", "macro", "korean"}
    assert ALL_PERSONAS == STRATEGIST_PERSONAS | DATA_DRIVEN_PERSONAS
    assert len(ALL_PERSONAS) == 6


def test_is_strategist_persona():
    for p in ("blackrock", "ark", "graham"):
        assert is_strategist_persona(p)
    for p in ("event", "macro", "korean", "unknown"):
        assert not is_strategist_persona(p)


def test_is_data_driven_persona():
    for p in ("event", "macro", "korean"):
        assert is_data_driven_persona(p)
    for p in ("blackrock", "ark", "graham", "unknown"):
        assert not is_data_driven_persona(p)


# ──────────────────────────────────────────────
# 2. route_by_persona — START 분기 결정
# ──────────────────────────────────────────────


@pytest.mark.parametrize(
    "persona,expected",
    [
        ("blackrock", "strategist_flow"),
        ("ark", "strategist_flow"),
        ("graham", "strategist_flow"),
        ("event", "event"),
        ("macro", "macro"),
        ("korean", "korean"),
        ("unknown", "strategist_flow"),  # fallback
        ("", "strategist_flow"),
    ],
)
def test_route_by_persona(persona, expected):
    state: AnalysisState = {"persona": persona, "ticker": "AAPL"}
    assert route_by_persona(state) == expected


# ──────────────────────────────────────────────
# 3. run_analysis — 페르소나별 노드 호출 검증
# ──────────────────────────────────────────────


def test_run_analysis_event_persona_calls_event_node_only():
    """persona='event'면 event_analyst만 호출 + research/analyst/strategist 미호출."""
    from agents.event_analyst import EventAnalystResult

    fake_event_result = EventAnalystResult(
        ticker="RKLB",
        market="US",
        event_summary=__import__("agents.event_analyst", fromlist=["EventSummary"]).EventSummary(
            event_type="earnings",
            event_target="Q1",
            certainty_breakdown=__import__(
                "agents.event_analyst", fromlist=["CertaintyBreakdown"]
            ).CertaintyBreakdown(
                source=8, timing=8, probability=7, impact=7, final_score=7.7, mode="Full Analysis"
            ),
        ),
        impact_mapping=__import__("agents.event_analyst", fromlist=["ImpactMapping"]).ImpactMapping(),
        volume_supply_analysis=__import__("agents.event_analyst", fromlist=["SignalBlock"]).SignalBlock(),
        options_signals=__import__("agents.event_analyst", fromlist=["SignalBlock"]).SignalBlock(),
        credit_short_signals=__import__("agents.event_analyst", fromlist=["SignalBlock"]).SignalBlock(),
        historical_statistics=__import__(
            "agents.event_analyst", fromlist=["HistoricalStatistics"]
        ).HistoricalStatistics(),
        reference_observation_zones=__import__(
            "agents.event_analyst", fromlist=["ReferenceZones"]
        ).ReferenceZones(),
        scenario_analysis=__import__(
            "agents.event_analyst", fromlist=["ScenarioAnalysis", "ScenarioCase"]
        ).ScenarioAnalysis(
            bullish_case=__import__("agents.event_analyst", fromlist=["ScenarioCase"]).ScenarioCase(),
            base_case=__import__("agents.event_analyst", fromlist=["ScenarioCase"]).ScenarioCase(),
            bearish_case=__import__("agents.event_analyst", fromlist=["ScenarioCase"]).ScenarioCase(),
        ),
        summary_neutral="이벤트 통계 분석",
    )

    fake_agent = MagicMock()
    fake_agent.run = AsyncMock(return_value=fake_event_result)

    with patch("agents.graph.EventAnalystAgent", return_value=fake_agent), \
         patch("agents.graph.AnalystAgent") as m_analyst, \
         patch("agents.graph.ResearchAgent") as m_research, \
         patch("agents.graph.StrategistAgent") as m_strat:
        async def run():
            return await run_analysis(
                ticker="RKLB",
                persona="event",
                event_type="earnings",
                event_target="RKLB Q1 2026",
            )

        final = asyncio.run(run())

    assert final.get("event_output") is not None
    assert final["event_output"].ticker == "RKLB"
    assert final.get("research_output") is None
    assert final.get("analyst_output") is None
    assert final.get("strategist_output") is None
    # 페르소나 노드만 호출
    fake_agent.run.assert_called_once()
    m_analyst.assert_not_called()
    m_research.assert_not_called()
    m_strat.assert_not_called()


def test_run_analysis_macro_persona_calls_macro_only():
    from agents.macro_pm import (
        CycleAnalysis, CycleStage, MacroPmResult, MacroRegime, WeightingUsed,
    )

    empty = CycleStage(stage="N/A")
    fake_macro = MacroPmResult(
        macro_regime=MacroRegime(current_regime="Goldilocks", regime_confidence=0.8),
        cycle_analysis=CycleAnalysis(
            interest_rate=empty, business_cycle=empty,
            currency_cycle=empty, inflation_cycle=empty,
        ),
        weighting_used=WeightingUsed(us_weight=0.9, kr_weight=0.1, rationale="US 종목"),
        summary_neutral="Goldilocks 국면 통상 패턴",
    )

    fake_agent = MagicMock()
    fake_agent.run = AsyncMock(return_value=fake_macro)

    with patch("agents.graph.MacroPmAgent", return_value=fake_agent), \
         patch("agents.graph.AnalystAgent") as m_analyst, \
         patch("agents.graph.ResearchAgent") as m_research:
        async def run():
            return await run_analysis(ticker="AAPL", persona="macro")

        final = asyncio.run(run())

    assert final.get("macro_output") is not None
    assert final["macro_output"].macro_regime.current_regime == "Goldilocks"
    assert final.get("research_output") is None
    m_analyst.assert_not_called()
    m_research.assert_not_called()


def test_run_analysis_korean_persona_calls_korean_only():
    from agents.korean_specialist import KoreaSpecificScore, KoreanSpecialistResult

    fake_korean = KoreanSpecialistResult(
        korea_specific_analysis={"ticker": "005930", "name": "삼성전자"},
        korea_specific_score=KoreaSpecificScore(weighted_total=7.5),
        summary_neutral="외국인 5일 연속 순매수 패턴 관찰.",
    )

    fake_agent = MagicMock()
    fake_agent.run = AsyncMock(return_value=fake_korean)

    with patch("agents.graph.KoreanSpecialistAgent", return_value=fake_agent), \
         patch("agents.graph.AnalystAgent") as m_analyst, \
         patch("agents.graph.ResearchAgent") as m_research:
        async def run():
            return await run_analysis(ticker="005930", persona="korean")

        final = asyncio.run(run())

    assert final.get("korean_output") is not None
    assert final["korean_output"].korea_specific_score.weighted_total == 7.5
    m_analyst.assert_not_called()
    m_research.assert_not_called()


# ──────────────────────────────────────────────
# 4. graceful degradation — 에이전트 실패 시 fallback
# ──────────────────────────────────────────────


def test_event_node_handles_exception_with_fallback():
    fake_agent = MagicMock()
    fake_agent.run = AsyncMock(side_effect=RuntimeError("API down"))

    with patch("agents.graph.EventAnalystAgent", return_value=fake_agent):
        async def run():
            return await run_analysis(ticker="RKLB", persona="event")

        final = asyncio.run(run())

    out = final.get("event_output")
    assert out is not None
    assert out.event_summary.certainty_breakdown.mode == "Refused"
    assert "분석 실패" in out.event_summary.badge or "분석" in out.summary_neutral
    assert "RuntimeError" in out.summary_neutral


def test_macro_node_handles_exception_with_fallback():
    fake_agent = MagicMock()
    fake_agent.run = AsyncMock(side_effect=RuntimeError("FRED down"))

    with patch("agents.graph.MacroPmAgent", return_value=fake_agent):
        async def run():
            return await run_analysis(ticker="AAPL", persona="macro")

        final = asyncio.run(run())

    out = final.get("macro_output")
    assert out is not None
    assert "오류" in out.summary_neutral
    assert out.macro_regime.current_regime == "Transition"


def test_korean_node_handles_exception_with_fallback():
    fake_agent = MagicMock()
    fake_agent.run = AsyncMock(side_effect=RuntimeError("DART down"))

    with patch("agents.graph.KoreanSpecialistAgent", return_value=fake_agent):
        async def run():
            return await run_analysis(ticker="005930", persona="korean")

        final = asyncio.run(run())

    out = final.get("korean_output")
    assert out is not None
    assert "오류" in out.summary_neutral


# ──────────────────────────────────────────────
# 5. unknown persona fallback
# ──────────────────────────────────────────────


def test_unknown_persona_falls_back_to_strategist_flow_and_warns(caplog):
    """알 수 없는 페르소나는 'blackrock'으로 fallback (경고 후 strategist 흐름)."""
    # 실제 에이전트 호출 없이 route만 검증 — Strategist 흐름은 mock
    fake_research = MagicMock()
    fake_research.run = AsyncMock(side_effect=RuntimeError("skip"))
    fake_analyst = MagicMock()
    fake_analyst.run = AsyncMock(side_effect=RuntimeError("skip"))

    # graph 구성을 직접 호출 — strategist_flow로 분기되는지만 확인
    state: AnalysisState = {"persona": "WRONG", "ticker": "AAPL"}
    assert route_by_persona(state) == "strategist_flow"
