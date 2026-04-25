"""LangGraph 오케스트레이션 — 4 에이전트 파이프라인.

흐름:
    START
      ↓
    [fanout]  (research + analyst 병렬 시작 트리거)
      ├─→ research ─┐
      └─→ analyst  ─┴─→ [validator] (rendezvous: 둘 다 완료 후 실행)
                              │
              ┌───────────────┴────────────┐
        FAIL & retry<2                    PASS/WARN
              │                            │
              └─→ fanout (재시도)          └─→ [strategist] ─→ END

조건부 라우팅:
  - validator.requires_reanalysis == True && retry_count < 2 → 재시도
  - 그 외 → strategist (확정)
"""

from __future__ import annotations

from typing import Optional, TypedDict

from loguru import logger

from agents.analyst import AnalystAgent, AnalystInput, AnalystResult
from agents.research import ResearchAgent, ResearchInput, ResearchResult
from agents.strategist import (
    StrategistAgent,
    StrategistInput,
    StrategistResult,
    UserProfile,
)
from agents.validator import ValidatorAgent, ValidatorInput, ValidatorResult


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

    # 에이전트 출력 (각각 독립 필드 → 병렬 업데이트 충돌 없음)
    research_output: Optional[ResearchResult]
    analyst_output: Optional[AnalystResult]
    validator_output: Optional[ValidatorResult]
    strategist_output: Optional[StrategistResult]

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
# 라우팅
# ──────────────────────────────────────────────

MAX_RETRIES = 2


def route_after_validator(state: AnalysisState) -> str:
    v = state.get("validator_output")
    retry = state.get("retry_count", 0)
    if v is not None and v.requires_reanalysis and retry < MAX_RETRIES:
        return "retry"
    return "finalize"


# ──────────────────────────────────────────────
# 그래프 빌더
# ──────────────────────────────────────────────

def create_analysis_graph():
    """LangGraph StateGraph 컴파일.

    Returns:
        compiled graph — `await graph.ainvoke(state)` 또는 `graph.astream(state)` 호출 가능.
    """
    from langgraph.graph import END, START, StateGraph

    builder = StateGraph(AnalysisState)
    builder.add_node("fanout", fanout_node)
    builder.add_node("research", research_node)
    builder.add_node("analyst", analyst_node)
    builder.add_node("validator", validator_node)
    builder.add_node("strategist", strategist_node)

    builder.add_edge(START, "fanout")
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
) -> AnalysisState:
    """그래프 1회 실행 후 최종 state 반환."""
    graph = create_analysis_graph()
    initial: AnalysisState = {
        "ticker": ticker,
        "query": query,
        "persona": persona,
        "user_uid": user_uid,
        "user_profile": user_profile or UserProfile(),
        "retry_count": 0,
    }
    final_state = await graph.ainvoke(initial)
    return final_state
