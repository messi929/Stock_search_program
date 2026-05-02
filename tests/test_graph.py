"""LangGraph 4 에이전트 파이프라인 단위 테스트.

⚠️  Opus 1회 호출 발생 (Strategist) — 약 300~400원.
캐시 히트 시 (이전 테스트와 동일 input) 비용 0원 가능.

실행:
    py -m tests.test_graph
"""

from __future__ import annotations

import asyncio
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import pytest
from dotenv import load_dotenv

load_dotenv()

from agents.graph import (
    AnalysisState,
    create_analysis_graph,
    run_analysis,
)
from agents.strategist import UserProfile

# 실 Claude 4 에이전트 호출 — 비용 큼. `pytest --run-integration` 추가 시에만.
pytestmark = pytest.mark.integration


async def test_full_pipeline() -> None:
    """전체 파이프라인 — 4 에이전트 모두 실행되어 state에 결과 채워짐."""
    user_profile = UserProfile(
        investing_experience="1-5y",
        holding_period="1-2y",
        volatility_tolerance="20",
        interested_sectors=["바이오", "반도체"],
        investment_principles=["이미 오른 것 피한다", "장기 보유"],
    )

    final = await run_analysis(
        ticker="207940",
        query="삼성바이오 어때?",
        persona="blackrock",
        user_profile=user_profile,
    )

    assert final.get("research_output") is not None, "research_output 누락"
    assert final.get("analyst_output") is not None, "analyst_output 누락"
    assert final.get("validator_output") is not None, "validator_output 누락"
    assert final.get("strategist_output") is not None, "strategist_output 누락"

    r = final["research_output"]
    a = final["analyst_output"]
    v = final["validator_output"]
    s = final["strategist_output"]

    print(f"[full_pipeline] retry_count={final.get('retry_count', 0)}")
    print(f"  research.market_sentiment: {r.market_sentiment}")
    print(f"  analyst.name: {a.name}, current_price: {a.technical.current_price:,}원, buy_score: {a.buy_score.buy_score}")
    print(f"  validator.overall: {v.overall_status}, fresh={v.fresh_data_count}, contrarian={len(v.contrarian_scenarios)}")
    print(f"  strategist.persona: {s.persona_used}, follow-ups: {len(s.follow_up_questions)}")
    if s.entry_points:
        print(f"  entry: {s.entry_points.tier_1:,} / {s.entry_points.tier_2:,} / {s.entry_points.tier_3:,}")


async def test_graph_structure() -> None:
    """그래프가 올바른 노드/엣지로 컴파일되었는지 확인."""
    graph = create_analysis_graph()
    # LangGraph compiled graph는 internal nodes/edges를 노출
    nodes = list(graph.nodes.keys())
    expected = {"__start__", "fanout", "research", "analyst", "validator", "strategist"}
    actual = set(nodes)
    missing = expected - actual
    assert not missing, f"누락된 노드: {missing}"
    print(f"[graph_structure] 노드 {len(nodes)}개 모두 등록됨: {sorted(actual)}")


async def main() -> None:
    print("=" * 60)
    print("LangGraph 파이프라인 테스트 시작")
    print("=" * 60)

    await test_graph_structure()
    print()
    await test_full_pipeline()

    print("\n" + "=" * 60)
    print("[OK] 모든 테스트 통과")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
