"""Analyst Agent 단위 테스트.

ANTHROPIC_API_KEY 가 .env에 있어야 실행 가능 (Sonnet 호출 2회).

실행:
    py -m tests.test_analyst
"""

from __future__ import annotations

import asyncio

import pytest
from dotenv import load_dotenv

load_dotenv()

from agents.analyst import (
    AnalystAgent,
    AnalystInput,
    AnalystResult,
)

# 실 Claude Sonnet 호출 — 비용 발생. `pytest --run-integration` 추가 시에만 실행.
pytestmark = pytest.mark.integration


VALID_TIERS = {"상위", "준상위", "중간", "관찰"}


async def test_analyst_samsung_bio() -> None:
    """삼성바이오로직스(207940) 분석 — 데이터 일관성 + 스키마 검증."""
    agent = AnalystAgent()
    result = await agent.run(AnalystInput(ticker="207940"))

    assert isinstance(result, AnalystResult)
    assert result.ticker == "207940"
    assert "삼성바이오" in result.name or "Samsung" in result.name
    assert result.technical.current_price > 0
    assert result.fundamental.per >= 0
    assert 0 <= result.buy_score.buy_score <= 100
    assert result.buy_score.score_tier in VALID_TIERS, (
        f"score_tier '{result.buy_score.score_tier}'는 중립 표현이 아님 (허용: {VALID_TIERS})"
    )
    assert result.summary, "summary 비어 있음"
    print(f"[samsung_bio] {result.name} ({result.ticker})")
    print(f"  현재가: {result.technical.current_price:,}원, RSI {result.technical.rsi:.1f}")
    print(f"  PER {result.fundamental.per:.1f}, PBR {result.fundamental.pbr:.1f}, ROE {result.fundamental.roe:.1f}%")
    print(f"  buy_score: {result.buy_score.buy_score:.1f} ({result.buy_score.score_tier})")
    print(f"  peers: {len(result.peer_comparison)}개")
    print(f"  summary: {result.summary[:140]}...")


async def test_analyst_no_peers() -> None:
    """include_peers=False 옵션 동작."""
    agent = AnalystAgent()
    result = await agent.run(AnalystInput(ticker="207940", include_peers=False))
    assert len(result.peer_comparison) == 0
    print(f"[no_peers] peer_comparison 비어 있음 OK")


async def test_forbidden_words_filtered() -> None:
    """LEGAL.md 원칙: 응답에 금지 단어가 들어가도 filter_forbidden 후 클린해야 함."""
    agent = AnalystAgent()
    result = await agent.run(AnalystInput(ticker="207940"))
    serialized = result.model_dump_json()
    filtered, found = agent.filter_forbidden(serialized)
    _, found_again = agent.filter_forbidden(filtered)
    assert not found_again, f"필터링 후에도 잔존: {found_again}"
    if found:
        print(f"[forbidden_check] 원본에 {len(found)}개 발견 → 필터 후 0개 (PASS)")
        print(f"  발견된 단어: {found}")
    else:
        print(f"[forbidden_check] 원본부터 클린 (PASS)")


async def main() -> None:
    print("=" * 60)
    print("Analyst Agent 테스트 시작")
    print("=" * 60)

    await test_analyst_samsung_bio()
    print()
    await test_analyst_no_peers()
    print()
    await test_forbidden_words_filtered()

    print("\n" + "=" * 60)
    print("[OK] 모든 테스트 통과")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
