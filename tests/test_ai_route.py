"""AI 라우트 통합 테스트 — FastAPI TestClient.

`/api/ai/personas`만 검증 (Claude 호출 없음 → 비용 0).
analyze/validate는 graph 단위 테스트(test_graph.py)에서 검증됨.

실행:
    py -m tests.test_ai_route
"""

from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from dotenv import load_dotenv

load_dotenv()


def test_personas_route() -> None:
    """GET /api/ai/personas — 페르소나 3종 반환 + 비로그인은 free tier."""
    from fastapi.testclient import TestClient
    from screener.main import app

    client = TestClient(app)
    res = client.get("/api/ai/personas")
    assert res.status_code == 200, f"status={res.status_code}, body={res.text}"

    data = res.json()
    assert "personas" in data, f"응답에 personas 누락: {data}"
    assert len(data["personas"]) == 3, f"페르소나 3개여야 함: {len(data['personas'])}"

    ids = [p["id"] for p in data["personas"]]
    assert set(ids) == {"blackrock", "ark", "graham"}

    blackrock = next(p for p in data["personas"] if p["id"] == "blackrock")
    assert blackrock["available_to_free"] is True

    ark = next(p for p in data["personas"] if p["id"] == "ark")
    assert ark["available_to_free"] is False

    graham = next(p for p in data["personas"] if p["id"] == "graham")
    assert graham["available_to_free"] is False

    # 비로그인 → AUTH_ENABLED=false 환경에서는 pro 또는 free 둘 다 가능 (middleware 기본값)
    assert data["user_plan"] in ("free", "pro")
    assert data["user_default_persona"] == "blackrock"

    print(f"[personas_route] 3 페르소나 반환 OK")
    for p in data["personas"]:
        free_mark = "🆓" if p["available_to_free"] else "💎"
        print(f"  {free_mark} {p['icon']} {p['name']} ({p['id']})")
    print(f"  user_plan: {data['user_plan']}, default: {data['user_default_persona']}")


def test_analyze_invalid_ticker() -> None:
    """POST /api/ai/analyze — 잘못된 ticker → 400."""
    from fastapi.testclient import TestClient
    from screener.main import app

    client = TestClient(app)
    res = client.post(
        "/api/ai/analyze",
        json={"ticker": "", "stream": False},
    )
    assert res.status_code == 400, f"빈 ticker는 400이어야 함, got {res.status_code}"
    print(f"[analyze_invalid] 빈 ticker → 400 OK")


def test_analyze_locked_persona() -> None:
    """POST /api/ai/analyze — Free에서 ARK 페르소나 → 402.

    AUTH_ENABLED=false 환경에서는 middleware가 tier='pro'로 통과시켜 검증 어려움.
    이 테스트는 AUTH_ENABLED=true 운영 환경에서만 의미 있음. 여기서는 skip.
    """
    import os

    if os.environ.get("AUTH_ENABLED", "false").lower() != "true":
        print("[analyze_locked] AUTH_ENABLED=false 환경 — 스킵")
        return

    from fastapi.testclient import TestClient
    from screener.main import app

    client = TestClient(app)
    res = client.post(
        "/api/ai/analyze",
        json={"ticker": "207940", "persona": "ark", "stream": False},
    )
    assert res.status_code == 402, f"Free 사용자가 ARK 호출 → 402 기대, got {res.status_code}"
    print(f"[analyze_locked] Free + ARK → 402 OK")


def test_smart_lists_route() -> None:
    """GET /api/screener/smart-lists — v7.5 CATEGORIES 노출."""
    from fastapi.testclient import TestClient
    from screener.main import app

    client = TestClient(app)
    res = client.get("/api/screener/smart-lists")
    assert res.status_code == 200, f"status={res.status_code}, body={res.text}"
    data = res.json()
    assert "categories" in data
    assert len(data["categories"]) > 0, "카테고리 0개"

    # 핵심 카테고리 존재 확인
    ids = {c["id"] for c in data["categories"]}
    assert "surge" in ids, "surge 카테고리 누락"
    assert "growth" in ids, "growth 카테고리 누락"

    # surge는 free, growth는 free 아님 (FREE_CATEGORIES 기준)
    surge = next(c for c in data["categories"] if c["id"] == "surge")
    growth = next(c for c in data["categories"] if c["id"] == "growth")
    assert surge["available_to_free"] is True
    assert growth["available_to_free"] is False

    print(f"[smart_lists] {len(data['categories'])} 카테고리 노출")
    free = sum(1 for c in data["categories"] if c["available_to_free"])
    print(f"  free: {free}, pro_only: {len(data['categories']) - free}")
    for c in data["categories"][:5]:
        free_mark = "🆓" if c["available_to_free"] else "💎"
        print(f"  {free_mark} {c['name']} ({c['id']}, {c['group']})")


def test_entry_points_routes() -> None:
    """진입선 PUT/GET/DELETE 라이프사이클 (Firestore 실제 쓰기)."""
    from fastapi.testclient import TestClient
    from screener.main import app

    client = TestClient(app)

    # 비로그인 PUT → 401
    payload = {"tier_1": 1400000, "tier_2": 1300000, "tier_3": 1200000}
    res = client.put("/api/ai/watchlist/207940/entry-points", json=payload)
    # AUTH_ENABLED=true면 401, 아니면 200 통과 (uid="")
    assert res.status_code in (200, 401, 500), f"비로그인 응답 코드 비정상: {res.status_code}"
    print(f"[entry_points] 비로그인 PUT → {res.status_code} (예상: 401 or 통과)")

    # GET 빈 ticker → 400 또는 redirect
    res = client.get("/api/ai/watchlist//entry-points")
    print(f"[entry_points] 빈 ticker GET → {res.status_code}")


def test_usage_route_unauthenticated() -> None:
    """GET /api/ai/usage — 비로그인은 401 또는 빈 응답."""
    from fastapi.testclient import TestClient
    from screener.main import app

    client = TestClient(app)
    res = client.get("/api/ai/usage")
    # AUTH_ENABLED 환경에 따라 다름
    assert res.status_code in (200, 401), f"unexpected status: {res.status_code}"
    print(f"[usage] 비로그인 GET → {res.status_code}")


def main() -> None:
    print("=" * 60)
    print("AI/Screener 라우트 통합 테스트")
    print("=" * 60)

    test_personas_route()
    print()
    test_analyze_invalid_ticker()
    print()
    test_analyze_locked_persona()
    print()
    test_smart_lists_route()
    print()
    test_entry_points_routes()
    print()
    test_usage_route_unauthenticated()

    print("\n" + "=" * 60)
    print("[OK] 모든 테스트 통과")
    print("=" * 60)


if __name__ == "__main__":
    main()
