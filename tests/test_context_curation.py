"""④ 컨텍스트 큐레이션 단위 테스트 — Analyst 섹터 상대 밸류에이션 렌더링.

_build_user_message는 IO 없는 순수 문자열 빌더라 mock dict로 검증 가능.
실제 섹터 통계 산출(_sector_stats)은 Firestore 의존이라 evals 하네스로 커버.
"""

from __future__ import annotations

from agents.analyst import AnalystAgent


def _stock(**over) -> dict:
    base = {
        "ticker": "005930",
        "name": "삼성전자",
        "sector": "반도체",
        "market": "kr",
        "current_price": 70000,
        "change_pct": 1.0,
        "market_cap": 4000000.0,
        "ma5": 69000, "ma20": 68000, "ma60": 67000,
        "vs_ma5_pct": 1.4, "vs_ma20_pct": 2.9, "vs_ma60_pct": 4.5,
        "ma_aligned": 1, "ma_squeeze": 0.1, "golden_cross": 0, "death_cross": 0,
        "rsi": 55.0, "vs_high_52w": -10.0, "vs_low_52w": 30.0, "volatility_20d": 2.0,
        "per": 8.5, "pbr": 1.2, "roe": 14.0, "div_yield": 2.0, "eps": 8000,
        "operating_margin": 20.0, "profit_margin": 15.0, "debt_equity": 40.0,
        "buy_score": 60.0, "buy_grade": "준상위", "target_upside": 10.0, "risk_grade": "중",
        "foreign_consecutive": 2, "foreign_net": 100.0, "inst_net": 50.0,
        "dual_buy": True, "supply_grade": "양호",
        "is_pre_surge": False, "pre_surge_score": 1,
        "themes": "AI, 반도체", "updated_at": "2026-06-05",
    }
    base.update(over)
    return base


def test_sector_section_rendered_with_pctile():
    agent = AnalystAgent()
    stats = {
        "sector": "반도체", "count": 12,
        "median_per": 6.2, "median_pbr": 1.0, "median_roe": 9.0,
        "per_pctile": 70, "pbr_pctile": 65,
    }
    msg = agent._build_user_message(_stock(), [], stats)
    assert "섹터 상대 밸류에이션" in msg
    assert "섹터 PER 중앙값: 6.20" in msg
    assert "섹터 하위 70%" in msg
    assert "임의 수치를 만들지 마세요" in msg


def test_sector_section_omitted_when_no_stats():
    agent = AnalystAgent()
    msg = agent._build_user_message(_stock(), [], None)
    assert "섹터 상대 밸류에이션" not in msg
    # 기본 펀더멘털은 그대로 존재
    assert "PER: 8.50" in msg


def test_sector_section_omitted_when_empty_medians():
    agent = AnalystAgent()
    msg = agent._build_user_message(_stock(), [], {"sector": "반도체", "count": 2})
    assert "섹터 상대 밸류에이션" not in msg
