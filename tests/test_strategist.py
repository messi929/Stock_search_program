"""Strategist Agent 단위 테스트.

⚠️  Opus 호출 3회 발생 (페르소나 3종) — 비용 약 450~600원 예상.

검증 포인트:
  1. 3 페르소나 모두 정상 응답
  2. persona_perspective 텍스트가 페르소나마다 명확히 다름
  3. 사용자 원칙 부합도 user_principles_alignment 채워짐
  4. forbidden_words 후처리 클린

실행:
    py -m tests.test_strategist
"""

from __future__ import annotations

import asyncio

from dotenv import load_dotenv

load_dotenv()

from agents.analyst import AnalystAgent, AnalystInput, AnalystResult
from agents.research import ResearchAgent, ResearchInput, ResearchResult
from agents.strategist import (
    StrategistAgent,
    StrategistInput,
    StrategistResult,
    UserProfile,
)
from agents.validator import ValidatorAgent, ValidatorInput, ValidatorResult


async def _build_pipeline_inputs(ticker: str = "207940") -> tuple[ResearchResult, AnalystResult, ValidatorResult]:
    """Research + Analyst + Validator 한 번씩 돌려 Strategist 입력 준비.
    캐시 덕분에 두 번째 호출부터 비용 0."""
    research_task = ResearchAgent().run(ResearchInput(query=f"{ticker} 시황", ticker=ticker))
    analyst_task = AnalystAgent().run(AnalystInput(ticker=ticker, include_peers=False))
    research_result, analyst_result = await asyncio.gather(research_task, analyst_task)

    validator_result = await ValidatorAgent().run(
        ValidatorInput(
            ticker=ticker,
            research_output=research_result,
            analyst_output=analyst_result,
        )
    )
    return research_result, analyst_result, validator_result


async def test_three_personas_differ() -> None:
    """3 페르소나 — 같은 입력 → 명확히 다른 persona_perspective."""
    research, analyst, validator = await _build_pipeline_inputs("207940")

    user = UserProfile(
        investing_experience="1-5y",
        holding_period="1-2y",
        volatility_tolerance="20",
        interested_sectors=["바이오", "반도체"],
        investment_principles=["이미 오른 것 피한다", "장기 보유"],
    )

    agent = StrategistAgent()
    results: dict[str, StrategistResult] = {}

    for persona in ["blackrock", "ark", "graham"]:
        result = await agent.run(
            StrategistInput(
                research_output=research,
                analyst_output=analyst,
                validator_output=validator,
                user_profile=user,
                persona=persona,
                query="삼성바이오 어때?",
            )
        )
        results[persona] = result
        assert result.persona_used == persona
        assert result.summary, f"{persona} summary 비어 있음"
        assert result.persona_perspective, f"{persona} persona_perspective 비어 있음"
        assert result.disclaimer, "disclaimer 누락"
        print(f"\n[{persona}] perspective: {result.persona_perspective[:140]}...")
        print(f"  summary: {result.summary[:100]}...")
        if result.entry_points:
            print(
                f"  entry: {result.entry_points.tier_1:,} / "
                f"{result.entry_points.tier_2:,} / {result.entry_points.tier_3:,}"
            )
        print(f"  follow-ups: {len(result.follow_up_questions)}개")

    # 페르소나 차별화 검증 — perspective/summary가 동일하면 안 됨
    assert results["blackrock"].persona_perspective != results["ark"].persona_perspective
    assert results["ark"].persona_perspective != results["graham"].persona_perspective
    assert results["blackrock"].summary != results["graham"].summary
    print("\n[differentiation] 3 페르소나 perspective/summary 모두 다름 (PASS)")


async def test_user_principles_alignment() -> None:
    """사용자 원칙이 user_principles_alignment에 키로 들어가야 함."""
    research, analyst, validator = await _build_pipeline_inputs("207940")

    principles = ["이미 오른 것 피한다", "장기 보유", "변동성 낮은 것"]
    user = UserProfile(
        investing_experience="1-5y",
        investment_principles=principles,
    )

    result = await StrategistAgent().run(
        StrategistInput(
            research_output=research,
            analyst_output=analyst,
            validator_output=validator,
            user_profile=user,
            persona="blackrock",
            query="삼성바이오 어때?",
        )
    )
    matched = sum(1 for p in principles if p in result.user_principles_alignment)
    assert matched >= 2, (
        f"3개 원칙 중 {matched}개만 매칭됨 — alignment 부족: "
        f"{list(result.user_principles_alignment.keys())}"
    )
    print(f"[principles] {matched}/{len(principles)} 매칭")
    for k, v in result.user_principles_alignment.items():
        print(f"  • {k}: {v[:60] if isinstance(v, str) else v}")


async def test_forbidden_words_filtered() -> None:
    """LEGAL: 모든 string 필드에 금지 단어가 들어가도 필터 후 클린."""
    research, analyst, validator = await _build_pipeline_inputs("207940")

    result = await StrategistAgent().run(
        StrategistInput(
            research_output=research,
            analyst_output=analyst,
            validator_output=validator,
            user_profile=UserProfile(),
            persona="blackrock",
            query="",
        )
    )
    serialized = result.model_dump_json()
    filtered, found = StrategistAgent.filter_forbidden(serialized)
    _, found_again = StrategistAgent.filter_forbidden(filtered)
    assert not found_again
    if found:
        print(f"[forbidden_check] 원본 {len(found)}개 → 필터 후 0개 (PASS): {found}")
    else:
        print(f"[forbidden_check] 원본부터 클린 (PASS)")


async def main() -> None:
    print("=" * 60)
    print("Strategist Agent 테스트 시작 (Opus 호출 3~4회)")
    print("=" * 60)

    await test_three_personas_differ()
    print()
    await test_user_principles_alignment()
    print()
    await test_forbidden_words_filtered()

    print("\n" + "=" * 60)
    print("[OK] 모든 테스트 통과")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
