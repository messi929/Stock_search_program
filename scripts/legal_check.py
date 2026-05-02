"""배포 전 LEGAL 자동 검사 — 권유성 단어가 코드에 누출됐는지 확인.

사용법:
    python scripts/legal_check.py

검사 대상: agents/, personas/, api/, web/app/, web/components/, web/hooks/, scripts/
파일 형식: .py, .ts, .tsx, .md

엔진: agents/base.py의 FORBIDDEN_PATTERNS와 동일한 정규식 사용 → 런타임/CI 일치.

화이트리스트 (정의 vs 사용 구분):
1. 같은 줄에 따옴표 인접 등장 → 정의/예시로 간주
2. `# legal-check: allow` (Python) 또는 `// legal-check: allow` (TS/JS) 어노테이션이
   해당 줄 또는 직전 줄에 있으면 통과 — *반드시* 사유 명시
3. 주석 줄 (#, //) — 자유 텍스트로 간주, 통과
4. 디렉토리: node_modules/, .next/, __pycache__/, tests/

종료 코드:
    0 — 통과
    1 — 위반 발견 (CI 차단용)
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Windows cp949 환경에서 한글/이모지 출력 — stdout을 UTF-8로 강제
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass

# ── agents/base.py와 동일 패턴 (런타임 필터와 CI 일치) ──
# Note: agents/base.py를 import하지 않고 복제 — scripts/는 의존성 무관해야 함.
FORBIDDEN_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"(?<![비非])"
            r"추천(합니다|드립니다|드려요|해요|한다|됩니다|되었|되며|받|드린|받았|드림)"
        ),
        "추천",
    ),
    (re.compile(r"사세요"), "사세요"),
    (re.compile(r"매수하세요"), "매수하세요"),
    (re.compile(r"매도하세요"), "매도하세요"),
    # "신호" + "시그널" 양쪽 차단 (agents/base.py와 일치)
    (re.compile(r"매수\s*(신호|시그널)"), "매수 신호"),
    (re.compile(r"매도\s*(신호|시그널)"), "매도 신호"),
    (re.compile(r"진입\s*(신호|시그널)"), "진입 신호"),
    (re.compile(r"유망(합니다|한|주\b|할 것)"), "유망"),
    (
        re.compile(r"(확실히|반드시|분명히)\s*(오릅|오를|상승|수익|매수|이익)"),
        "확정 어조",
    ),
    (re.compile(r"(사야|팔아야)\s*(합니다|한다)"), "당위 어조"),
)

# ── 검사 대상 디렉토리 ──
TARGET_DIRS = (
    "agents",
    "personas",
    "api",
    "web/app",
    "web/components",
    "web/hooks",
    "scripts",
)

TARGET_SUFFIXES = (".py", ".ts", ".tsx", ".md")

WHITELIST_DIRS = (
    "node_modules",
    ".next",
    "__pycache__",
    "tests",
)

# 라인 어노테이션 — 같은 줄 또는 직전 줄
ALLOW_MARKER = "legal-check: allow"

# 따옴표 인접성 검사용 (Korean smart quotes 포함)
_QUOTE_CHARS = "\"'“”‘’「」『』＂"


def _is_comment_line(text: str, suffix: str) -> bool:
    s = text.lstrip()
    if suffix == ".py":
        return s.startswith("#")
    if suffix in (".ts", ".tsx"):
        return s.startswith("//") or s.startswith("*") or s.startswith("/*")
    return False


def _has_allow_marker(lines: list[str], line_no: int) -> bool:
    """현재 줄 또는 직전 줄에 `legal-check: allow` 어노테이션이 있는지."""
    if line_no - 1 >= 0 and ALLOW_MARKER in lines[line_no - 1]:
        return True
    if line_no - 2 >= 0 and ALLOW_MARKER in lines[line_no - 2]:
        return True
    return False


def _all_matches_quote_adjacent(line: str, pattern: re.Pattern[str]) -> bool:
    """줄 안의 패턴 모든 매치가 따옴표 인접한지 (정의/예시로 간주).

    매치 양쪽 중 하나라도 따옴표 문자면 통과. 한 쪽이라도 평문 단독이면 위반.
    """
    matches = list(pattern.finditer(line))
    if not matches:
        return False  # 매치 없음 — 호출자가 처리
    for m in matches:
        before = line[m.start() - 1] if m.start() > 0 else ""
        after = line[m.end()] if m.end() < len(line) else ""
        if before not in _QUOTE_CHARS and after not in _QUOTE_CHARS:
            return False
    return True


def _check_file(path: Path, repo_root: Path) -> list[tuple[Path, int, str]]:
    """단일 파일 검사. (path, line_no, label) 위반 리스트 반환."""
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []

    issues: list[tuple[Path, int, str]] = []
    suffix = path.suffix
    lines = text.splitlines()
    for line_no, line in enumerate(lines, start=1):
        # 1) 주석 줄은 자유 텍스트로 통과 (.md 제외)
        if _is_comment_line(line, suffix):
            continue
        # 2) 어노테이션 (현재/직전 줄)
        if _has_allow_marker(lines, line_no):
            continue
        # 3) 패턴 매칭
        for pattern, label in FORBIDDEN_PATTERNS:
            if not pattern.search(line):
                continue
            # 정의/예시 (따옴표 인접) 통과
            if _all_matches_quote_adjacent(line, pattern):
                continue
            issues.append((path, line_no, label))
    return issues


def _walk_targets(repo_root: Path):
    for target in TARGET_DIRS:
        d = repo_root / target
        if not d.exists():
            continue
        for p in d.rglob("*"):
            if not p.is_file():
                continue
            if p.suffix not in TARGET_SUFFIXES:
                continue
            parts = set(p.parts)
            if any(wd in parts for wd in WHITELIST_DIRS):
                continue
            yield p


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="LEGAL 권유성 단어 검사")
    parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parent.parent
    issues: list[tuple[Path, int, str]] = []

    files_checked = 0
    for path in _walk_targets(repo_root):
        files_checked += 1
        issues.extend(_check_file(path, repo_root))

    print(f"📁 검사 파일 수: {files_checked}")
    if not issues:
        print("✅ LEGAL 검사 통과 — 권유성 단어 0건")
        return 0

    print(f"🚨 권유성 단어 발견 — {len(issues)}건")
    for path, line_no, label in issues:
        rel = path.relative_to(repo_root)
        print(f"  {rel}:{line_no}: [{label}]")
    print()
    print(f"정의/예시인 경우 같은 줄 또는 직전 줄에 `{ALLOW_MARKER}` 어노테이션 추가.")
    print("예: # legal-check: allow — v7.5 호환 식별자")
    return 1


if __name__ == "__main__":
    sys.exit(main())
