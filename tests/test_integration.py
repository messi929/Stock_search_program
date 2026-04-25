"""End-to-End HTTP 통합 테스트 — 사용자 시나리오 그대로.

⚠️ Claude 호출 발생: analyze(4 에이전트 ~454원) + validate 재호출(~40원) = 약 500원.

시나리오:
  1. GET /api/ai/personas               → 3 페르소나 + free tier
  2. GET /api/screener/smart-lists      → 17 카테고리 노출
  3. POST /api/ai/analyze (non-stream)  → 4 에이전트 결과 종합
  4. POST /api/ai/validate/{ticker}     → 직전 결과 재검증
  5. (옵션) PUT /api/ai/watchlist/{ticker}/entry-points → strategist 진입선 저장

실행:
    py -m tests.test_integration
"""

from __future__ import annotations

import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from dotenv import load_dotenv

load_dotenv()


def main() -> None:
    print("=" * 60)
    print("E2E HTTP 통합 테스트")
    print("=" * 60)

    from fastapi.testclient import TestClient

    from screener.main import app

    client = TestClient(app)

    # 1) personas
    print("\n[1] GET /api/ai/personas")
    res = client.get("/api/ai/personas")
    assert res.status_code == 200, res.text
    data = res.json()
    assert len(data["personas"]) == 3
    print(f"  → {len(data['personas'])} 페르소나, plan={data['user_plan']}")

    # 2) smart-lists
    print("\n[2] GET /api/screener/smart-lists")
    res = client.get("/api/screener/smart-lists")
    assert res.status_code == 200
    data = res.json()
    assert len(data["categories"]) >= 6
    print(f"  → {len(data['categories'])} 카테고리")

    # 3) analyze (non-stream, full pipeline)
    print("\n[3] POST /api/ai/analyze ticker=207940 persona=blackrock (full pipeline)")
    t0 = time.time()
    res = client.post(
        "/api/ai/analyze",
        json={
            "ticker": "207940",
            "query": "삼성바이오 어때?",
            "persona": "blackrock",
            "stream": False,
            "user_profile": {
                "investing_experience": "1-5y",
                "holding_period": "1-2y",
                "volatility_tolerance": "20",
                "investment_principles": ["이미 오른 것 피한다", "장기 보유"],
            },
        },
        timeout=300,
    )
    elapsed_3 = time.time() - t0
    assert res.status_code == 200, f"status={res.status_code}, body={res.text[:500]}"
    body = res.json()

    # 4 에이전트 결과 모두 채워졌는지
    assert body.get("research"), "research 누락"
    assert body.get("analyst"), "analyst 누락"
    assert body.get("validator"), "validator 누락"
    assert body.get("strategist"), "strategist 누락"
    assert body.get("disclaimer"), "disclaimer 누락"

    analyst = body["analyst"]
    strategist = body["strategist"]
    validator = body["validator"]

    print(f"  → elapsed={elapsed_3:.1f}s, validation={validator['overall_status']}")
    print(f"    analyst: {analyst['name']} ({analyst['ticker']}) 가격 {analyst['technical']['current_price']:,}원")
    print(f"    strategist: persona={strategist['persona_used']}, follow-ups={len(strategist['follow_up_questions'])}")
    if strategist.get("entry_points"):
        ep = strategist["entry_points"]
        print(f"    entry: {ep['tier_1']:,} / {ep['tier_2']:,} / {ep['tier_3']:,}")

    # 4) validate using analyst output from step 3
    print("\n[4] POST /api/ai/validate/207940 (재검증)")
    t0 = time.time()
    res = client.post(
        f"/api/ai/validate/{analyst['ticker']}",
        json={
            "ticker": analyst["ticker"],
            "research_output": body["research"],
            "analyst_output": analyst,
        },
        timeout=120,
    )
    elapsed_4 = time.time() - t0
    assert res.status_code == 200, f"status={res.status_code}, body={res.text[:500]}"
    val_body = res.json()
    assert val_body["overall_status"] in ("PASS", "WARN", "FAIL")
    print(f"  → elapsed={elapsed_4:.1f}s, status={val_body['overall_status']}")
    print(f"    fresh={val_body['fresh_data_count']}, stale={val_body['stale_data_count']}")
    print(f"    confidence={val_body['confidence_score']}, requires_reanalysis={val_body['requires_reanalysis']}")

    # 5) (인증 필요한 경로는 스킵 또는 401 확인만)
    print("\n[5] PUT entry-points (비로그인 → 401 예상)")
    if strategist.get("entry_points"):
        ep = strategist["entry_points"]
        res = client.put(
            f"/api/ai/watchlist/{analyst['ticker']}/entry-points",
            json={
                "tier_1": ep["tier_1"],
                "tier_2": ep["tier_2"],
                "tier_3": ep["tier_3"],
                "technical_basis": ep.get("technical_basis", []),
                "persona_used": "blackrock",
                "source": "strategist",
            },
        )
        # AUTH_ENABLED 환경에 따라 401 또는 200
        assert res.status_code in (200, 401), f"unexpected: {res.status_code}"
        print(f"  → {res.status_code}")

    print("\n" + "=" * 60)
    print(f"[OK] E2E 통합 시나리오 통과 (총 elapsed {elapsed_3 + elapsed_4:.1f}s)")
    print("=" * 60)


if __name__ == "__main__":
    main()
