"""Pro 구독 가격 상수 — 관리자 수입(MRR/ARR) 추정용.

가격은 Lemon Squeezy 대시보드에서 관리되고 코드엔 variant ID만 있었다(2026-06-07).
수입 집계를 위해 가격을 코드 상수(env 오버라이드 가능)로 둔다. LS 환불·프로모·
세금 등 실제 정산과 미세 오차가 있을 수 있어 관리자 화면엔 "추정"으로 표기한다.
"""

from __future__ import annotations

import os

# Pro 요금 (원). CLAUDE.md / project_payment_decision 기준: 월 29,000 / 연 319,000.
PRO_MONTHLY_KRW: int = int(os.environ.get("PRO_MONTHLY_KRW", "29000"))
PRO_YEARLY_KRW: int = int(os.environ.get("PRO_YEARLY_KRW", "319000"))


def monthly_recurring_krw(monthly_count: int, yearly_count: int) -> float:
    """활성 구독 수 → 월 환산 매출(MRR). 연간 구독은 12로 나눠 월 환산."""
    return monthly_count * PRO_MONTHLY_KRW + yearly_count * (PRO_YEARLY_KRW / 12.0)


def plan_price_krw(plan: str) -> int:
    """플랜명(monthly|yearly) → 청구 금액(원). 알 수 없으면 0."""
    if plan == "monthly":
        return PRO_MONTHLY_KRW
    if plan == "yearly":
        return PRO_YEARLY_KRW
    return 0
