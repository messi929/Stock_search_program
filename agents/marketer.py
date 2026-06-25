"""마케팅 콘텐츠 생성기 — 스레드(Threads)용 종목 글 자동 초안.

기존 자산 재활용:
  - build_instant_snapshot(): 스크리너 in-memory 스냅샷에서 안전 수치만 추출(LLM 비호출)
  - Haiku 1회(~5원): 스냅샷 → 500자 이내 스레드 글로 재가공
  - BaseAgent.filter_forbidden / 면책: LEGAL 가드(추천·목표가 금지)

0→1 마케팅 목적. 4가지 포맷(호기심/반대의견/신뢰/댓글모집)으로 생성하며,
관리자가 콘솔에서 검수·수정 후 복사(또는 Phase 2에서 자동 발행)한다.

LEGAL: 추천/매수·매도/목표가/매수가/손절가 절대 금지. 관찰·참고·중립 해석만.
스레드 500자 제약상 본문 면책은 1줄 압축 버전을 사용한다(정보제공·판단은 본인).
"""

from __future__ import annotations

import asyncio
import re
from typing import Optional

from loguru import logger
from pydantic import BaseModel, Field

from agents.base import BaseAgent
from agents.instant import build_instant_snapshot, _snapshot_facts
from utils.claude_client import MODEL_HAIKU


# ──────────────────────────────────────────────
# 포맷 정의 (4종) — docs/axis 마케팅 전략의 콘텐츠 엔진
# ──────────────────────────────────────────────

THREADS_MAX = 500  # Threads 글자 수 제한
# 본문 1줄 면책 — 풀 DISCLAIMER는 4줄이라 500자 글에 부적합.
COMPACT_DISCLAIMER = "📌 투자 권유 아님 · 정보 제공일 뿐 판단은 본인 몫 (Axis)"

FORMATS: dict[str, dict[str, str]] = {
    "curiosity": {
        "label": "호기심 (AI한테 물어봤더니)",
        "guide": (
            "'AI한테 이 종목 물어봤더니' 톤. 스냅샷 수치 1~2개를 흥미롭게 제시하고, "
            "마지막에 '근데 검증 돌려보니…' 같은 데이터 신선도/검증 포인트를 한 줄 흘려 "
            "호기심을 남긴다. 단정 금지, 관찰 표현만."
        ),
    },
    "contrarian": {
        "label": "반대의견 (반대로 보면)",
        "guide": (
            "'다들 좋다는데 반대로 보면' 톤. 스냅샷 수치에서 읽히는 약점·과열·리스크 "
            "관찰 포인트를 균형 있게 제시한다. 공포 조장/단정 금지. '이런 점은 관찰이 필요' "
            "식 중립 프레이밍. 반대 시나리오를 생각하게 만드는 게 목적."
        ),
    },
    "trust": {
        "label": "신뢰 (데이터 검증)",
        "guide": (
            "'AI 답변, 그대로 믿어도 되나?' 톤. 이 종목 수치가 며칠 전 데이터일 수 있다는 "
            "점, 그래서 현재 시점 재검증이 왜 중요한지를 종목 예시로 설명한다. Axis가 "
            "검증을 핵심으로 둔다는 브랜드 메시지를 자연스럽게. 과장 금지."
        ),
    },
    "cta": {
        "label": "댓글 모집 (종목 남겨주세요)",
        "guide": (
            "참여 유도 글. 이 종목을 짧게 예시로 들고 '궁금한 종목 댓글로 남겨주시면 "
            "AI로 양쪽(강점/약점) 다 뜯어서 관찰 포인트를 정리해 드린다'고 초대한다. "
            "추천이 아니라 '판단용 자료 제공'임을 분명히. 댓글을 부르는 한 문장으로 마무리."
        ),
    },
}

DEFAULT_FORMATS = ("curiosity", "contrarian", "cta")


_SYSTEM = """당신은 한국 주식 정보 서비스 'Axis'의 SNS(스레드) 카피라이터입니다.
주어진 종목 스냅샷 수치만으로, 스크롤을 멈추게 하는 짧은 한국어 스레드 글을 씁니다.

절대 원칙(법적 안전 — 어기면 서비스가 위법):
- 금지: 추천/추천합니다, 사세요, 매수·매도, 매수가/목표가/손절가 등 가격 제시,
  "매수 신호/시그널", "반드시·확실히 오른다", "유망주" 등 권유·단정 표현
- 허용: '관찰', '참고', '현재 ~ 구간', 수치의 중립적 해석, 질문형
- 종목명은 주어진 것만 사용(추정·창작 금지)

문체:
- 스레드 감성: 짧은 문장, 줄바꿈, 과한 이모지 금지(0~3개), 광고 티 최소화
- 사람이 쓴 듯 담백하게. 표/마크다운 금지
- hook(첫 문장)은 한 줄로 강하게, body는 3~6줄, hashtags는 2~4개(한국어 키워드, # 제외)
- 전체가 380자를 넘지 않도록(면책 문구 자리 확보)"""


class ThreadsPost(BaseModel):
    """스레드 글 구조화 출력."""

    hook: str = Field(description="첫 문장 한 줄 — 스크롤을 멈추게 하는 후킹")
    body: str = Field(description="본문 3~6줄. 줄바꿈 포함. 수치 중립 해석")
    hashtags: list[str] = Field(
        default_factory=list, description="해시태그 키워드 2~4개 (# 제외, 한국어)"
    )


class MarketerAgent(BaseAgent):
    """Haiku 기반 스레드 글 생성기."""

    def __init__(self, claude=None):
        super().__init__(
            agent_name="marketer",
            model=MODEL_HAIKU,
            system_prompt=_SYSTEM,
            claude=claude,
        )

    async def run(self, input_data: BaseModel) -> BaseModel:  # noqa: D401
        """BaseAgent 추상 메서드 충족용 — 실제 진입점은 generate()."""
        raise NotImplementedError("MarketerAgent은 generate()를 사용하세요")

    async def generate(
        self, ticker: str, fmt: str, uid: str = ""
    ) -> Optional[dict]:
        """단일 (종목 × 포맷) 초안 생성. 실패 시 None."""
        fmt = fmt if fmt in FORMATS else "curiosity"
        snapshot = build_instant_snapshot(ticker)
        if not snapshot:
            # 스냅샷 없으면(미적재 종목) 최소 정보로라도 진행
            snapshot = {"ticker": ticker.upper(), "name": ticker.upper(), "is_kr": bool(re.match(r"^\d{6}$", ticker))}

        name = snapshot.get("name") or ticker.upper()
        facts = _snapshot_facts(snapshot)
        guide = FORMATS[fmt]["guide"]
        user_msg = (
            f"{facts}\n\n"
            f"# 글 포맷\n{guide}\n\n"
            f"위 스냅샷과 포맷에 맞춰 스레드 글 한 편을 작성하세요. "
            f"종목명은 '{name}'만 사용하세요."
        )

        try:
            post, _meta = await self.call_claude_json(
                user_message=user_msg,
                schema=ThreadsPost,
                max_tokens=700,
                uid=uid,
                structured_output=True,
            )
        except Exception as e:
            logger.warning(f"[marketer] 생성 실패 {ticker}/{fmt}: {e}")
            return None

        text = assemble_post(post)
        text, found = BaseAgent.filter_forbidden(text)
        if found:
            logger.warning(f"[marketer] 금지표현 필터됨 {ticker}/{fmt}: {found}")

        return {
            "ticker": snapshot.get("ticker", ticker.upper()),
            "name": name,
            "market": snapshot.get("market", ""),
            "is_kr": bool(snapshot.get("is_kr")),
            "fmt": fmt,
            "fmt_label": FORMATS[fmt]["label"],
            "text": text,
            "char_count": len(text),
            "filtered": found,
            "source": "haiku",
        }


def assemble_post(post: ThreadsPost) -> str:
    """ThreadsPost → 발행용 본문 문자열 (hook + body + hashtags + 1줄 면책)."""
    parts: list[str] = [post.hook.strip(), post.body.strip()]
    tags = [t.strip().lstrip("#") for t in (post.hashtags or []) if t and t.strip()]
    if tags:
        parts.append(" ".join(f"#{t}" for t in tags))
    parts.append(COMPACT_DISCLAIMER)
    text = "\n\n".join(p for p in parts if p)
    return text.strip()


async def generate_batch(
    tickers: list[str], formats: list[str], uid: str = ""
) -> list[dict]:
    """여러 (종목 × 포맷) 조합을 동시 생성. 실패 항목은 제외."""
    agent = MarketerAgent()
    pairs = [(t, f) for t in tickers for f in formats]
    results = await asyncio.gather(
        *(agent.generate(t, f, uid=uid) for t, f in pairs),
        return_exceptions=True,
    )
    out: list[dict] = []
    for r in results:
        if isinstance(r, dict):
            out.append(r)
        elif isinstance(r, Exception):
            logger.warning(f"[marketer] batch 항목 예외: {r}")
    return out


def pick_hot_tickers(limit: int = 3) -> list[str]:
    """스크리너 스냅샷에서 '오늘 화제 종목' 자동 선정 — 등락 절댓값 + 거래량비 상위.

    KR 대형주 위주(노이즈 적은 종목). 데이터 없으면 빈 리스트.
    """
    try:
        from screener.api.routes import _get_combined_df

        df = _get_combined_df()
        if df is None or df.empty:
            return []
        d = df.copy()
        # KR 대형주 우선(시총 상위 300 내에서 변동성 큰 종목)
        if "market" in d.columns:
            kr = d[d["market"].isin(["KOSPI", "KOSDAQ"])]
            if not kr.empty:
                d = kr
        if "market_cap" in d.columns:
            d = d.nlargest(300, "market_cap")
        if "change_pct" not in d.columns:
            return d.head(limit)["ticker"].astype(str).tolist()
        d = d.assign(_abs=d["change_pct"].abs())
        if "volume_ratio" in d.columns:
            d = d.assign(_score=d["_abs"].fillna(0) + d["volume_ratio"].fillna(0) * 2)
        else:
            d = d.assign(_score=d["_abs"].fillna(0))
        d = d.sort_values("_score", ascending=False)
        return d.head(max(1, limit))["ticker"].astype(str).tolist()
    except Exception as e:
        logger.debug(f"[marketer] hot tickers 선정 실패: {e}")
        return []
