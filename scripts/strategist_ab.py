"""Strategist 모델 A/B 검증 — Opus 4.7 vs Sonnet 4.6.

동일 입력(research/analyst/validator)으로 Strategist만 두 모델로 호출해
출력 품질·비용·시간을 비교한다. 앞단은 1회만 실행해 비용 최소화.

용법:
    py scripts/strategist_ab.py [TICKER] [PERSONA]
    (기본: 005930 blackrock)

산출물: docs/axis/strategist_ab_result.md
"""

from __future__ import annotations

import asyncio
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv

load_dotenv()

from agents.graph import run_analysis
from agents.strategist import (
    StrategistAgent,
    StrategistInput,
    StrategistResult,
    UserProfile,
)
from utils.claude_client import MODEL_OPUS, MODEL_SONNET
from utils.cost_tracker import calculate_cost

# (ticker, persona) 조합 — 페르소나별 대표 종목
COMBOS = [
    ("005930", "blackrock"),  # 삼성전자 — 대형 안정 + 리스크 프레임
    ("000660", "ark"),        # SK하이닉스 — AI반도체 혁신 + 성장 서사
    ("005380", "graham"),     # 현대차 — 저평가 가치 + 안전마진
]
MAX_TOKENS = 2048  # 1차에서 1500이 Sonnet truncation 유발 → 상향


async def _call_strategist(model: str, si: StrategistInput):
    """Strategist를 지정 모델로 1회 호출 → (result, cost_krw, elapsed, usage)."""
    agent = StrategistAgent()
    agent.model = model  # 런타임 모델 전환 (base.call_claude가 self.model 참조)
    agent.claude.use_response_cache = False  # 캐시 우회 — 공정 비교 (max_tokens만 다른 동일 키 충돌 방지)

    full_system = agent._build_full_system(si.persona)
    user_message = agent._build_user_message(si)

    t0 = time.time()
    result, raw = await agent.call_claude_json(
        user_message=user_message,
        schema=StrategistResult,
        max_tokens=MAX_TOKENS,
        uid="",
        system=full_system,
    )
    elapsed = round(time.time() - t0, 2)

    # raw에서 usage 추출 (dict이면 .get, 객체면 attr)
    usage = None
    if isinstance(raw, dict):
        usage = raw.get("usage")
    else:
        usage = getattr(raw, "usage", None)
    cost_krw = None
    if usage is not None:
        cost_krw = calculate_cost(model, usage).krw
    return result, cost_krw, elapsed, usage


def _fmt_result(r) -> str:
    """StrategistResult를 사람이 비교하기 좋은 마크다운으로."""
    d = r.model_dump()
    lines = []
    if d.get("summary"):
        lines.append(f"**종합(summary)**\n\n{d['summary']}\n")
    if d.get("persona_perspective"):
        lines.append(f"**페르소나 관점(persona_perspective)**\n\n{d['persona_perspective']}\n")
    if d.get("entry_points"):
        lines.append(f"**관찰 구간(entry_points)**: {d['entry_points']}")
    if d.get("exit_points"):
        lines.append(f"**참고선(exit_points)**: {d['exit_points']}")
    if d.get("alert_conditions"):
        lines.append(f"**알림 조건**: {d['alert_conditions']}")
    if d.get("user_principles_alignment"):
        lines.append(f"\n**원칙 부합도**: {d['user_principles_alignment']}")
    if d.get("follow_up_questions"):
        lines.append("\n**후속 질문**")
        for q in d["follow_up_questions"]:
            lines.append(f"- {q}")
    if d.get("confidence_note"):
        lines.append(f"\n**신뢰 노트**: {d['confidence_note']}")
    return "\n".join(lines)


def _cost(c):
    return f"{c:,.1f}원" if c is not None else "n/a"


def _completeness(r) -> str:
    """필수 구조 필드 충실도 — truncation 탐지."""
    d = r.model_dump()
    have = []
    have.append("summary" if d.get("summary") else "—")
    have.append("persona" if d.get("persona_perspective") else "—")
    have.append("entry" if d.get("entry_points") else "—")
    have.append("exit" if d.get("exit_points") else "—")
    have.append(f"alert×{len(d.get('alert_conditions') or [])}")
    return " / ".join(have)


async def _run_combo(ticker: str, persona: str) -> dict:
    print(f"\n[A/B] {ticker} / {persona} — 앞단 실행...")
    final = await run_analysis(ticker=ticker, persona=persona, user_profile=UserProfile())
    research = final.get("research_output")
    analyst = final.get("analyst_output")
    validator = final.get("validator_output")
    if not (research and analyst and validator):
        print(f"[ERR] {ticker} 앞단 누락 — 스킵")
        return {}

    si = StrategistInput(
        research_output=research, analyst_output=analyst, validator_output=validator,
        persona=persona, user_profile=UserProfile(),
    )
    print(f"[A/B] {ticker} Opus 호출...")
    opus_r, opus_c, opus_t, opus_u = await _call_strategist(MODEL_OPUS, si)
    print(f"[A/B] {ticker} Sonnet 호출...")
    son_r, son_c, son_t, son_u = await _call_strategist(MODEL_SONNET, si)
    return {
        "ticker": ticker, "persona": persona,
        "opus": (opus_r, opus_c, opus_t, opus_u),
        "sonnet": (son_r, son_c, son_t, son_u),
    }


async def main():
    results = [r for c in COMBOS if (r := await _run_combo(*c))]

    # 종합 요약표
    sum_md = ["# Strategist A/B 재검증 — max_tokens=2048, 캐시 우회\n",
              "> 동일 입력으로 Strategist만 두 모델 호출. 페르소나별 대표 종목.\n",
              "## 종합 비교\n",
              "| 종목/페르소나 | Opus 비용 | Sonnet 비용 | 절감 | Opus out | Sonnet out | Opus 구조 | Sonnet 구조 |",
              "|---|---|---|---|---|---|---|---|"]
    tot_o = tot_s = 0.0
    for r in results:
        o_r, o_c, o_t, o_u = r["opus"]
        s_r, s_c, s_t, s_u = r["sonnet"]
        tot_o += o_c or 0
        tot_s += s_c or 0
        save = f"{(1 - s_c/o_c)*100:.0f}%" if (o_c and s_c) else "n/a"
        sum_md.append(
            f"| {r['ticker']}/{r['persona']} | {_cost(o_c)} | {_cost(s_c)} | {save} | "
            f"{getattr(o_u,'output_tokens','?')} | {getattr(s_u,'output_tokens','?')} | "
            f"{_completeness(o_r)} | {_completeness(s_r)} |"
        )
    tot_save = f"{(1 - tot_s/tot_o)*100:.0f}%" if tot_o else "n/a"
    sum_md.append(f"| **합계** | **{_cost(tot_o)}** | **{_cost(tot_s)}** | **{tot_save}** | | | | |")

    # 조합별 상세
    detail = []
    for r in results:
        o_r = r["opus"][0]
        s_r = r["sonnet"][0]
        detail.append(f"\n---\n\n# {r['ticker']} / {r['persona']}\n")
        detail.append(f"## 🅰️ Opus 4.7\n\n{_fmt_result(o_r)}\n")
        detail.append(f"## 🅱️ Sonnet 4.6\n\n{_fmt_result(s_r)}\n")

    out = "docs/axis/strategist_ab_result.md"
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(sum_md) + "\n" + "\n".join(detail))
    print(f"\n[OK] 결과 저장: {out}")
    print(f"  총 Opus {_cost(tot_o)} / Sonnet {_cost(tot_s)} (절감 {tot_save})")


if __name__ == "__main__":
    asyncio.run(main())
