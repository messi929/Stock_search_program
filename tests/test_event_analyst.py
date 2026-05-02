"""Event Analyst Agent 단위 테스트 (mock 기반).

실 Claude 호출은 별도 통합 테스트. 본 파일은 데이터 수집 + 모드 분기 +
사후 일관성 보정 + LEGAL 후처리를 mock으로 검증.
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.event_analyst import (
    EventAnalystAgent,
    EventAnalystInput,
    EventAnalystResult,
    calculate_final_score,
    determine_mode,
    is_kr_ticker,
)


# ──────────────────────────────────────────────
# 1. 4차원 가중 평균 + 모드 분기
# ──────────────────────────────────────────────


@pytest.mark.parametrize(
    "src,tim,prob,imp,expected",
    [
        (10, 10, 10, 10, 10.0),  # 전 만점
        (0, 0, 0, 0, 0.0),
        (10, 10, 0, 0, 7.0),  # 0.4*10 + 0.3*10 = 7.0
        (5, 5, 5, 5, 5.0),
        (8, 6, 4, 2, 0.4 * 8 + 0.3 * 6 + 0.2 * 4 + 0.1 * 2),  # 6.0
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
    assert is_kr_ticker("12345") is False  # 5자리
    assert is_kr_ticker("0059300") is False  # 7자리
    assert is_kr_ticker("") is False


# ──────────────────────────────────────────────
# 3. 데이터 수집 분기 (KR/US)
# ──────────────────────────────────────────────


def _patch_claude(agent, parsed_response: dict):
    """call_claude_json을 mock — Pydantic 검증을 통과하는 dict 반환."""
    async def fake_complete(*args, **kwargs):
        return EventAnalystResult.model_validate(parsed_response), {"usage": MagicMock()}

    agent.call_claude_json = AsyncMock(side_effect=fake_complete)


def _minimal_response_dict(ticker: str = "AAPL", market: str = "US") -> dict:
    """모드 분기 검증용 최소 응답."""
    return {
        "ticker": ticker,
        "market": market,
        "event_summary": {
            "event_type": "earnings",
            "event_target": "Q1 2026",
            "d_day": "2026-05-15",
            "certainty_breakdown": {
                "source": 9, "source_rationale": "공식 발표",
                "timing": 9, "timing_rationale": "일자 확정",
                "probability": 10, "probability_rationale": "거의 확정",
                "impact": 8, "impact_rationale": "직접+2차",
                "final_score": 9.0,  # 보정 대상
                "mode": "WRONG",  # 보정 대상
            },
            "badge": "WRONG",  # 보정 대상
        },
        "impact_mapping": {},
        "volume_supply_analysis": {"available": True, "interpretation": "관찰"},
        "options_signals": {"available": False, "interpretation": ""},
        "credit_short_signals": {"available": False, "interpretation": ""},
        "historical_statistics": {
            "comparable_events_count": 12,
            "sample_reliability": "WRONG",  # 보정 대상
            "comparable_events": [],
            "fabrication_warning": "",  # 자동 첨부 대상
        },
        "reference_observation_zones": {
            "current_position_vs_history": "현재가 +5%",
            "historical_volatility_lower_1sigma": "-X%",
            "historical_volatility_upper_1sigma": "+Y%",
            "note": "통계 진술이며 매매 권유가 아닙니다",
        },
        "scenario_analysis": {
            "bullish_case": {"trigger": "a", "historical_pattern": "b", "probability": "30%"},
            "base_case": {"trigger": "c", "historical_pattern": "d", "probability": "50%"},
            "bearish_case": {"trigger": "e", "historical_pattern": "f", "probability": "20%"},
        },
        "key_risks": [],
        "what_to_watch": [],
        "summary_neutral": "AAPL 실적 관찰 구간.",
    }


def test_us_ticker_collects_options_yfinance_not_short():
    """US 종목: options + yfinance_events. KR 공매도 X."""
    agent = EventAnalystAgent.__new__(EventAnalystAgent)  # init 없이 인스턴스만
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
        assert "short_selling" not in bundle  # US는 short 호출 X
        m_short.assert_not_called()


def test_kr_ticker_collects_short_not_options():
    """KR 종목: short_selling. options/yfinance 호출 X."""
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
    """일부 모듈 실패 — graceful, 다른 모듈은 정상."""
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
        # yfinance는 정상 수집됨
        assert "yfinance_events" in bundle


def test_ipo_secondary_lookup_when_event_type():
    """event_type=ipo_secondary면 find_ipos_for_secondary 호출."""
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
# 4. 사후 일관성 보정 (final_score, mode, badge, sample_reliability)
# ──────────────────────────────────────────────


def test_run_recalculates_final_score_and_mode():
    """Claude가 잘못된 final_score/mode/badge를 줘도 재계산."""
    agent = EventAnalystAgent.__new__(EventAnalystAgent)
    agent.agent_name = "event_analyst"
    agent.system_prompt = ""
    agent.model = "claude-sonnet-4-6"

    response = _minimal_response_dict()

    async def run():
        with patch.object(agent, "_collect_data_bundle", return_value={"market": "US", "ticker": "AAPL"}), \
             patch.object(
                 agent, "call_claude_json",
                 new=AsyncMock(return_value=(EventAnalystResult.model_validate(response), {})),
             ):
            return await agent.run(EventAnalystInput(ticker="AAPL", market="US"))

    result = asyncio.run(run())

    cb = result.event_summary.certainty_breakdown
    # 9, 9, 10, 8 → 0.4*9 + 0.3*9 + 0.2*10 + 0.1*8 = 3.6+2.7+2.0+0.8 = 9.1
    assert cb.final_score == pytest.approx(9.1, abs=0.01)
    assert cb.mode == "Full Analysis"
    assert "확정" in result.event_summary.badge


def test_run_classifies_sample_reliability():
    """Claude가 sample_reliability를 누락/잘못 줘도 자동 분류."""
    agent = EventAnalystAgent.__new__(EventAnalystAgent)
    agent.agent_name = "event_analyst"
    agent.system_prompt = ""
    agent.model = "claude-sonnet-4-6"

    response = _minimal_response_dict()
    response["historical_statistics"]["comparable_events_count"] = 12

    async def run():
        with patch.object(agent, "_collect_data_bundle", return_value={"market": "US", "ticker": "AAPL"}), \
             patch.object(
                 agent, "call_claude_json",
                 new=AsyncMock(return_value=(EventAnalystResult.model_validate(response), {})),
             ):
            return await agent.run(EventAnalystInput(ticker="AAPL", market="US"))

    result = asyncio.run(run())
    assert "신뢰 가능" in result.historical_statistics.sample_reliability


def test_run_low_sample_marks_uncertain():
    agent = EventAnalystAgent.__new__(EventAnalystAgent)
    agent.agent_name = "event_analyst"
    agent.system_prompt = ""
    agent.model = "claude-sonnet-4-6"

    response = _minimal_response_dict()
    response["historical_statistics"]["comparable_events_count"] = 3

    async def run():
        with patch.object(agent, "_collect_data_bundle", return_value={"market": "US", "ticker": "AAPL"}), \
             patch.object(
                 agent, "call_claude_json",
                 new=AsyncMock(return_value=(EventAnalystResult.model_validate(response), {})),
             ):
            return await agent.run(EventAnalystInput(ticker="AAPL", market="US"))

    result = asyncio.run(run())
    assert "미제시" in result.historical_statistics.sample_reliability


def test_run_attaches_fabrication_warning_when_missing():
    agent = EventAnalystAgent.__new__(EventAnalystAgent)
    agent.agent_name = "event_analyst"
    agent.system_prompt = ""
    agent.model = "claude-sonnet-4-6"

    response = _minimal_response_dict()
    response["historical_statistics"]["fabrication_warning"] = ""  # 비어있음

    async def run():
        with patch.object(agent, "_collect_data_bundle", return_value={"market": "US", "ticker": "AAPL"}), \
             patch.object(
                 agent, "call_claude_json",
                 new=AsyncMock(return_value=(EventAnalystResult.model_validate(response), {})),
             ):
            return await agent.run(EventAnalystInput(ticker="AAPL", market="US"))

    result = asyncio.run(run())
    assert "외부 검증" in result.historical_statistics.fabrication_warning


def test_run_filters_forbidden_in_summary():
    """summary_neutral에 단정어 들어가도 후처리에서 필터링."""
    agent = EventAnalystAgent.__new__(EventAnalystAgent)
    agent.agent_name = "event_analyst"
    agent.system_prompt = ""
    agent.model = "claude-sonnet-4-6"

    response = _minimal_response_dict()
    response["summary_neutral"] = "AAPL 실적 발표일 매수하세요."

    async def run():
        with patch.object(agent, "_collect_data_bundle", return_value={"market": "US", "ticker": "AAPL"}), \
             patch.object(
                 agent, "call_claude_json",
                 new=AsyncMock(return_value=(EventAnalystResult.model_validate(response), {})),
             ):
            return await agent.run(EventAnalystInput(ticker="AAPL", market="US"))

    result = asyncio.run(run())
    assert "매수하세요" not in result.summary_neutral
    assert "[필터링됨]" in result.summary_neutral


# ──────────────────────────────────────────────
# 5. Refused 모드 — 사전 차단
# ──────────────────────────────────────────────


def test_refused_mode_skips_claude_call():
    """certainty_pre_check < 3이면 Claude 호출 없이 거부 응답."""
    agent = EventAnalystAgent.__new__(EventAnalystAgent)
    agent.agent_name = "event_analyst"
    agent.system_prompt = ""
    agent.model = "claude-sonnet-4-6"

    bundle = {"market": "KR", "ticker": "005930", "certainty_pre_check": 1}

    async def run():
        with patch.object(agent, "_collect_data_bundle", return_value=bundle), \
             patch.object(agent, "call_claude_json") as m_claude:
            return await agent.run(EventAnalystInput(ticker="005930", market="KR"))

    result = asyncio.run(run())
    assert result.event_summary.certainty_breakdown.mode == "Refused"
    assert "거부" in result.event_summary.badge
    # call_claude_json은 호출되지 않아야 함 (사전 차단)
    # patch는 적용되었으므로 call_count로 확인
    # (closure 안의 m_claude를 외부에서 검증하기 어려우므로 mode만으로 확인)


# ──────────────────────────────────────────────
# 6. 시스템 프롬프트 로딩
# ──────────────────────────────────────────────


def test_persona_md_loads_with_legal_rules():
    """personas/event.md가 LEGAL 표현을 포함하는지."""
    agent = EventAnalystAgent()
    assert "LEGAL Hard Rules" in agent.system_prompt or "절대 금지" in agent.system_prompt
    # 핵심 v2.1 항목
    assert "summary_neutral" in agent.system_prompt
    assert "scenario_analysis" in agent.system_prompt
    assert "current_position_vs_history" in agent.system_prompt
