"""4대 매크로 사이클 자동 판정 모듈.

WEEK_B.md Day 3 산출물 — Macro PM 페르소나용 사이클 판정 엔진.

4개 사이클 (각 dict 반환: stage + confidence + rationale + 진단 데이터):
  1. 금리 (interest_rate)   — 인하시작/인하후반/횡보/인상시작/인상후반
  2. 경기 (business_cycle)  — 확장초기/확장후기/수축초기/수축후기/전환기
  3. 인플레 (inflation)     — 디플레이션우려/저인플레/고인플레(둔화)/고인플레(가속)/하이퍼인플레
  4. 통화 (currency)        — 달러강세/달러횡보/달러약세

설계 원칙:
- 모든 함수는 순수 함수 (외부 의존성 X, 입력 → 출력 결정적)
- 입력은 단순 float (FRED/ECOS 호출은 호출자 책임)
- LEGAL: "매수/사세요" 단어 X. 사이클 단계 명사만 (정보 제공 목적)
- 후행성 명시: 응답에 data_lag_warning 포함
- confidence: 0~1 (데이터 변동 폭이 클수록 신뢰도 높음)

⚠️ 매크로 데이터는 후행 발표 (한 달~분기 지연).
   응답에 "최근 발표 데이터 기준" 명시 — Macro PM 페르소나가 그대로 노출.
"""

from __future__ import annotations

from typing import Any, Literal


# ──────────────────────────────────────────────
# 임계값 — 국가별 분리 (US/KR 잠재성장률·정책 관행 차이 반영)
# ──────────────────────────────────────────────

# 금리 사이클 — 12개월 누적 변화 (%p) — Fed/BOK 모두 25bp 단위 변경, 50bp 임계는 의미 있음
RATE_HIKE_THRESHOLD_12M = 0.5
RATE_CUT_THRESHOLD_12M = -0.5

# 경기 사이클 — GDP YoY 임계 (%) — 국가별 잠재성장률
# 미국: ~1.8%, 한국: ~2.0% (한국은 잠재성장률 둔화 추세 반영)
GDP_EXPANSION_THRESHOLD: dict[str, float] = {
    "US": 1.5,
    "KR": 2.0,
}
UNEMPLOYMENT_FAST_DROP = -0.5    # 실업률 12M 변화 -0.5%p+ = 빠른 회복
UNEMPLOYMENT_FAST_RISE = 0.5     # +0.5%p+ = 빠른 악화

# 인플레 사이클 — CPI YoY 임계 (%) — Fed 2% / BOK 2% 목표 동일, 같은 임계 사용
INFLATION_DEFLATION_RISK = 1.0
INFLATION_LOW_HIGH_BORDER = 3.0
INFLATION_HYPER_BORDER = 6.0

# 통화 사이클 — DXY 12M 변화 (%)
CURRENCY_STRONG_THRESHOLD = 5.0
CURRENCY_WEAK_THRESHOLD = -5.0


# Country 타입 별칭
Country = Literal["US", "KR"]


# ──────────────────────────────────────────────
# Confidence 표준화
# ──────────────────────────────────────────────
# 모든 사이클의 confidence는 0~1, 의미 통일:
#   1.0 = 강한 신호 (임계의 2배 이상 변동)
#   0.5 = 중간 신호 (임계 부근)
#   0.0 = 약한 신호 (변동 거의 없음)
# 분모는 "강한 신호" 기준값 (그 이상이면 1.0 cap).


def _normalize_confidence(observed: float, strong_signal_threshold: float) -> float:
    """관측값 절대값 / 강한신호 기준 → 0~1 정규화."""
    if strong_signal_threshold <= 0:
        return 0.0
    return round(min(abs(observed) / strong_signal_threshold, 1.0), 2)


# 사이클별 "강한 신호" 기준 (1.0 confidence가 되는 변동 폭)
STRONG_RATE_CHANGE_12M = 1.0          # 100bp 이상 = 매우 강한 사이클
STRONG_GDP_DEVIATION = 2.0            # GDP가 임계에서 ±2%p 이상 벗어남 = 매우 명확
STRONG_INFLATION_DEVIATION = 2.0      # CPI가 가장 가까운 임계에서 2%p 이상 = 매우 명확
STRONG_CURRENCY_CHANGE_12M = 10.0     # DXY 12M ±10% 이상 = 매우 강한 사이클


# 모든 응답에 첨부되는 공통 메타
DATA_LAG_WARNING = (
    "매크로 지표는 후행 발표 (월~분기 지연). 최근 발표 데이터 기준 판정이며, "
    "현재 시점 실제 상태와 다를 수 있음."
)
LEGAL_NOTE = "사이클 판정은 정보 제공 목적이며 매매 신호가 아님."


# ──────────────────────────────────────────────
# 1. 금리 사이클 판정
# ──────────────────────────────────────────────


def detect_interest_rate_stage(
    rate_current: float,
    rate_3m_ago: float,
    rate_12m_ago: float,
    spread_10y_2y: float | None = None,
) -> dict[str, Any]:
    """금리 사이클 단계 판정.

    Args:
        rate_current: 현재 정책금리 (%) — Fed Funds 또는 한국 기준금리
        rate_3m_ago: 3개월 전 정책금리
        rate_12m_ago: 12개월 전 정책금리
        spread_10y_2y: 10Y-2Y 장단기 스프레드 (%, 음수 = 역전, optional)

    Returns:
        {
            "stage": "인상 시작" | "인상 후반" | "인하 시작" | "인하 후반" | "횡보",
            "confidence": 0~1,
            "rationale": str,
            "rate_change_3m": float,
            "rate_change_12m": float,
            "yield_curve_signal": "정상" | "역전" | None,
            "data_lag_warning": str,
            "legal_note": str,
        }
    """
    rate_change_3m = round(rate_current - rate_3m_ago, 4)
    rate_change_12m = round(rate_current - rate_12m_ago, 4)

    # 인상 사이클 (12M 변화 > +0.5)
    if rate_change_12m > RATE_HIKE_THRESHOLD_12M:
        if rate_change_3m > 0.0:
            stage = "인상 후반"
            rationale = (
                f"12개월 +{rate_change_12m:.2f}%p 누적 인상 + "
                f"최근 3개월 +{rate_change_3m:.2f}%p 인상 지속 → 인상 사이클 진행 중"
            )
        elif rate_change_3m < 0.0:
            stage = "인상 시작"  # 12M는 인상이지만 최근 3M 인하 시작 → 변곡점
            rationale = (
                f"12개월 +{rate_change_12m:.2f}%p 인상이지만 최근 3개월 {rate_change_3m:.2f}%p 인하 → "
                f"인상 사이클 종료 + 인하 사이클 시작 가능성"
            )
        else:
            stage = "인상 후반"
            rationale = (
                f"12개월 +{rate_change_12m:.2f}%p 인상 후 3개월 횡보 → "
                f"인상 사이클 후반 (정점 부근)"
            )

    # 인하 사이클 (12M 변화 < -0.5)
    elif rate_change_12m < RATE_CUT_THRESHOLD_12M:
        if rate_change_3m < 0.0:
            stage = "인하 시작"
            rationale = (
                f"12개월 {rate_change_12m:.2f}%p 인하 + 최근 3개월 {rate_change_3m:.2f}%p 인하 진행 중"
            )
        elif rate_change_3m > 0.0:
            stage = "인하 후반"  # 12M 인하지만 최근 반등 → 사이클 종료
            rationale = (
                f"12개월 {rate_change_12m:.2f}%p 인하 후 최근 3개월 +{rate_change_3m:.2f}%p 반등 → "
                f"인하 사이클 종료 가능성"
            )
        else:
            stage = "인하 후반"
            rationale = (
                f"12개월 {rate_change_12m:.2f}%p 인하 후 3개월 횡보 → 인하 사이클 후반"
            )

    # 횡보
    else:
        stage = "횡보"
        rationale = (
            f"12개월 변동 {rate_change_12m:+.2f}%p (±{RATE_HIKE_THRESHOLD_12M}%p 범위 내) → 정책금리 동결 구간"
        )

    # confidence 표준화: 100bp(STRONG_RATE_CHANGE_12M) 이상 변동 = 1.0
    confidence = _normalize_confidence(rate_change_12m, STRONG_RATE_CHANGE_12M)

    yield_signal: str | None = None
    if spread_10y_2y is not None:
        yield_signal = "정상" if spread_10y_2y > 0 else "역전"

    return {
        "stage": stage,
        "confidence": confidence,
        "rationale": rationale,
        "rate_change_3m": rate_change_3m,
        "rate_change_12m": rate_change_12m,
        "yield_curve_signal": yield_signal,
        "data_lag_warning": DATA_LAG_WARNING,
        "legal_note": LEGAL_NOTE,
    }


# ──────────────────────────────────────────────
# 2. 경기 사이클 판정
# ──────────────────────────────────────────────


def detect_business_cycle_stage(
    gdp_yoy: float,
    industrial_production_yoy: float,
    unemployment_current: float,
    unemployment_12m_ago: float,
    pmi: float | None = None,
    country: Country = "US",
) -> dict[str, Any]:
    """경기 사이클 단계 판정.

    Args:
        gdp_yoy: 실질 GDP 전년동기대비 (%)
        industrial_production_yoy: 산업생산 전년동기대비 (%)
        unemployment_current: 현재 실업률 (%)
        unemployment_12m_ago: 12개월 전 실업률
        pmi: ISM 제조업 PMI (option, 50 기준)
        country: "US" | "KR" — 잠재성장률 임계 분리 (US 1.5%, KR 2.0%)

    Returns:
        stage: 확장 초기 / 확장 후기 / 수축 초기 / 수축 후기 / 전환기 (불확실)

    분기 logic:
      - 확장: GDP > 임계 AND IP > 0 (둘 다 양수)
      - 수축: GDP < 임계 AND IP < 0 (둘 다 음수)
      - 전환기: GDP↔IP 모순 또는 임계 부근 (GDP > 임계 + IP < 0 등)
    """
    threshold = GDP_EXPANSION_THRESHOLD.get(country, GDP_EXPANSION_THRESHOLD["US"])
    unemployment_change = round(unemployment_current - unemployment_12m_ago, 2)

    gdp_above = gdp_yoy > threshold
    gdp_below = gdp_yoy < threshold
    ip_positive = industrial_production_yoy > 0
    ip_negative = industrial_production_yoy < 0

    # 확장 (GDP + IP 둘 다 양수)
    if gdp_above and ip_positive:
        if unemployment_change < UNEMPLOYMENT_FAST_DROP:
            stage = "확장 초기"
            rationale = (
                f"[{country}] GDP +{gdp_yoy:.1f}% (>{threshold}%) + "
                f"산업생산 +{industrial_production_yoy:.1f}% + "
                f"실업률 {unemployment_change:+.2f}%p 빠른 하락 → 강한 회복기"
            )
        else:
            stage = "확장 후기"
            rationale = (
                f"[{country}] GDP +{gdp_yoy:.1f}% 양호 + 산업생산 +{industrial_production_yoy:.1f}%, "
                f"실업률 안정 ({unemployment_change:+.2f}%p) → 확장 사이클 성숙"
            )

    # 수축 (GDP + IP 둘 다 음수/임계 미달)
    elif gdp_below and ip_negative:
        if unemployment_change > UNEMPLOYMENT_FAST_RISE:
            stage = "수축 후기"
            rationale = (
                f"[{country}] GDP {gdp_yoy:+.1f}% (<{threshold}%) + "
                f"산업생산 {industrial_production_yoy:+.1f}% + "
                f"실업률 +{unemployment_change:.2f}%p 빠른 상승 → 본격 침체"
            )
        else:
            stage = "수축 초기"
            rationale = (
                f"[{country}] GDP {gdp_yoy:+.1f}% 둔화 + 산업생산 {industrial_production_yoy:+.1f}%, "
                f"실업률 변화 {unemployment_change:+.2f}%p → 수축 시작 단계"
            )

    # 모순/전환 (GDP ↔ IP 신호 충돌, 또는 임계 부근)
    else:
        stage = "전환기 (불확실)"
        rationale = (
            f"[{country}] GDP {gdp_yoy:+.1f}% (임계 {threshold}%) + "
            f"산업생산 {industrial_production_yoy:+.1f}% — 신호 모순/경계 부근, 추가 데이터 필요"
        )

    # confidence 표준화: GDP가 임계에서 ±2%p 이상 벗어나면 1.0 (강한 신호)
    gdp_distance = abs(gdp_yoy - threshold)
    confidence = _normalize_confidence(gdp_distance, STRONG_GDP_DEVIATION)

    return {
        "stage": stage,
        "confidence": confidence,
        "rationale": rationale,
        "country": country,
        "gdp_yoy": gdp_yoy,
        "gdp_threshold": threshold,
        "industrial_production_yoy": industrial_production_yoy,
        "unemployment_current": unemployment_current,
        "unemployment_change_12m": unemployment_change,
        "pmi": pmi,
        "pmi_signal": _pmi_signal(pmi),
        "data_lag_warning": DATA_LAG_WARNING,
        "legal_note": LEGAL_NOTE,
    }


def _pmi_signal(pmi: float | None) -> str | None:
    if pmi is None:
        return None
    if pmi >= 50:
        return "확장 (PMI ≥ 50)"
    return "수축 (PMI < 50)"


# ──────────────────────────────────────────────
# 3. 인플레이션 사이클 판정
# ──────────────────────────────────────────────


def detect_inflation_stage(
    cpi_yoy: float,
    core_cpi_yoy: float | None = None,
    cpi_3m_avg_change: float = 0.0,
) -> dict[str, Any]:
    """인플레이션 사이클 단계 판정.

    Args:
        cpi_yoy: CPI 전년동기대비 (%)
        core_cpi_yoy: Core CPI YoY (option)
        cpi_3m_avg_change: 3개월 이동평균 변화 (%, 양수=가속 / 음수=둔화)

    Returns:
        stage: 디플레이션 우려/저인플레/고인플레(둔화 중)/고인플레(가속)/하이퍼인플레
    """
    if cpi_yoy < INFLATION_DEFLATION_RISK:
        stage = "디플레이션 우려"
        rationale = (
            f"CPI {cpi_yoy:+.1f}% < {INFLATION_DEFLATION_RISK}% → 수요 부진/물가 하락 위험"
        )
    elif cpi_yoy < INFLATION_LOW_HIGH_BORDER:
        stage = "저인플레이션"
        rationale = (
            f"CPI {cpi_yoy:+.1f}% — 중앙은행 목표(2%) 부근 정상 범위"
        )
    elif cpi_yoy < INFLATION_HYPER_BORDER:
        if cpi_3m_avg_change < 0:
            stage = "고인플레이션 (둔화 중)"
            rationale = (
                f"CPI {cpi_yoy:+.1f}% 높음 + 3개월 추세 {cpi_3m_avg_change:+.2f}%p 둔화 → "
                f"피크 통과 후 안정화"
            )
        else:
            stage = "고인플레이션 (가속)"
            rationale = (
                f"CPI {cpi_yoy:+.1f}% 높음 + 3개월 추세 +{cpi_3m_avg_change:.2f}%p 가속 → "
                f"인플레 정점 미도달"
            )
    elif cpi_yoy < 10.0:
        stage = "고인플레이션 (가속)" if cpi_3m_avg_change >= 0 else "고인플레이션 (둔화 중)"
        rationale = (
            f"CPI {cpi_yoy:+.1f}% 매우 높음 (>{INFLATION_HYPER_BORDER}%) — "
            f"중앙은행 적극 대응 필요 구간"
        )
    else:
        stage = "하이퍼인플레이션"
        rationale = f"CPI {cpi_yoy:+.1f}% 위기 수준 (>10%)"

    trend = "accelerating" if cpi_3m_avg_change > 0 else (
        "decelerating" if cpi_3m_avg_change < 0 else "stable"
    )

    # confidence 표준화: 가장 가까운 임계에서 ±2%p 이상 벗어나면 1.0
    distance = min(
        abs(cpi_yoy - INFLATION_DEFLATION_RISK),
        abs(cpi_yoy - INFLATION_LOW_HIGH_BORDER),
        abs(cpi_yoy - INFLATION_HYPER_BORDER),
    )
    confidence = _normalize_confidence(distance, STRONG_INFLATION_DEVIATION)

    return {
        "stage": stage,
        "confidence": confidence,
        "rationale": rationale,
        "cpi_yoy": cpi_yoy,
        "core_cpi_yoy": core_cpi_yoy,
        "cpi_3m_avg_change": cpi_3m_avg_change,
        "trend": trend,
        "data_lag_warning": DATA_LAG_WARNING,
        "legal_note": LEGAL_NOTE,
    }


# ──────────────────────────────────────────────
# 4. 통화 사이클 판정
# ──────────────────────────────────────────────


def detect_currency_stage(
    dxy_current: float,
    dxy_3m_ago: float,
    dxy_12m_ago: float,
) -> dict[str, Any]:
    """달러 강세/약세 판정 (DXY 광범위 인덱스).

    Args:
        dxy_current: 현재 DXY 값
        dxy_3m_ago: 3개월 전 DXY
        dxy_12m_ago: 12개월 전 DXY

    Returns:
        stage: 달러 강세 (다소 약화)/달러 강세/달러 횡보/달러 약세 (다소 강화)/달러 약세
    """
    if dxy_3m_ago == 0 or dxy_12m_ago == 0:
        return {
            "stage": "산정 불가",
            "confidence": 0.0,
            "rationale": "기준 시점 DXY 0 — 데이터 없음",
            "dxy_current": dxy_current,
            "data_lag_warning": DATA_LAG_WARNING,
            "legal_note": LEGAL_NOTE,
        }

    change_3m = round((dxy_current - dxy_3m_ago) / dxy_3m_ago * 100, 2)
    change_12m = round((dxy_current - dxy_12m_ago) / dxy_12m_ago * 100, 2)

    if change_12m > CURRENCY_STRONG_THRESHOLD:
        if change_3m > 0:
            stage = "달러 강세"
            rationale = f"12M +{change_12m}% + 3M +{change_3m}% — 달러 강세 지속"
        else:
            stage = "달러 강세 (다소 약화)"
            rationale = f"12M +{change_12m}% 누적 강세이나 최근 3M {change_3m}% 약화"
    elif change_12m < CURRENCY_WEAK_THRESHOLD:
        if change_3m < 0:
            stage = "달러 약세"
            rationale = f"12M {change_12m}% + 3M {change_3m}% — 달러 약세 지속"
        else:
            stage = "달러 약세 (다소 강화)"
            rationale = f"12M {change_12m}% 누적 약세이나 최근 3M +{change_3m}% 반등"
    else:
        stage = "달러 횡보"
        rationale = f"12M {change_12m:+}% (±{CURRENCY_STRONG_THRESHOLD}% 범위) — 달러 변동 작음"

    # confidence 표준화: ±10% 이상 12M 변화 = 1.0
    confidence = _normalize_confidence(change_12m, STRONG_CURRENCY_CHANGE_12M)

    return {
        "stage": stage,
        "confidence": confidence,
        "rationale": rationale,
        "dxy_current": dxy_current,
        "change_3m_pct": change_3m,
        "change_12m_pct": change_12m,
        "data_lag_warning": DATA_LAG_WARNING,
        "legal_note": LEGAL_NOTE,
    }


# ──────────────────────────────────────────────
# 통합 진단 헬퍼 (4 사이클 한 번에)
# ──────────────────────────────────────────────


REQUIRED_INPUTS = {
    "rate_current", "rate_3m_ago", "rate_12m_ago",
    "gdp_yoy", "industrial_production_yoy",
    "unemployment_current", "unemployment_12m_ago",
    "cpi_yoy",
    "dxy_current", "dxy_3m_ago", "dxy_12m_ago",
}


def detect_all_cycles(
    inputs: dict[str, Any], country: Country = "US"
) -> dict[str, dict[str, Any]]:
    """4 사이클을 한 번에 판정.

    Args:
        inputs: 필수 키 (REQUIRED_INPUTS) + 선택 키 (spread_10y_2y, pmi, core_cpi_yoy, cpi_3m_avg_change)
        country: "US" | "KR" — 경기 사이클 임계 분리

    Raises:
        ValueError: REQUIRED_INPUTS 키 누락 시 (어느 키 빠졌는지 명시)

    Returns:
        {"interest_rate": {...}, "business_cycle": {...}, "inflation": {...}, "currency": {...}}
    """
    missing = REQUIRED_INPUTS - set(inputs.keys())
    if missing:
        raise ValueError(
            f"detect_all_cycles 필수 입력 누락: {sorted(missing)} "
            f"(필수 {len(REQUIRED_INPUTS)}개 중 {len(missing)}개 빠짐)"
        )

    return {
        "interest_rate": detect_interest_rate_stage(
            inputs["rate_current"],
            inputs["rate_3m_ago"],
            inputs["rate_12m_ago"],
            inputs.get("spread_10y_2y"),
        ),
        "business_cycle": detect_business_cycle_stage(
            inputs["gdp_yoy"],
            inputs["industrial_production_yoy"],
            inputs["unemployment_current"],
            inputs["unemployment_12m_ago"],
            inputs.get("pmi"),
            country=country,
        ),
        "inflation": detect_inflation_stage(
            inputs["cpi_yoy"],
            inputs.get("core_cpi_yoy"),
            inputs.get("cpi_3m_avg_change", 0.0),
        ),
        "currency": detect_currency_stage(
            inputs["dxy_current"],
            inputs["dxy_3m_ago"],
            inputs["dxy_12m_ago"],
        ),
    }
