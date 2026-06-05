"""evals 결정론 채점기 단위 테스트 (API 호출 없음).

LLM-judge는 @integration 마커로 분리하지 않고, 결정론 채점기만 검증한다.
판정 로직(점수 계산)이 회귀하면 eval 신뢰도 자체가 무너지므로 가드한다.
"""

from __future__ import annotations

from agents.strategist import (
    AlertCondition,
    EntryPoints,
    ExitPoints,
    StrategistResult,
)
from evals.scorers import (
    completeness_score,
    legal_score,
    numeric_coherence_score,
    persona_differentiation_score,
)


def _strategist(
    *,
    summary="삼성전자는 관찰 구간으로 분류됩니다.",
    perspective="블랙록 관점에서 리스크 프레임을 봅니다.",
    entry=(70000, 65000, 60000),
    exit_=(68000, 85000, 100000),
    alerts=True,
    follow_ups=True,
) -> StrategistResult:
    return StrategistResult(
        persona_used="blackrock",
        persona_perspective=perspective,
        summary=summary,
        entry_points=EntryPoints(tier_1=entry[0], tier_2=entry[1], tier_3=entry[2]),
        exit_points=ExitPoints(
            stop_loss=exit_[0], take_profit_1=exit_[1], take_profit_final=exit_[2]
        ),
        alert_conditions=(
            [AlertCondition(condition_type="price_below", threshold=65000.0, action="관찰 신호 도달")]
            if alerts
            else []
        ),
        follow_up_questions=["환율 영향은?"] if follow_ups else [],
    )


# ── legal ──

def test_legal_clean_passes():
    r = legal_score(_strategist())
    assert r.score == 1.0
    assert not r.issues


def test_legal_detects_forbidden_in_nested_field():
    r = legal_score(_strategist(summary="지금 사세요. 확실히 오릅니다."))
    assert r.score == 0.0
    assert r.issues  # 위반 경로 기록


# ── completeness ──

def test_completeness_full():
    r = completeness_score("blackrock", _strategist())
    assert r.score == 1.0


def test_completeness_missing_fields_penalized():
    r = completeness_score(
        "blackrock", _strategist(alerts=False, follow_ups=False)
    )
    assert r.score < 1.0
    assert "alert_conditions" in r.issues
    assert "follow_up_questions" in r.issues


# ── numeric ──

def test_numeric_coherent_full_marks():
    # entry 내림차순·현재가 미만, exit 방향 정상
    r = numeric_coherence_score(_strategist(), current_price=72000)
    assert r.score == 1.0


def test_numeric_incoherent_penalized():
    # entry가 오름차순(잘못), stop_loss가 현재가보다 높음(잘못)
    bad = _strategist(entry=(60000, 65000, 70000), exit_=(90000, 85000, 100000))
    r = numeric_coherence_score(bad, current_price=72000)
    assert r.score < 1.0
    assert r.issues


def test_numeric_no_data_is_neutral():
    r = numeric_coherence_score({}, current_price=None)
    assert r.score == 1.0  # 검사 대상 없으면 페널티 없음


# ── persona_diff ──

def test_persona_diff_distinct_full_marks():
    outputs = {
        "blackrock": _strategist(entry=(70000, 65000, 60000)),
        "ark": _strategist(entry=(76000, 72000, 68000)),
        "graham": _strategist(entry=(63000, 58000, 53000)),
    }
    r = persona_differentiation_score(outputs)
    assert r.score == 1.0


def test_persona_diff_identical_penalized():
    same = {
        "blackrock": _strategist(entry=(70000, 65000, 60000)),
        "ark": _strategist(entry=(70000, 65000, 60000)),
        "graham": _strategist(entry=(70000, 65000, 60000)),
    }
    r = persona_differentiation_score(same)
    assert r.score == 0.0
    assert r.issues


def test_persona_diff_single_persona_neutral():
    r = persona_differentiation_score({"blackrock": _strategist()})
    assert r.score == 1.0  # 비교 불가 → 페널티 없음
