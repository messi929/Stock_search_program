"""utils/data_collectors/dart_event_collector.py 단위 테스트."""

from __future__ import annotations

import pytest

from utils.data_collectors.dart_event_collector import (
    EVENT_KEYWORDS,
    EVENT_RATING,
    classify_event,
)


@pytest.mark.parametrize(
    "report_nm,expected_type,expect_amendment",
    [
        # M&A
        ("회사합병결정", "ma_decision", False),
        ("[기재정정]회사분할결정", "ma_decision", True),
        ("영업양수도결정", "ma_decision", False),
        ("주식교환·이전 결정", "ma_decision", False),
        # 실적
        ("사업보고서", "performance", False),
        ("반기보고서", "performance", False),
        ("분기보고서", "performance", False),
        # CB / BW
        ("전환사채발행결정", "convertible_bond", False),
        ("[정정]신주인수권부사채발행결정", "convertible_bond", True),
        # 증자
        ("유상증자결정", "new_shares", False),
        ("무상증자결정", "new_shares", False),
        # 분할/병합
        ("주식분할결정", "stock_split", False),
        # 배당
        ("현금ㆍ현물배당결정", "dividend_decision", False),
        # 자사주 (buyback으로 디스패치)
        ("주식소각결정", "buyback", False),
        ("자기주식취득결정", "buyback", False),
        # 미해당
        ("증권발행실적보고서", "unknown", False),
        ("", "unknown", False),
    ],
)
def test_classify_event(report_nm, expected_type, expect_amendment):
    r = classify_event(report_nm)
    assert r["event_type"] == expected_type
    assert r["is_amendment"] is expect_amendment


def test_buyback_subtype_filled():
    """event_type=buyback이면 buyback_subtype도 함께 분류되어야 함."""
    r = classify_event("주식소각결정")
    assert r["event_type"] == "buyback"
    assert r["buyback_subtype"] == "burn"
    # buyback weight는 dart_buyback의 세분 등급 (소각=3) 사용
    assert r["weight"] == 3
    assert r["rating"] == "★★★"


def test_buyback_buy_decision_subtype():
    r = classify_event("주요사항보고서(자기주식취득결정)")
    assert r["event_type"] == "buyback"
    assert r["buyback_subtype"] == "buy_decision"
    assert r["weight"] == 1


def test_amendment_does_not_change_event_type():
    """[기재정정] prefix는 event_type 분류에 영향 X."""
    r1 = classify_event("회사합병결정")
    r2 = classify_event("[기재정정]회사합병결정")
    assert r1["event_type"] == r2["event_type"]
    assert r2["is_amendment"] is True


def test_priority_ma_over_buyback_when_both_present():
    """가설: M&A 키워드가 자사주 키워드보다 먼저 매칭됨 (EVENT_KEYWORDS 순서)."""
    # "회사합병결정 자기주식취득" — M&A가 우선
    r = classify_event("회사합병결정 및 자기주식취득결정")
    assert r["event_type"] == "ma_decision"


def test_unknown_for_non_event_disclosure():
    r = classify_event("기타 안내공시")
    assert r["event_type"] == "unknown"
    assert r["weight"] == 0
    assert r["buyback_subtype"] is None


def test_event_rating_completeness():
    """EVENT_KEYWORDS의 모든 카테고리는 EVENT_RATING에 등록되어야 함."""
    for event_type, _kw in EVENT_KEYWORDS:
        assert event_type in EVENT_RATING, f"{event_type} missing in EVENT_RATING"
    assert "unknown" in EVENT_RATING
