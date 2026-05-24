"""LangGraph 오케스트레이션 — 6 페르소나 분기.

페르소나 그룹:
  - **Strategist 흐름** (blackrock/ark/graham): 기존 4노드 파이프라인.
        research + analyst → validator → strategist → END
  - **Event Analyst** (event): 단일 노드, Week C 데이터 인프라 호출
  - **Macro PM** (macro): 단일 노드, FRED+ECOS+regime_detector 결과 주입
  - **Korean Specialist** (korean): 단일 노드, Week A 6 모듈 호출

라우팅 (START 직후):
  blackrock | ark | graham → fanout(research+analyst)
  event   → event_analyst → END
  macro   → macro_pm → END
  korean  → korean_specialist → END

⚠️ 데이터 부족 시 graceful — 각 에이전트가 자체 처리 (Week C/D 보정 로직).
비용 추적은 Claude API 호출 시 자동 (utils.cost_tracker.log_usage).
"""

from __future__ import annotations

from typing import Optional, TypedDict

from loguru import logger

from agents.analyst import AnalystAgent, AnalystInput, AnalystResult
from agents.event_analyst import (
    EventAnalystAgent,
    EventAnalystInput,
    EventAnalystResult,
)
from agents.korean_specialist import (
    KoreanSpecialistAgent,
    KoreanSpecialistInput,
    KoreanSpecialistResult,
)
from agents.macro_pm import MacroPmAgent, MacroPmInput, MacroPmResult
from agents.research import ResearchAgent, ResearchInput, ResearchResult
from agents.strategist import (
    StrategistAgent,
    StrategistInput,
    StrategistResult,
    UserProfile,
)
from agents.validator import ValidatorAgent, ValidatorInput, ValidatorResult


# ──────────────────────────────────────────────
# 페르소나 그룹 분류
# ──────────────────────────────────────────────

STRATEGIST_PERSONAS = {"blackrock", "ark", "graham"}
DATA_DRIVEN_PERSONAS = {"event", "macro", "korean"}
ALL_PERSONAS = STRATEGIST_PERSONAS | DATA_DRIVEN_PERSONAS


def is_strategist_persona(persona: str) -> bool:
    return persona in STRATEGIST_PERSONAS


def is_data_driven_persona(persona: str) -> bool:
    return persona in DATA_DRIVEN_PERSONAS


# ──────────────────────────────────────────────
# State 스키마
# ──────────────────────────────────────────────

class AnalysisState(TypedDict, total=False):
    # 입력
    ticker: str
    query: str
    persona: str
    user_uid: str
    user_profile: UserProfile
    # Event Analyst 전용 (옵션)
    event_type: Optional[str]
    event_target: Optional[str]
    primary_ticker: Optional[str]

    # 에이전트 출력 — 각 페르소나 그룹별 독립 필드.
    research_output: Optional[ResearchResult]
    analyst_output: Optional[AnalystResult]
    validator_output: Optional[ValidatorResult]
    strategist_output: Optional[StrategistResult]
    event_output: Optional[EventAnalystResult]
    macro_output: Optional[MacroPmResult]
    korean_output: Optional[KoreanSpecialistResult]

    # 제어
    retry_count: int


# ──────────────────────────────────────────────
# 노드
# ──────────────────────────────────────────────

async def fanout_node(state: AnalysisState) -> dict:
    """Pass-through — research/analyst 병렬 진입점.

    재시도 시에도 이 노드를 거쳐 두 에이전트를 동시에 다시 시작합니다.
    """
    return {}


async def research_node(state: AnalysisState) -> dict:
    agent = ResearchAgent()
    result = await agent.run(
        ResearchInput(
            query=state.get("query", "") or f"{state['ticker']} 시황",
            ticker=state.get("ticker"),
        ),
        uid=state.get("user_uid", ""),
    )
    return {"research_output": result}


async def analyst_node(state: AnalysisState) -> dict:
    agent = AnalystAgent()
    result = await agent.run(
        AnalystInput(ticker=state["ticker"]),
        uid=state.get("user_uid", ""),
    )
    return {"analyst_output": result}


async def validator_node(state: AnalysisState) -> dict:
    agent = ValidatorAgent()
    result = await agent.run(
        ValidatorInput(
            ticker=state["ticker"],
            research_output=state.get("research_output"),
            analyst_output=state.get("analyst_output"),
        ),
        uid=state.get("user_uid", ""),
    )
    new_retry = state.get("retry_count", 0)
    if result.requires_reanalysis:
        new_retry += 1
        logger.info(
            f"[graph] Validator FAIL (재분석 필요) — retry_count={new_retry}/2"
        )
    return {"validator_output": result, "retry_count": new_retry}


async def strategist_node(state: AnalysisState) -> dict:
    agent = StrategistAgent()
    result = await agent.run(
        StrategistInput(
            research_output=state["research_output"],
            analyst_output=state["analyst_output"],
            validator_output=state["validator_output"],
            user_profile=state.get("user_profile") or UserProfile(),
            persona=state.get("persona", "blackrock"),
            query=state.get("query", ""),
        ),
        uid=state.get("user_uid", ""),
    )
    return {"strategist_output": result}


# ──────────────────────────────────────────────
# 신규 3 페르소나 노드 (data-driven, 단일 노드)
# ──────────────────────────────────────────────


async def event_analyst_node(state: AnalysisState) -> dict:
    """Event Analyst — Week C 데이터 인프라 직접 호출.

    market은 ticker 형식으로 자동 추론 (KoreaSupply 등은 6자리 숫자만 처리).
    """
    from agents.event_analyst import is_kr_ticker

    ticker = state.get("ticker", "")
    market = "KR" if is_kr_ticker(ticker) else "US"
    agent = EventAnalystAgent()
    try:
        result = await agent.run(
            EventAnalystInput(
                ticker=ticker,
                market=market,
                event_type=state.get("event_type"),
                event_target=state.get("event_target"),
                primary_ticker=state.get("primary_ticker"),
            ),
            uid=state.get("user_uid", ""),
        )
    except Exception as e:
        logger.error(
            f"[graph:event] EventAnalyst 실행 실패: {type(e).__name__}: {e}"
        )
        # graceful — 에러를 응답으로 변환 (사용자에게 노출 가능한 형태)
        result = EventAnalystResult(
            ticker=ticker,
            market=market,
            event_summary=_fallback_event_summary(),
            impact_mapping=__import__(
                "agents.event_analyst", fromlist=["ImpactMapping"]
            ).ImpactMapping(),
            volume_supply_analysis=__import__(
                "agents.event_analyst", fromlist=["SignalBlock"]
            ).SignalBlock(),
            options_signals=__import__(
                "agents.event_analyst", fromlist=["SignalBlock"]
            ).SignalBlock(),
            credit_short_signals=__import__(
                "agents.event_analyst", fromlist=["SignalBlock"]
            ).SignalBlock(),
            historical_statistics=__import__(
                "agents.event_analyst", fromlist=["HistoricalStatistics"]
            ).HistoricalStatistics(
                fabrication_warning=f"분석 실행 실패: {_friendly_error_msg(e)}"
            ),
            reference_observation_zones=__import__(
                "agents.event_analyst", fromlist=["ReferenceZones"]
            ).ReferenceZones(),
            scenario_analysis=_fallback_scenario_analysis(),
            summary_neutral=(
                f"{ticker} 이벤트 분석 중 오류가 발생했습니다. "
                f"사유: {_friendly_error_msg(e)}"
            ),
            persona="event",
        )
    return {"event_output": result}


async def macro_pm_node(state: AnalysisState) -> dict:
    """Macro PM — 4 사이클 + 6 국면 응답."""
    from agents.event_analyst import is_kr_ticker

    ticker = state.get("ticker") or None
    market = None
    qtype = "macro_only"
    if ticker:
        market = "KR" if is_kr_ticker(ticker) else "US"
        qtype = "stock"

    agent = MacroPmAgent()
    try:
        result = await agent.run(
            MacroPmInput(ticker=ticker, market=market, question_type=qtype),
            uid=state.get("user_uid", ""),
        )
    except Exception as e:
        logger.error(f"[graph:macro] MacroPm 실행 실패: {type(e).__name__}: {e}")
        result = _fallback_macro_result(market or "GLOBAL", _friendly_error_msg(e))
    return {"macro_output": result}


async def korean_specialist_node(state: AnalysisState) -> dict:
    """Korean Specialist — 한국 종목 한정. 비한국 종목은 거부 응답."""
    ticker = state.get("ticker", "")
    agent = KoreanSpecialistAgent()
    try:
        result = await agent.run(
            KoreanSpecialistInput(ticker=ticker),
            uid=state.get("user_uid", ""),
        )
    except Exception as e:
        logger.error(
            f"[graph:korean] KoreanSpecialist 실행 실패: {type(e).__name__}: {e}"
        )
        result = _fallback_korean_result(ticker, _friendly_error_msg(e))
    return {"korean_output": result}


# ──────────────────────────────────────────────
# Fallback 응답 빌더 (graceful degradation)
# ──────────────────────────────────────────────


def _friendly_error_msg(e: Exception) -> str:
    """예외를 사용자에게 노출 가능한 친화 메시지로 변환.

    - Claude API 크레딧 부족·rate limit·overload·timeout 등 알려진 패턴은
      한국어로 매핑. 그 외는 클래스명+detail 일부 노출.
    """
    raw = str(e)
    low = raw.lower()
    if "credit balance" in low or "billing" in low or "insufficient" in low:
        return "Claude API 크레딧 부족 — 관리자가 충전한 뒤 다시 시도해주세요."
    if "rate limit" in low or "429" in low:
        return "AI 호출 한도 도달 — 잠시 후 다시 시도해주세요."
    if "overload" in low or "529" in low:
        return "AI 일시 과부하 — 잠시 후 다시 시도해주세요."
    if "timeout" in low or "timed out" in low:
        return "응답 지연 — 잠시 후 다시 시도해주세요."
    if "unauthorized" in low or "authentication" in low or "401" in low:
        return "AI 인증 실패 — 관리자에게 문의해주세요."
    # generic — 클래스명 + 메시지 앞부분
    snippet = raw[:120]
    return f"{type(e).__name__}: {snippet}"


def _fallback_event_summary():
    from agents.event_analyst import CertaintyBreakdown, EventSummary

    return EventSummary(
        event_type="unknown",
        event_target="",
        d_day="",
        certainty_breakdown=CertaintyBreakdown(
            source=0, timing=0, probability=0, impact=0,
            final_score=0.0, mode="Refused",
        ),
        badge="🔴 분석 실패",
    )


def _fallback_scenario_analysis():
    from agents.event_analyst import ScenarioAnalysis, ScenarioCase

    empty = ScenarioCase()
    return ScenarioAnalysis(bullish_case=empty, base_case=empty, bearish_case=empty)


def _fallback_macro_result(market: str, error: str) -> MacroPmResult:
    from agents.macro_pm import (
        CycleAnalysis,
        CycleStage,
        MacroRegime,
        WeightingUsed,
    )

    empty_stage = CycleStage(stage="데이터 부재")
    return MacroPmResult(
        macro_regime=MacroRegime(current_regime="Transition"),
        cycle_analysis=CycleAnalysis(
            interest_rate=empty_stage,
            business_cycle=empty_stage,
            currency_cycle=empty_stage,
            inflation_cycle=empty_stage,
        ),
        weighting_used=WeightingUsed(rationale=f"분석 실패: {error}"),
        summary_neutral=f"매크로 분석 중 오류가 발생했습니다 ({error}).",
        persona="macro",
    )


def _fallback_korean_result(ticker: str, error: str) -> KoreanSpecialistResult:
    from agents.korean_specialist import KoreaSpecificScore

    return KoreanSpecialistResult(
        korea_specific_analysis={"ticker": ticker, "note": "분석 실패"},
        korea_specific_score=KoreaSpecificScore(),
        summary_neutral=f"한국 시장 분석 중 오류가 발생했습니다 ({error}).",
        persona="korean",
    )


# ──────────────────────────────────────────────
# 라우팅
# ──────────────────────────────────────────────

MAX_RETRIES = 2


def route_after_validator(state: AnalysisState) -> str:
    v = state.get("validator_output")
    retry = state.get("retry_count", 0)
    if v is not None and v.requires_reanalysis and retry < MAX_RETRIES:
        return "retry"
    return "finalize"


def route_by_persona(state: AnalysisState) -> str:
    """START 직후 페르소나 그룹별 분기.

    - blackrock/ark/graham → 'strategist_flow' (기존 4노드)
    - event   → 'event'
    - macro   → 'macro'
    - korean  → 'korean'
    - 미상/기본 → 'strategist_flow' (블랙록 기본)
    """
    persona = state.get("persona", "blackrock")
    if persona == "event":
        return "event"
    if persona == "macro":
        return "macro"
    if persona == "korean":
        return "korean"
    return "strategist_flow"


# ──────────────────────────────────────────────
# 그래프 빌더
# ──────────────────────────────────────────────

def create_analysis_graph():
    """LangGraph StateGraph 컴파일 — 6 페르소나 분기 통합.

    Returns:
        compiled graph — `await graph.ainvoke(state)` 또는 `graph.astream(state)` 호출 가능.
    """
    from langgraph.graph import END, START, StateGraph

    builder = StateGraph(AnalysisState)

    # 기존 4 노드 (Strategist 흐름)
    builder.add_node("fanout", fanout_node)
    builder.add_node("research", research_node)
    builder.add_node("analyst", analyst_node)
    builder.add_node("validator", validator_node)
    builder.add_node("strategist", strategist_node)

    # 신규 3 페르소나 (단일 노드 → END)
    builder.add_node("event_analyst", event_analyst_node)
    builder.add_node("macro_pm", macro_pm_node)
    builder.add_node("korean_specialist", korean_specialist_node)

    # START → 페르소나 분기
    builder.add_conditional_edges(
        START,
        route_by_persona,
        {
            "strategist_flow": "fanout",
            "event": "event_analyst",
            "macro": "macro_pm",
            "korean": "korean_specialist",
        },
    )

    # Strategist 흐름 (기존)
    builder.add_edge("fanout", "research")
    builder.add_edge("fanout", "analyst")
    builder.add_edge("research", "validator")
    builder.add_edge("analyst", "validator")
    builder.add_conditional_edges(
        "validator",
        route_after_validator,
        {"retry": "fanout", "finalize": "strategist"},
    )
    builder.add_edge("strategist", END)

    # 신규 3 페르소나 → END
    builder.add_edge("event_analyst", END)
    builder.add_edge("macro_pm", END)
    builder.add_edge("korean_specialist", END)

    return builder.compile()


# ──────────────────────────────────────────────
# 편의 함수
# ──────────────────────────────────────────────

async def run_analysis(
    ticker: str,
    query: str = "",
    persona: str = "blackrock",
    user_profile: Optional[UserProfile] = None,
    user_uid: str = "",
    *,
    event_type: Optional[str] = None,
    event_target: Optional[str] = None,
    primary_ticker: Optional[str] = None,
) -> AnalysisState:
    """그래프 1회 실행 후 최종 state 반환.

    Args:
        ticker, query, persona, user_profile, user_uid: 공통.
        event_type, event_target, primary_ticker: persona='event' 전용 옵션.
    """
    if persona not in ALL_PERSONAS:
        logger.warning(f"[graph] 알 수 없는 persona='{persona}' → 'blackrock'으로 fallback")
        persona = "blackrock"

    graph = create_analysis_graph()
    initial: AnalysisState = {
        "ticker": ticker,
        "query": query,
        "persona": persona,
        "user_uid": user_uid,
        "user_profile": user_profile or UserProfile(),
        "retry_count": 0,
        "event_type": event_type,
        "event_target": event_target,
        "primary_ticker": primary_ticker,
    }
    final_state = await graph.ainvoke(initial)
    return final_state
