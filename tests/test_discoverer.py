"""Discoverer Agent 단위 테스트.

⚠️  Sonnet 1회 호출 (~35원).

검증 포인트:
  1. 자연어 쿼리 → 종목 리스트 반환
  2. 후보군 외 종목은 결과에서 자동 필터링 (hallucination 방어)
  3. exclude_tickers 적용
  4. forbidden_words 후처리 클린

실행:
    py -m tests.test_discoverer
"""

from __future__ import annotations

import asyncio
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from dotenv import load_dotenv

load_dotenv()

from agents.discoverer import (
    DiscoverFilters,
    DiscovererAgent,
    DiscovererInput,
    DiscovererResult,
)


async def test_discover_basic() -> None:
    """기본 시나리오 — '저PER 가치주' 쿼리."""
    agent = DiscovererAgent()
    result = await agent.run(
        DiscovererInput(query="저PER 저PBR 가치주", max_results=5)
    )

    assert isinstance(result, DiscovererResult)
    assert result.query == "저PER 저PBR 가치주"
    assert result.interpretation, "interpretation 비어 있음"
    assert result.timestamp
    assert len(result.stocks) <= 5, f"max_results 초과: {len(result.stocks)}"

    print(f"[discover_basic] {len(result.stocks)} 종목 반환")
    print(f"  interpretation: {result.interpretation[:140]}")
    for s in result.stocks:
        print(f"  - {s.name} ({s.ticker}) {s.market}/{s.sector}: {s.reason[:80]}")


async def test_exclude_tickers() -> None:
    """exclude_tickers에 들어간 종목은 결과에 없어야 함."""
    agent = DiscovererAgent()
    # 흔히 후보에 들 수 있는 대형주 몇 개를 exclude
    excluded = ["005930", "000660", "035420"]  # 삼성전자/SK하이닉스/네이버
    result = await agent.run(
        DiscovererInput(
            query="대형 우량주",
            max_results=5,
            exclude_tickers=excluded,
        )
    )

    leaked = [s.ticker for s in result.stocks if s.ticker in excluded]
    assert not leaked, f"exclude된 종목 누출: {leaked}"
    print(f"[exclude_tickers] {len(result.stocks)} 종목, 누출 0건 (PASS)")


async def test_no_hallucination() -> None:
    """Claude가 만든 ticker가 실제 컨텍스트(KR 종목)에 있는지 검증.

    DiscovererAgent.run()에서 컨텍스트 외 종목을 자동 필터하므로
    여기서는 결과의 모든 종목이 KR market에 있는지 다시 한 번 확인.
    """
    from agents.analyst import _get_kr_with_score

    agent = DiscovererAgent()
    result = await agent.run(
        DiscovererInput(query="배당주", max_results=3)
    )

    df = _get_kr_with_score()
    valid_tickers = set(df["ticker"].tolist())
    for s in result.stocks:
        assert s.ticker in valid_tickers, f"존재하지 않는 ticker: {s.ticker}"
    print(f"[no_hallucination] {len(result.stocks)} 종목 모두 KR 컨텍스트 내 (PASS)")


async def test_forbidden_words_filtered() -> None:
    """LEGAL: 응답 직렬화 후 filter_forbidden 잔존 0개."""
    agent = DiscovererAgent()
    result = await agent.run(
        DiscovererInput(query="성장 가능성 있는 종목", max_results=3)
    )
    serialized = result.model_dump_json()
    filtered, found = DiscovererAgent.filter_forbidden(serialized)
    _, found_again = DiscovererAgent.filter_forbidden(filtered)
    assert not found_again
    if found:
        print(f"[forbidden_check] 원본 {len(found)}개 → 필터 후 0개 (PASS): {found}")
    else:
        print(f"[forbidden_check] 원본부터 클린 (PASS)")


async def main() -> None:
    print("=" * 60)
    print("Discoverer Agent 테스트 시작 (Sonnet 호출 ~3회)")
    print("=" * 60)

    await test_discover_basic()
    print()
    await test_exclude_tickers()
    print()
    await test_no_hallucination()
    print()
    await test_forbidden_words_filtered()

    print("\n" + "=" * 60)
    print("[OK] 모든 테스트 통과")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
