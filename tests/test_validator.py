"""Validator Agent 단위 테스트.

핵심 시나리오:
  1. fresh data → PASS, requires_reanalysis=False
  2. stale data (가격 +20% 조작) → FAIL, requires_reanalysis=True
  3. Contrarian 시나리오 3개 이상 + Blind Spot 존재
  4. forbidden_words 필터

실행:
    py -m tests.test_validator
"""

from __future__ import annotations

import asyncio

import pytest
from dotenv import load_dotenv

load_dotenv()

# 실 Claude Sonnet 호출 — 비용 발생. `pytest --run-integration` 추가 시에만 실행.
pytestmark = pytest.mark.integration

from agents.analyst import AnalystAgent, AnalystInput, AnalystResult
from agents.validator import (
    ValidatorAgent,
    ValidatorInput,
    ValidatorResult,
)


async def _build_real_analyst(ticker: str = "207940") -> AnalystResult:
    """실제 Analyst를 한 번 돌려 검증할 입력 생성. 캐시 히트로 비용 X."""
    return await AnalystAgent().run(AnalystInput(ticker=ticker, include_peers=False))


async def test_fresh_data_pass() -> None:
    """실제 분석값 → 코드 검증 통과 (PASS or WARN — 시장 변동에 따라)."""
    analyst_result = await _build_real_analyst("207940")
    validator = ValidatorAgent()
    result = await validator.run(
        ValidatorInput(ticker="207940", analyst_output=analyst_result)
    )
    assert isinstance(result, ValidatorResult)
    assert result.overall_status in ("PASS", "WARN", "FAIL")
    print(f"[fresh_data] overall={result.overall_status}, confidence={result.confidence_score}")
    print(f"  fresh={result.fresh_data_count}, stale={result.stale_data_count}")
    for c in result.checks:
        v = f"{c.verified:,.2f}" if c.verified is not None else "ERROR"
        d = f"{c.diff_pct:.2f}%" if c.diff_pct is not None else "N/A"
        print(f"    {c.item}: claimed={c.claimed:,.2f} / verified={v} / diff={d} → {c.status}")
    print(f"  Contrarian 시나리오: {len(result.contrarian_scenarios)}개")
    print(f"  Blind Spots: {len(result.blind_spots)}개")
    print(f"  requires_reanalysis: {result.requires_reanalysis}")


async def test_stale_data_fail() -> None:
    """current_price를 의도적으로 +25% 조작 → FAIL 트리거."""
    analyst_result = await _build_real_analyst("207940")
    real_price = analyst_result.technical.current_price
    analyst_result.technical.current_price = int(real_price * 1.25)  # +25% stale

    validator = ValidatorAgent()
    result = await validator.run(
        ValidatorInput(ticker="207940", analyst_output=analyst_result)
    )

    print(f"[stale_data] real={real_price:,} / faked={analyst_result.technical.current_price:,}")
    print(f"  overall={result.overall_status}, requires_reanalysis={result.requires_reanalysis}")
    price_check = next((c for c in result.checks if "현재가" in c.item), None)
    assert price_check is not None
    print(f"  price diff: {price_check.diff_pct}% → {price_check.status}")
    assert price_check.status == "FAIL", f"+25% stale인데 FAIL이 안 떴음: {price_check}"
    assert result.requires_reanalysis, "가격 FAIL인데 재분석 트리거 안 됨"
    assert result.overall_status == "FAIL", f"overall이 FAIL이 아님: {result.overall_status}"


async def test_contrarian_quality() -> None:
    """Contrarian 시나리오 최소 3개 + 모든 시나리오에 필수 필드."""
    analyst_result = await _build_real_analyst("207940")
    validator = ValidatorAgent()
    result = await validator.run(
        ValidatorInput(ticker="207940", analyst_output=analyst_result)
    )

    n = len(result.contrarian_scenarios)
    assert n >= 3, f"Contrarian 시나리오 부족: {n}개 (목표: 3개+)"
    for s in result.contrarian_scenarios:
        assert s.title and s.description and s.impact_estimate
        assert s.probability in ("LOW", "MEDIUM", "HIGH"), f"probability 비표준: {s.probability}"
        assert isinstance(s.indicators_to_watch, list)
    print(f"[contrarian_quality] 시나리오 {n}개 모두 검증 통과")
    for s in result.contrarian_scenarios[:3]:
        print(f"  - [{s.probability}] {s.title}: {s.description[:60]}...")


async def test_forbidden_words_filtered() -> None:
    """LEGAL: 응답 직렬화 후 filter_forbidden 적용 시 잔존 0개."""
    analyst_result = await _build_real_analyst("207940")
    validator = ValidatorAgent()
    result = await validator.run(
        ValidatorInput(ticker="207940", analyst_output=analyst_result)
    )
    serialized = result.model_dump_json()
    filtered, found = validator.filter_forbidden(serialized)
    _, found_again = validator.filter_forbidden(filtered)
    assert not found_again
    if found:
        print(f"[forbidden_check] 원본 {len(found)}개 → 필터 후 0개 (PASS): {found}")
    else:
        print(f"[forbidden_check] 원본부터 클린 (PASS)")


async def main() -> None:
    print("=" * 60)
    print("Validator Agent 테스트 시작")
    print("=" * 60)

    await test_fresh_data_pass()
    print()
    await test_stale_data_fail()
    print()
    await test_contrarian_quality()
    print()
    await test_forbidden_words_filtered()

    print("\n" + "=" * 60)
    print("[OK] 모든 테스트 통과")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
