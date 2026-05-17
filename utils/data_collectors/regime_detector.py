"""6대 매크로 국면 매핑 + 매크로 캘린더 모듈.

WEEK_B.md Day 4 산출물 — Macro PM 페르소나용 국면 종합 판정.

4개 사이클 (cycle_detector.py 결과) → 6 국면 자동 매핑:
  - Goldilocks    : 저인플레 + 확장 후기 + 인하 후반/횡보 + 달러 약세/횡보
  - Reflation     : 저~고인플레둔화 + 확장 초기 + 인하 시작 + 달러 약세
  - Stagflation   : 고인플레 + 수축 + 인상 후반 + 달러 강세
  - Risk-Off      : 저인플레 + 수축 후기 + 인상 후반 + 달러 강세
  - Recovery      : 저인플레 + 수축후기/확장초기 + 인하 시작 + 달러 약세
  - Late Cycle    : 고인플레 + 확장 후기 + 인상 + 달러 강세

⚠️ 매칭 모호 시 (점수 < 2 또는 동률):
  - "Transition (전환기)" 라벨
  - confidence < 0.5 명시
  - secondary 국면 함께 표시

⚠️ 한국 vs 미국 분리:
  - 미국 매크로 우선 (Macro PM 글로벌)
  - 한국은 Korean Specialist에서 별도 판정 (별도 호출)

⚠️ LEGAL: 국면 라벨은 정보 제공 목적. "Goldilocks → 매수" 같은 해석 X.
   페르소나 시스템 프롬프트에 "국면 ≠ 매매 신호" 명시 필요 (Week D).
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


CALENDAR_FILE = Path(__file__).resolve().parents[2] / "data" / "macro_calendar.json"


# ──────────────────────────────────────────────
# 6 국면 정의 (spec macro.md §5.1)
# ──────────────────────────────────────────────
# 각 국면당 4 사이클 stage 후보 list. 매칭 점수 1점/사이클, 4점 만점.

REGIME_PATTERNS: dict[str, dict[str, list[str]]] = {
    "Goldilocks": {
        # 적당 성장 + 저인플레 + 인상 종료/횡보 + 달러 약화
        "interest_rate": ["인하 후반", "횡보"],
        "business_cycle": ["확장 후기"],
        "inflation": ["저인플레이션"],
        "currency": ["달러 약세", "달러 약세 (다소 강화)", "달러 횡보"],
    },
    "Reflation": {
        # 회복 진입 (디플레 → 정상) + 인플레 둔화 진행 + 인하 진행 + 달러 약세
        # ⚠️ Recovery와 차별화: business_cycle "확장 초기"만 (Recovery는 "수축 후기"만)
        "interest_rate": ["인하 시작"],
        "business_cycle": ["확장 초기"],
        "inflation": ["저인플레이션", "고인플레이션 (둔화 중)"],
        "currency": ["달러 약세", "달러 약세 (다소 강화)"],
    },
    "Stagflation": {
        # 인플레 가속 + 경기 둔화 + 정책 매파 + 달러 강세
        "interest_rate": ["인상 후반"],
        "business_cycle": ["수축 초기", "수축 후기"],
        "inflation": ["고인플레이션 (가속)", "고인플레이션 (둔화 중)", "하이퍼인플레이션"],
        "currency": ["달러 강세", "달러 강세 (다소 약화)"],
    },
    "Risk-Off": {
        # 위기 + 디플레/저인플레 + 매파 정점 + 달러 강세 (안전자산)
        "interest_rate": ["인상 후반"],
        "business_cycle": ["수축 후기"],
        "inflation": ["저인플레이션", "디플레이션 우려"],
        "currency": ["달러 강세", "달러 강세 (다소 약화)"],
    },
    "Recovery": {
        # 침체 직후 회복 시작 (아직 수축 단계) + 디플레/저인플레 + 인하 + 달러 약세
        # ⚠️ Reflation과 차별화: business_cycle "수축 후기"만 (Reflation은 "확장 초기"만)
        # 학계 정의: Recovery = 침체에서 빠져나오는 시점, Reflation = 이미 확장 진입
        "interest_rate": ["인하 시작"],
        "business_cycle": ["수축 후기"],
        "inflation": ["저인플레이션", "디플레이션 우려"],
        "currency": ["달러 약세", "달러 약세 (다소 강화)"],
    },
    "Late Cycle": {
        # 인플레 가속 + 확장 마지막 + 정책 매파 + 달러 강세
        "interest_rate": ["인상 시작", "인상 후반"],
        "business_cycle": ["확장 후기"],
        "inflation": ["고인플레이션 (가속)", "고인플레이션 (둔화 중)"],
        "currency": ["달러 강세", "달러 강세 (다소 약화)"],
    },
}

REGIME_NAMES_KR: dict[str, str] = {
    "Goldilocks": "골디락스 (적정 성장 + 저인플레)",
    "Reflation": "리플레이션 (회복 초기)",
    "Stagflation": "스태그플레이션 (스태그 + 인플레)",
    "Risk-Off": "리스크 오프 (위기/방어)",
    "Recovery": "리커버리 (회복 진행)",
    "Late Cycle": "레이트 사이클 (확장 후반)",
}

# 매핑 모호 임계
# 4점 만점에서 50% 매칭 (2점)은 너무 약한 신호 → 3점부터 primary로 분류 (75% 이상 매칭).
# spec macro.md §5.2 "점수 < 2 → 전환기"보다 강화 — 페르소나 출력 신뢰도 향상.
MIN_PRIMARY_SCORE = 3          # 최고 점수 < 3 = 전환기 (75% 미만 매칭)
TRANSITION_GAP_THRESHOLD = 1   # 1위와 2위 점수 차 ≤ 임계 = transition_to 명시
TRANSITION_MIN_SECONDARY = 2   # secondary 점수 ≥ 임계여야 transition_to 노출


LEGAL_NOTE = "국면 판정은 정보 제공 목적. 매매 신호로 해석 X."


# ──────────────────────────────────────────────
# 국면 판정 (4 사이클 stage → 6 국면)
# ──────────────────────────────────────────────


def detect_macro_regime(
    interest_rate_stage: str,
    business_cycle_stage: str,
    inflation_stage: str,
    currency_stage: str,
) -> dict[str, Any]:
    """4 사이클 stage → 6 국면 매핑.

    Args:
        interest_rate_stage: cycle_detector.detect_interest_rate_stage["stage"]
        business_cycle_stage: 동
        inflation_stage: 동
        currency_stage: 동

    Returns:
        {
            "regime": "Late Cycle" | ... | "Transition",
            "regime_kr": "레이트 사이클 (...)" | ...,
            "regime_score": 0~4,
            "regime_confidence": 0~1.0 (score/4),
            "transition_to": "Stagflation" | None,
            "transition_kr": "..." | None,
            "all_scores": {"Goldilocks": 1, ...},
            "matched_axes": {regime: [matched_axes...]},
            "legal_note": str,
        }
    """
    matches: dict[str, int] = {}
    matched_axes: dict[str, list[str]] = {}

    inputs = {
        "interest_rate": interest_rate_stage,
        "business_cycle": business_cycle_stage,
        "inflation": inflation_stage,
        "currency": currency_stage,
    }

    for regime, criteria in REGIME_PATTERNS.items():
        score = 0
        axes: list[str] = []
        for axis, accepted_stages in criteria.items():
            if inputs[axis] in accepted_stages:
                score += 1
                axes.append(axis)
        matches[regime] = score
        matched_axes[regime] = axes

    # 점수 내림차순 정렬 (동률 시 사전순 — 결정적)
    sorted_matches = sorted(matches.items(), key=lambda x: (-x[1], x[0]))
    primary_name, primary_score = sorted_matches[0]
    secondary_name, secondary_score = (
        sorted_matches[1] if len(sorted_matches) > 1 else (None, 0)
    )

    # primary 점수가 임계 미만 → 전환기
    if primary_score < MIN_PRIMARY_SCORE:
        return {
            "regime": "Transition",
            "regime_kr": "전환기 (4 사이클 매칭 모호)",
            "regime_score": primary_score,
            "regime_confidence": round(primary_score / 4.0, 2),
            "transition_to": None,
            "transition_kr": None,
            "all_scores": matches,
            "matched_axes": matched_axes,
            "legal_note": LEGAL_NOTE,
            "rationale": (
                f"최고 점수 {primary_name}={primary_score}/4 — "
                f"{MIN_PRIMARY_SCORE}점 미만이라 명확한 국면 단정 불가"
            ),
        }

    # primary와 secondary 점수 차가 작으면 transition_to 명시
    transition_to: str | None = None
    transition_kr: str | None = None
    if (
        secondary_name is not None
        and secondary_score >= TRANSITION_MIN_SECONDARY
        and (primary_score - secondary_score) <= TRANSITION_GAP_THRESHOLD
    ):
        transition_to = secondary_name
        transition_kr = REGIME_NAMES_KR.get(secondary_name)

    return {
        "regime": primary_name,
        "regime_kr": REGIME_NAMES_KR.get(primary_name, primary_name),
        "regime_score": primary_score,
        "regime_confidence": round(primary_score / 4.0, 2),
        "transition_to": transition_to,
        "transition_kr": transition_kr,
        "all_scores": matches,
        "matched_axes": matched_axes,
        "legal_note": LEGAL_NOTE,
        "rationale": (
            f"{primary_name} {primary_score}/4 매칭 ({', '.join(matched_axes[primary_name])})"
            + (
                f" | 전환 가능: {transition_to} ({secondary_score}/4)"
                if transition_to
                else ""
            )
        ),
    }


REQUIRED_CYCLE_KEYS = {"interest_rate", "business_cycle", "inflation", "currency"}


def detect_regime_from_cycles(
    cycles: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """cycle_detector.detect_all_cycles() 결과를 직접 받아서 국면 판정.

    Args:
        cycles: {"interest_rate": {...}, "business_cycle": {...}, "inflation": {...}, "currency": {...}}
                각 dict에 "stage" 키 필수.

    Raises:
        ValueError: cycles에 4 사이클 키 누락 시 또는 "stage" 서브키 누락 시.
                    cycle_detector.detect_all_cycles와 동일한 예외 타입으로 일관성.
    """
    missing_top = REQUIRED_CYCLE_KEYS - set(cycles.keys())
    if missing_top:
        raise ValueError(
            f"detect_regime_from_cycles 필수 사이클 키 누락: {sorted(missing_top)}"
        )
    missing_stage = [k for k in REQUIRED_CYCLE_KEYS if "stage" not in (cycles.get(k) or {})]
    if missing_stage:
        raise ValueError(
            f"cycle 결과에 'stage' 서브키 누락: {missing_stage}"
        )

    return detect_macro_regime(
        interest_rate_stage=cycles["interest_rate"]["stage"],
        business_cycle_stage=cycles["business_cycle"]["stage"],
        inflation_stage=cycles["inflation"]["stage"],
        currency_stage=cycles["currency"]["stage"],
    )


# ──────────────────────────────────────────────
# 매크로 캘린더 조회
# ──────────────────────────────────────────────


_calendar_cache: dict[str, Any] | None = None
_calendar_lock = threading.Lock()


# 파일 I/O 실패 시 빈 결과 (캐시는 X — 다음 호출 시 재시도)
_EMPTY_CALENDAR: dict[str, Any] = {"_meta": {}, "events": []}


def _load_calendar(force_refresh: bool = False) -> dict[str, Any]:
    """매크로 캘린더 JSON 로드 + thread-safe 캐시.

    파일 미존재/파싱 실패 시 빈 결과 반환 (캐시 X) → 다음 호출 시 재시도 가능.
    Cloud Run 멀티 워커 race condition은 워커 분리로 사실상 없음.
    스레드 안전성: double-checked locking.
    """
    global _calendar_cache
    if _calendar_cache is not None and not force_refresh:
        return _calendar_cache

    with _calendar_lock:
        if _calendar_cache is not None and not force_refresh:
            return _calendar_cache

        if not CALENDAR_FILE.exists():
            # 캐시 X → 파일 추후 생성 시 자동 reload
            return _EMPTY_CALENDAR

        try:
            with open(CALENDAR_FILE, encoding="utf-8") as f:
                _calendar_cache = json.load(f)
        except Exception:
            # 파싱 실패도 캐시 X (파일 수정으로 복구 가능)
            return _EMPTY_CALENDAR

        return _calendar_cache


def reset_calendar_cache() -> None:
    """테스트용."""
    global _calendar_cache
    with _calendar_lock:
        _calendar_cache = None


def get_upcoming_macro_events(
    days_ahead: int = 30, today: datetime | None = None
) -> list[dict[str, Any]]:
    """앞으로 N일 안의 매크로 이벤트 (FOMC/BOK/CPI 등).

    Args:
        days_ahead: 향후 며칠
        today: 기준일 (테스트용 주입). None이면 datetime.now()

    Returns:
        [{date, type, country, days_until}, ...] (date 오름차순)
    """
    today = today or datetime.now()
    today_date = today.date()
    end_date = today_date + timedelta(days=days_ahead)

    data = _load_calendar()
    events_raw = data.get("events", []) or []

    upcoming: list[dict[str, Any]] = []
    for event in events_raw:
        try:
            event_date = datetime.fromisoformat(event["date"]).date()
        except (ValueError, KeyError):
            continue
        if today_date <= event_date <= end_date:
            upcoming.append(
                {
                    **event,
                    "days_until": (event_date - today_date).days,
                }
            )

    return sorted(upcoming, key=lambda e: e["days_until"])


def get_calendar_metadata() -> dict[str, Any]:
    return _load_calendar().get("_meta") or {}
