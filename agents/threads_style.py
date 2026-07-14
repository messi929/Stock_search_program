"""스레드(Threads) 공통 스타일·가드·타래 조립 — 모든 마케팅 생성기의 단일 출처.

2026-07-14. 배경: `docs/axis/THREADS_FORMAT.md`

이 파일이 생기기 전에는 문체 규칙이 생성기 5개(종목글·새벽브리핑·주말브리핑·교육·지수)에
**복붙**돼 있었고, 지어낸 수치 가드는 서사 타래에만 있었다. 톤을 바꾸려면 5곳을 고쳐야 했고,
가드는 한 곳에만 걸려 있었다. 그래서 셋을 여기로 모은다:

  ① 화자(반말/구어체) — JEON 결정 2026-07-14
  ② 결정론적 가드 — 지어낸 수치 / 방어적 사족 / 존댓말 혼입 / 자기언급
  ③ 타래 조립 — 파트 번호, 법적 필터, 홍보 파트 부착

가장 중요한 가드는 **지어낸 수치**다. 뉴스 훅과 반말은 누구나 복제한다. 우리가 남과 갈리는
지점은 글에 나오는 숫자가 진짜라는 것 하나뿐이라, 지어낸 숫자는 차별점 자체를 무너뜨린다.
"""

from __future__ import annotations

import os
import re

from pydantic import BaseModel, Field

from agents.base import BaseAgent
from utils.threads_client import MAX_TEXT, join_parts

THREADS_MAX = MAX_TEXT  # 글(=파트) 1개의 글자 한도
LLM_BUDGET = max(200, THREADS_MAX - 20)  # 파트 1개에 LLM이 쓸 수 있는 예산(여백 20자)


# ──────────────────────────────────────────────
# 홍보(CTA) — 결정론적. LLM이 쓰지 않는다 (JEON 결정 2026-07-12)
# 2026-07-14: 본문 결합 → **별도 파트(첫 댓글)**. 링크가 본문에서 빠지고 예산도 되찾는다.
# ──────────────────────────────────────────────

PROMO_ENABLED = (os.getenv("MARKETING_PROMO", "1") or "1").strip().lower() not in (
    "0", "false", "off", "no",
)

# 문구는 한 곳에서만 고친다. 두 가지만 지킨다:
#  ① 법적 안전 — 추천·매수/매도·목표가·수익률 등 권유 표현 금지. 파는 것은 '분석'이지 종목이 아니다.
#  ② 사실 — 검증 못 하는 수치(소요 시간·정확도)를 넣지 말 것. 첫 사용자가 바로 확인하는 주장이라
#     거짓이면 0→1 구간에서 가장 비싼 실수가 된다. (딥다이브 실측은 콜드 ~150초다.)
PROMO_TEXT = (
    os.getenv("MARKETING_PROMO_TEXT")
    or "📊 종목 하나를 수급·차트·밸류·매크로까지 한 번에 뜯어봅니다.\n→ axislytics.com"
)


def promo_part() -> str:
    """홍보 파트(타래의 마지막 글 = 첫 댓글). 비활성이면 빈 문자열."""
    if not PROMO_ENABLED:
        return ""
    text = (PROMO_TEXT or "").strip()
    # 단일 글 시절 본문과 홍보를 갈라주던 구분선은 별도 파트에선 의미가 없다.
    return re.sub(r"^[─—\-_]{2,}[ \t]*\n", "", text).strip()


def attach_promo(body_parts: list[str]) -> tuple[list[str], str]:
    """본문 파트 배열 → (발행할 파트 배열, 검수/복사용 단일 text). 홍보를 마지막 파트로.

    ⚠️ 반드시 **모든 LLM 단계 + 가드가 끝난 뒤** 호출할 것. 먼저 붙이면 홍보 문구의
    'Axis/axislytics'가 자기언급 가드에 걸리고, 편집 단계 후보 목록에 섞이면 모델이
    홍보를 흉내 내기 시작한다.
    """
    parts = [p.strip() for p in body_parts if p and p.strip()]
    promo = promo_part()
    if promo:
        parts.append(promo)
    return parts, join_parts(parts)


# ──────────────────────────────────────────────
# ① 화자 — 반말/구어체 (JEON 결정 2026-07-14)
# ──────────────────────────────────────────────

VOICE_RULES = """# 화자 (반말/구어체)
- 반말로 쓴다. "~습니다" 존댓말도, "~함/~임" 음슴체도 아니다. 친구한테 말하듯 "~해", "~야", "~거든", "~지".
- **반말은 훅과 해석에만.** 수치를 말할 때는 정확하게 쓴다.
  ❌ "외국인이 좀 많이 팔았어"   ✅ "외국인이 3,200억 순매도했어"
- 옆에서 같이 차트 보는 친구의 톤. "내가 정답을 알려줄게"가 아니라 "같이 숫자 까보자".
- ㅋㅋ/ㅠㅠ 남발 금지. 짧은 문장, 줄바꿈으로 호흡. 이모지 0~2개. 표/마크다운 금지.
- **순한국어로만**(한자·중국어·일본어 글자 금지). 영문 약어는 지표·지수명만 허용(RSI/PER/S&P500 등).

# 방어적 사족 금지 (자주 어긴다)
- 절대 금지: "판단은 본인이 하는 거야", "추천은 안 해", "참고만 해", "책임은 못 져",
  "투자 권유가 아니야" — 독자를 향한 말이 아니라 **우리를 향한 보험**이라 글이 죽는다.
- 안 하는 것 대신 **하는 것**을 긍정형으로 쓴다.
  ❌ "종목 추천은 안 해"   ✅ "좋은 숫자랑 나쁜 숫자를 같이 꺼내놔"
- 면책은 프로필 bio에 이미 있다. 본문에 넣지 마라.

# 독자 시점
- 글의 주어는 독자의 관심사다. 우리 서비스가 아니다.
- 절대 금지(자기언급): "Axis는~", "우리는~", "이 서비스는~", "~에서 끝내지 않아", "검증까지가 기본".
- 절대 금지(내부용어): "스냅샷", "데이터 기준". 독자는 그게 뭔지 모른다.
- 절대 금지(AI 프레이밍): "AI한테 물어봤더니". 글의 주어는 '수치'다.
- 해시태그를 쓰지 마라(# 태그 줄 금지 — 유입 기여 0인데 글자만 먹는다).
- 링크·서비스명을 쓰지 마라. 링크는 시스템이 별도 댓글로 붙인다.

# 수치 정확성 (검증 브랜드의 생명선)
- **주어진 자료에 있는 수치만** 쓴다. 기억·추측으로 숫자를 만들면 그 글은 폐기다.
- 자료에 없으면 그 문장을 빼라. 애매하면 단정 말고 관찰형으로.
- 시점 있는 수치에 '오늘/지금/현재' 금지(발행이 며칠 뒤일 수 있다). 주어진 기준일로 쓴다.

# 법적 안전 (어기면 서비스가 위법)
- 금지: 추천/추천해, 사라/팔아라, 매수·매도, 목표가·매수가·손절가, "매수 신호", "확실히 오른다", "유망주".
- 허용: 수치의 중립적 해석, 관찰, 질문형.
- 핵심: '추천하지 마라' ≠ '아무 말도 하지 마라'. 숫자는 구체적으로 쓰고 결론(사라/팔라)만 빼라.
  그리고 그걸 **변명으로 적지 마라**(위 '방어적 사족 금지')."""


def thread_rules(min_parts: int, max_parts: int, *, closing: str) -> str:
    """타래 구조 규칙. closing = 마지막 파트가 무엇으로 끝나야 하는지(생성기마다 다름)."""
    return f"""# 타래 구조 (필수)
- 파트 {min_parts}~{max_parts}개. 각 파트는 **{LLM_BUDGET}자 이내**(넘으면 발행이 안 된다).
- 각 파트는 그 자체로 읽히는 완결된 글이다. 문장을 파트 경계에서 자르지 마라.
- **1번 파트가 노출을 거의 다 먹는다.** 첫 줄에서 스크롤을 멈추게 해야 한다.
  사실만 나열하지 말고 **관점**을 준다 — 그게 스크롤을 멈추는 것이다.
- 뒷파트는 훅이 한 약속을 갚는다. 숫자와 근거는 여기 있다.
- 마지막 파트: {closing}
- 파트 번호((1/4) 등)를 본문에 넣지 마라. 시스템이 붙인다."""


# ──────────────────────────────────────────────
# 스키마 (모든 생성기 공용)
# ──────────────────────────────────────────────

class ThreadDraft(BaseModel):
    """작가 출력 — 타래 한 편."""

    parts: list[str] = Field(
        description=(
            "타래 파트 배열. 각 파트는 완결된 글 하나(500자 이내). "
            "파트 번호((1/4) 등)를 본문에 넣지 마라 — 시스템이 붙인다."
        )
    )


class EditedThread(BaseModel):
    """편집/심판 출력 — 최종본 + 메타."""

    parts: list[str] = Field(description="최종 타래 파트 배열")
    score_total: int = Field(default=0, description="루브릭 합산 점수(최종본 기준)")
    issues_fixed: list[str] = Field(default_factory=list, description="고친 문제들")
    base_candidate: int = Field(default=0, description="베이스로 고른 후보 번호(0-based)")


# ──────────────────────────────────────────────
# ② 결정론적 가드
# ──────────────────────────────────────────────

_READER_FIRST_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    # 한국어는 조사가 브랜드명에 바로 붙어("Axis는") \b 끝경계가 깨지므로 경계 없이 매칭.
    (re.compile(r"Axis|액시스", re.IGNORECASE), "자기언급(Axis)"),
    (re.compile(r"우리(는|가|의|\s)"), "자기언급(우리)"),
    (re.compile(r"이\s*(도구|서비스|앱|플랫폼)"), "자기언급(서비스)"),
    (re.compile(r"스냅샷"), "내부용어(스냅샷)"),
    (re.compile(r"데이터\s*기준"), "내부용어(데이터 기준)"),
    (re.compile(r"(끝내지|그치지|멈추지)\s*않"), "셀링멘트(끝내지 않)"),
    (re.compile(r"검증까지"), "셀링멘트(검증까지)"),
    (re.compile(r"구간에\s*있다"), "번역투(구간에 있다)"),
)

# 방어적 사족·책임전가 — JEON이 두 번 지적한 패턴(becc450, 2026-07-13).
_HEDGE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"판단은\s*(본인|너|당신|여러분)"), "사족(판단은 본인)"),
    (re.compile(r"추천(은|을)?\s*(안|하지\s*않)"), "사족(추천 안 함)"),
    (re.compile(r"책임(은|을)?\s*(안|못|지지\s*않)"), "사족(책임 전가)"),
    (re.compile(r"투자\s*권유(가|는)?\s*아니"), "사족(투자권유 아님)"),
    (re.compile(r"참고만\s*(해|하)"), "사족(참고만)"),
)

# 반말 화자에 존댓말이 섞이는 것 — 톤 붕괴.
_HONORIFIC_RE = re.compile(r"(습니다|입니다|하세요|해요|세요\b)")

# 숫자 토큰: 1,234 / 3.5 / 72. 한 자리 수(개수·순서·(n/N))는 오탐만 늘려서 보지 않는다.
_NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")

# 근사 허용 오차. "코스피 7000선"은 실제 6,941을 가리키는 수사지 지어낸 수치가 아니다.
# 이걸 잡으면 좋은 훅마다 경고가 떠서 ⓐ검수자가 경고를 무시하게 되고 ⓑ재편집이 훅을 지운다.
_NUM_TOLERANCE = 0.02


def guard_reader_first(text: str) -> list[str]:
    """자기언급·내부용어·셀링멘트 검출."""
    return [label for pat, label in _READER_FIRST_PATTERNS if pat.search(text)]


def guard_hedging(text: str) -> list[str]:
    """방어적 사족·책임전가 검출."""
    return [label for pat, label in _HEDGE_PATTERNS if pat.search(text)]


def guard_tone(text: str) -> list[str]:
    """반말 화자에 존댓말 혼입 검출."""
    return ["톤(존댓말 혼입)"] if _HONORIFIC_RE.search(text) else []


def _numbers(text: str) -> list[float]:
    """텍스트의 수치(정수부 2자리 이상)를 float로."""
    out: list[float] = []
    for m in _NUM_RE.finditer(text or ""):
        raw = m.group().replace(",", "")
        if len(raw.split(".")[0]) < 2:
            continue
        try:
            out.append(float(raw))
        except ValueError:
            continue
    return out


def guard_hallucinated_numbers(text: str, facts: str) -> list[str]:
    """본문 수치 중 자료에 근거가 없는 것 검출 — 브랜드의 생명선.

    반올림·근사(6,941 → "7000선")는 통과시킨다. 그건 수사지 데이터 주장이 아니다.
    사람이 검수하므로 경고만 남긴다(본문 강제 훼손 X).
    """
    known = _numbers(facts)
    if not known:
        return []
    unknown = [
        x
        for x in _numbers(text)
        if not any(abs(x - k) <= _NUM_TOLERANCE * max(abs(k), 1.0) for k in known)
    ]
    if not unknown:
        return []
    return [f"미확인 수치({', '.join(f'{x:g}' for x in unknown[:5])})"]


def guard_thread(parts: list[str], facts: str, *, min_parts: int, max_parts: int) -> list[str]:
    """타래 전체 가드 — 경고 라벨 리스트(비면 통과)."""
    text = "\n".join(parts)
    w: list[str] = []
    w += guard_reader_first(text)
    w += guard_hedging(text)
    w += guard_tone(text)
    w += guard_hallucinated_numbers(text, facts)
    if not (min_parts <= len(parts) <= max_parts):
        w.append(f"파트수({len(parts)} — {min_parts}~{max_parts} 권장)")
    for i, p in enumerate(parts, 1):
        if len(p) > THREADS_MAX:
            w.append(f"{i}번째 파트 길이초과({len(p)}>{THREADS_MAX})")
    return w


# ──────────────────────────────────────────────
# ③ 타래 조립
# ──────────────────────────────────────────────

def number_parts(parts: list[str]) -> list[str]:
    """(n/N) 진행 표시를 결정론적으로 부여. 모델이 쓰면 실제 개수와 어긋난다."""
    n = len(parts)
    if n <= 1:
        return list(parts)
    return [f"{p}\n\n({i}/{n})" for i, p in enumerate(parts, 1)]


def finalize_thread(body_parts: list[str]) -> tuple[list[str], str, list[str]]:
    """가드가 끝난 본문 파트 → (발행 파트, 검수용 text, 필터된 금지표현).

    법적 필터(하드 치환) → 파트 번호 → 홍보 파트 순. 홍보는 필터 뒤에 붙어야 자기언급
    가드에 걸리지 않는다.
    """
    cleaned: list[str] = []
    filtered: list[str] = []
    for p in body_parts:
        t, found = BaseAgent.filter_forbidden(p)
        cleaned.append(t.strip())
        filtered += found
    parts, text = attach_promo(number_parts(cleaned))
    return parts, text, filtered
