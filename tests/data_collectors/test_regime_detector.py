"""utils/data_collectors/regime_detector.py 단위 테스트.

검증 범주:
  1. 6 국면 명확 매칭 (각 국면별 input → primary regime 1.0 confidence)
  2. 4개 알려진 시점 (2008/2017/2020/2022)
  3. 점수 동률/모호 처리 (Transition + transition_to)
  4. detect_regime_from_cycles 통합 (cycle_detector 결과 직접 받기)
  5. 매크로 캘린더 (upcoming events)
  6. LEGAL — 국면 라벨에 권유성 표현 X
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from utils.data_collectors import regime_detector as rd


@pytest.fixture(autouse=True)
def _reset_calendar():
    rd.reset_calendar_cache()
    yield
    rd.reset_calendar_cache()


# ──────────────────────────────────────────────
# 1. 6 국면 명확 매칭 (각 국면 4/4 점수)
# ──────────────────────────────────────────────


class TestSixRegimeClearMatching:
    def test_goldilocks_full_match(self):
        result = rd.detect_macro_regime(
            interest_rate_stage="횡보",
            business_cycle_stage="확장 후기",
            inflation_stage="저인플레이션",
            currency_stage="달러 횡보",
        )
        assert result["regime"] == "Goldilocks"
        assert result["regime_score"] == 4
        assert result["regime_confidence"] == 1.0
        assert "골디락스" in result["regime_kr"]

    def test_reflation_full_match(self):
        """Reflation 명확 매칭 — 인플레 둔화 (Recovery는 저인플레/디플레만 받음)."""
        result = rd.detect_macro_regime(
            interest_rate_stage="인하 시작",
            business_cycle_stage="확장 초기",
            inflation_stage="고인플레이션 (둔화 중)",  # Reflation만 매칭 (Recovery는 X)
            currency_stage="달러 약세",
        )
        assert result["regime"] == "Reflation"
        assert result["regime_score"] == 4

    def test_reflation_recovery_tie_resolves_to_one(self):
        """둘 다 4점 매칭 케이스 → 사전순 정렬로 Recovery 우선 + Reflation transition_to.

        실제 입력: 인하시작+확장초기+저인플레+달러약세 → Reflation/Recovery 모두 4/4.
        spec상 두 국면 정의 중첩 (확장 초기 + 저인플레 + 달러약세 + 인하시작은 둘 다 포함).
        결정적 정렬로 Recovery가 primary, Reflation이 transition_to.
        """
        result = rd.detect_macro_regime(
            interest_rate_stage="인하 시작",
            business_cycle_stage="확장 초기",
            inflation_stage="저인플레이션",
            currency_stage="달러 약세",
        )
        assert result["regime"] in ("Recovery", "Reflation")
        assert result["regime_score"] == 4
        # 동률이라 transition_to 명시
        assert result["transition_to"] in ("Recovery", "Reflation")
        assert result["transition_to"] != result["regime"]

    def test_stagflation_full_match(self):
        result = rd.detect_macro_regime(
            interest_rate_stage="인상 후반",
            business_cycle_stage="수축 초기",
            inflation_stage="고인플레이션 (가속)",
            currency_stage="달러 강세",
        )
        assert result["regime"] == "Stagflation"
        assert result["regime_score"] == 4

    def test_risk_off_full_match(self):
        result = rd.detect_macro_regime(
            interest_rate_stage="인상 후반",
            business_cycle_stage="수축 후기",
            inflation_stage="디플레이션 우려",
            currency_stage="달러 강세",
        )
        assert result["regime"] == "Risk-Off"
        assert result["regime_score"] == 4

    def test_recovery_full_match(self):
        result = rd.detect_macro_regime(
            interest_rate_stage="인하 시작",
            business_cycle_stage="수축 후기",
            inflation_stage="저인플레이션",
            currency_stage="달러 약세",
        )
        # 동시에 Reflation도 일부 매칭 가능 — primary는 점수 비교
        # Recovery: 4/4 (모두 매칭), Reflation: 3/4 (수축 후기는 Reflation 패턴에 없음)
        assert result["regime"] == "Recovery"
        assert result["regime_score"] == 4

    def test_late_cycle_full_match(self):
        result = rd.detect_macro_regime(
            interest_rate_stage="인상 시작",
            business_cycle_stage="확장 후기",
            inflation_stage="고인플레이션 (가속)",
            currency_stage="달러 강세",
        )
        assert result["regime"] == "Late Cycle"
        assert result["regime_score"] == 4


# ──────────────────────────────────────────────
# 2. 4개 알려진 시점 검증
# ──────────────────────────────────────────────


class TestKnownPeriodRegimes:
    def test_2022_09_late_cycle_or_stagflation(self):
        """2022-09: 인상 후반 + 확장 후기 + 고인플레 가속 + 달러 강세 → Late Cycle."""
        result = rd.detect_macro_regime(
            interest_rate_stage="인상 후반",
            business_cycle_stage="확장 후기",
            inflation_stage="고인플레이션 (가속)",
            currency_stage="달러 강세",
        )
        assert result["regime"] == "Late Cycle"
        # Stagflation도 일부 매칭이지만 business_cycle "확장 후기"는 Stagflation에 없음
        assert result["regime_score"] == 4

    def test_2020_04_recovery(self):
        """2020-04: 인하 시작 + 수축 후기 + 디플레 우려 + (DXY 약세 가정) → Recovery."""
        result = rd.detect_macro_regime(
            interest_rate_stage="인하 시작",
            business_cycle_stage="수축 후기",
            inflation_stage="디플레이션 우려",
            currency_stage="달러 약세",
        )
        assert result["regime"] == "Recovery"

    def test_2017_06_goldilocks(self):
        """2017-06: 인상 후반 + 확장 후기 + 저인플레 + 달러 약세."""
        result = rd.detect_macro_regime(
            interest_rate_stage="인상 후반",  # Late Cycle 매칭
            business_cycle_stage="확장 후기",  # Goldilocks + Late Cycle 둘 다
            inflation_stage="저인플레이션",  # Goldilocks
            currency_stage="달러 약세",  # Reflation/Recovery
        )
        # Late Cycle: 인상 후반(✓) + 확장 후기(✓) + 고인플레(✗ — 저인플레임) + 달러 강세(✗) = 2점
        # Goldilocks: 횡보(✗) + 확장 후기(✓) + 저인플레(✓) + 달러 횡보/약세(✓) = 3점
        # → Goldilocks
        assert result["regime"] == "Goldilocks"
        assert result["regime_score"] == 3

    def test_2008_12_risk_off(self):
        """2008-12: 인하 시작 + 수축 후기 + 디플레 우려 + 달러 강세 → Recovery + Risk-Off 혼재."""
        result = rd.detect_macro_regime(
            interest_rate_stage="인하 시작",
            business_cycle_stage="수축 후기",
            inflation_stage="디플레이션 우려",
            currency_stage="달러 강세",
        )
        # Recovery: 인하시작(✓) + 수축후기(✓) + 디플레우려(✓) + 달러약세(✗) = 3점
        # Risk-Off: 인상 후반(✗) + 수축후기(✓) + 디플레(✓) + 달러 강세(✓) = 3점
        # 동률 → 정렬 (사전순 Recovery vs Risk-Off → R-e-covery < R-i-sk-Off, sorted ascending → Recovery 먼저)
        # Recovery primary, Risk-Off transition_to
        assert result["regime"] in ("Recovery", "Risk-Off")
        # 동률 시 transition_to 명시 (점수 차 0 ≤ 1)
        assert result["transition_to"] is not None
        assert result["regime_score"] == 3


# ──────────────────────────────────────────────
# 3. 점수 모호 / Transition 처리
# ──────────────────────────────────────────────


class TestTransitionLogic:
    def test_low_score_returns_transition(self):
        """4 사이클 매칭이 모두 약하면 (< 3점) Transition."""
        result = rd.detect_macro_regime(
            interest_rate_stage="횡보",  # Goldilocks만 (1점)
            business_cycle_stage="전환기 (불확실)",  # 어디에도 매칭 X
            inflation_stage="고인플레이션 (둔화 중)",  # Stagflation/Reflation/Late Cycle (여러)
            currency_stage="달러 횡보",  # Goldilocks만
        )
        # 최고 점수 < 3 → Transition
        assert result["regime"] == "Transition"
        assert result["regime_confidence"] < 0.75
        assert result["transition_to"] is None

    def test_two_point_match_is_now_transition(self):
        """2점 매칭 (50% confidence)도 Transition으로 분류 (MIN_PRIMARY_SCORE 3 강화).

        과거: 2점 → primary로 분류 (사용자에게 잘못된 단정 위험)
        새 logic: 3점 (75%) 이상만 명확한 국면, 2점은 Transition
        """
        # Goldilocks 2/4 매칭 케이스 만들기
        result = rd.detect_macro_regime(
            interest_rate_stage="횡보",  # Goldilocks
            business_cycle_stage="전환기 (불확실)",  # 매칭 없음
            inflation_stage="저인플레이션",  # Goldilocks
            currency_stage="달러 강세",  # Late Cycle/Stagflation/Risk-Off
        )
        # Goldilocks: 횡보(✓) + 확장후기(✗) + 저인플레(✓) + 횡보/약세(✗) = 2점
        # → MIN_PRIMARY_SCORE 3 미만 → Transition
        assert result["regime"] == "Transition"

    def test_three_point_match_is_primary(self):
        """3점 매칭 (75%)은 primary로 분류 (임계 정확히 충족)."""
        # Goldilocks 3/4 매칭
        result = rd.detect_macro_regime(
            interest_rate_stage="횡보",
            business_cycle_stage="확장 후기",
            inflation_stage="저인플레이션",
            currency_stage="달러 강세",  # Goldilocks 매칭 X
        )
        # Goldilocks: 횡보(✓) + 확장후기(✓) + 저인플레(✓) + 달러약세/횡보(✗) = 3점
        assert result["regime"] == "Goldilocks"
        assert result["regime_score"] == 3
        assert result["regime_confidence"] == 0.75


# ──────────────────────────────────────────────
# 4. detect_regime_from_cycles (cycle_detector 결과 통합)
# ──────────────────────────────────────────────


def test_detect_regime_from_cycles_integration():
    cycles = {
        "interest_rate": {"stage": "인하 시작"},
        "business_cycle": {"stage": "확장 초기"},
        "inflation": {"stage": "고인플레이션 (둔화 중)"},  # Reflation 명확
        "currency": {"stage": "달러 약세"},
    }
    result = rd.detect_regime_from_cycles(cycles)
    assert result["regime"] == "Reflation"
    assert result["regime_score"] == 4


def test_detect_regime_from_cycles_raises_valueerror_on_missing_keys():
    """cycles 4 키 누락 시 ValueError (cycle_detector와 일관성)."""
    incomplete = {"interest_rate": {"stage": "횡보"}}
    with pytest.raises(ValueError, match="필수 사이클 키 누락"):
        rd.detect_regime_from_cycles(incomplete)


def test_detect_regime_from_cycles_raises_valueerror_on_missing_stage():
    """4 키는 있지만 stage 서브키 누락 시 ValueError."""
    cycles_no_stage = {
        "interest_rate": {"confidence": 1.0},  # stage 없음
        "business_cycle": {"stage": "확장 후기"},
        "inflation": {"stage": "저인플레이션"},
        "currency": {"stage": "달러 약세"},
    }
    with pytest.raises(ValueError, match="stage"):
        rd.detect_regime_from_cycles(cycles_no_stage)


# ──────────────────────────────────────────────
# 5. 매크로 캘린더 — JSON 로드 + upcoming events
# ──────────────────────────────────────────────


class TestMacroCalendar:
    def test_calendar_metadata_present(self):
        meta = rd.get_calendar_metadata()
        assert "schema_version" in meta
        assert "country_codes" in meta

    def test_get_upcoming_events_filters_window(self):
        """today 기준 30일 이내 이벤트만 반환."""
        # 2026-05-02 기준
        today = datetime(2026, 5, 2)
        events = rd.get_upcoming_macro_events(days_ahead=30, today=today)

        # 2026-05-07 FOMC, 2026-05-13 CPI, 2026-05-28 BOK 등이 30일 안에 있어야 함
        assert len(events) >= 2
        for e in events:
            assert 0 <= e["days_until"] <= 30

    def test_get_upcoming_events_sorted_by_date(self):
        today = datetime(2026, 1, 1)
        events = rd.get_upcoming_macro_events(days_ahead=60, today=today)
        days = [e["days_until"] for e in events]
        assert days == sorted(days)

    def test_get_upcoming_events_empty_window(self):
        """과거만 검색 → 0건."""
        today = datetime(2030, 1, 1)
        events = rd.get_upcoming_macro_events(days_ahead=30, today=today)
        # 2026 캘린더만 있어서 2030+30일은 0
        assert events == []

    def test_calendar_handles_missing_file(self, monkeypatch, tmp_path):
        fake = tmp_path / "not_exist.json"
        monkeypatch.setattr(rd, "CALENDAR_FILE", fake)
        rd.reset_calendar_cache()
        events = rd.get_upcoming_macro_events(days_ahead=30, today=datetime(2026, 5, 2))
        assert events == []

    def test_calendar_includes_fomc_and_bok(self):
        events = rd.get_upcoming_macro_events(days_ahead=365, today=datetime(2026, 1, 1))
        types = {e["type"] for e in events}
        assert "FOMC" in types
        assert "BOK_RATE" in types
        assert "US_CPI" in types


# ──────────────────────────────────────────────
# 6. LEGAL — 권유성 표현 0건
# ──────────────────────────────────────────────


def test_regime_response_has_no_recommendation_words():
    result = rd.detect_macro_regime(
        interest_rate_stage="인하 시작",
        business_cycle_stage="확장 초기",
        inflation_stage="저인플레이션",
        currency_stage="달러 약세",
    )
    text_fields = [result["regime"], result["regime_kr"], result["rationale"], result["legal_note"]]
    for v in text_fields:
        for forbidden in ["매수", "매도", "사세요", "팔아라", "추천"]:
            assert forbidden not in v


def test_legal_note_attached_to_all_responses():
    result = rd.detect_macro_regime(
        interest_rate_stage="횡보", business_cycle_stage="전환기 (불확실)",
        inflation_stage="저인플레이션", currency_stage="달러 횡보",
    )
    assert result["legal_note"] == rd.LEGAL_NOTE


# ──────────────────────────────────────────────
# 7. JSON 데이터 sanity
# ──────────────────────────────────────────────


def test_macro_calendar_json_loadable():
    path = Path(__file__).resolve().parents[2] / "data" / "macro_calendar.json"
    assert path.exists()
    import json

    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    assert "_meta" in data
    assert "events" in data
    assert len(data["events"]) >= 50  # FOMC 8 + BOK 8 + CPI 24 + 그 외


def test_macro_calendar_event_format():
    """모든 이벤트가 date/type/country/name 필드 보유."""
    data = rd._load_calendar()
    for event in data.get("events", []):
        assert "date" in event
        assert "type" in event
        assert "country" in event
        assert event["country"] in ("US", "KR", "GLOBAL")
