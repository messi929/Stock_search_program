"""출력물 채점기 — 결정론(무료) + LLM-judge(opt-in).

각 채점기는 ScoreResult(0.0~1.0 + detail)를 반환한다. 점수는 회귀 비교를 위해
정규화되며, detail에는 사람이 읽을 수 있는 근거/위반 내역을 담는다.

결정론 채점기는 API 호출이 없어 단위 테스트로 검증 가능 (tests/test_evals.py).
judge_output만 Claude(Haiku) 1회 호출.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from pydantic import BaseModel, Field


# ──────────────────────────────────────────────
# 결과 컨테이너
# ──────────────────────────────────────────────

@dataclass
class ScoreResult:
    name: str
    score: float  # 0.0 ~ 1.0
    detail: str = ""
    issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "score": round(self.score, 3),
            "detail": self.detail,
            "issues": self.issues,
        }


# ──────────────────────────────────────────────
# 공통 헬퍼 — pydantic/dict 재귀 순회
# ──────────────────────────────────────────────

def _to_dict(obj: Any) -> Any:
    if isinstance(obj, BaseModel):
        return obj.model_dump()
    return obj


def _walk_strings(obj: Any, path: str = "") -> list[tuple[str, str]]:
    """중첩 dict/list/모델에서 (경로, 문자열) 쌍을 모두 수집."""
    obj = _to_dict(obj)
    out: list[tuple[str, str]] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.extend(_walk_strings(v, f"{path}.{k}" if path else str(k)))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out.extend(_walk_strings(v, f"{path}[{i}]"))
    elif isinstance(obj, str):
        if obj.strip():
            out.append((path, obj))
    return out


# ──────────────────────────────────────────────
# 1) LEGAL — 출력 전체 문자열에 권유성 단어 0건
# ──────────────────────────────────────────────

def legal_score(output: Any) -> ScoreResult:
    """출력물 내 모든 문자열을 런타임 필터와 동일 규칙으로 스캔.

    출력 단계의 후처리 필터는 free-text에만 적용되므로, JSON 필드 내부에
    단정어가 남아있을 수 있다 — 이 채점기는 모든 필드를 검사한다.
    """
    from agents.base import BaseAgent

    issues: list[str] = []
    for path, text in _walk_strings(output):
        _, found = BaseAgent.filter_forbidden(text)
        for label in found:
            issues.append(f"{path}: [{label}] {text[:60]}")

    score = 1.0 if not issues else 0.0
    detail = "위반 0건" if not issues else f"권유성 표현 {len(issues)}건"
    return ScoreResult("legal", score, detail, issues)


# ──────────────────────────────────────────────
# 2) COMPLETENESS — 페르소나별 필수 콘텐츠 필드 충실도
# ──────────────────────────────────────────────

# 페르소나 그룹 → 채워져야 할 (dotted path, 비어있지 않아야 함) 목록
_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "strategist": (
        "persona_perspective",
        "summary",
        "entry_points",
        "exit_points",
        "alert_conditions",
        "follow_up_questions",
    ),
    "event": ("summary_neutral", "event_summary", "scenario_analysis"),
    "macro": ("summary_neutral", "macro_regime", "cycle_analysis"),
    "korean": ("summary_neutral", "korea_specific_score"),
}


def _is_nonempty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict, tuple)):
        return len(value) > 0
    return True


def _get_path(d: dict, path: str) -> Any:
    cur: Any = d
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def completeness_score(persona: str, output: Any) -> ScoreResult:
    group = persona if persona in _REQUIRED_FIELDS else "strategist"
    required = _REQUIRED_FIELDS.get(group, ())
    if not required:
        return ScoreResult("completeness", 1.0, "필수 필드 미정의")

    d = _to_dict(output) or {}
    missing = [f for f in required if not _is_nonempty(_get_path(d, f))]
    score = 1.0 - len(missing) / len(required)
    detail = "모든 필수 필드 충실" if not missing else f"누락: {', '.join(missing)}"
    return ScoreResult("completeness", score, detail, missing)


# ──────────────────────────────────────────────
# 3) NUMERIC — 진입/청산 수치 정합성 (strategist 전용)
# ──────────────────────────────────────────────

def numeric_coherence_score(output: Any, current_price: Optional[float]) -> ScoreResult:
    """진입선·청산선이 현재가 대비 방향/순서가 맞는지.

    관찰 구간(entry tiers)은 현재가보다 낮고 tier1 > tier2 > tier3.
    손실 한도(stop_loss)는 현재가 미만, 차익선(take_profit)은 현재가 초과·오름차순.
    제약 충족 비율을 점수로 (검사 불가 시 1.0 — 페널티 없음).
    """
    d = _to_dict(output) or {}
    checks: list[tuple[str, bool]] = []

    entry = d.get("entry_points") or {}
    exit_ = d.get("exit_points") or {}

    if entry:
        t1, t2, t3 = entry.get("tier_1"), entry.get("tier_2"), entry.get("tier_3")
        if all(isinstance(x, (int, float)) and x > 0 for x in (t1, t2, t3)):
            checks.append(("entry 내림차순(tier1>tier2>tier3)", t1 > t2 > t3))
            if current_price and current_price > 0:
                checks.append(("entry tier1 < 현재가", t1 < current_price))

    if exit_:
        sl = exit_.get("stop_loss")
        tp1 = exit_.get("take_profit_1")
        tpf = exit_.get("take_profit_final")
        if current_price and current_price > 0:
            if isinstance(sl, (int, float)) and sl > 0:
                checks.append(("stop_loss < 현재가", sl < current_price))
            if isinstance(tp1, (int, float)) and tp1 > 0:
                checks.append(("take_profit_1 > 현재가", tp1 > current_price))
        if all(isinstance(x, (int, float)) and x > 0 for x in (tp1, tpf)):
            checks.append(("take_profit 오름차순", tpf >= tp1))

    if not checks:
        return ScoreResult("numeric", 1.0, "검사 대상 수치 없음 (해당 없음)")

    passed = sum(1 for _, ok in checks if ok)
    score = passed / len(checks)
    failed = [name for name, ok in checks if not ok]
    detail = f"{passed}/{len(checks)} 정합" + (f" — 실패: {', '.join(failed)}" if failed else "")
    return ScoreResult("numeric", score, detail, failed)


# ──────────────────────────────────────────────
# 4) PERSONA_DIFF — 같은 종목에서 페르소나별 진입선이 실제로 다른가
# ──────────────────────────────────────────────

def persona_differentiation_score(
    outputs_by_persona: dict[str, Any],
) -> ScoreResult:
    """같은 종목에 대한 여러 strategist 페르소나 출력의 차별성.

    entry tier_1 값이 페르소나마다 유의미하게 달라야 한다(프롬프트가 명시 강제).
    모든 쌍의 상대 차이가 ≥2%면 1.0, 동일 값이 많을수록 감점.
    """
    tiers: dict[str, float] = {}
    for persona, out in outputs_by_persona.items():
        d = _to_dict(out) or {}
        entry = d.get("entry_points") or {}
        t1 = entry.get("tier_1")
        if isinstance(t1, (int, float)) and t1 > 0:
            tiers[persona] = float(t1)

    if len(tiers) < 2:
        return ScoreResult(
            "persona_diff", 1.0, f"비교 불가 (entry tier_1 있는 페르소나 {len(tiers)}개)"
        )

    personas = list(tiers)
    pairs = [
        (personas[i], personas[j])
        for i in range(len(personas))
        for j in range(i + 1, len(personas))
    ]
    distinct = 0
    same: list[str] = []
    for a, b in pairs:
        base = max(abs(tiers[a]), abs(tiers[b]), 1.0)
        rel = abs(tiers[a] - tiers[b]) / base
        if rel >= 0.02:
            distinct += 1
        else:
            same.append(f"{a}≈{b}({tiers[a]:.0f}/{tiers[b]:.0f})")

    score = distinct / len(pairs)
    detail = (
        f"{distinct}/{len(pairs)} 페르소나 쌍이 구별됨"
        + (f" — 유사: {', '.join(same)}" if same else "")
    )
    detail += " | tier1=" + ", ".join(f"{p}:{v:.0f}" for p, v in tiers.items())
    return ScoreResult("persona_diff", score, detail, same)


# ──────────────────────────────────────────────
# 5) LLM-JUDGE (opt-in, Haiku)
# ──────────────────────────────────────────────

class JudgeVerdict(BaseModel):
    """판정자 출력 스키마 (1~5 정수)."""

    reasoning_quality: int = Field(ge=1, le=5, description="추론의 구체성·일관성")
    data_grounded: int = Field(ge=1, le=5, description="주어진 데이터 근거 충실도")
    persona_fit: int = Field(ge=1, le=5, description="선언된 페르소나 철학 부합")
    hallucinations: list[str] = Field(default_factory=list, description="근거 없는 구체적 주장")
    rationale: str = Field(default="", description="채점 근거 1~2문장")


_JUDGE_SYSTEM = """당신은 투자 분석 AI의 출력을 채점하는 엄격한 평가자입니다.
당신의 임무는 칭찬이 아니라 약점을 찾는 것입니다.

주어지는 것:
1. 분석에 사용된 입력 데이터(수치·시황)
2. 적용된 페르소나의 투자 철학·기준 (시스템이 함께 제공)
3. AI가 생성한 분석 출력

채점(각 1~5 정수):
- reasoning_quality: 일반론·동어반복이면 낮게, 데이터를 짚어 구체적이면 높게
- data_grounded: 입력에 없는 종목 고유 사실을 지어내면 낮게, 입력에 충실하면 높게
- persona_fit: 페르소나 철학이 분석에 실제로 반영됐으면 높게, 페르소나 무관하면 낮게
- hallucinations: 아래 정의에 해당하는 것만 배열로 나열 (없으면 빈 배열)

## 환각의 정의 (엄격히 구분 — 과대 플래그 금지)
**환각으로 판정 O** — 입력에 없는 *이 종목에 대한 구체적 외부 사실*:
- 특정 인수/계약/제품명 (예: "보스턴다이나믹스 인수", "Apple Intelligence")
- 특정 경쟁사의 구체적 행동 (예: "BYD 가격 인하")
- 입력에 없는 과거 통계/수치 (예: "과거 평균 10~20% 되돌림")
- 입력 데이터와 모순되는 주장

**환각 아님 X** — 다음은 정상이므로 절대 환각으로 세지 말 것:
- 페르소나의 표준 투자 철학·기준 (예: 그레이엄 'PER<15·PBR<1.5', ARK '고성장 선호',
  'Mr. Market', '안전마진') — 위에 제공된 페르소나 철학에 부합하면 정당
- 입력으로 주어진 수치의 단순 산술 (예: 현재가와 52주 저가 대비율로 절대값 역산,
  관찰구간 가격 계산)
- 일반 금융 상식·중립적 해석

엄격하게. 무난하면 3점. 5점은 정말 뛰어날 때만.

반드시 JSON만 출력:
{"reasoning_quality": 3, "data_grounded": 4, "persona_fit": 3, "hallucinations": ["..."], "rationale": "..."}
"""


def _load_persona_philosophy(persona: str) -> str:
    """personas/<persona>.md 를 읽어 judge에 제공 (페르소나 지식 오판 방지)."""
    from pathlib import Path

    path = Path(__file__).resolve().parent.parent / "personas" / f"{persona}.md"
    try:
        text = path.read_text(encoding="utf-8")
        return text[:2500]  # 핵심 철학부 — judge 토큰 절약
    except Exception:
        return "(페르소나 철학 파일 없음 — 일반 통념으로 평가)"


def _judge_model() -> str:
    """판정 모델 — 기본 Sonnet. Haiku는 reasoning/data를 일괄 2점으로 포화시키고
    자기검증 문장을 환각으로 오판해 판별력이 없음(검증 완료). env로 override 가능."""
    import os

    from utils.claude_client import MODEL_HAIKU, MODEL_SONNET

    m = os.environ.get("AXIS_JUDGE_MODEL", "").strip().lower()
    if m == "haiku":
        return MODEL_HAIKU
    return MODEL_SONNET


async def judge_output(
    persona: str,
    input_context: str,
    output_text: str,
    uid: str = "",
    model: str | None = None,
) -> tuple[ScoreResult, dict]:
    """Claude로 출력 품질 판정. (ScoreResult, raw_verdict_dict) 반환.

    종합 점수 = 가중 루브릭(reasoning 0.4·data 0.3·persona 0.3, 각 /5)
              − 환각 페널티(건당 0.04, 최대 0.2).
    환각 페널티를 캡으로 둬 저점 포화를 방지(이전 0.1/건은 3~5건에서 전부 0으로 붕괴).
    data_grounded가 이미 환각을 반영하므로 페널티는 보조 신호로만.

    judge에 페르소나 철학을 함께 제공해, 페르소나 표준 기준(그레이엄 PER<15 등)을
    환각으로 오판하지 않게 한다.
    """
    from agents.base import BaseAgent

    class _Judge(BaseAgent):
        async def run(self, input_data):  # noqa: D401 - 미사용 (call_claude_json만 사용)
            raise NotImplementedError

    judge = _Judge(
        agent_name="eval_judge",
        model=model or _judge_model(),
        system_prompt=_JUDGE_SYSTEM,
    )
    philosophy = _load_persona_philosophy(persona)
    user_message = (
        f"# 적용 페르소나\n{persona}\n\n"
        f"# 페르소나 투자 철학·기준 (이 범위의 개념·기준은 환각이 아님)\n{philosophy}\n\n"
        f"# 입력 데이터\n{input_context}\n\n"
        f"# AI 분석 출력\n{output_text}\n\n"
        f"# 작업\n위 출력을 채점하세요. 환각은 시스템 정의에 해당하는 '종목 고유 외부 사실'만 — "
        f"페르소나 표준 기준이나 단순 산술은 환각이 아닙니다."
    )
    try:
        verdict, _raw = await judge.call_claude_json(
            user_message=user_message,
            schema=JudgeVerdict,
            max_tokens=768,
            uid=uid,
        )
    except Exception as e:
        return ScoreResult("judge", 0.5, f"판정 실패: {type(e).__name__}: {e}"), {}

    base = (
        0.4 * verdict.reasoning_quality
        + 0.3 * verdict.data_grounded
        + 0.3 * verdict.persona_fit
    ) / 5.0
    penalty = min(0.2, 0.04 * len(verdict.hallucinations))
    score = max(0.0, min(1.0, base - penalty))
    detail = (
        f"reasoning={verdict.reasoning_quality} data={verdict.data_grounded} "
        f"persona={verdict.persona_fit} 환각={len(verdict.hallucinations)} | {verdict.rationale}"
    )
    return ScoreResult("judge", score, detail, verdict.hallucinations), verdict.model_dump()
