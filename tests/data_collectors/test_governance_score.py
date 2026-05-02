"""utils/data_collectors/governance_score.py 단위 테스트.

5개 evaluate_* 함수 단위 검증 + 종합 calculate_governance_score 통합.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from utils.data_collectors import governance_score as gs


@pytest.fixture(autouse=True)
def _reset_cache():
    gs.reset_chaebol_cache()
    yield
    gs.reset_chaebol_cache()


# ──────────────────────────────────────────────
# 1. score_to_grade 등급 변환
# ──────────────────────────────────────────────


@pytest.mark.parametrize(
    "score,expected",
    [
        (10, "S"),
        (9, "A+"),
        (8, "A"),
        (7, "B+"),
        (6, "B"),
        (5, "C"),
        (4, "C"),
        (3, "D"),
        (0, "D"),
    ],
)
def test_score_to_grade(score, expected):
    assert gs.score_to_grade(score) == expected


# ──────────────────────────────────────────────
# 2. evaluate_buyback_policy
# ──────────────────────────────────────────────


def test_evaluate_buyback_policy_with_burn():
    summary = {"has_burn": True, "by_action": {"burn": 1, "buy_decision": 2}}
    result = gs.evaluate_buyback_policy(summary)
    assert result["score"] == 2
    assert result["completeness"] == "verified"


def test_evaluate_buyback_policy_buy_only():
    """소각은 없고 취득만 있음 → 1점."""
    summary = {"has_burn": False, "by_action": {"buy_decision": 1, "buy_complete": 1}}
    result = gs.evaluate_buyback_policy(summary)
    assert result["score"] == 1
    assert result["completeness"] == "verified"


def test_evaluate_buyback_policy_no_activity():
    summary = {"has_burn": False, "by_action": {}}
    result = gs.evaluate_buyback_policy(summary)
    assert result["score"] == 0
    assert result["completeness"] == "verified"


def test_evaluate_buyback_policy_none_data():
    result = gs.evaluate_buyback_policy(None)
    assert result["score"] == 0
    assert result["completeness"] == "unavailable"


# ──────────────────────────────────────────────
# 3. evaluate_dividend
# ──────────────────────────────────────────────


def test_evaluate_dividend_5y_growing():
    """5년 연속 + 증가 → 2점."""
    stock = {"div_yield": 2.5, "div_years": 5, "div_growth": 8.0}
    result = gs.evaluate_dividend(stock)
    assert result["score"] == 2
    assert result["completeness"] == "verified"


def test_evaluate_dividend_5y_no_growth():
    """5년 연속, 성장 X → 1점."""
    stock = {"div_yield": 2.5, "div_years": 5, "div_growth": 0}
    result = gs.evaluate_dividend(stock)
    assert result["score"] == 1


def test_evaluate_dividend_short_history():
    """배당 있으나 5년 미만 → partial 1점."""
    stock = {"div_yield": 2.5, "div_years": 3, "div_growth": 0}
    result = gs.evaluate_dividend(stock)
    assert result["score"] == 1
    assert result["completeness"] == "partial"


def test_evaluate_dividend_no_dividend():
    stock = {"div_yield": 0, "div_years": 0}
    result = gs.evaluate_dividend(stock)
    assert result["score"] == 0


def test_evaluate_dividend_none_data():
    result = gs.evaluate_dividend(None)
    assert result["score"] == 0
    assert result["completeness"] == "unavailable"


# ──────────────────────────────────────────────
# 4. evaluate_circular_ownership
# ──────────────────────────────────────────────


def test_evaluate_circular_samsung_resolved():
    """삼성전자 (005930) — 삼성 그룹 + 순환출자 해소."""
    result = gs.evaluate_circular_ownership("005930")
    assert result["score"] == 2
    assert result["completeness"] == "verified"
    assert "삼성" in result["reason"]


def test_evaluate_circular_hyundai_unresolved():
    """현대차 (005380) — 현대자동차 그룹 circular_ownership_resolved=false."""
    result = gs.evaluate_circular_ownership("005380")
    assert result["score"] == 0
    assert result["completeness"] == "verified"
    assert "현대자동차" in result["reason"]


def test_evaluate_circular_non_chaebol_estimated():
    """10대 그룹에 없는 종목 → estimated 2점."""
    result = gs.evaluate_circular_ownership("999999")
    assert result["score"] == 2
    assert result["completeness"] == "estimated"


# ──────────────────────────────────────────────
# 5. estimated 변수
# ──────────────────────────────────────────────


def test_evaluate_controlling_shareholder_estimated():
    result = gs.evaluate_controlling_shareholder("005930")
    assert result["completeness"] == "estimated"
    assert result["score"] == 1


def test_evaluate_audit_opinion_estimated():
    result = gs.evaluate_audit_opinion("005930")
    assert result["completeness"] == "estimated"
    assert result["score"] == 2


# ──────────────────────────────────────────────
# 6. find_chaebol_group
# ──────────────────────────────────────────────


def test_find_chaebol_group_samsung_subsidiary():
    g = gs.find_chaebol_group("005930")
    assert g is not None
    assert g["group_name"] == "삼성"
    assert g["membership_role"] == "subsidiary"


def test_find_chaebol_group_holding_company():
    """LG (003550) = 지주사 자체."""
    g = gs.find_chaebol_group("003550")
    assert g is not None
    assert g["group_name"] == "LG"
    assert g["membership_role"] == "holding"


def test_find_chaebol_group_unknown():
    assert gs.find_chaebol_group("999999") is None


# ──────────────────────────────────────────────
# 7. KoreaGovernanceAnalyzer 통합
# ──────────────────────────────────────────────


def _mk_analyzer(stock_data: dict | None, buyback_summary: dict | None):
    """db + buyback_collector mock 주입."""
    db = MagicMock()
    if stock_data is None:
        doc = SimpleNamespace(exists=False, to_dict=lambda: {})
    else:
        doc = SimpleNamespace(exists=True, to_dict=lambda: stock_data)
    db.collection.return_value.document.return_value.get.return_value = doc

    buyback_collector = MagicMock()
    buyback_collector.summarize_buyback_history.return_value = buyback_summary

    return gs.KoreaGovernanceAnalyzer(db=db, buyback_collector=buyback_collector)


def test_calculate_governance_score_strong_company():
    """강한 거버넌스 시나리오 — 모든 verified 변수 만점."""
    analyzer = _mk_analyzer(
        stock_data={"div_yield": 3.0, "div_years": 7, "div_growth": 5.0},
        buyback_summary={"has_burn": True, "by_action": {"burn": 1}},
    )
    result = analyzer.calculate_governance_score("005930")

    assert result["ticker"] == "005930"
    # buyback 2 + dividend 2 + circular 2 (삼성 해소) + controlling 1 (estimated) + audit 2 (estimated) = 9
    assert result["total_score"] == 9
    assert result["grade"] == "A+"
    assert result["components"]["buyback_policy"]["score"] == 2
    assert result["components"]["dividend_consistency"]["score"] == 2
    assert result["components"]["circular_ownership"]["score"] == 2
    assert result["data_completeness_summary"]["verified"] == 3
    assert result["data_completeness_summary"]["estimated"] == 2
    assert result["method"] == gs.KoreaGovernanceAnalyzer.METHOD_LABEL
    assert result["disclaimer"]
    assert "computed_at" in result


def test_calculate_governance_score_weak_company():
    """약한 거버넌스 — 자사주/배당 없음, 순환출자 잔존 (현대차)."""
    analyzer = _mk_analyzer(
        stock_data={"div_yield": 0, "div_years": 0},
        buyback_summary={"has_burn": False, "by_action": {}},
    )
    result = analyzer.calculate_governance_score("005380")

    # buyback 0 + dividend 0 + circular 0 (현대 미해소) + controlling 1 + audit 2 = 3
    assert result["total_score"] == 3
    assert result["grade"] == "D"
    assert "circular_ownership" in result["rationale"]


def test_calculate_governance_score_handles_missing_stock_data():
    """stocks 데이터 없음 + buyback 정상 → 부분 점수."""
    analyzer = _mk_analyzer(stock_data=None, buyback_summary=None)
    result = analyzer.calculate_governance_score("005930")
    # buyback 0 (unavailable) + div 0 (unavailable) + circular 2 (verified) + ctrl 1 + audit 2 = 5
    assert result["total_score"] == 5
    assert result["data_completeness_summary"]["unavailable"] >= 2


def test_calculate_governance_score_handles_buyback_collector_exception():
    """buyback_collector 예외 시 buyback unavailable 처리."""
    db = MagicMock()
    db.collection.return_value.document.return_value.get.return_value = SimpleNamespace(
        exists=True, to_dict=lambda: {"div_yield": 2.0, "div_years": 5, "div_growth": 5.0}
    )
    buyback_collector = MagicMock()
    buyback_collector.summarize_buyback_history.side_effect = ConnectionError("network")

    analyzer = gs.KoreaGovernanceAnalyzer(db=db, buyback_collector=buyback_collector)
    result = analyzer.calculate_governance_score("005930")

    assert result["components"]["buyback_policy"]["score"] == 0
    assert result["components"]["buyback_policy"]["completeness"] == "unavailable"
    # dividend는 정상이라 2점
    assert result["components"]["dividend_consistency"]["score"] == 2
