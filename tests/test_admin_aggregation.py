"""관리자 집계 헬퍼 단위 테스트 — 수입(MRR) 계산 + 사용량 평면키 파싱.

Firestore/네트워크 없이 순수 함수만 검증한다.
"""

from __future__ import annotations

from screener.services.pricing import (
    PRO_MONTHLY_KRW,
    PRO_YEARLY_KRW,
    monthly_recurring_krw,
    plan_price_krw,
)


# ──────────────────────────────────────────────
# 수입(MRR) 계산
# ──────────────────────────────────────────────


def test_mrr_monthly_only():
    assert monthly_recurring_krw(5, 0) == 5 * PRO_MONTHLY_KRW


def test_mrr_yearly_amortized_to_month():
    # 연간 구독은 12로 나눠 월 환산
    assert monthly_recurring_krw(0, 12) == 12 * (PRO_YEARLY_KRW / 12.0)
    assert monthly_recurring_krw(0, 12) == PRO_YEARLY_KRW


def test_mrr_mixed():
    expected = 3 * PRO_MONTHLY_KRW + 2 * (PRO_YEARLY_KRW / 12.0)
    assert monthly_recurring_krw(3, 2) == expected


def test_mrr_zero():
    assert monthly_recurring_krw(0, 0) == 0


def test_plan_price():
    assert plan_price_krw("monthly") == PRO_MONTHLY_KRW
    assert plan_price_krw("yearly") == PRO_YEARLY_KRW
    assert plan_price_krw("unknown") == 0


# ──────────────────────────────────────────────
# 사용량 평면키 파싱 (cost_tracker가 'agents.<name>.calls'로 저장)
# ──────────────────────────────────────────────


def test_parse_usage_doc_flat_keys():
    from screener.api.admin_routes import _new_usage_acc, _parse_usage_doc

    acc = _new_usage_acc()
    doc = {
        "total.krw": 100.0,
        "total.usd": 0.07,
        "agents.strategist.calls": 2,
        "agents.event_analyst.calls": 1,
        "agents.validator.calls": 3,
        "agents.discoverer.calls": 4,
    }
    _parse_usage_doc(doc, acc)
    assert acc["krw"] == 100.0
    assert acc["usd"] == 0.07
    # analyses = strategist + event_analyst (+ macro_pm + korean = 0)
    assert acc["analyses"] == 3
    assert acc["validations"] == 3
    assert acc["discoveries"] == 4
    assert acc["by_agent"]["strategist"] == 2
    assert acc["by_agent"]["validator"] == 3
    assert acc["by_agent"]["discoverer"] == 4


def test_parse_usage_doc_accumulates_across_days():
    from screener.api.admin_routes import _new_usage_acc, _parse_usage_doc

    acc = _new_usage_acc()
    day1 = {"total.krw": 50.0, "agents.strategist.calls": 1}
    day2 = {"total.krw": 30.0, "agents.strategist.calls": 2}
    _parse_usage_doc(day1, acc)
    _parse_usage_doc(day2, acc)
    assert acc["krw"] == 80.0
    assert acc["analyses"] == 3
    assert acc["by_agent"]["strategist"] == 3


def test_parse_usage_doc_empty():
    from screener.api.admin_routes import _new_usage_acc, _parse_usage_doc

    acc = _new_usage_acc()
    _parse_usage_doc({}, acc)
    assert acc["krw"] == 0.0
    assert acc["analyses"] == 0


# ──────────────────────────────────────────────
# 에러 싱크 — 예외 전파 안 함 (firebase 미초기화 환경에서도 무해)
# ──────────────────────────────────────────────


def test_log_error_never_raises():
    from screener.services.error_log import log_error

    # firebase 미초기화여도 조용히 넘어가야 함
    log_error("test_error", "메시지", uid="u1", ticker="005930", agent="x")
