"""서사 타래 생성기 — 스레드 브로드캐스트의 새 기본 포맷 (2026-07-14).

배경: `docs/axis/THREADS_FORMAT.md`
  같은 계정 안에서 개별 종목 리포트는 좋아요 3, 거시 서사는 좋아요 231이 나왔다.
  우리 현행 종목글은 전자와 구조가 같았다. → **브로드캐스트는 서사, 종목은 리플라이.**

이 모듈이 만드는 것: 오늘의 사건에서 출발해 '왜 그런지 가르는 프레임'을 주고,
그 프레임을 **실측 수치로 시연**한 뒤 댓글로 초대하는 3~5파트 타래.

우리만 쓸 수 있는 글이어야 한다 (해자):
  뉴스 훅과 반말은 누구나 복제한다. 남들과 갈리는 지점은 뒷파트에 **진짜 숫자**가
  나온다는 것 하나뿐이다 — 외국인 vs 기관 수급, 업종 대비, PER vs 매출 추세.
  그래서 '데이터 근거'가 루브릭 1순위이고, 지어낸 수치는 결정론적 가드가 잡는다.

화자: **반말/구어체** (JEON 결정 2026-07-14). 단 반말은 훅·해석에만 쓰고
      수치는 정확하게 — "좀 많이 팔았어"가 아니라 "3,200억 순매도했어".

LEGAL: 추천/매수·매도/목표가 금지. 더불어 **방어적 사족도 금지**("판단은 본인이 하는 거임",
       "추천 안 함") — 독자를 향한 말이 아니라 우리를 향한 보험이라 글을 죽인다.
       면책은 프로필 bio에서 상시 고지한다.
"""

from __future__ import annotations

import asyncio
import re
from typing import Optional

from loguru import logger
from pydantic import BaseModel, Field

from agents.instant import _snapshot_facts, build_instant_snapshot
from agents.marketer import (
    ANGLE_MODEL,
    MARKETER_MODEL,
    WRITER_CANDIDATES,
    _as_of_label,
    pick_hot_tickers,
)
from agents.threads_style import (  # 문체·가드·조립의 단일 출처
    LLM_BUDGET,
    VOICE_RULES,
    EditedThread,
    ThreadDraft,
    finalize_thread,
    guard_thread,
    thread_rules,
)
from agents.base import BaseAgent

# 파트 수 — 3~5. 루트가 노출을 거의 다 먹으므로 뒷파트는 read-through 신호 + 내용 전달용.
# 상한을 낮게 잡는 또 다른 이유: 발행이 중간에 끊길 지점을 줄인다(글삭제 API가 없다).
MIN_PARTS = 3
MAX_NARRATIVE_PARTS = 5

# 파트 1개의 글자 예산.
PART_BUDGET = LLM_BUDGET

# 서사에 수치 삽화로 끌어 쓸 화제 종목 수.
EXAMPLE_TICKERS = 2


# ──────────────────────────────────────────────
# 프롬프트 — 문체·사족·법적안전은 VOICE_RULES(공통), 여기선 이 포맷 고유 규칙만
# ──────────────────────────────────────────────

_CORE = f"""# 0순위 — 이 글은 '종목 리포트'가 아니라 '세상에 대한 이야기'다
- 출발점은 **오늘의 사건**(지수 급락, 정책, 금리, 업종 쇼크 등)이다.
- 종목은 **서사의 예시로만** 등장한다. 특정 종목 하나를 평가하는 글이 되면 실패다.
- 독자가 가져가는 건 종목이 아니라 **'다음에 이런 일이 생기면 뭘 갈라봐야 하나'** 라는 도구다.

# 1순위 — 데이터 근거 (어기면 글은 폐기)
- 최소 한 파트는 **실측 수치를 의미와 함께** 담아야 한다. 이게 이 글이 남과 갈리는 유일한 지점이다.
  예: "외국인은 3,200억 순매도인데 기관은 1,100억 순매수", "PER은 업종 평균보다 낮은데 매출은 3분기째 감소"

{VOICE_RULES}

{thread_rules(MIN_PARTS, MAX_NARRATIVE_PARTS, closing="우리가 뭘 하는지 한 줄(긍정형) + **궁금한 종목을 댓글로 부르는 초대**.")}
- 1번 파트의 관점이 훅의 핵심이다 — "무서운 건 하락이 아니라, 왜 빠지는지 모른 채 버티는 거야" 같은.
- 중간 파트: 흔한 설명이 왜 설명이 아닌지 → 갈라볼 질문 → **실측 수치로 시연**."""

_ANGLE_SYSTEM = """당신은 주식 SNS 타래의 '편집 앵글'을 잡는 에디터입니다.
오늘의 사건과 실측 수치에서, 타래 한 편을 떠받칠 '단 하나의 관점'을 뽑습니다.

중요: 당신이 뽑는 건 종목에 대한 평가가 아니라 **사건에 대한 관점**입니다.
좋은 관점은 사건을 독자 자신의 문제로 바꿉니다.
  사건: "코스피 7000선 붕괴"
  관점: "무서운 건 하락이 아니라, 내 종목이 왜 빠지는지 설명 못 한 채 버티는 거다"

- event: 오늘의 사건 한 줄 (주어진 헤드라인/지수 수치에서. 지어내지 말 것)
- tension: 그 사건을 독자의 문제로 바꾸는 관점 한 문장 (작가에게 줄 방향)
- frame: 독자가 갈라봐야 할 질문 2~3개 (예: '외국인이 판 건가 기관이 판 건가')
- data_hooks: 그 프레임을 시연할 수 있는, facts에 **실제로 있는** 수치 2~4개(의미 포함)
  ⚠️ facts에 없는 숫자를 절대 만들지 마라.

추천/매수·매도/목표가 금지. '오늘/지금' 대신 주어진 기준일을 쓸 것."""

_WRITER_SYSTEM = (
    "당신은 한국 주식 스레드(Threads) 계정의 화자입니다.\n"
    "오늘의 사건에서 출발해, 독자가 스스로 판단할 도구를 쥐여주는 반말 타래를 씁니다.\n\n"
    + _CORE
)

_EDITOR_SYSTEM = (
    "당신은 SNS 타래의 냉정한 편집장입니다. 후보 타래들을 루브릭으로 채점하고,\n"
    "가장 나은 후보를 베이스로 골라 약점까지 고쳐 '최종본 한 편'을 만듭니다.\n\n"
    "# 루브릭 (각 0~5, 합산 0~35)\n"
    "1. 데이터 근거: 수치가 facts에 실제로 있는 것인가. **facts에 없는 숫자가 하나라도 있으면 0점**\n"
    "   이고 그 문장을 들어내야 한다. ← 이 글이 남과 갈리는 유일한 지점\n"
    "2. 훅: 1번 파트가 '사건 + 관점'으로 스크롤을 멈추나. 관점 없이 사건만 있으면 2점 이하\n"
    "3. 서사: 종목 리포트가 아니라 세상에 대한 이야기인가. 종목이 예시가 아니라 주인공이면 0점\n"
    "4. 톤: 반말/구어체가 일관되나. 존댓말('~습니다')이 섞이면 감점. 단 **수치를 뭉개면**\n"
    "   ('좀 많이 팔았어') 반말이어도 감점\n"
    "5. 사족 없음: 방어적 사족·책임전가('판단은 본인이', '추천 안 해', '참고만')가 0인가.\n"
    "   하나라도 있으면 0점 — 문장째 들어내고 긍정형으로 대체한다\n"
    "6. 독자시점·법적안전: 자기언급(Axis/우리)·내부용어(스냅샷)·추천·가격제시가 0인가\n"
    "7. 타래 구조: 파트가 3~5개, 각 480자 이내, 뒷파트가 훅의 약속을 갚나, 마지막이 댓글 초대인가\n\n"
    "# 출력\n"
    "- 최고 후보를 베이스로 하되, 위 7축에서 깎인 점을 직접 고쳐 최종본을 낸다.\n"
    "- 파트 번호((1/5) 등)를 본문에 넣지 마라. 시스템이 붙인다.\n"
    "- score_total은 '최종본' 기준. issues_fixed에 고친 문제를 적는다.\n\n"
    + _CORE
)

# best-of-N 다양성: 후보마다 다른 훅 스타일.
_STYLE_SEEDS = (
    "사건을 한 방으로 던지고 곧바로 관점으로 뒤집는 직설형.",
    "독자가 지금 하고 있을 행동을 짚어주며 시작하는 관찰형.",
    "흔한 설명을 먼저 인용한 뒤 그게 왜 설명이 아닌지 되묻는 반문형.",
)


# ──────────────────────────────────────────────
# 스키마
# ──────────────────────────────────────────────

class NarrativeAngle(BaseModel):
    """① 앵글 — 사건을 독자의 문제로 바꾸는 관점."""

    event: str = Field(description="오늘의 사건 한 줄(주어진 자료에서. 지어내지 말 것)")
    tension: str = Field(description="사건을 독자의 문제로 바꾸는 관점 한 문장")
    frame: list[str] = Field(default_factory=list, description="갈라볼 질문 2~3개")
    data_hooks: list[str] = Field(
        default_factory=list, description="프레임을 시연할 실측 수치 2~4개(facts에 실제로 있는 것만)"
    )


class NarrativeThread(ThreadDraft):
    """② 작가 출력 — 타래 한 편(공통 ThreadDraft)."""


def guard_all(parts: list[str], facts: str) -> list[str]:
    """④ 결정론적 가드 — 공통 guard_thread에 이 포맷의 파트 수 규칙을 얹는다."""
    return guard_thread(parts, facts, min_parts=MIN_PARTS, max_parts=MAX_NARRATIVE_PARTS)


# ──────────────────────────────────────────────
# 재료 수집 — 사건(뉴스·지수) + 실측(화제 종목)
# ──────────────────────────────────────────────

def _headlines_block() -> tuple[str, str]:
    """오늘의 사건 후보 헤드라인. (블록 문자열, 대표 기사 URL)."""
    news: list[dict] = []
    try:
        from utils.news_rss import fetch_market_news, fetch_news_search

        news = fetch_news_search(["코스피 마감", "코스닥 마감", "증시 마감"], limit=6) or []
        if len(news) < 3:
            news += fetch_market_news(limit=6) or []
    except Exception as e:
        logger.debug(f"[narrative] 뉴스 수집 실패: {e}")
    if not news:
        return "", ""
    lines = [f"- [{n.get('source', '')}] {n.get('headline', '')}" for n in news[:6]]
    return "## 오늘의 헤드라인\n" + "\n".join(lines), (news[0].get("link") or "")


def _index_block() -> str:
    """코스피/코스닥 지수 수치 — 사건의 뼈대."""
    try:
        from agents.index_chart import build_index_snapshot
    except Exception:
        return ""
    lines: list[str] = []
    for key in ("KS11", "KQ11"):
        try:
            s = build_index_snapshot(key) or {}
        except Exception as e:
            logger.debug(f"[narrative] 지수 스냅샷 실패 {key}: {e}")
            continue
        if not s or s.get("price") is None:
            continue
        bits = [f"{s.get('name', key)} {s['price']:,.2f}"]
        if s.get("change_pct") is not None:
            bits.append(f"{s['change_pct']:+.2f}%")
        if s.get("vs_ma20_pct") is not None:
            # 주어를 명시한다 — "20일선 대비 -15.6%"는 방향이 뒤집혀 읽힌다.
            bits.append(f"지수가 20일선 대비 {s['vs_ma20_pct']:+.1f}%")
        lines.append("- " + ", ".join(bits))
    return "## 지수\n" + "\n".join(lines) if lines else ""


def _examples_block(tickers: list[str]) -> tuple[str, list[dict]]:
    """화제 종목 실측 — 서사를 시연할 삽화. (블록, 스냅샷들)."""
    blocks: list[str] = []
    snaps: list[dict] = []
    for t in tickers:
        try:
            s = build_instant_snapshot(t)
        except Exception as e:
            logger.debug(f"[narrative] 종목 스냅샷 실패 {t}: {e}")
            continue
        if not s:
            continue
        snaps.append(s)
        blocks.append(f"### {s.get('name', t)}\n{_snapshot_facts(s)}")
    if not blocks:
        return "", []
    head = (
        "## 삽화용 실측 종목 (서사의 '예시'로만 써라 — 이 종목을 평가하는 글이 되면 실패다)\n"
        "여기 있는 수치만 인용할 수 있다. 없는 숫자는 지어내지 마라.\n\n"
    )
    return head + "\n\n".join(blocks), snaps


def build_facts(tickers: Optional[list[str]] = None) -> tuple[str, dict]:
    """서사 타래의 입력 facts를 조립. (facts, meta)."""
    if not tickers:
        tickers = pick_hot_tickers(limit=EXAMPLE_TICKERS)
    news_block, news_url = _headlines_block()
    idx = _index_block()
    ex, snaps = _examples_block(tickers or [])

    as_of = _as_of_label(snaps[0]) if snaps else ""
    date_note = (
        f"## 기준일 (필수)\n이 수치는 {as_of} 종가 기준이다. 시점 있는 수치는 "
        f"'오늘/지금/현재'가 아니라 '{as_of}'로 표기하라(한 번만)."
        if as_of
        else "## 기준일\n기준일 정보가 없다. '오늘/지금/현재' 시점어 없이 수치만 제시하라."
    )
    facts = "\n\n".join(b for b in (news_block, idx, ex, date_note) if b)
    meta = {
        "news_url": news_url,  # 3단계(루트 이미지 첨부)에서 쓸 기사 링크
        "example_tickers": [s.get("ticker", "") for s in snaps],
        "example_names": [s.get("name", "") for s in snaps],
    }
    return facts, meta


# ──────────────────────────────────────────────
# 하네스
# ──────────────────────────────────────────────

class NarrativeAgent(BaseAgent):
    """서사 타래 생성기 — 앵글→작가 best-of-N→편집→가드."""

    def __init__(self, claude=None):
        super().__init__(
            agent_name="narrative",
            model=MARKETER_MODEL,
            system_prompt=_WRITER_SYSTEM,
            claude=claude,
        )

    async def run(self, input_data: BaseModel) -> BaseModel:  # noqa: D401
        raise NotImplementedError("NarrativeAgent은 generate()를 사용하세요")

    async def _find_angle(self, facts: str, uid: str) -> Optional[NarrativeAngle]:
        try:
            angle, _ = await self.call_claude_json(
                user_message=(
                    f"{facts}\n\n위 자료에서 오늘의 사건 하나를 고르고, 그 사건을 독자 자신의 "
                    f"문제로 바꾸는 관점 하나를 잡아라."
                ),
                schema=NarrativeAngle,
                system=_ANGLE_SYSTEM,
                model=ANGLE_MODEL,
                max_tokens=700,
                uid=uid,
                structured_output=True,
            )
            return angle
        except Exception as e:
            logger.warning(f"[narrative] 앵글 실패: {e} — 앵글 없이 진행")
            return None

    async def _write_one(
        self, facts: str, brief: str, seed: str, uid: str
    ) -> Optional[NarrativeThread]:
        try:
            post, _ = await self.call_claude_json(
                user_message=(
                    f"{facts}\n\n{brief}\n\n# 이 후보의 훅 스타일\n{seed}\n\n"
                    f"위 앵글로 스레드 타래 한 편({MIN_PARTS}~{MAX_NARRATIVE_PARTS}파트)을 작성하라."
                ),
                schema=NarrativeThread,
                max_tokens=1600,
                uid=uid,
                structured_output=True,
            )
            return post
        except Exception as e:
            logger.warning(f"[narrative] 작가 후보 실패: {e}")
            return None

    async def _write_candidates(self, facts: str, brief: str, uid: str) -> list[NarrativeThread]:
        seeds = [_STYLE_SEEDS[i % len(_STYLE_SEEDS)] for i in range(WRITER_CANDIDATES)]
        results = await asyncio.gather(
            *(self._write_one(facts, brief, s, uid) for s in seeds), return_exceptions=True
        )
        out: list[NarrativeThread] = []
        for r in results:
            if isinstance(r, NarrativeThread) and (r.parts or []):
                out.append(r)
            elif isinstance(r, Exception):
                logger.warning(f"[narrative] 후보 예외: {r}")
        return out

    async def _edit_and_pick(
        self,
        candidates: list[NarrativeThread],
        facts: str,
        brief: str,
        uid: str,
        repair_note: str = "",
    ) -> Optional[EditedThread]:
        listing = "\n\n".join(
            f"## 후보 {i}\n" + "\n\n--- 파트 경계 ---\n\n".join(c.parts)
            for i, c in enumerate(candidates)
        )
        user_msg = (
            f"{facts}\n\n{brief}\n\n# 후보 타래 ({len(candidates)}개)\n{listing}\n\n"
            f"위 후보들을 루브릭으로 채점하고, 최고를 베이스로 골라 약점까지 고쳐 최종본 한 편을 내라."
        )
        if repair_note:
            user_msg += f"\n\n⚠️ 반드시 고칠 것: {repair_note}"
        try:
            edited, _ = await self.call_claude_json(
                user_message=user_msg,
                schema=EditedThread,
                max_tokens=2000,
                uid=uid,
                system=_EDITOR_SYSTEM,
                structured_output=True,
            )
            return edited
        except Exception as e:
            logger.warning(f"[narrative] 편집 실패: {e}")
            return None


def _brief(angle: NarrativeAngle) -> str:
    """앵글 → 작가/편집 입력용 브리핑."""
    out = [f"# 편집 앵글(이 관점 하나로 타래를 수렴시켜라)\n사건: {angle.event}\n관점: {angle.tension}"]
    if angle.frame:
        out.append("갈라볼 질문: " + " / ".join(angle.frame))
    if angle.data_hooks:
        out.append("시연에 쓸 실측 수치(facts에 있는 것): " + ", ".join(angle.data_hooks))
    return "\n".join(out)


async def generate_narrative(
    tickers: Optional[list[str]] = None, uid: str = ""
) -> Optional[dict]:
    """서사 타래 초안 1건 생성. 실패 시 None."""
    facts, meta = build_facts(tickers)
    if not facts.strip():
        logger.warning("[narrative] 재료 없음(뉴스·지수·종목 모두 결손) — 생성 건너뜀")
        return None

    # 헛글 방지 — 삽화 수치가 없으면 쓰지 않는다.
    # 뉴스 훅 + 반말만 있는 글은 누구나 쓴다. 실측 수치가 빠지면 이 포맷의 존재 이유가
    # 통째로 사라지므로, 그런 글은 생성 자체를 거부한다(종목글의 MIN_NUMERIC_FACTS와 같은 원칙).
    if not meta["example_tickers"]:
        logger.warning(
            "[narrative] 삽화용 실측 종목 0개 — 생성 건너뜀. "
            "종목 store 미적재(잡이면 _prime_name_store 필요)이거나 스크리너 데이터 결손."
        )
        return None

    agent = NarrativeAgent()
    angle = await agent._find_angle(facts, uid)
    brief = _brief(angle) if angle else "# 편집 앵글\n(앵글 실패 — facts에서 직접 관점을 잡아라)"

    candidates = await agent._write_candidates(facts, brief, uid)
    if not candidates:
        logger.warning("[narrative] 작가 후보 0개 — 생성 실패")
        return None

    edited = await agent._edit_and_pick(candidates, facts, brief, uid)
    if edited is None or not (edited.parts or []):
        logger.warning("[narrative] 편집 실패 — 첫 후보로 폴백")
        edited = EditedThread(parts=candidates[0].parts)

    body_parts = [p.strip() for p in edited.parts if p and p.strip()]
    warnings = guard_all(body_parts, facts)

    # 가드에 걸리면 1회 재편집. 지어낸 수치·방어적 사족·길이는 사람이 손대기 전에 모델이 고친다.
    repair = [w for w in warnings if not w.startswith("파트수")]
    if repair:
        logger.info(f"[narrative] 가드 재편집: {repair}")
        repaired = await agent._edit_and_pick(
            candidates,
            facts,
            brief,
            uid,
            repair_note=(
                " / ".join(repair)
                + " — 특히 facts에 없는 숫자는 그 문장째 들어내라. 방어적 사족은 긍정형으로 바꿔라."
            ),
        )
        if repaired is not None and (repaired.parts or []):
            edited = repaired
            body_parts = [p.strip() for p in edited.parts if p and p.strip()]
            warnings = guard_all(body_parts, facts)
            if warnings:
                logger.warning(f"[narrative] 재편집 후에도 잔존: {warnings}")

    # 법적 필터 → 파트 번호 → 홍보 파트. 전부 공통 조립기가 한다.
    parts, text, filtered = finalize_thread(body_parts)
    if filtered:
        logger.warning(f"[narrative] 금지표현 필터됨: {filtered}")

    return {
        "kind": "narrative",
        "ticker": "",
        "name": (angle.event[:40] if angle else "서사 타래"),
        "market": "KR",
        "is_kr": True,
        "fmt": "narrative",
        "fmt_label": "🧵 서사 타래",
        "parts": parts,
        "text": text,
        "char_count": len(parts[0]) if parts else 0,
        "filtered": filtered,
        "warnings": warnings,
        "score": edited.score_total,
        "angle": (angle.tension if angle else ""),
        "archetype": "서사",
        "source": "narrative-v1",
        "news_url": meta["news_url"],
        "example_tickers": meta["example_tickers"],
    }
