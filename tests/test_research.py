"""Research Agent 단위 테스트.

ANTHROPIC_API_KEY 가 .env에 있어야 실행 가능 (실제 Haiku 호출 1회).

실행:
    py -m tests.test_research
"""

from __future__ import annotations

import asyncio

import pytest
from dotenv import load_dotenv

load_dotenv()

from agents.research import ResearchAgent, ResearchInput, ResearchResult

# 실 Claude Haiku 호출 — 비용 발생. `pytest --run-integration` 추가 시에만 실행.
pytestmark = pytest.mark.integration


async def test_smoke_no_ticker() -> None:
    """가장 가벼운 케이스 — 일반 시황 쿼리."""
    agent = ResearchAgent()
    result = await agent.run(
        ResearchInput(query="오늘 한국 증시 분위기 어떤가?"),
    )
    assert isinstance(result, ResearchResult)
    assert result.market_sentiment in ("낙관적", "신중", "비관적")
    assert result.summary, "summary가 비어 있음"
    assert result.timestamp, "timestamp가 비어 있음"
    print(f"[smoke_no_ticker] sentiment={result.market_sentiment}")
    print(f"  summary: {result.summary[:120]}...")
    print(f"  sectors: {[s.name for s in result.sector_status]}")
    print(f"  news count: {len(result.relevant_news)}")


async def test_with_ticker() -> None:
    """종목 컨텍스트 포함."""
    agent = ResearchAgent()
    result = await agent.run(
        ResearchInput(query="삼성바이오로직스 시황", ticker="207940"),
    )
    assert isinstance(result, ResearchResult)
    assert result.summary
    print(f"[with_ticker] sentiment={result.market_sentiment}")
    print(f"  summary: {result.summary[:120]}...")


async def test_forbidden_words_filtered() -> None:
    """응답에 금지 단어가 있더라도 filter_forbidden 적용 후 클린해야 함.

    LEGAL.md 원칙: 원본 LLM 응답에는 단어가 포함될 수 있으나,
    사용자 노출 전 코드 레벨에서 [필터링됨]으로 치환되어야 함.
    """
    agent = ResearchAgent()
    result = await agent.run(
        ResearchInput(query="반도체 섹터 분석", sector="반도체"),
    )
    serialized = result.model_dump_json()
    filtered, found = agent.filter_forbidden(serialized)
    # 1차 필터링 후 다시 돌려서 잔존 단어 0개 확인
    _, found_again = agent.filter_forbidden(filtered)
    assert not found_again, f"필터링 후에도 잔존: {found_again}"
    if found:
        print(f"[forbidden_check] 원본에 {len(found)}개 발견 → 필터 후 0개 (PASS)")
        print(f"  발견된 단어: {found}")
    else:
        print(f"[forbidden_check] 원본부터 클린 (PASS)")


async def main() -> None:
    print("=" * 60)
    print("Research Agent 테스트 시작")
    print("=" * 60)

    await test_smoke_no_ticker()
    print()
    await test_with_ticker()
    print()
    await test_forbidden_words_filtered()

    print("\n" + "=" * 60)
    print("[OK] 모든 테스트 통과")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
