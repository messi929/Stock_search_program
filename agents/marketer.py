"""마케팅 콘텐츠 생성기 — 스레드(Threads)용 종목 글 자동 초안.

기존 자산 재활용:
  - build_instant_snapshot(): 스크리너 in-memory 스냅샷에서 안전 수치만 추출(LLM 비호출)
  - LLM 1회: 스냅샷 → 480자 이내 스레드 글로 재가공 (기본 Sonnet, MARKETER_MODEL=haiku 회귀 가능)
  - BaseAgent.filter_forbidden: LEGAL 가드(추천·목표가 금지)

품질 원칙(JEON 피드백 2026-06-27):
  - 실수치를 숫자 그대로 인용(≥2개). 숫자 없는 두루뭉술(_numeric_fact_count 가드로 생성 차단).
  - "AI한테 물어봤더니" 류 프레이밍 금지 — 글의 주어는 'AI'가 아니라 '수치'.

0→1 마케팅 목적. 4가지 포맷(호기심/반대의견/신뢰/댓글모집)으로 생성하며,
관리자가 콘솔에서 검수·수정 후 복사(또는 Phase 2에서 자동 발행)한다.

LEGAL: 추천/매수·매도/목표가/매수가/손절가 절대 금지. 관찰·참고·중립 해석만.
면책은 계정 프로필(bio)에 상시 고지하므로 본문에는 넣지 않는다(JEON 결정 2026-06-27).
"""

from __future__ import annotations

import asyncio
import os
from typing import Optional

from loguru import logger
from pydantic import BaseModel, Field

from agents.base import BaseAgent
from agents.instant import build_instant_snapshot, resolve_ticker, _snapshot_facts
from utils.claude_client import MODEL_HAIKU, MODEL_SONNET

# 마케팅 글 = 서비스의 얼굴 → 품질 우선 기본 Sonnet. 비용 절감 시 MARKETER_MODEL=haiku.
MARKETER_MODEL = MODEL_HAIKU if os.getenv("MARKETER_MODEL", "").lower() == "haiku" else MODEL_SONNET

# 헛글 방지 가드: 글에 인용할 실수치가 이만큼 미만이면 생성 자체를 건너뛴다.
MIN_NUMERIC_FACTS = 2


# ──────────────────────────────────────────────
# 포맷 정의 (4종) — docs/axis 마케팅 전략의 콘텐츠 엔진
# ──────────────────────────────────────────────

THREADS_MAX = 500  # Threads 글자 수 제한
# 면책은 본문이 아니라 계정 프로필(bio)에 상시 고지한다(JEON 결정 2026-06-27).
# bio가 모든 게시물에 적용되므로 본문 면책은 중복 + 광고 톤이라 제거.

FORMATS: dict[str, dict[str, str]] = {
    "curiosity": {
        "label": "호기심 (눈에 띄는 수치)",
        "guide": (
            "스냅샷에서 가장 눈에 띄는 수치 1~2개를 **숫자 그대로** 던지며 시작한다. "
            "예: '거래량이 평소의 3.1배 터졌다. 그런데 외국인은 5일째 순매도.' "
            "마지막에 '이 수치, 지금도 유효할까' 식으로 데이터 신선도/재검증 포인트를 한 줄 흘려 "
            "호기심을 남긴다. 'AI한테 물어봤더니' 류 프레이밍 금지, 단정 금지."
        ),
    },
    "contrarian": {
        "label": "반대의견 (반대로 보면)",
        "guide": (
            "'다들 좋다는데, 숫자로 보면 이런 약점도' 톤. 스냅샷의 구체 수치에서 읽히는 "
            "과열·고평가·수급 피로 같은 리스크를 **숫자를 짚어가며** 제시한다. "
            "예: 'RSI 74로 과열권 + 52주 고가 -3% 코앞, 그런데 외국인은 3일째 순매도.' "
            "공포 조장·단정 금지, 중립 프레이밍('이 수치는 관찰이 필요'). "
            "강점만 보면 놓치는 반대 시나리오를 숫자로 생각하게 만드는 게 목적."
        ),
    },
    "trust": {
        "label": "신뢰 (데이터 검증)",
        "guide": (
            "이 종목의 구체 수치(예: RSI, 등락률, 외국인 수급)를 하나 인용한 뒤, "
            "그 값이 며칠 전 데이터일 수 있다는 점과 현재 시점 재검증의 중요성을 설명한다. "
            "Axis가 '검증'을 핵심으로 둔다는 메시지를 자연스럽게. 'AI 답변' 프레이밍 대신 "
            "'숫자는 늘 갱신된다'는 관점으로. 과장 금지."
        ),
    },
    "cta": {
        "label": "댓글 모집 (종목 남겨주세요)",
        "guide": (
            "이 종목의 실제 수치 하나를 짧게 예시로 던진 뒤, '궁금한 종목 댓글로 남겨주시면 "
            "강점·약점 수치를 양쪽 다 정리해 드린다'고 초대한다. "
            "'AI한테 물어봤더니' 프레이밍 금지. 추천이 아니라 '판단용 자료 제공'임을 분명히. "
            "댓글을 부르는 한 문장으로 마무리."
        ),
    },
}

DEFAULT_FORMATS = ("curiosity", "contrarian", "cta")


_SYSTEM = """당신은 한국/미국 주식 정보 서비스 'Axis'의 SNS(스레드) 카피라이터입니다.
주어진 종목 스냅샷의 '실제 수치'로, 스크롤을 멈추게 하는 짧고 구체적인 한국어 스레드 글을 씁니다.

# 1순위 규칙 — 구체성 (어기면 글은 폐기)
- 스냅샷에 있는 **실제 숫자를 최소 2개 이상 그대로 인용**한다.
  예: "RSI 72", "외국인 8일 연속 순매수", "거래량 평소의 2.3배", "PER 14.1", "52주 고가 대비 -8%"
- 숫자에는 의미를 붙인다. 예: "RSI 72 — 과열권", "PER 14는 업종 평균보다 낮은 편"
- **금지된 헛소리(절대 쓰지 말 것)**: "뭔가 움직임이 있다", "평소와 다른 패턴",
  "관찰할 만한 수치들이 눈에 띈다", "특정 흐름/기류", "심상치 않다" 등 숫자 없는 두루뭉술한 표현.
  숫자로 못 쓰겠으면 그 문장을 통째로 빼라.

# 2순위 규칙 — 톤
- **"AI한테 물어봤더니 / AI에게 물어보니 / AI가 분석했더니" 식의 프레이밍 절대 금지.**
  글의 주어는 'AI'가 아니라 '수치'다. 데이터를 직접 보여주는 사람의 말투로 쓴다.
- 광고/홍보 티, 챗봇 말투, 과장 금지. 사람이 직접 차트 보며 쓴 듯 담백하게.

# 법적 안전 (어기면 서비스가 위법)
- 금지: 추천/추천합니다, 사세요, 매수·매도, 매수가/목표가/손절가 등 가격 제시,
  "매수 신호/시그널", "반드시·확실히 오른다", "유망주" 등 권유·단정
- 허용: 수치의 중립적 해석, '관찰', '참고', '현재 ~ 구간', 질문형
- 종목명은 주어진 것만 사용(추정·창작 금지)
- 핵심: '추천하지 마라'가 '아무 말도 하지 마라'는 뜻이 아니다 — 숫자는 구체적으로, 결론(사라/팔라)만 빼라.

# 문체
- 짧은 문장, 줄바꿈, 이모지 0~3개. 표/마크다운 금지
- hook(첫 문장)은 가장 강한 수치 하나로 시작. body는 3~6줄, hashtags는 2~4개(한국어 키워드, # 제외)
- 전체가 480자를 넘지 않도록(Threads 500자 제한 — 본문 면책 없음, 면책은 프로필 bio)"""


class ThreadsPost(BaseModel):
    """스레드 글 구조화 출력."""

    hook: str = Field(description="첫 문장 한 줄 — 스크롤을 멈추게 하는 후킹")
    body: str = Field(description="본문 3~6줄. 줄바꿈 포함. 수치 중립 해석")
    hashtags: list[str] = Field(
        default_factory=list, description="해시태그 키워드 2~4개 (# 제외, 한국어)"
    )


def _numeric_fact_count(s: dict) -> int:
    """스냅샷에서 글에 인용 가능한 '실제 수치' 개수. 헛글 가드용."""
    keys = (
        "price", "change_pct", "rsi", "per", "pbr", "roe",
        "vs_high_52w", "foreign_consecutive", "volume_ratio",
    )
    n = 0
    for k in keys:
        v = s.get(k)
        if v is None:
            continue
        try:
            if float(v) != 0.0:
                n += 1
        except (TypeError, ValueError):
            continue
    return n


class MarketerAgent(BaseAgent):
    """스레드 글 생성기 (기본 Sonnet — MARKETER_MODEL=haiku로 회귀 가능)."""

    def __init__(self, claude=None):
        super().__init__(
            agent_name="marketer",
            model=MARKETER_MODEL,
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
        # 종목명으로 입력해도 동작하게 티커 해석(예: 'HD현대일렉트릭' → '267260').
        ticker = resolve_ticker(ticker) or ticker
        snapshot = build_instant_snapshot(ticker)
        # 헛글 방지: 인용할 실수치가 부족하면 생성을 건너뛴다(숫자 없는 두루뭉술한 글 차단).
        if not snapshot or _numeric_fact_count(snapshot) < MIN_NUMERIC_FACTS:
            logger.warning(
                f"[marketer] 실수치 부족 — 생성 건너뜀 {ticker}/{fmt} "
                f"(facts={_numeric_fact_count(snapshot) if snapshot else 0}). "
                f"store 미적재 또는 데이터 결손일 수 있음."
            )
            return None

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
    """ThreadsPost → 발행용 본문 문자열 (hook + body + hashtags).

    면책 문구는 본문에 넣지 않는다 — 계정 프로필(bio)에 상시 고지(JEON 결정 2026-06-27).
    """
    parts: list[str] = [post.hook.strip(), post.body.strip()]
    tags = [t.strip().lstrip("#") for t in (post.hashtags or []) if t and t.strip()]
    if tags:
        parts.append(" ".join(f"#{t}" for t in tags))
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
