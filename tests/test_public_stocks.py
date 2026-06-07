"""공개 종목 페이지 백엔드 엔드포인트 테스트.

검증 포인트:
  - /api/stocks/{ticker}: 중립 데이터 반환, 대소문자 무시, 404
  - /api/stocks: sitemap용 전체 목록
  - 법적 원칙: target_price·buy_score·buy_grade 등 추천/목표가 필드 비노출
"""
from __future__ import annotations

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from screener.main import app
from screener.api.routes import set_data


@pytest.fixture(scope="module")
def client():
    df = pd.DataFrame(
        [
            {
                "ticker": "005930", "name": "삼성전자", "market": "KOSPI",
                "stock_type": "stock", "close": 71000, "change_pct": 1.5,
                "volume": 1000000, "trading_value": 7.1e10, "market_cap": 4.2e14,
                "per": 12.3, "pbr": 1.1, "roe": 9.5, "div_yield": 2.1,
                "vs_high_52w": -8.0, "vs_low_52w": 22.0, "rsi": 55.0,
                "sector": "반도체", "industry": "메모리", "themes": "AI,반도체",
                # 비공개여야 하는 내부 필드
                "target_price": 95000, "target_upside": 33.0,
                "buy_score": 78.0, "buy_grade": "A",
            },
            {
                "ticker": "AAPL", "name": "Apple", "market": "NASDAQ",
                "stock_type": "stock", "close": 195.0, "change_pct": -0.8,
                "volume": 5000000, "trading_value": 9.7e8, "market_cap": 3.0e12,
                "per": 30.1, "pbr": 45.0, "roe": 150.0, "div_yield": 0.5,
                "vs_high_52w": -3.0, "vs_low_52w": 40.0, "rsi": 48.0,
                "sector": "Technology", "industry": "Consumer Electronics", "themes": "AI",
                "target_price": 220.0, "buy_score": 65.0, "buy_grade": "B",
            },
        ]
    )
    set_data(df)
    return TestClient(app)


def test_public_stock_kr(client):
    res = client.get("/api/stocks/005930")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ticker"] == "005930"
    assert body["name"] == "삼성전자"
    assert body["market"] == "KOSPI"
    assert body["per"] == 12.3
    assert "chart" in body
    assert "updated_at" in body


def test_public_stock_case_insensitive(client):
    res = client.get("/api/stocks/aapl")
    assert res.status_code == 200, res.text
    assert res.json()["ticker"] == "AAPL"


def test_public_stock_excludes_recommendation_fields(client):
    """법적 원칙: 목표가·매수점수는 절대 노출 금지."""
    body = client.get("/api/stocks/005930").json()
    for forbidden in ("target_price", "target_upside", "buy_score", "buy_grade"):
        assert forbidden not in body, f"{forbidden}가 공개 응답에 노출됨"


def test_public_stock_not_found(client):
    res = client.get("/api/stocks/000000")
    assert res.status_code == 404


def test_public_stock_list(client):
    res = client.get("/api/stocks")
    assert res.status_code == 200, res.text
    body = res.json()
    tickers = {s["ticker"] for s in body["stocks"]}
    assert {"005930", "AAPL"} <= tickers
    # 목록도 경량(ticker/name/market)만
    assert set(body["stocks"][0].keys()) == {"ticker", "name", "market"}
