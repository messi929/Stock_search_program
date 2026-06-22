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
import sys

# Windows cp949 콘솔에서도 한국어/이모지/em-dash 안전하게 출력
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import pytest
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

# 실 Claude Opus + Sonnet + Haiku 호출 — 비용 큼. `pytest --run-integration` 추가 시에만.
pytestmark = pytest.mark.integration


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


async def test_horizons_differ() -> None:
    """관점(시간축) — 같은 입력 → 명확히 다른 persona_perspective."""
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

    for horizon in ["short", "mid", "long"]:
        result = await agent.run(
            StrategistInput(
                research_output=research,
                analyst_output=analyst,
                validator_output=validator,
                user_profile=user,
                horizon=horizon,
                query="삼성바이오 어때?",
            )
        )
        results[horizon] = result
        assert result.persona_used == horizon
        assert result.summary, f"{horizon} summary 비어 있음"
        assert result.persona_perspective, f"{horizon} persona_perspective 비어 있음"
        assert result.disclaimer, "disclaimer 누락"
        # LEGAL: 실무자 실명이 출력에 노출되면 안 됨 (출력 마스킹)
        blob = result.model_dump_json()
        for name in ("그레이엄", "버핏", "오닐", "린치", "미너비니"):
            assert name not in blob, f"[{horizon}] 실무자 실명 '{name}' 노출됨"
        print(f"\n[{horizon}] perspective: {result.persona_perspective[:140]}...")
        print(f"  summary: {result.summary[:100]}...")
        if result.entry_points:
            print(
                f"  entry: {result.entry_points.tier_1:,} / "
                f"{result.entry_points.tier_2:,} / {result.entry_points.tier_3:,}"
            )
        print(f"  follow-ups: {len(result.follow_up_questions)}개")

    # 관점 차별화 검증 — perspective/summary가 동일하면 안 됨
    assert results["short"].persona_perspective != results["long"].persona_perspective
    assert results["short"].summary != results["long"].summary
    print("\n[differentiation] 관점별 perspective/summary 다름 (PASS)")

    # forbidden_words 필터 검증 — 모든 관점 (LEGAL: 필터 후 클린)
    total_found = 0
    for persona, r in results.items():
        serialized = r.model_dump_json()
        filtered, found = StrategistAgent.filter_forbidden(serialized)
        _, found_again = StrategistAgent.filter_forbidden(filtered)
        assert not found_again, f"[{persona}] 필터 후에도 잔존: {found_again}"
        total_found += len(found)
        if found:
            print(f"  [{persona}] 원본 {len(found)}개 → 필터 후 0개: {found}")
    if total_found == 0:
        print("[forbidden_check] 모든 관점 원본부터 클린 (PASS)")
    else:
        print(f"[forbidden_check] 총 {total_found}개 발견 → 모두 필터링 (PASS)")


async def test_user_principles_alignment() -> None:
    """사용자 원칙이 user_principles_alignment에 키로 들어가야 함.
    Test 1과 동일 input 사용 → default_cache 히트로 추가 비용 0원."""
    research, analyst, validator = await _build_pipeline_inputs("207940")

    # Test 1과 동일 input (캐시 히트용)
    user = UserProfile(
        investing_experience="1-5y",
        holding_period="1-2y",
        volatility_tolerance="20",
        interested_sectors=["바이오", "반도체"],
        investment_principles=["이미 오른 것 피한다", "장기 보유"],
    )
    principles = user.investment_principles

    result = await StrategistAgent().run(
        StrategistInput(
            research_output=research,
            analyst_output=analyst,
            validator_output=validator,
            user_profile=user,
            horizon="mid",
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
        v_str = v[:60] if isinstance(v, str) else str(v)
        print(f"  - {k}: {v_str}")


async def main() -> None:
    print("=" * 60)
    print("Strategist Agent 테스트 시작 (Opus 호출 3~4회)")
    print("=" * 60)

    await test_horizons_differ()
    print()
    await test_user_principles_alignment()

    print("\n" + "=" * 60)
    print("[OK] 모든 테스트 통과")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
