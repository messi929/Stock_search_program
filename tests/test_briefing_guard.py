"""새벽 미국시장 브리핑 신선도 가드 단위 테스트.

미 공휴일(예: 독립기념일 관측휴장)에 '간밤 미국장' 브리핑이 잘못 생성되지 않는지를
NYSE 캘린더 + 데이터 신선도 2중 방어 관점에서 검증한다. 실 API/네트워크 불필요.

실행:
    py -m pytest tests/test_briefing_guard.py -q
"""

from __future__ import annotations

from datetime import date

import pytest

from agents.briefing import (
    consensus_us_session_date,
    us_session_is_stale,
)
from utils.market_calendar import us_market_closed

# holidays 라이브러리 가용 여부(prod requirements엔 포함). 없으면 공휴일 정밀 테스트는 skip.
try:
    import holidays as _holidays  # noqa: F401

    _HAS_HOLIDAYS = True
except Exception:  # pragma: no cover
    _HAS_HOLIDAYS = False

needs_holidays = pytest.mark.skipif(
    not _HAS_HOLIDAYS, reason="holidays 라이브러리 필요(NYSE 공휴일 정밀 판별)"
)


def _snap(equity_date: str, *, phantom: dict | None = None, fx: str | None = None) -> dict:
    """테스트용 스냅샷 — 5개 주식지표에 동일 종가일 + 선택적 팬텀/FX 오염."""
    keys = ["sp500", "nasdaq", "dow", "sox", "vix"]
    snap = {k: {"label": k, "last": 100.0, "change_pct": 0.1, "date": equity_date} for k in keys}
    if phantom:
        for k, d in phantom.items():
            snap[k]["date"] = d
    if fx:
        snap["usdkrw"] = {"label": "usdkrw", "last": 1500.0, "change_pct": 0.0, "date": fx}
    return snap


# ── NYSE 캘린더 프리미티브 ──────────────────────────


@needs_holidays
def test_us_market_closed_independence_day_observed():
    # 2026-07-04(토) 독립기념일 → 7/3(금) 관측휴장.
    assert us_market_closed(date(2026, 7, 3))[0] is True
    assert us_market_closed(date(2026, 7, 2)) == (False, "")  # 목요일 정상 개장


def test_us_market_closed_weekend_no_lib_needed():
    # 주말은 라이브러리 없이도 항상 휴장.
    assert us_market_closed(date(2026, 7, 4))[0] is True  # 토
    assert us_market_closed(date(2026, 7, 5))[0] is True  # 일


@needs_holidays
def test_us_market_closed_juneteenth_and_good_friday():
    assert us_market_closed(date(2026, 6, 19))[0] is True  # Juneteenth
    assert us_market_closed(date(2026, 4, 3))[0] is True   # Good Friday 2026


# ── 가드: 미 공휴일 원천 차단(핵심 회귀) ──────────────


@needs_holidays
def test_guard_skips_independence_day_saturday():
    """7/4(토) 아침: 간밤(7/3 금)이 관측휴장 → 반드시 생략. (실제로 놓쳤던 케이스)"""
    snap = _snap("2026-07-02", fx="2026-07-03")  # 주식은 7/2에 멈춤, FX만 7/3
    stale, reason = us_session_is_stale(snap, today=date(2026, 7, 4))
    assert stale is True
    assert reason.startswith("overnight_closed")


@needs_holidays
def test_guard_skips_midweek_holiday():
    """추수감사절(2026-11-26 목) 다음 금요일 아침 → 간밤 목요일 휴장으로 생략."""
    snap = _snap("2026-11-25")  # 수요일이 마지막 실장
    stale, reason = us_session_is_stale(snap, today=date(2026, 11, 27))
    assert stale is True
    assert reason.startswith("overnight_closed")


def test_guard_skips_after_weekend_monday():
    """월요일 아침: 간밤(일요일)은 주말 휴장 → 생략(라이브러리 불필요)."""
    snap = _snap("2026-07-10")  # 금요일 종가
    stale, reason = us_session_is_stale(snap, today=date(2026, 7, 13))  # 월
    assert stale is True
    assert reason.startswith("overnight_closed")


# ── 가드: 정상일엔 통과 ──────────────────────────────


def test_guard_passes_normal_friday():
    """금요일 아침: 간밤 목요일 정상장 + 신선한 데이터 → 통과."""
    snap = _snap("2026-07-02")
    stale, reason = us_session_is_stale(snap, today=date(2026, 7, 3))
    assert stale is False
    assert reason == ""


def test_guard_passes_normal_saturday():
    """토요일 아침(공휴일 아님): 간밤 금요일 정상장 → 통과(화~토 스케줄에 토 포함)."""
    snap = _snap("2026-07-10")  # 금요일 종가
    stale, reason = us_session_is_stale(snap, today=date(2026, 7, 11))  # 토
    assert stale is False


# ── 가드: 데이터 신선도 백업 & 팬텀 바 방어 ─────────────


def test_guard_stale_data_backup():
    """캘린더상 간밤은 개장이었지만 데이터가 2일 이상 묵음 → 백업 신선도로 생략."""
    # 목요일 아침(간밤 수요일 개장)인데 스냅샷은 월요일 종가에 멈춤(diff=3).
    snap = _snap("2026-07-06")  # 월
    stale, reason = us_session_is_stale(snap, today=date(2026, 7, 9))  # 목
    assert stale is True
    assert reason.startswith("stale_data")


def test_consensus_ignores_single_phantom_bar():
    """지표 1개가 팬텀 미래 날짜를 뱉어도 합의(최빈값)는 다수 날짜를 유지."""
    # 4개는 7/2, sox만 7/3 팬텀. max()=7/3(오판) 이지만 consensus=7/2.
    snap = _snap("2026-07-02", phantom={"sox": "2026-07-03"})
    assert consensus_us_session_date(snap) == date(2026, 7, 2)


@needs_holidays
def test_guard_survives_phantom_when_calendar_backstops():
    """팬텀 바로 신선도가 흐려져도 캘린더(1차)가 공휴일이면 여전히 생략."""
    # 7/4(토) 아침, sox만 7/3 팬텀 — 신선도만 보면 통과할 뻔하지만 캘린더가 막는다.
    snap = _snap("2026-07-02", phantom={"sox": "2026-07-03"})
    stale, reason = us_session_is_stale(snap, today=date(2026, 7, 4))
    assert stale is True
    assert reason.startswith("overnight_closed")


def test_consensus_tie_prefers_earlier():
    """최빈값 동률이면 더 이른 날짜(보수적)를 택한다."""
    snap = _snap("2026-07-02", phantom={"sox": "2026-07-03", "vix": "2026-07-03"})
    # 7/2 x3, 7/3 x2 → 최빈 7/2
    assert consensus_us_session_date(snap) == date(2026, 7, 2)
    # 완전 동률(각 지표 서로 다른 날 2:2 상황 구성)
    snap2 = _snap("2026-07-02", phantom={"dow": "2026-07-03", "sox": "2026-07-03", "vix": "2026-07-01"})
    # 7/2 x2, 7/3 x2, 7/1 x1 → 동률(7/2,7/3) → 더 이른 7/2
    assert consensus_us_session_date(snap2) == date(2026, 7, 2)


def test_guard_no_data():
    stale, reason = us_session_is_stale({}, today=date(2026, 7, 3))
    assert stale is True
    assert reason == "no_data"
