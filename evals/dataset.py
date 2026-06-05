"""Eval 골든 케이스 — 페르소나 × 종목 조합.

설계 의도:
  - **persona_diff 그룹**: 같은 종목을 blackrock/ark/graham 3개로 돌려, 페르소나가
    실제로 다른 진입선을 내는지 검증 가능하게 한다. → 005930·005380 두 그룹.
  - **시장 다양성**: KR 대형/가치 + US 대형.
  - **데이터 페르소나**: macro/korean/event 각 1건씩 — 단일 노드 경로도 회귀 커버.

비용 가이드 (실행 시 --real):
  - 기본 세트(DEFAULT_CASES) ≈ strategist 8건 + 데이터 3건 ≈ ₩1,500~2,000
  - --smoke ≈ ₩200
  - --full (60건) ≈ ₩12,000 (tests.regression 매트릭스 재사용)
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class EvalCase:
    persona: str
    ticker: str
    name: str
    query: str = ""
    # 같은 종목을 여러 페르소나로 돌릴 때 persona_diff 그룹을 묶는 키.
    # 비어 있으면 ticker를 그룹키로 사용.
    diff_group: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)

    @property
    def group_key(self) -> str:
        return self.diff_group or self.ticker

    @property
    def case_id(self) -> str:
        return f"{self.persona}:{self.ticker}"


# ──────────────────────────────────────────────
# 기본 세트 — 회귀 비교용 대표 케이스
# ──────────────────────────────────────────────

DEFAULT_CASES: tuple[EvalCase, ...] = (
    # persona_diff 그룹 1: 삼성전자 (대형 안정)
    EvalCase("blackrock", "005930", "삼성전자", "삼성전자 지금 어때?", "samsung", ("strategist", "diff")),
    EvalCase("ark", "005930", "삼성전자", "삼성전자 지금 어때?", "samsung", ("strategist", "diff")),
    EvalCase("graham", "005930", "삼성전자", "삼성전자 지금 어때?", "samsung", ("strategist", "diff")),
    # persona_diff 그룹 2: 현대차 (가치/저평가 성격)
    EvalCase("blackrock", "005380", "현대차", "현대차 분석해줘", "hyundai", ("strategist", "diff")),
    EvalCase("ark", "005380", "현대차", "현대차 분석해줘", "hyundai", ("strategist", "diff")),
    EvalCase("graham", "005380", "현대차", "현대차 분석해줘", "hyundai", ("strategist", "diff")),
    # 단일 strategist (US 대형)
    EvalCase("blackrock", "AAPL", "Apple", "애플 분석", tags=("strategist",)),
    EvalCase("graham", "AAPL", "Apple", "애플 분석", tags=("strategist",)),
    # 데이터 페르소나 (단일 노드 경로)
    EvalCase("macro", "005930", "삼성전자", "지금 거시 환경에서 삼성전자는?", tags=("data",)),
    EvalCase("korean", "005930", "삼성전자", "한국 시장 특성 관점 삼성전자", tags=("data",)),
    EvalCase("event", "RKLB", "RocketLab", "RKLB 이벤트 분석", tags=("data",)),
)


# ──────────────────────────────────────────────
# Smoke — 1건 (strategist 경로 전체를 가장 빨리 점검)
# ──────────────────────────────────────────────

SMOKE_CASES: tuple[EvalCase, ...] = (
    EvalCase("blackrock", "005930", "삼성전자", "삼성전자 지금 어때?", tags=("strategist",)),
)


def full_cases() -> tuple[EvalCase, ...]:
    """tests.regression 60건 매트릭스를 EvalCase로 변환 (--full).

    매트릭스를 단일 소스로 유지하기 위해 import 시점에 변환한다.
    """
    from tests.regression.test_60_cases import ALL_TICKERS, PERSONAS

    cases: list[EvalCase] = []
    for persona in PERSONAS:
        for ticker, name, _desc in ALL_TICKERS:
            tag = "strategist" if persona in {"blackrock", "ark", "graham"} else "data"
            cases.append(
                EvalCase(
                    persona=persona,
                    ticker=ticker,
                    name=name,
                    query=f"{name} 분석",
                    diff_group=ticker,
                    tags=(tag, "full"),
                )
            )
    return tuple(cases)
