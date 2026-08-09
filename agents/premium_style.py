"""네이버 프리미엄콘텐츠 컬럼 문체·조립 — **프리미엄 트랙 단일 출처**.

2026-08-09 신설. 근거: `docs/axis/NAVER_PREMIUM.md` (특히 §7-0-1 실제 글 해부)

⚠️ `agents/threads_style.py`와 **완전히 별개다.** 두 채널은 별도 트랙으로 운영한다(JEON 결정
2026-08-09). 전제가 하나도 겹치지 않으므로 공유하면 둘 다 망가진다:

  |            | 스레드                  | 프리미엄콘텐츠            |
  |------------|------------------------|--------------------------|
  | 길이        | 파트당 500자 하드 한도    | 10,000~17,000자          |
  | 화자        | 반말                    | **존댓말**                |
  | 구조        | 타래(파트 배열)          | 단일 장문 + 섹션 위계      |
  | 면책        | bio에만(본문 금지)       | **본문 말미에 필수**       |
  | 발행        | API 자동                | **API 없음 — 수동 복붙**   |

면책이 정반대인 것에 주의. 스레드에서 본문 면책은 '방어적 사족'이라 글을 죽이지만, 프리미엄
콘텐츠 재테크 판에서는 **표준 관행**이다(§7-0-1 관찰 5 — 상위 채널 글이 전부 달고 있다).

수치 가드는 두 트랙 공용이라 `threads_style`에서 순수 함수만 가져다 쓴다. 문체·조립은
공유하지 않는다.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timezone

from pydantic import BaseModel, Field

from agents.base import BaseAgent

# 순수 함수만 재사용 — 채널 전제와 무관한 범용 가드다.
from agents.threads_style import guard_hallucinated_numbers, guard_reader_first

# 목표 분량. 알파킨 실측 16,956자(§7-0-1)를 상한 기준으로 잡는다.
# 하한을 6,000으로 두는 이유: 이보다 짧으면 블로그 글이지 컬럼이 아니다.
COLUMN_MIN_CHARS = 6_000
COLUMN_TARGET_CHARS = 12_000
COLUMN_MAX_CHARS = 18_000


# ──────────────────────────────────────────────
# ① 텍스트 기호 위계 — 결정론적. LLM이 그리지 않는다.
# ──────────────────────────────────────────────
#
# 프리미엄콘텐츠는 발행 API가 없어서 스튜디오 에디터에 **복붙**해야 한다. 서식(굵기·색·헤딩)은
# 붙여넣기에서 깨지지만 **문자 자체는 안 깨진다.** 상위 채널이 `█ ▌ ─── ━━━` 같은 기호로
# 위계를 만드는 이유가 이것으로 보인다 — 이미지 0장으로도 구조가 살고, 복붙에도 살아남는다.
#
# 그래서 이 기호들은 LLM에게 시키지 않고 코드가 붙인다. 모델에게 맡기면 매번 달라져서
# 연재물의 시각적 일관성이 무너진다(스레드 (n/N) 번호를 코드가 붙이는 것과 같은 이유).

MARK_SECTION = "█"   # 섹션 본문 소제목
MARK_SUB = "▌"       # 하위 소제목
MARK_RULE = "───"    # 항목 구분선
MARK_HEAVY = "━━━"   # 체크리스트 구분선
MARK_NOTICE = "██"   # 면책 등 고지


def section_head(no: int, headline_stat: str, title: str) -> str:
    """섹션 헤더 — `[  0 1  ]` + 대표 수치 + `█ 소제목`.

    알파킨 구조 그대로다(§7-0-1). 대표 수치를 헤더에 올리는 게 핵심 — 독자가 섹션을
    스캔하면서 숫자만 훑어도 논지가 따라온다.
    """
    return f"[  0 {no}  ]\n\n  {headline_stat}  \n\n{MARK_SECTION}  {title}"


def rule_item(label: str, value: str, note: str = "") -> str:
    """구분선 + 라벨/수치/한 줄 해석. 업종·종목 나열의 기본 단위."""
    body = f"{MARK_RULE}\n\n  {label}  \n\n{value}"
    return f"{body}\n\n{note}" if note else body


def check_item(when: str, what: str, why: str = "") -> str:
    """'다음 주 확인할 자리' 체크리스트 한 줄."""
    body = f"{MARK_HEAVY}\n\n  {when}  \n\n▹ {what}"
    return f"{body}\n\n{why}" if why else body


def breathe(text: str) -> str:
    """한 문장마다 개행 — 모바일 가독성.

    상위 채널 공통 관행이다(§7-0-1 관찰 3). 마침표 뒤에서만 끊고, 소수점·약어는 건드리지
    않는다. 이미 개행된 곳은 그대로 둔다.
    """
    out = re.sub(r"(?<=[가-힣\)])\.\s+(?=[가-힣\[\(])", ".\n\n", text or "")
    return re.sub(r"\n{4,}", "\n\n\n", out)


# ──────────────────────────────────────────────
# ② 면책 — 이 판의 표준 관행 (스레드와 정반대)
# ──────────────────────────────────────────────

DISCLAIMER = (
    f"{MARK_NOTICE}  이 글은 투자 권유가 아닙니다.\n\n"
    f"{MARK_NOTICE}  투자 판단과 그 결과의 책임은 투자자 본인에게 있습니다."
)


# ──────────────────────────────────────────────
# ③ 주차 연번 — 연재물 신호
# ──────────────────────────────────────────────

def week_label(d: date | None = None) -> str:
    """ISO 주차 라벨. 알파킨이 `32주차(8/3~8/7)`로 쓰는 그 형식."""
    d = d or datetime.now(timezone.utc).date()
    iso = d.isocalendar()
    return f"{iso.week}주차"


def week_range_label(start: date, end: date) -> str:
    """`32주차(8/3~8/7)` 전체 라벨."""
    return f"{week_label(start)}({start.month}/{start.day}~{end.month}/{end.day})"


# ──────────────────────────────────────────────
# ④ 화자 — 존댓말 컬럼
# ──────────────────────────────────────────────

COLUMN_VOICE = f"""# 화자 (존댓말 컬럼)
- **존댓말로 씁니다.** "~습니다", "~입니다". 반말·음슴체 금지.
- 애널리스트가 쓰는 주간 컬럼의 톤입니다. 친근함이 아니라 **정확함**이 신뢰를 만듭니다.
- 1인칭 관점 표명은 허용하되 남발하지 않습니다. 주어는 대부분 **수치**입니다.
- **한 문장마다 줄을 바꿉니다.** 모바일에서 읽히는 형태입니다. 문단을 뭉치지 마세요.
- 순한국어로 씁니다(한자·중국어·일본어 글자 금지). 영문 약어는 지표·지수·종목명만.

# 이 글이 남과 갈리는 지점 (가장 중요)
- 뉴스 해설은 누구나 씁니다. 우리가 파는 것은 **데이터 조립**입니다.
- 업종 전체 등락, 규모별(대형/중형/소형) 분화, 종목별 기여, 거래대금 귀속, 수급 주체 —
  **이 수치들을 서로 연결해서 하나의 인과로 만드는 것**이 이 글의 본체입니다.
- "지수가 빠졌습니다"는 정보가 아닙니다. "23개 업종 중 16개가 올랐는데 지수가 빠졌습니다.
  전기전자 하나가 -11.04%였기 때문입니다"가 정보입니다.

# 수치 정확성 (생명선)
- **주어진 자료에 있는 수치만** 씁니다. 기억·추측으로 숫자를 만들면 그 글은 폐기입니다.
- 자료에 없으면 그 문장을 뺍니다. 애매하면 단정하지 말고 관찰형으로.
- 시점 있는 수치에 '오늘/지금/현재' 금지(발행이 며칠 뒤일 수 있습니다). 주어진 기준일로.
- 종목명·티커를 추측하지 마세요. 자료에 있는 것만 씁니다.

# 법적 안전 (어기면 서비스가 위법)
- 금지: 추천/추천합니다, 사세요/파세요, 매수·매도, 목표가·매수가·손절가, "매수 신호",
  "확실히 오릅니다", "유망주".
- 허용: 수치의 중립적 해석, 관찰, 질문형, 시나리오 양방 제시.
- 핵심: '추천하지 않는다' ≠ '아무 말도 하지 않는다'. 숫자는 구체적으로 쓰고 결론만 뺍니다.
- 면책 문구는 **시스템이 말미에 자동으로 붙입니다.** 본문에 직접 쓰지 마세요.

# 자기언급 금지
- 절대 금지: "Axis는~", "우리 서비스는~", "이 도구는~", "AI가 분석한 결과".
- 글의 주어는 수치이고 화자는 필자입니다. 서비스가 아닙니다.

# 제목
- 관찰 + 반전으로 만듭니다. 구체 수치를 하나 넣습니다.
  ✅ "코스피 -5.1%인데 오른 종목이 더 많았습니다 — 돈은 반도체 한 곳에서만 나갔습니다"
  ❌ "이번 주 증시 리뷰" (검색도 안 되고 클릭도 안 됩니다)"""


COLUMN_STRUCTURE = f"""# 구조 (필수)
- 도입: 대표 수치 제시 → 대조되는 수치 → 전 주 대비 → **이 글이 무엇을 추적하는지 선언**.
  예: "그 격차가 어디서 왔는지를 돈의 이동 경로로 따라갑니다."
- 본문: 섹션 3~5개. 각 섹션은 **대표 수치 하나**를 머리에 세우고 그것을 해부합니다.
- 마무리: `다음 주 확인할 자리` — 날짜별 체크리스트. 관찰 대상이지 지시가 아닙니다.
- 전체 {COLUMN_MIN_CHARS:,}자 이상, {COLUMN_TARGET_CHARS:,}자 내외를 목표로 합니다.
  **짧으면 반려됩니다.** 이 판의 경쟁 글은 17,000자입니다.
- 섹션 기호(`[  0 1  ]`, `{MARK_SECTION}`, `{MARK_RULE}`)는 **시스템이 붙입니다.**
  본문에 직접 그리지 마세요. 각 섹션의 제목·대표수치·항목만 채우면 됩니다."""


# ──────────────────────────────────────────────
# ⑤ 스키마
# ──────────────────────────────────────────────

class ColumnSection(BaseModel):
    """컬럼의 섹션 하나."""

    headline_stat: str = Field(description="섹션 머리에 세울 대표 수치. 예: '-11.04%'")
    title: str = Field(description="섹션 소제목. 관찰을 담은 한 문장")
    body: str = Field(description="섹션 본문. 존댓말, 자료에 있는 수치만")


class ColumnDraft(BaseModel):
    """컬럼 한 편."""

    title: str = Field(description="글 제목 — 관찰 + 반전 + 구체 수치")
    lede: str = Field(description="도입부. 대표 수치 → 대조 → 추적 선언")
    sections: list[ColumnSection] = Field(description="본문 섹션 3~5개")
    watchlist: list[str] = Field(
        default_factory=list,
        description="'다음 주 확인할 자리' 항목. '날짜 | 무엇 | 왜' 형식 문자열",
    )


# ──────────────────────────────────────────────
# ⑥ 가드 — 프리미엄 전용
# ──────────────────────────────────────────────

# 존댓말 컬럼에 반말이 섞이는 것. 스레드 `guard_tone`의 정확한 역방향이다.
#
# ⚠️ 평서형 '~다'(무너졌다/올랐다)는 **잡지 않는다.** 그건 반말이 아니라 문어체다.
#    잡아야 하는 것은 구어체 반말 종결이다 — 스레드 생성기에서 문장을 가져다 붙일 때
#    실제로 새어 들어오는 형태가 이쪽이다.
_CASUAL_RE = re.compile(
    r"(았어|었어|였어|거든|잖아|줄게|해봐|알려줄"
    r"|[가-힣](야|지|네|어)\s*[.!?…]"      # 문장 끝 반말 종결
    r"|(보자|같아|이야|이지)\s*[.!?…\n]|(보자|같아|이야|이지)$)",
    re.MULTILINE,
)

# 본문에 면책을 직접 쓰면 시스템 부착분과 중복된다.
_DISCLAIM_RE = re.compile(r"투자\s*권유(가|는)?\s*아닙니다|본인에게\s*있습니다")


def guard_casual(text: str) -> list[str]:
    """존댓말 화자에 반말 혼입 검출."""
    return ["톤(반말 혼입)"] if _CASUAL_RE.search(text) else []


def guard_duplicate_disclaimer(text: str) -> list[str]:
    """본문에 면책이 직접 쓰였는지 — 시스템이 붙이므로 중복이다."""
    return ["면책 중복(본문에 직접 작성)"] if _DISCLAIM_RE.search(text) else []


def _factual_part(text: str) -> str:
    """수치 대조 대상 구간만 남긴다 — 도입부 + 섹션 본문.

    잘라내는 두 구간은 **원리적으로 자료와 대조할 수 없는 것들**이다:
      · `다음 주 확인할 자리` — 앞으로의 일정. 미래 날짜는 스냅샷에 있을 수가 없다.
      · 시스템 면책 — 우리가 붙인 고정 문구.
    이걸 안 자르면 **모든 초안에서 경고가 뜬다.** 그러면 검수자가 경고를 무시하게 되고,
    정작 진짜 환각을 놓친다(threads_style의 근사 허용과 같은 이유의 조치다).
    """
    head = (text or "").split(f"{MARK_SUB} 다음 주 확인할 자리")[0]
    return head.replace(DISCLAIMER, "")


def guard_column(text: str, facts: str) -> list[str]:
    """컬럼 전체 가드 — 경고 라벨 리스트(비면 통과).

    사람이 검수하므로 경고만 남기고 본문을 훼손하지 않는다. 다만 길이 미달은
    이 판에서 치명적이라 반드시 경고로 띄운다.
    """
    checkable = _factual_part(text)
    w: list[str] = []
    w += guard_reader_first(text)
    w += guard_casual(checkable)
    w += guard_duplicate_disclaimer(checkable)
    w += guard_hallucinated_numbers(checkable, facts)
    n = len(text)
    if n < COLUMN_MIN_CHARS:
        w.append(f"길이 미달({n:,}자 < {COLUMN_MIN_CHARS:,}자)")
    elif n > COLUMN_MAX_CHARS:
        w.append(f"길이 초과({n:,}자 > {COLUMN_MAX_CHARS:,}자)")
    return w


# ──────────────────────────────────────────────
# ⑦ 조립 — 기호 위계 부착 + 면책
# ──────────────────────────────────────────────

def assemble_column(draft: ColumnDraft) -> tuple[str, list[str]]:
    """ColumnDraft → (스튜디오에 붙여넣을 전문, 필터된 금지표현).

    법적 필터를 먼저 돌리고(치환) → 기호 위계를 붙이고 → 면책을 맨 뒤에 단다.
    면책은 필터 뒤에 붙어야 '권유가 아닙니다'가 필터에 걸리지 않는다.
    """
    filtered: list[str] = []

    def clean(s: str) -> str:
        t, found = BaseAgent.filter_forbidden(s or "")
        filtered.extend(found)
        return t.strip()

    blocks: list[str] = [breathe(clean(draft.lede))]

    for i, sec in enumerate(draft.sections, 1):
        blocks.append(
            section_head(i, clean(sec.headline_stat), clean(sec.title))
        )
        blocks.append(breathe(clean(sec.body)))

    if draft.watchlist:
        blocks.append(f"{MARK_SUB} 다음 주 확인할 자리")
        for raw in draft.watchlist:
            bits = [b.strip() for b in str(raw).split("|")]
            when = clean(bits[0]) if bits else "상시"
            what = clean(bits[1]) if len(bits) > 1 else ""
            why = clean(bits[2]) if len(bits) > 2 else ""
            blocks.append(check_item(when, what, why))

    blocks.append(DISCLAIMER)
    return "\n\n\n".join(b for b in blocks if b), filtered
