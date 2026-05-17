"""페르소나별 캐릭터 일관성 검증 — 시스템 프롬프트 정합성 + 응답 후처리 정책.

WEEK_E.md Day 3 산출물.

검사 항목:
  1. 6 페르소나 프롬프트 파일 존재 + 최소 길이
  2. 모든 페르소나 프롬프트에 LEGAL Hard Rules 포함
  3. 신규 3 페르소나 (event/macro/korean)에 v2 핵심 키워드 포함
     - event: "확실성 점수", "scenario_analysis", "summary_neutral", "current_position_vs_history"
     - macro: "Goldilocks", "Reflation", "Stagflation", "Risk-Off", "Recovery", "Late Cycle"
     - korean: "외국인", "재벌", "밸류업", "거버넌스", "공매도"
  4. 6 페르소나 모두 "절대 금지" 단정어 표현 가이드 포함
  5. 페르소나 메타 (frontend types/persona.ts)와 백엔드 ALL_PERSONAS 일치

종료 코드:
    0 — 통과
    1 — 위반 발견
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Windows cp949 환경에서 한글 출력
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass


REPO_ROOT = Path(__file__).resolve().parent.parent
PERSONAS_DIR = REPO_ROOT / "personas"

# standalone 실행 시 repo root를 sys.path에 추가 (agents import 가능하게)
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

PERSONA_IDS = ("blackrock", "ark", "graham", "event", "macro", "korean")
MIN_PROMPT_CHARS = 800  # 최소 길이 (너무 짧으면 가이드 부족)

# 모든 페르소나 공통: LEGAL Hard Rules 표시 키워드
COMMON_LEGAL_KEYWORDS = ("절대 금지", "추천")

# 신규 3 페르소나별 v2 핵심 키워드
V2_KEYWORDS = {
    "event": (
        "확실성",
        "scenario_analysis",
        "summary_neutral",
        "current_position_vs_history",
    ),
    "macro": (
        "Goldilocks",
        "Reflation",
        "Stagflation",
        "Risk-Off",
        "Recovery",
        "Late Cycle",
    ),
    "korean": (
        "외국인",
        "재벌",
        "밸류업",
        "거버넌스",
        "공매도",
    ),
}


@dataclass
class CheckIssue:
    persona: str
    severity: str  # "HIGH" | "MEDIUM"
    detail: str


@dataclass
class CheckReport:
    issues: list[CheckIssue] = field(default_factory=list)
    files_checked: int = 0

    def add(self, persona: str, severity: str, detail: str) -> None:
        self.issues.append(CheckIssue(persona, severity, detail))

    def has_high(self) -> bool:
        return any(i.severity == "HIGH" for i in self.issues)


def _check_prompt_file(persona: str, report: CheckReport) -> str | None:
    """페르소나 프롬프트 파일 존재 + 최소 길이. 본문 텍스트 반환 (없으면 None)."""
    path = PERSONAS_DIR / f"{persona}.md"
    if not path.exists():
        report.add(persona, "HIGH", f"페르소나 프롬프트 파일 누락: {path.relative_to(REPO_ROOT)}")
        return None
    text = path.read_text(encoding="utf-8")
    if len(text) < MIN_PROMPT_CHARS:
        report.add(
            persona,
            "MEDIUM",
            f"프롬프트 짧음 ({len(text)}자 < {MIN_PROMPT_CHARS}자) — 가이드 부족 가능",
        )
    report.files_checked += 1
    return text


def _check_common_legal(persona: str, text: str, report: CheckReport) -> None:
    for kw in COMMON_LEGAL_KEYWORDS:
        if kw not in text:
            report.add(persona, "HIGH", f"공통 LEGAL 키워드 '{kw}' 누락")


def _check_v2_keywords(persona: str, text: str, report: CheckReport) -> None:
    if persona not in V2_KEYWORDS:
        return
    for kw in V2_KEYWORDS[persona]:
        if kw not in text:
            report.add(persona, "HIGH", f"v2 핵심 키워드 '{kw}' 누락")


def _check_persona_alignment(report: CheckReport) -> None:
    """프론트엔드 PERSONA_META와 백엔드 ALL_PERSONAS 일치 여부."""
    try:
        from agents.graph import ALL_PERSONAS as backend
    except Exception as e:
        report.add("(global)", "HIGH", f"agents.graph import 실패: {e}")
        return
    backend_set = set(backend)
    if backend_set != set(PERSONA_IDS):
        report.add(
            "(global)",
            "HIGH",
            f"백엔드 ALL_PERSONAS != PERSONA_IDS: backend={sorted(backend_set)}, "
            f"expected={sorted(PERSONA_IDS)}",
        )

    persona_ts = REPO_ROOT / "web" / "types" / "persona.ts"
    if not persona_ts.exists():
        report.add("(global)", "MEDIUM", "web/types/persona.ts 누락 — 프론트엔드 메타 미정의")
        return
    ts_text = persona_ts.read_text(encoding="utf-8")
    for pid in PERSONA_IDS:
        if f'id: "{pid}"' not in ts_text:
            report.add(
                "(global)",
                "HIGH",
                f"web/types/persona.ts에 id='{pid}' 누락",
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="6 페르소나 캐릭터 일관성 검증")
    parser.add_argument(
        "--allow-medium",
        action="store_true",
        help="MEDIUM 이슈도 허용 (HIGH만 fail)",
    )
    args = parser.parse_args(argv)

    report = CheckReport()

    for persona in PERSONA_IDS:
        text = _check_prompt_file(persona, report)
        if text is None:
            continue
        _check_common_legal(persona, text, report)
        _check_v2_keywords(persona, text, report)

    _check_persona_alignment(report)

    print(f"📁 검사 파일 수: {report.files_checked} (페르소나 6개)")
    if not report.issues:
        print("✅ 페르소나 일관성 검사 통과 — 이슈 0건")
        return 0

    by_severity: dict[str, list[CheckIssue]] = {"HIGH": [], "MEDIUM": []}
    for issue in report.issues:
        by_severity.setdefault(issue.severity, []).append(issue)

    print(f"🚨 이슈 발견 — HIGH {len(by_severity['HIGH'])}건, MEDIUM {len(by_severity['MEDIUM'])}건\n")
    for severity in ("HIGH", "MEDIUM"):
        for issue in by_severity[severity]:
            print(f"  [{severity}] {issue.persona}: {issue.detail}")

    if report.has_high():
        return 1
    if not args.allow_medium and by_severity["MEDIUM"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
