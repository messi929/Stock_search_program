"""Eval 러너 — 케이스 실행 → 다차원 채점 → 스코어카드 → 회귀 diff.

용법:
    py -m evals.runner --smoke            # 1건, 결정론 점수만 (~₩200)
    py -m evals.runner                    # 기본 세트 (~₩2,000)
    py -m evals.runner --judge            # + LLM-judge (Haiku, 케이스당 ~₩3)
    py -m evals.runner --label baseline   # evals/results/baseline.json 저장
    py -m evals.runner --judge --baseline evals/results/baseline.json   # diff

결과 JSON에는 전체 출력 덤프가 포함되어, 채점 로직만 바꿔 오프라인 재채점도 가능.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from evals.dataset import DEFAULT_CASES, SMOKE_CASES, EvalCase, full_cases
from evals.scorers import (
    ScoreResult,
    completeness_score,
    judge_output,
    legal_score,
    numeric_coherence_score,
    persona_differentiation_score,
)

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass


_OUTPUT_KEY = {
    "blackrock": "strategist_output",
    "ark": "strategist_output",
    "graham": "strategist_output",
    "event": "event_output",
    "macro": "macro_output",
    "korean": "korean_output",
}

_DETERMINISTIC_SCORERS = ("legal", "completeness", "numeric")
_GROUP_SCORERS = ("persona_diff",)


# ──────────────────────────────────────────────
# 출력/컨텍스트 추출
# ──────────────────────────────────────────────

def _extract_output(state: dict, persona: str) -> Any:
    return state.get(_OUTPUT_KEY.get(persona, "strategist_output"))


def _current_price(state: dict) -> Optional[float]:
    a = state.get("analyst_output")
    try:
        return float(a.technical.current_price) if a else None
    except Exception:
        return None


def _input_context(state: dict, persona: str, query: str = "") -> str:
    """judge에 전달할 입력 데이터 — 에이전트가 **실제로 본 것 그대로**.

    grounding/환각 채점의 신뢰도는 "judge가 본 입력 == 에이전트가 본 입력"에 달려
    있다. 요약으로 줄이면 grounding된 수치(MA값·수급 등)를 환각으로 오판한다.
    그래서 strategist 페르소나는 strategist가 받은 user_message를 그대로 재구성한다.
    데이터 페르소나는 단일 노드 자체 페처라 재구성이 어려워 출력 내 data 필드로 갈음.
    """
    a = state.get("analyst_output")
    r = state.get("research_output")
    v = state.get("validator_output")

    # strategist 경로: 실제 입력 user_message를 그대로 재구성 (가장 충실)
    if a and r and v:
        try:
            from agents.strategist import StrategistAgent, StrategistInput, UserProfile

            si = StrategistInput(
                research_output=r,
                analyst_output=a,
                validator_output=v,
                user_profile=UserProfile(),
                persona=persona,
                query=query,
            )
            return StrategistAgent()._build_user_message(si)
        except Exception:
            pass

    # 데이터 페르소나: 단일 노드 — 원시 입력 재구성 불가. 출력 내 정량 필드로 갈음.
    out = _extract_output(state, persona)
    d = out.model_dump() if hasattr(out, "model_dump") else (out or {})
    note = (
        "(데이터 페르소나 — 단일 노드 자체 데이터 페처 경로. 원시 입력 전량 재구성 "
        "불가하므로, 명백히 지어낸 고유명사/수치만 환각으로 판정하고 grounding은 보수적으로 평가)"
    )
    keep = {k: d.get(k) for k in ("macro_regime", "cycle_analysis", "korea_specific_score", "event_summary") if d.get(k)}
    return note + ("\n" + json.dumps(keep, ensure_ascii=False)[:800] if keep else "")


def _output_text(output: Any, persona: str) -> str:
    """judge에 전달할 출력 텍스트 (핵심 서술 필드)."""
    if output is None:
        return "(출력 없음)"
    d = output.model_dump() if hasattr(output, "model_dump") else dict(output)
    parts: list[str] = []
    for key in ("summary", "persona_perspective", "summary_neutral"):
        if d.get(key):
            parts.append(str(d[key]))
    if d.get("entry_points"):
        parts.append(f"관찰구간: {d['entry_points']}")
    if d.get("exit_points"):
        parts.append(f"참고선: {d['exit_points']}")
    return "\n".join(parts) if parts else json.dumps(d, ensure_ascii=False)[:1500]


# ──────────────────────────────────────────────
# 케이스 실행 + 채점
# ──────────────────────────────────────────────

async def _run_case(case: EvalCase, judge: bool) -> dict:
    from agents.graph import run_analysis

    started = datetime.now(timezone.utc)
    rec: dict[str, Any] = {
        "case_id": case.case_id,
        "persona": case.persona,
        "ticker": case.ticker,
        "name": case.name,
        "group_key": case.group_key,
        "ok": False,
        "scores": {},
    }
    try:
        state = await run_analysis(
            ticker=case.ticker, query=case.query, persona=case.persona
        )
    except Exception as e:
        rec["error"] = f"{type(e).__name__}: {str(e)[:200]}"
        rec["elapsed_sec"] = round((datetime.now(timezone.utc) - started).total_seconds(), 1)
        return rec

    rec["elapsed_sec"] = round((datetime.now(timezone.utc) - started).total_seconds(), 1)
    output = _extract_output(state, case.persona)
    if output is None:
        rec["error"] = "출력 없음"
        return rec
    rec["ok"] = True
    rec["output"] = output.model_dump() if hasattr(output, "model_dump") else output

    # 결정론 채점
    scores: dict[str, dict] = {}
    scores["legal"] = legal_score(output).to_dict()
    scores["completeness"] = completeness_score(case.persona, output).to_dict()
    if case.persona in {"blackrock", "ark", "graham"}:
        scores["numeric"] = numeric_coherence_score(output, _current_price(state)).to_dict()

    # LLM-judge (opt-in)
    if judge:
        ictx = _input_context(state, case.persona, case.query)
        result, verdict = await judge_output(
            persona=case.persona,
            input_context=ictx,
            output_text=_output_text(output, case.persona),
        )
        scores["judge"] = result.to_dict()
        rec["judge_verdict"] = verdict
        # 향후 오프라인 재채점/검토용 — judge가 본 입력/출력 보존
        rec["judge_input_context"] = ictx

    rec["scores"] = scores
    return rec


def _apply_group_scores(records: list[dict]) -> None:
    """persona_diff — 같은 group_key의 strategist 출력끼리 차별성 채점.

    각 그룹의 점수를 그룹 내 모든 케이스 레코드에 동일하게 부착.
    """
    groups: dict[str, dict[str, Any]] = {}
    for rec in records:
        if rec.get("persona") in {"blackrock", "ark", "graham"} and rec.get("ok"):
            groups.setdefault(rec["group_key"], {})[rec["persona"]] = rec.get("output")

    for key, outputs in groups.items():
        if len(outputs) < 2:
            continue
        result = persona_differentiation_score(outputs)
        for rec in records:
            if rec.get("group_key") == key and rec.get("persona") in outputs:
                rec["scores"]["persona_diff"] = result.to_dict()


# ──────────────────────────────────────────────
# 집계 + 스코어카드
# ──────────────────────────────────────────────

def _aggregate(records: list[dict]) -> dict[str, float]:
    """채점기별 평균 (해당 케이스가 있는 것만). overall = 채점기 평균의 평균."""
    sums: dict[str, float] = {}
    counts: dict[str, int] = {}
    for rec in records:
        for name, sd in rec.get("scores", {}).items():
            sums[name] = sums.get(name, 0.0) + sd["score"]
            counts[name] = counts.get(name, 0) + 1
    agg = {name: round(sums[name] / counts[name], 3) for name in sums}
    if agg:
        agg["overall"] = round(sum(agg.values()) / len(agg), 3)
    return agg


def _print_scorecard(report: dict) -> None:
    agg = report["aggregate"]
    print("\n" + "=" * 64)
    print(f"  스코어카드 — {report['label']}  ({report['n_cases']}건, judge={report['judged']})")
    print("=" * 64)
    ok = sum(1 for r in report["cases"] if r.get("ok"))
    print(f"  실행 성공:  {ok}/{report['n_cases']}")
    for name in ("legal", "completeness", "numeric", "persona_diff", "judge", "overall"):
        if name in agg:
            bar = "█" * int(agg[name] * 20)
            print(f"  {name:14s} {agg[name]:.3f}  {bar}")
    print("=" * 64)

    # 케이스별 낮은 점수 하이라이트
    flagged = []
    for r in report["cases"]:
        if not r.get("ok"):
            flagged.append(f"  ❌ {r['case_id']}: {r.get('error', '실패')}")
            continue
        for name, sd in r.get("scores", {}).items():
            if sd["score"] < 0.8:
                flagged.append(f"  ⚠️  {r['case_id']} [{name} {sd['score']:.2f}]: {sd['detail'][:80]}")
    if flagged:
        print("  주의 케이스:")
        for line in flagged[:30]:
            print(line)
        print("=" * 64)


def _print_diff(current: dict, baseline: dict) -> None:
    print("\n" + "─" * 64)
    print(f"  회귀 비교 vs baseline ({baseline.get('label', '?')})")
    print("─" * 64)
    ca, ba = current["aggregate"], baseline.get("aggregate", {})
    for name in ("legal", "completeness", "numeric", "persona_diff", "judge", "overall"):
        if name in ca and name in ba:
            delta = ca[name] - ba[name]
            arrow = "▲" if delta > 0.005 else ("▼" if delta < -0.005 else "=")
            flag = "  🚨 회귀" if delta < -0.05 else ""
            print(f"  {name:14s} {ba[name]:.3f} → {ca[name]:.3f}  {arrow}{delta:+.3f}{flag}")
    print("─" * 64)


# ──────────────────────────────────────────────
# 메인
# ──────────────────────────────────────────────

async def run_eval(cases: tuple[EvalCase, ...], judge: bool, label: str) -> dict:
    records: list[dict] = []
    for i, case in enumerate(cases, 1):
        print(f"[{i}/{len(cases)}] {case.case_id} 실행...", flush=True)
        rec = await _run_case(case, judge)
        status = "✅" if rec.get("ok") else "❌"
        print(f"        {status} {rec.get('elapsed_sec', '-')}s", flush=True)
        records.append(rec)

    _apply_group_scores(records)
    return {
        "label": label,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "n_cases": len(cases),
        "judged": judge,
        "aggregate": _aggregate(records),
        "cases": records,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Axis AI 출력 품질 eval")
    parser.add_argument("--smoke", action="store_true", help="1건만 (~₩200)")
    parser.add_argument("--full", action="store_true", help="60건 매트릭스 (~₩12,000)")
    parser.add_argument(
        "--strategist-only",
        action="store_true",
        help="strategist 페르소나(blackrock/ark/graham)만 — ②③④ 효과 측정용 저비용 비교",
    )
    parser.add_argument("--judge", action="store_true", help="LLM-judge 추가 (Haiku)")
    parser.add_argument("--label", default="", help="결과 라벨 (evals/results/<label>.json 저장)")
    parser.add_argument("--baseline", default="", help="비교할 baseline JSON 경로")
    parser.add_argument("--out", default="", help="결과 저장 경로 (--label 우선)")
    args = parser.parse_args(argv)

    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:
        pass

    if args.smoke:
        cases = SMOKE_CASES
    elif args.full:
        cases = full_cases()
    else:
        cases = DEFAULT_CASES

    if args.strategist_only:
        cases = tuple(c for c in cases if c.persona in {"blackrock", "ark", "graham"})

    label = args.label or ("smoke" if args.smoke else "default")
    est = len(cases) * (205 if args.judge else 200)
    print(f"🔬 eval 실행 — {len(cases)}건 (judge={args.judge}) — 예상 ~₩{est:,}\n")

    report = asyncio.run(run_eval(cases, args.judge, label))
    _print_scorecard(report)

    out_path = Path(args.out) if args.out else Path("evals/results") / f"{label}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n결과 저장: {out_path}")

    if args.baseline:
        bp = Path(args.baseline)
        if bp.exists():
            baseline = json.loads(bp.read_text(encoding="utf-8"))
            _print_diff(report, baseline)
        else:
            print(f"⚠️  baseline 없음: {bp}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
