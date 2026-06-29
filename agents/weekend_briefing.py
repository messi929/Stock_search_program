"""주말 결산 브리핑 생성기 — 마케팅 콘텐츠 공장(스레드).

일요일 밤(22~23시 KST) 발행용. 주말 동안의 주요 소식 + 지난 금요일 미국장 마감을
정리해, **다음 거래일(보통 월요일) 한국장** 투자에 도움이 되는 중립 브리핑을 만든다.
새벽 미국시장 브리핑(agents/briefing.py)의 자매 콘텐츠 — 같은 급(Sonnet, 무슨일/왜/근거,
환각 금지, 순한국어).

데이터:
  - 지난 금요일 미국장 마감: FinanceDataReader (briefing.fetch_us_market_snapshot 재활용;
    일요일엔 FDR 마지막 종가 = 금요일이라 그대로 사용)
  - 주말 주요 소식 + 다음주 전망: utils.news_rss.fetch_weekend_news (Google News RSS)
  - 다음 거래일: utils.market_calendar.kr_next_session_hint

계정 정체성: "추천 안 함 · 양쪽 다 보여줌". 광고/CTA 없이 유틸리티 + 월요일 관전포인트.

LEGAL: 추천/매수·매도/목표가/단정 금지. 관찰·참고·중립 해석만.
면책은 본문이 아니라 계정 프로필(bio)에 상시 고지(JEON 결정 2026-06-27).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from loguru import logger

from agents.base import BaseAgent
from agents.briefing import _fmt_index_lines, fetch_us_market_snapshot
from agents.marketer import ThreadsPost, assemble_post
from utils.claude_client import MODEL_SONNET
from utils.market_calendar import kr_next_session_hint


# ──────────────────────────────────────────────
# 시스템 프롬프트
# ──────────────────────────────────────────────

_SYSTEM = """당신은 한국 주식 정보 서비스 'Axis'의 SNS(스레드) 카피라이터입니다.
계정 정체성은 "추천하지 않습니다. 양쪽 다 보여드립니다"입니다.
주말 동안의 주요 소식과 지난 금요일 미국장 마감을 받아, 한국 투자자가 일요일 밤에
1분 안에 읽고 '다음 거래일(보통 월요일) 국내장'을 준비하는 '주말 결산 브리핑' 스레드 글을 씁니다.

## 절대 원칙 (법적 안전 — 어기면 서비스가 위법)
- 금지: 추천/추천합니다, 사세요, 매수·매도, 매수가/목표가/손절가 등 가격 제시,
  "매수 신호/시그널", "반드시·확실히 오른다", "유망주" 등 권유·단정 표현
- 금지: 광고·홍보 문구, "가입하세요/구독하세요" 등 CTA, 서비스 자기홍보
- 허용: 지수 수치의 중립적 전달, '관찰', '참고', '~로 보입니다', 질문형
- 데이터에 없는 수치·종목·일정은 창작 금지(주어진 지수·뉴스 헤드라인만 사용)

## 주말 소식의 '무슨일/왜/근거' — 이 글의 핵심
주말 새 이슈나 금요일 미국장의 큰 움직임은 단순 보도가 아니라 **간단한 분석**을 한다:
1. **무슨 일**: 주말에 무엇이 있었나 / 금요일 미국장이 어떻게 마감했나 (수치·사실)
2. **왜(분석)**: 그 배경의 **구체적 촉발 요인**을 헤드라인들에서 종합해 특정한다.
   - ❌ 금지(동어반복): "투자심리 위축", "약세 흐름", "매도세 우세" 처럼 현상을 말만
     바꾼 표현 — 이건 이유가 아니다.
   - ✅ 요구: 실제 재료를 이름으로 — 특정 기업/이슈/정책/지표/지정학.
     예: "엔비디아 실적 경계", "중동 지정학 리스크 부각", "주말 사이 발표된 관세 이슈".
   - 여러 헤드라인이 같은 방향을 가리키면 묶어서 한 흐름으로 해석한다.
3. **근거**: 그 분석이 어디서 나왔는지 1개 정도 드러낸다(출처/사실).

## 다음주 일정(있으면)
- 헤드라인에 '이번주/다음주 주목' 일정(FOMC·CPI·주요 실적·옵션만기 등)이 있으면 1줄로
  '관찰 포인트'로만 언급한다. 헤드라인에 없으면 만들지 않는다.

## 환각 금지 (검증 브랜드의 생명선)
- 위 '왜/근거/일정'은 **반드시 제공된 헤드라인 안에서만** 도출한다. 헤드라인에 없는
  원인·종목·수치·일정은 절대 창작하지 않는다.
- 근거가 약하면 단정하지 말고 "~로 보입니다 / ~영향으로 관찰됩니다"처럼 관찰형으로.
- 어떤 헤드라인도 설명하지 못하면, 추측 대신 "주말 사이 뚜렷한 재료는 확인되지 않았습니다"
  라고 솔직하게 적거나 언급을 생략한다.

## 문체 (스레드 감성)
- 짧은 문장, 줄바꿈으로 호흡. 과한 이모지 금지(0~2개). 광고 티 0
- 사람이 담백하게 쓴 듯. 표/마크다운 금지
- **순한국어로만 작성**(한자·중국어·일본어 글자 금지). 영문 약어는 지수명(S&P500/SOXX/VIX)만 허용
- hook(첫 줄): '[주말 브리핑] M/D' 형태 + 한 줄 분위기
- body: ① 주말 주요 소식 1~2개(무슨일+왜) ② 지난 금요일 미국장 마감 핵심 1~2줄
       ③ 다음 거래일(월요일) 국내장 관전 포인트 1개 — **반드시 아래 '다음 거래일 상태'를 그대로 반영**.
          한국 증시는 낮(09:00~15:30)에 열린다. '오늘 국내장'·'오늘 밤 국내장' 표현 금지.
- 마지막 줄: "장 열리면 또 달라집니다" 류의 검증 뉘앙스 1줄(선택)
- 다음 거래일을 임의로 가정하지 말 것 — 제공된 '다음 거래일 상태'만 따른다.
- hashtags: 2~4개(# 제외, 한국어 키워드: 코스피/미국증시/주말브리핑 등)
- watchpoints: **비워 둔다([])**. 월요일 관전포인트는 위 body ③에 이미 포함하므로 따로 만들지 않는다.
- 전체가 480자를 넘지 않도록(Threads 500자 제한 — 본문 면책 없음, 면책은 프로필 bio)"""


class WeekendBriefingAgent(BaseAgent):
    """Sonnet 기반 주말 결산 브리핑 생성기."""

    def __init__(self, claude=None):
        # 간판 콘텐츠(주 1회) — 분석 깊이·한국어 품질을 위해 Sonnet 사용.
        super().__init__(
            agent_name="weekend_briefing",
            model=MODEL_SONNET,
            system_prompt=_SYSTEM,
            claude=claude,
        )

    async def run(self, input_data=None):  # noqa: D401
        """BaseAgent 추상 메서드 충족 — 실제 진입점은 generate()."""
        raise NotImplementedError("WeekendBriefingAgent은 generate()를 사용하세요")

    async def generate(self, uid: str = "") -> Optional[dict]:
        """주말 결산 브리핑 1편 생성. 실패 시 None.

        지수가 비어도(주말 FDR 일시 결손 등) 뉴스가 있으면 진행 — 주말 콘텐츠의
        본질은 '소식 정리'라 지수 없이도 글이 성립한다.
        """
        snap = fetch_us_market_snapshot()
        news_block = _gather_weekend_news_block()
        if not snap and not news_block:
            logger.warning("[weekend] 지수·뉴스 모두 비어 있음 — 생성 중단")
            return None

        index_block = _fmt_index_lines(snap) if snap else "- (금요일 미국장 데이터 일시 결손)"
        today = datetime.now(timezone.utc).astimezone().strftime("%m/%d")
        next_hint = kr_next_session_hint()

        user_msg = (
            f"# 오늘 날짜(한국)\n{today} (일요일 밤 발행)\n\n"
            f"# 다음 거래일 상태 (반드시 반영 — '오늘 국내장' 표현 금지)\n{next_hint}\n\n"
            f"# 지난 금요일 미국장 마감 (마지막 거래일 기준)\n{index_block}\n"
            f"{news_block}\n"
            f"위 데이터로 '주말 결산 브리핑' 스레드 글 한 편을 작성하세요. "
            f"hook 첫 줄에 [주말 브리핑] {today} 형태를 넣고, 주어진 수치·헤드라인만 사용하세요."
        )

        try:
            post, _meta = await self.call_claude_json(
                user_message=user_msg,
                schema=ThreadsPost,
                max_tokens=900,
                uid=uid,
                structured_output=True,
            )
        except Exception as e:
            logger.warning(f"[weekend] 생성 실패: {e}")
            return None

        text = assemble_post(post)
        text, found = BaseAgent.filter_forbidden(text)
        if found:
            logger.warning(f"[weekend] 금지표현 필터됨: {found}")

        return {
            "kind": "briefing",  # 검수 큐에서 브리핑 계열로 묶임(ticker/OG 숨김)
            "ticker": "",
            "name": "주말 결산 브리핑",
            "market": "US",
            "is_kr": False,
            "fmt": "weekend_briefing",
            "fmt_label": "주말 결산 브리핑",
            "text": text,
            "char_count": len(text),
            "filtered": found,
            "source": "sonnet",
            "indices": snap,  # 검수 화면에서 원본 수치 참고용
        }


def _gather_weekend_news_block() -> str:
    """주말 주요 소식 + 다음주 전망 헤드라인 → 프롬프트 보강 블록.

    주말 뉴스를 우선 사용. 비면 일반 경제 RSS로 폴백.
    """
    news: list[dict] = []
    try:
        from utils.news_rss import fetch_weekend_news

        news = fetch_weekend_news(limit=10) or []
    except Exception as e:
        logger.debug(f"[weekend] 주말 뉴스 실패: {e}")
    if not news:
        try:
            from utils.news_rss import fetch_market_news

            news = fetch_market_news(limit=8) or []
        except Exception as e:
            logger.debug(f"[weekend] 경제 뉴스 폴백 실패: {e}")
    if not news:
        return ""

    lines = [f"- [{n.get('source', '')}] {n.get('headline', '')}" for n in news[:10]]
    return (
        "\n# 주말 주요 소식 · 다음주 전망 헤드라인 (인용은 이 안에서만, 추측 금지)\n"
        + "\n".join(lines)
        + "\n"
    )


async def generate_weekend_briefing(uid: str = "") -> Optional[dict]:
    """편의 함수 — 주말 결산 브리핑 1편 생성."""
    return await WeekendBriefingAgent().generate(uid=uid)
