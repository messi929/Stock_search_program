"""Phase 5 라이브 스모크 — horizon analyze E2E.

run_analysis를 horizon으로 직접 호출(HTTP/auth 우회)해 통합 파이프라인을 검증:
  - 완료 여부 / persona_used == horizon
  - summary·entry/exit 채워짐
  - LEGAL: 실무자 실명(그레이엄·버핏·오닐·린치·미너비니) 미노출

실행: py -m scripts.smoke_horizon [ticker]
⚠️ Claude 실호출 — 비용 발생(관점 2종 = 약 ₩300~400).
"""

from __future__ import annotations

import asyncio
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from dotenv import load_dotenv

load_dotenv()

from agents.graph import run_analysis
from agents.strategist import UserProfile

_FORBIDDEN_NAMES = ("그레이엄", "버핏", "오닐", "린치", "미너비니")


async def _one(ticker: str, horizon: str) -> bool:
    print(f"\n{'='*60}\n[{horizon}] {ticker} 분석 시작\n{'='*60}")
    final = await run_analysis(
        ticker=ticker,
        query=f"{ticker} 어때?",
        horizon=horizon,
        user_profile=UserProfile(
            investing_experience="1-5y",
            holding_period="1-2y",
            volatility_tolerance="20",
        ),
    )
    ok = True
    s = final.get("strategist_output")
    if s is None:
        print("  ❌ strategist_output 없음")
        return False

    print(f"  persona_used: {s.persona_used} (기대: {horizon})")
    ok &= s.persona_used == horizon

    print(f"  perspective: {(s.persona_perspective or '')[:160]}")
    print(f"  summary: {(s.summary or '')[:160]}")
    ok &= bool(s.summary)
    ok &= bool(s.persona_perspective)

    if s.entry_points:
        print(
            f"  entry: {s.entry_points.tier_1:,} / "
            f"{s.entry_points.tier_2:,} / {s.entry_points.tier_3:,}"
        )
    if s.exit_points:
        print(
            f"  exit: SL {s.exit_points.stop_loss:,} / "
            f"TP {s.exit_points.take_profit_1:,} / {s.exit_points.take_profit_final:,}"
        )
    print(f"  alerts: {len(s.alert_conditions)} / follow-ups: {len(s.follow_up_questions)}")
    print(f"  disclaimer: {'있음' if s.disclaimer else '❌ 없음'}")
    ok &= bool(s.disclaimer)

    # LEGAL — 실무자 실명 미노출 (출력 마스킹)
    blob = s.model_dump_json()
    leaked = [n for n in _FORBIDDEN_NAMES if n in blob]
    if leaked:
        print(f"  ❌ 실무자 실명 노출: {leaked}")
        ok = False
    else:
        print("  ✅ 실무자 실명 미노출")

    v = final.get("validator_output")
    if v is not None:
        print(f"  validator: status={v.overall_status}, confidence={v.confidence_score}")

    print(f"  → {'✅ PASS' if ok else '❌ FAIL'}")
    return ok


async def main() -> int:
    ticker = sys.argv[1] if len(sys.argv) > 1 else "005930"
    results = {}
    for hz in ("short", "long"):
        try:
            results[hz] = await _one(ticker, hz)
        except Exception as e:
            print(f"  ❌ 예외: {type(e).__name__}: {e}")
            results[hz] = False

    print(f"\n{'='*60}\n결과: {results}")
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
