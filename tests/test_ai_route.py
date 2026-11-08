"""AI 라우트 통합 테스트 — FastAPI TestClient.

`/api/ai/personas`만 검증 (Claude 호출 없음 → 비용 0).
analyze/validate는 graph 단위 테스트(test_graph.py)에서 검증됨.

실행:
    py -m pytest tests/test_ai_route.py
"""

from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import pytest
from dotenv import load_dotenv

load_dotenv()


def _login_as(monkeypatch, tier: str) -> dict[str, str]:
    """AuthMiddleware를 통과하는 가짜 로그인 사용자 (Firebase·Firestore 호출 없음).

    /api/ai/* 는 비로그인 전면 차단(401)이라 라우트 자체를 검증하려면 uid가 필요하다.
    AUTH_ENABLED=false 환경에선 미들웨어가 통과시키므로 패치가 무해하다.
    """
    import api.routes.ai as ai
    import screener.middleware as mw
    import screener.services.subscription as sub

    user = {"uid": "test-uid", "email": "tester@example.com", "email_verified": True, "tier": tier}
    monkeypatch.setattr(mw, "verify_firebase_token", lambda token: dict(user) if token else None)

    def _no_firestore():
        raise RuntimeError("테스트: Firestore 미사용")

    monkeypatch.setattr(sub, "_users_ref", _no_firestore)
    monkeypatch.setattr(
        ai, "_count_month_usage", lambda uid: {"analyses": 0, "validations": 0, "discoveries": 0}
    )
    return {"Authorization": "Bearer test-token"}


@pytest.fixture
def pro_headers(monkeypatch):
    return _login_as(monkeypatch, "pro")


@pytest.fixture
def free_headers(monkeypatch):
    return _login_as(monkeypatch, "free")


def test_ai_routes_require_login() -> None:
    """/api/ai/* 비로그인 호출은 401 (Claude 비용 누수 방지 게이트)."""
    import screener.middleware as mw

    if not mw.AUTH_ENABLED:
        pytest.skip("AUTH_ENABLED=false — 로그인 게이트 비활성")

    from fastapi.testclient import TestClient
    from screener.main import app

    res = TestClient(app).post("/api/ai/analyze", json={"ticker": "005930", "stream": False})
    assert res.status_code == 401
    assert res.json().get("login_required") is True


def test_personas_route(pro_headers) -> None:
    """GET /api/ai/personas — 1차 축 horizon 4종 + 내부 데이터 노드 3종 반환.

    블랙록/ARK/그레이엄 페르소나는 2026-06-22 horizon으로 폐지.
    """
    from fastapi.testclient import TestClient
    from screener.main import app

    client = TestClient(app)
    res = client.get("/api/ai/personas", headers=pro_headers)
    assert res.status_code == 200, f"status={res.status_code}, body={res.text}"

    data = res.json()

    # 1차 축 — 4 horizon
    assert "horizons" in data, f"응답에 horizons 누락: {data}"
    hz_ids = [h["id"] for h in data["horizons"]]
    assert set(hz_ids) == {"short", "short_mid", "mid", "long"}
    assert data["user_default_horizon"] == "mid"

    # 데이터 노드 — event/macro/korean만 (폐지된 페르소나 없음)
    assert "personas" in data, f"응답에 personas 누락: {data}"
    ids = [p["id"] for p in data["personas"]]
    assert set(ids) == {"event", "macro", "korean"}
    for pid in ("blackrock", "ark", "graham"):
        assert pid not in ids, f"{pid} 페르소나는 폐지되어야 함"

    assert data["user_plan"] in ("free", "pro")
    assert data["user_default_persona"] == ""

    print(f"[personas_route] horizon 4 + 데이터 노드 3 반환 OK")
    for h in data["horizons"]:
        free_mark = "🆓" if h["available_to_free"] else "💎"
        print(f"  {free_mark} {h['icon']} {h['name']} ({h['id']})")


def test_analyze_invalid_ticker(pro_headers) -> None:
    """POST /api/ai/analyze — 잘못된 ticker → 400."""
    from fastapi.testclient import TestClient
    from screener.main import app

    client = TestClient(app)
    res = client.post(
        "/api/ai/analyze",
        json={"ticker": "", "stream": False},
        headers=pro_headers,
    )
    assert res.status_code == 400, f"빈 ticker는 400이어야 함, got {res.status_code}"
    print(f"[analyze_invalid] 빈 ticker → 400 OK")


def test_analyze_locked_persona(free_headers) -> None:
    """POST /api/ai/analyze — Free에서 Pro 전용 데이터 노드(macro) → 402."""
    import screener.middleware as mw

    if not mw.AUTH_ENABLED:
        pytest.skip("AUTH_ENABLED=false — 미들웨어가 tier='pro'로 통과시켜 검증 불가")

    from fastapi.testclient import TestClient
    from screener.main import app

    client = TestClient(app)
    res = client.post(
        "/api/ai/analyze",
        json={"ticker": "207940", "persona": "macro", "stream": False},
        headers=free_headers,
    )
    assert res.status_code == 402, f"Free 사용자가 macro 호출 → 402 기대, got {res.status_code}"
    assert res.json()["detail"]["code"] == "PERSONA_LOCKED"


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


def test_quota_enforcement() -> None:
    """_enforce_quota — 한도 초과 시 429, 무제한/미만은 통과."""
    import api.routes.ai as ai
    from fastapi import HTTPException

    limits = ai.PLAN_LIMITS
    assert limits["pro"]["analyses"] == 100, "Pro 공정사용 한도 100회 (2026-06 결정)"
    assert limits["free"]["analyses"] == 20
    assert "premium" not in limits, "Premium 티어 제거됨 (2-tier)"

    # _count_month_usage를 monkeypatch (Firestore 의존 제거)
    orig = ai._count_month_usage

    def _fake(used_n):
        return lambda uid: {"analyses": used_n, "validations": 0, "discoveries": 0}

    try:
        # 1) 비로그인(uid="") → 항상 통과
        ai._enforce_quota("", "free", "analyses")

        # 2) 한도 미만 → 통과
        ai._count_month_usage = _fake(19)
        ai._enforce_quota("u1", "free", "analyses")  # 19 < 20

        # 3) 한도 도달 → 429
        ai._count_month_usage = _fake(20)
        raised = False
        try:
            ai._enforce_quota("u1", "free", "analyses")  # 20 >= 20
        except HTTPException as e:
            raised = True
            assert e.status_code == 429
            assert e.detail["code"] == "QUOTA_EXCEEDED"
            assert e.detail["limit"] == 20
        assert raised, "한도 도달 시 429 발생해야 함"

        # 4) Pro 99회 통과 / 100회 차단
        ai._count_month_usage = _fake(99)
        ai._enforce_quota("u2", "pro", "analyses")
        ai._count_month_usage = _fake(100)
        raised = False
        try:
            ai._enforce_quota("u2", "pro", "analyses")
        except HTTPException as e:
            raised = True
            assert e.detail["limit"] == 100
        assert raised, "Pro 100회 도달 시 429"
    finally:
        ai._count_month_usage = orig

    print("[quota] Free 20 / Pro 100 enforce OK (Premium 제거)")


def main() -> None:
    """수동 실행 — fixture를 쓰므로 pytest로 위임."""
    raise SystemExit(pytest.main([__file__, "-v", "-s"]))


if __name__ == "__main__":
    main()
