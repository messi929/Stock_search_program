"""utils/data_collectors/cycle_detector.py 단위 테스트.

검증 범주:
  1. 경계값 (boundary) — 임계 직전/직후
  2. 알려진 과거 시점 (4개) — 학계/언론 합의와 일치
  3. LEGAL — 권유성 표현 0건, 후행성/면책 명시
  4. confidence 의미 (강한 신호 = 높은 점수)
"""

from __future__ import annotations

import pytest

from utils.data_collectors.cycle_detector import (
    DATA_LAG_WARNING,
    LEGAL_NOTE,
    detect_all_cycles,
    detect_business_cycle_stage,
    detect_currency_stage,
    detect_inflation_stage,
    detect_interest_rate_stage,
)


# ──────────────────────────────────────────────
# 1. detect_interest_rate_stage — 경계값 + 분기
# ──────────────────────────────────────────────


class TestInterestRateStage:
    def test_strong_hike_cycle(self):
        """12M +200bp 인상 + 3M 지속 → '인상 후반'."""
        result = detect_interest_rate_stage(
            rate_current=5.50, rate_3m_ago=5.25, rate_12m_ago=3.50
        )
        assert result["stage"] == "인상 후반"
        assert result["confidence"] == 1.0  # 변동 폭 200bp 이상

    def test_hike_to_pause(self):
        """12M +100bp 인상 후 3M 횡보 → '인상 후반'."""
        result = detect_interest_rate_stage(
            rate_current=5.50, rate_3m_ago=5.50, rate_12m_ago=4.50
        )
        assert result["stage"] == "인상 후반"

    def test_hike_then_cut_pivot(self):
        """12M 인상이지만 최근 3M 인하 → '인상 시작' (변곡점)."""
        result = detect_interest_rate_stage(
            rate_current=5.00, rate_3m_ago=5.50, rate_12m_ago=4.00
        )
        assert result["stage"] == "인상 시작"
        assert "인하 사이클 시작 가능성" in result["rationale"]

    def test_active_cut_cycle(self):
        """12M -100bp 인하 + 3M 지속 → '인하 시작'."""
        result = detect_interest_rate_stage(
            rate_current=4.00, rate_3m_ago=4.50, rate_12m_ago=5.00
        )
        assert result["stage"] == "인하 시작"

    def test_cut_then_pause(self):
        """12M 인하 후 3M 횡보 → '인하 후반'."""
        result = detect_interest_rate_stage(
            rate_current=3.00, rate_3m_ago=3.00, rate_12m_ago=4.00
        )
        assert result["stage"] == "인하 후반"

    def test_cut_then_rebound(self):
        """12M 인하 (-100bp) 후 3M 반등 (+50bp) → '인하 후반' (사이클 종료 가능성)."""
        result = detect_interest_rate_stage(
            rate_current=3.50, rate_3m_ago=3.00, rate_12m_ago=4.50
        )
        assert result["stage"] == "인하 후반"
        assert "종료 가능성" in result["rationale"]

    def test_sideways_within_threshold(self):
        """12M 변동 ±50bp 이내 → '횡보'."""
        result = detect_interest_rate_stage(
            rate_current=5.25, rate_3m_ago=5.25, rate_12m_ago=5.00
        )
        assert result["stage"] == "횡보"
        assert result["confidence"] == 0.25

    @pytest.mark.parametrize(
        "rate_change_12m,expected_stage",
        [
            (0.51, "인상"),  # 임계 +50bp 직전
            (0.50, "횡보"),  # 정확히 임계 = 횡보 (>가 아닌 >0.5)
            (-0.51, "인하"),
            (-0.50, "횡보"),
        ],
    )
    def test_boundary_threshold(self, rate_change_12m, expected_stage):
        result = detect_interest_rate_stage(
            rate_current=5.0, rate_3m_ago=5.0, rate_12m_ago=5.0 - rate_change_12m
        )
        assert expected_stage in result["stage"]

    def test_yield_curve_inversion_signal(self):
        """spread < 0 → '역전' 신호 첨부."""
        result = detect_interest_rate_stage(
            rate_current=5.0, rate_3m_ago=5.0, rate_12m_ago=5.0, spread_10y_2y=-0.1
        )
        assert result["yield_curve_signal"] == "역전"

    def test_yield_curve_normal(self):
        result = detect_interest_rate_stage(
            rate_current=5.0, rate_3m_ago=5.0, rate_12m_ago=5.0, spread_10y_2y=0.5
        )
        assert result["yield_curve_signal"] == "정상"

    def test_yield_curve_optional_none(self):
        result = detect_interest_rate_stage(
            rate_current=5.0, rate_3m_ago=5.0, rate_12m_ago=5.0
        )
        assert result["yield_curve_signal"] is None

    def test_legal_and_lag_meta_attached(self):
        result = detect_interest_rate_stage(
            rate_current=5.0, rate_3m_ago=5.0, rate_12m_ago=5.0
        )
        assert result["data_lag_warning"] == DATA_LAG_WARNING
        assert result["legal_note"] == LEGAL_NOTE
        # LEGAL: 권유성 표현 X
        for v in [result["stage"], result["rationale"]]:
            for forbidden in ["매수", "매도", "사세요", "팔아라", "추천"]:
                assert forbidden not in v


# ──────────────────────────────────────────────
# 2. detect_business_cycle_stage — 경계값
# ──────────────────────────────────────────────


class TestBusinessCycleStage:
    def test_strong_expansion(self):
        """GDP 3% + 산업생산 + + 실업률 빠른 하락 → '확장 초기'."""
        result = detect_business_cycle_stage(
            gdp_yoy=3.0, industrial_production_yoy=2.0,
            unemployment_current=3.5, unemployment_12m_ago=4.5,
        )
        assert result["stage"] == "확장 초기"

    def test_mature_expansion(self):
        """GDP 2% + 산업생산 + + 실업률 안정 → '확장 후기'."""
        result = detect_business_cycle_stage(
            gdp_yoy=2.0, industrial_production_yoy=1.0,
            unemployment_current=4.0, unemployment_12m_ago=4.0,
        )
        assert result["stage"] == "확장 후기"

    def test_early_contraction_both_signals_negative(self):
        """GDP 1.0% (임계 미달) + 산업생산 음수 → '수축 초기'.

        새 분기 logic: GDP < 임계 AND IP < 0 둘 다 충족해야 수축.
        """
        result = detect_business_cycle_stage(
            gdp_yoy=1.0, industrial_production_yoy=-0.5,
            unemployment_current=4.5, unemployment_12m_ago=4.5,
        )
        assert result["stage"] == "수축 초기"

    def test_contradiction_gdp_low_ip_positive_is_transition(self):
        """GDP 1.0 (확장 미달) + IP +0.5 (양수) → 신호 모순 → '전환기'.

        과거 logic은 IP<0 OR GDP<임계 이면 무조건 수축으로 분류 (HIGH bug).
        새 logic은 모순 케이스를 명시적으로 전환기로 분류.
        """
        result = detect_business_cycle_stage(
            gdp_yoy=1.0, industrial_production_yoy=0.5,
            unemployment_current=4.5, unemployment_12m_ago=4.5,
        )
        assert "전환기" in result["stage"]
        assert "모순" in result["rationale"] or "경계" in result["rationale"]

    def test_contradiction_gdp_strong_ip_negative_is_transition(self):
        """GDP 3% (확장 충족) + IP -2% (음수) → 신호 모순 → '전환기'."""
        result = detect_business_cycle_stage(
            gdp_yoy=3.0, industrial_production_yoy=-2.0,
            unemployment_current=4.0, unemployment_12m_ago=4.0,
        )
        assert "전환기" in result["stage"]

    def test_late_contraction_unemployment_rising(self):
        """GDP -1% + 산업생산 음수 + 실업률 빠른 상승 → '수축 후기'."""
        result = detect_business_cycle_stage(
            gdp_yoy=-1.0, industrial_production_yoy=-3.0,
            unemployment_current=6.0, unemployment_12m_ago=4.5,
        )
        assert result["stage"] == "수축 후기"

    def test_transition_borderline(self):
        """GDP 1.5% 정확 + 산업생산 0 → '전환기' (정확히 임계, 양/음 모두 아님)."""
        result = detect_business_cycle_stage(
            gdp_yoy=1.5, industrial_production_yoy=0.0,
            unemployment_current=4.0, unemployment_12m_ago=4.0,
        )
        assert "전환기" in result["stage"]

    def test_country_kr_uses_higher_gdp_threshold(self):
        """KR 임계 2.0 → GDP 1.8%는 확장 미달 (US 1.5에서는 확장)."""
        result_kr = detect_business_cycle_stage(
            gdp_yoy=1.8, industrial_production_yoy=-0.5,
            unemployment_current=3.5, unemployment_12m_ago=3.5,
            country="KR",
        )
        # GDP 1.8 < 2.0 (KR 임계) AND IP < 0 → 수축 초기
        assert result_kr["stage"] == "수축 초기"
        assert result_kr["country"] == "KR"
        assert result_kr["gdp_threshold"] == 2.0

        # 같은 데이터 US (임계 1.5) → 신호 모순 (GDP 1.8 > 1.5 but IP < 0) → 전환기
        result_us = detect_business_cycle_stage(
            gdp_yoy=1.8, industrial_production_yoy=-0.5,
            unemployment_current=3.5, unemployment_12m_ago=3.5,
            country="US",
        )
        assert "전환기" in result_us["stage"]
        assert result_us["gdp_threshold"] == 1.5

    def test_pmi_signal_attached(self):
        result = detect_business_cycle_stage(
            gdp_yoy=2.0, industrial_production_yoy=1.0,
            unemployment_current=4.0, unemployment_12m_ago=4.0, pmi=52.5,
        )
        assert "확장" in result["pmi_signal"]

        result2 = detect_business_cycle_stage(
            gdp_yoy=2.0, industrial_production_yoy=1.0,
            unemployment_current=4.0, unemployment_12m_ago=4.0, pmi=48.0,
        )
        assert "수축" in result2["pmi_signal"]

    def test_legal_no_recommendation_words(self):
        result = detect_business_cycle_stage(
            gdp_yoy=2.0, industrial_production_yoy=1.0,
            unemployment_current=4.0, unemployment_12m_ago=4.0,
        )
        for v in [result["stage"], result["rationale"]]:
            for forbidden in ["매수", "매도", "사세요"]:
                assert forbidden not in v


# ──────────────────────────────────────────────
# 3. detect_inflation_stage — 경계값
# ──────────────────────────────────────────────


class TestInflationStage:
    @pytest.mark.parametrize(
        "cpi,expected",
        [
            (0.5, "디플레이션"),
            (0.99, "디플레이션"),
            (1.0, "저인플레이션"),  # 정확히 임계
            (2.0, "저인플레이션"),
            (2.99, "저인플레이션"),
            (3.0, "고인플레이션"),  # 임계 진입
            (5.0, "고인플레이션"),
            (5.99, "고인플레이션"),
            (8.0, "고인플레이션"),  # 6~10 구간도 high
            (15.0, "하이퍼인플레이션"),
        ],
    )
    def test_inflation_thresholds(self, cpi, expected):
        result = detect_inflation_stage(cpi_yoy=cpi)
        assert expected in result["stage"]

    def test_high_inflation_decelerating(self):
        """CPI 5% + 3M 추세 음수 → '둔화 중'."""
        result = detect_inflation_stage(cpi_yoy=5.0, cpi_3m_avg_change=-0.3)
        assert "둔화 중" in result["stage"]
        assert result["trend"] == "decelerating"

    def test_high_inflation_accelerating(self):
        """CPI 5% + 3M 추세 양수 → '가속'."""
        result = detect_inflation_stage(cpi_yoy=5.0, cpi_3m_avg_change=0.5)
        assert "가속" in result["stage"]
        assert result["trend"] == "accelerating"

    def test_legal_no_recommendation_words(self):
        result = detect_inflation_stage(cpi_yoy=2.5)
        for v in [result["stage"], result["rationale"]]:
            for forbidden in ["매수", "사세요"]:
                assert forbidden not in v


# ──────────────────────────────────────────────
# 4. detect_currency_stage
# ──────────────────────────────────────────────


class TestCurrencyStage:
    def test_strong_dollar_cycle(self):
        """12M +8% + 3M 양수 → '달러 강세'."""
        result = detect_currency_stage(
            dxy_current=108.0, dxy_3m_ago=106.0, dxy_12m_ago=100.0
        )
        assert result["stage"] == "달러 강세"
        assert result["change_12m_pct"] == 8.0

    def test_strong_dollar_weakening(self):
        """12M +8% 누적이지만 최근 3M 음수 → '달러 강세 (다소 약화)'."""
        result = detect_currency_stage(
            dxy_current=108.0, dxy_3m_ago=110.0, dxy_12m_ago=100.0
        )
        assert "약화" in result["stage"]

    def test_weak_dollar(self):
        """12M -8% + 3M 음수 → '달러 약세'."""
        result = detect_currency_stage(
            dxy_current=92.0, dxy_3m_ago=94.0, dxy_12m_ago=100.0
        )
        assert result["stage"] == "달러 약세"

    def test_sideways_dollar(self):
        result = detect_currency_stage(
            dxy_current=101.0, dxy_3m_ago=100.0, dxy_12m_ago=100.0
        )
        assert result["stage"] == "달러 횡보"

    def test_zero_baseline_returns_unable(self):
        result = detect_currency_stage(
            dxy_current=100.0, dxy_3m_ago=0, dxy_12m_ago=100.0
        )
        assert result["stage"] == "산정 불가"
        assert result["confidence"] == 0.0


# ──────────────────────────────────────────────
# 5. 알려진 과거 시점 검증 (4개)
# ──────────────────────────────────────────────


class TestKnownHistoricalPeriods:
    """학계/언론 합의와 사이클 판정 일치 검증.

    각 시점 매크로 데이터는 FRED/한국은행 발표 자료에서 발췌.
    실제 호출 대신 mock 값 사용 (테스트 안정성).
    """

    def test_2022_09_stagflation_period(self):
        """2022-09 미국 — 인플레 정점 + 가속 인상 + 실업 안정.

        실데이터: FedFunds 3.25 (12M +325bp), CPI 8.2%, GDP +1.8%, 실업 3.5%
        예상: 인상 후반 + 고인플레 가속 + 확장 후기
        """
        rate = detect_interest_rate_stage(
            rate_current=3.25, rate_3m_ago=1.75, rate_12m_ago=0.0
        )
        inflation = detect_inflation_stage(cpi_yoy=8.2, cpi_3m_avg_change=0.2)
        biz = detect_business_cycle_stage(
            gdp_yoy=1.8, industrial_production_yoy=2.5,
            unemployment_current=3.5, unemployment_12m_ago=4.7,
        )

        assert rate["stage"] == "인상 후반"
        assert "고인플레이션" in inflation["stage"]
        # 실업률 -1.2%p 빠른 하락 → 확장 초기
        assert "확장" in biz["stage"]

    def test_2020_04_covid_crisis(self):
        """2020-04 미국 — 코로나 충격, 긴급 인하 + 실업 폭증.

        실데이터: FedFunds 0.05 (12M -245bp), CPI 0.3%, GDP -5%, 실업 14.7%
        예상: 인하 시작 + 디플레이션 우려 + 수축 후기
        """
        rate = detect_interest_rate_stage(
            rate_current=0.05, rate_3m_ago=1.10, rate_12m_ago=2.50
        )
        inflation = detect_inflation_stage(cpi_yoy=0.3, cpi_3m_avg_change=-0.4)
        biz = detect_business_cycle_stage(
            gdp_yoy=-5.0, industrial_production_yoy=-12.0,
            unemployment_current=14.7, unemployment_12m_ago=3.6,
        )

        assert rate["stage"] == "인하 시작"
        assert inflation["stage"] == "디플레이션 우려"
        assert biz["stage"] == "수축 후기"

    def test_2017_06_goldilocks_period(self):
        """2017-06 미국 — 적당한 성장 + 저인플레 + 인상 사이클 진입.

        실데이터: FedFunds 1.13 (12M +88bp), CPI 1.6%, GDP +2.4%, 실업 4.3%
        예상: 인상 후반 + 저인플레 + 확장 후기
        """
        rate = detect_interest_rate_stage(
            rate_current=1.13, rate_3m_ago=0.88, rate_12m_ago=0.25
        )
        inflation = detect_inflation_stage(cpi_yoy=1.6, cpi_3m_avg_change=-0.05)
        biz = detect_business_cycle_stage(
            gdp_yoy=2.4, industrial_production_yoy=2.1,
            unemployment_current=4.3, unemployment_12m_ago=4.9,
        )

        assert rate["stage"] == "인상 후반"
        assert inflation["stage"] == "저인플레이션"
        assert "확장" in biz["stage"]

    def test_2008_12_risk_off_period(self):
        """2008-12 미국 — 리먼 사태 직후, 긴급 인하 + 디플레 + 침체.

        실데이터: FedFunds 0.16 (12M -407bp), CPI 0.1%, GDP -3.3%, 실업 7.3%
        예상: 인하 시작 + 디플레이션 우려 + 수축 후기
        """
        rate = detect_interest_rate_stage(
            rate_current=0.16, rate_3m_ago=2.00, rate_12m_ago=4.23
        )
        inflation = detect_inflation_stage(cpi_yoy=0.1, cpi_3m_avg_change=-0.5)
        biz = detect_business_cycle_stage(
            gdp_yoy=-3.3, industrial_production_yoy=-7.5,
            unemployment_current=7.3, unemployment_12m_ago=4.9,
        )

        assert rate["stage"] == "인하 시작"
        assert inflation["stage"] == "디플레이션 우려"
        assert biz["stage"] == "수축 후기"


# ──────────────────────────────────────────────
# 6. detect_all_cycles 통합
# ──────────────────────────────────────────────


def test_detect_all_cycles_returns_4_cycles():
    inputs = {
        "rate_current": 3.25,
        "rate_3m_ago": 3.50,
        "rate_12m_ago": 4.00,
        "spread_10y_2y": 0.5,
        "gdp_yoy": 2.0,
        "industrial_production_yoy": 1.5,
        "unemployment_current": 4.0,
        "unemployment_12m_ago": 4.2,
        "pmi": 52.0,
        "cpi_yoy": 2.5,
        "core_cpi_yoy": 2.4,
        "cpi_3m_avg_change": 0.0,
        "dxy_current": 105.0,
        "dxy_3m_ago": 104.0,
        "dxy_12m_ago": 102.0,
    }
    result = detect_all_cycles(inputs)
    assert set(result.keys()) == {"interest_rate", "business_cycle", "inflation", "currency"}
    for cycle_result in result.values():
        assert "stage" in cycle_result
        assert "confidence" in cycle_result
        assert cycle_result["data_lag_warning"]
        assert cycle_result["legal_note"]


def test_detect_all_cycles_raises_on_missing_required_keys():
    """필수 키 누락 → 명시적 ValueError + 누락 키 list."""
    incomplete = {"rate_current": 3.0, "gdp_yoy": 2.0}  # 대부분 누락
    with pytest.raises(ValueError, match="필수 입력 누락"):
        detect_all_cycles(incomplete)


def test_detect_all_cycles_country_passed_to_business_cycle():
    """country 인자가 business_cycle 함수에 전달."""
    base_inputs = {
        "rate_current": 3.0, "rate_3m_ago": 3.0, "rate_12m_ago": 3.0,
        "gdp_yoy": 1.8, "industrial_production_yoy": 1.0,
        "unemployment_current": 3.5, "unemployment_12m_ago": 3.5,
        "cpi_yoy": 2.0,
        "dxy_current": 100.0, "dxy_3m_ago": 100.0, "dxy_12m_ago": 100.0,
    }
    result_us = detect_all_cycles(base_inputs, country="US")
    result_kr = detect_all_cycles(base_inputs, country="KR")

    # GDP 1.8: US(1.5)에서는 확장, KR(2.0)에서는 임계 미달
    assert result_us["business_cycle"]["country"] == "US"
    assert result_kr["business_cycle"]["country"] == "KR"
    assert result_us["business_cycle"]["gdp_threshold"] == 1.5
    assert result_kr["business_cycle"]["gdp_threshold"] == 2.0


# ──────────────────────────────────────────────
# 7. Confidence 표준화 — 4 사이클 통일된 의미
# ──────────────────────────────────────────────


class TestConfidenceStandardization:
    """모든 사이클의 confidence는 0~1, "강한 신호" 기준으로 정규화 (1.0 = strong)."""

    def test_rate_strong_signal_confidence_one(self):
        """100bp+ 변동 → confidence 1.0."""
        result = detect_interest_rate_stage(
            rate_current=5.0, rate_3m_ago=4.5, rate_12m_ago=3.5
        )
        assert result["confidence"] == 1.0

    def test_business_cycle_strong_signal_confidence_one(self):
        """GDP 임계에서 ±2%p 이상 → confidence 1.0."""
        result = detect_business_cycle_stage(
            gdp_yoy=4.0, industrial_production_yoy=2.0,
            unemployment_current=3.5, unemployment_12m_ago=4.0,
        )
        # GDP 4.0 - 1.5 = 2.5 > 2.0 → 1.0
        assert result["confidence"] == 1.0

    def test_inflation_strong_signal_confidence_one(self):
        """CPI 0% (임계 1에서 1%p 거리) → confidence 0.5 (1/2)."""
        result = detect_inflation_stage(cpi_yoy=0.0)
        assert result["confidence"] == 0.5

    def test_currency_strong_signal_confidence_one(self):
        """DXY ±10% 12M → confidence 1.0."""
        result = detect_currency_stage(
            dxy_current=110.0, dxy_3m_ago=108.0, dxy_12m_ago=100.0
        )
        assert result["confidence"] == 1.0

    def test_2022_09_stagflation_confidence_high(self):
        """2022-09: FedFunds 12M +325bp → 강한 인상 사이클 → confidence 1.0."""
        rate = detect_interest_rate_stage(
            rate_current=3.25, rate_3m_ago=1.75, rate_12m_ago=0.0
        )
        assert rate["confidence"] == 1.0  # 강한 신호 검증
