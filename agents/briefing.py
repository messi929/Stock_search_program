"""새벽 미국시장 브리핑 생성기 — 마케팅 콘텐츠 공장(스레드).

간밤 미국 지수(S&P500/나스닥/다우/반도체/VIX/환율)를 FinanceDataReader로 수집 →
공개 RSS 경제 헤드라인으로 보강 → Haiku 1회로 **중립·법적안전** 스레드 브리핑 생성.

계정 정체성: "추천 안 함 · 양쪽 다 보여줌". 광고/CTA 없이 유틸리티 + 오늘 국내장
관전포인트. 매일 아침 자동 발행(검수 큐 경유)용.

LEGAL: 추천/매수·매도/목표가/단정 금지. 관찰·참고·중립 해석만.
면책은 본문이 아니라 계정 프로필(bio)에 상시 고지(JEON 결정 2026-06-27).
"""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from loguru import logger

from agents.base import BaseAgent
from agents.marketer import ThreadsPost, assemble_post
from utils.claude_client import MODEL_SONNET
from utils.market_calendar import kr_market_status_hint, us_market_closed

_KST = ZoneInfo("Asia/Seoul")


def _kst_today() -> date:
    """현재 KST 날짜. 컨테이너 TZ 설정에 의존하지 않도록 명시적으로 Asia/Seoul을 쓴다."""
    return datetime.now(timezone.utc).astimezone(_KST).date()


# ──────────────────────────────────────────────
# 지수 스냅샷 (LLM 비호출 — FinanceDataReader)
# ──────────────────────────────────────────────

# (key, 표시라벨, FDR 심볼) — 간밤 미국장 + 한국장 연결 지표
_INDICES: tuple[tuple[str, str, str], ...] = (
    ("sp500", "S&P500", "US500"),
    ("nasdaq", "나스닥", "IXIC"),
    ("dow", "다우", "DJI"),
    ("sox", "필라델피아 반도체(SOXX)", "SOXX"),
    ("vix", "VIX 변동성", "VIX"),
    ("usdkrw", "원/달러 환율", "USD/KRW"),
)


def fetch_us_market_snapshot() -> dict:
    """간밤 미국 지수 스냅샷. {key: {label, last, change_pct, date}}.

    각 지표는 일별 종가 시계열의 마지막 2개로 등락률 계산(불완전 바는 dropna로 제외).
    실패한 지표는 graceful하게 생략.
    """
    try:
        import FinanceDataReader as fdr
    except Exception as e:  # pragma: no cover
        logger.warning(f"[briefing] FinanceDataReader import 실패: {e}")
        return {}

    out: dict = {}
    for key, label, sym in _INDICES:
        try:
            df = fdr.DataReader(sym)
            if df is None or df.empty or "Close" not in df.columns:
                continue
            closes = df["Close"].dropna()
            if len(closes) < 1:
                continue
            last = float(closes.iloc[-1])
            chg = None
            if len(closes) >= 2:
                prev = float(closes.iloc[-2])
                chg = (last / prev - 1.0) * 100.0 if prev else None
            out[key] = {
                "label": label,
                "last": last,
                "change_pct": chg,
                "date": str(closes.index[-1].date()),
            }
        except Exception as e:
            logger.debug(f"[briefing] 지수 수집 실패 {label}({sym}): {e}")
    return out


# 신선도 판단은 미국 '주식' 세션 기준만 — usdkrw(원/달러)는 24/5 FX라 월요일 아침
# (KST)엔 이미 당일 날짜를 가져, 미 주식 휴장 여부를 흐린다. 그래서 FX는 제외한다.
# (VIX는 Cboe 미 정규장 시간 상품이라 주식 세션과 정렬됨 → 포함.)
_US_EQUITY_KEYS = ("sp500", "nasdaq", "dow", "sox", "vix")


def latest_us_session_date(snap: dict) -> Optional[date]:
    """스냅샷의 미국 '주식' 지표 중 가장 최근 종가일(date). 없으면 None. FX(usdkrw) 제외."""
    dates = _equity_dates(snap)
    return max(dates) if dates else None


def _equity_dates(snap: dict) -> list[date]:
    """스냅샷 미국 '주식' 지표들의 종가일 목록(FX 제외, 파싱 실패는 생략)."""
    out: list[date] = []
    for key in _US_EQUITY_KEYS:
        ds = (snap.get(key) or {}).get("date")
        if not ds:
            continue
        try:
            out.append(date.fromisoformat(ds))
        except (ValueError, TypeError):
            continue
    return out


def consensus_us_session_date(snap: dict) -> Optional[date]:
    """미국 '주식' 지표들의 '합의' 종가일. 없으면 None. FX(usdkrw) 제외.

    max()가 아니라 **최빈값(mode)** 을 쓴다 — FDR 소스가 지수마다 달라서 어느 한 지표가
    휴장일에 팬텀 바(예: 관측휴장일 종가)를 뱉어도, 다수 지표의 합의 날짜가 그 이상치에
    끌려가지 않게 한다. (max()는 지표 1개만 오염돼도 신선하다고 오판했다.)
    동률이면 보수적으로 더 이른(작은) 날짜를 택한다 — 신선하다고 과신하지 않기 위해.
    """
    dates = _equity_dates(snap)
    if not dates:
        return None
    counts = Counter(dates)
    top = max(counts.values())
    return min(d for d, c in counts.items() if c == top)


def us_session_is_stale(snap: dict, today: Optional[date] = None) -> tuple[bool, str]:
    """간밤 브리핑할 '신규' 미국 세션이 없으면 (True, 사유). 있으면 (False, "").

    2중 방어:
      (1) 캘린더(정밀·주력): KST '오늘'의 간밤에 해당하는 미 세션일(= 오늘−1일, ET)이
          NYSE 휴장(주말·미 공휴일·Good Friday 등)이면 애초에 브리핑할 실장이 없다 →
          stale. 이것이 미 공휴일(예: 독립기념일 관측휴장 다음 KST 토요일 아침)을 원천
          차단한다. 데이터 신선도 추론에 앞서 '달력상 장이 열렸나'를 먼저 본다.
      (2) 데이터 신선도(백업): 스냅샷 합의 종가일이 KST 오늘보다 2일 이상 과거면 묵은
          값 → stale. 캘린더 라이브러리가 결손돼 (1)이 놓쳐도 단일 휴장은 여기서 걸린다.
          (미 종가일은 날짜변경선상 KST보다 하루 뒤 → 정상=diff 1.)

    today(KST 날짜)를 명시 인자로 받는다. 기본값은 컨테이너 TZ에 의존하지 않는 KST.
    """
    today = today or _kst_today()

    # (1) 간밤 미 세션 캘린더 확인 — KST 오늘의 직전 미 세션은 ET 기준 (오늘−1)일.
    overnight_et = today - timedelta(days=1)
    closed, reason = us_market_closed(overnight_et)
    if closed:
        return True, f"overnight_closed:{overnight_et}({reason})"

    # (2) 데이터 신선도 백업.
    sess = consensus_us_session_date(snap)
    if sess is None:
        return True, "no_data"
    diff = (today - sess).days
    if diff >= 2:
        return True, f"stale_data:{sess}(diff={diff})"

    return False, ""


def _fmt_index_lines(snap: dict) -> str:
    """지수 스냅샷 → Haiku 입력용 한국어 팩트 목록."""
    lines: list[str] = []
    for key, label, _sym in _INDICES:
        d = snap.get(key)
        if not d:
            continue
        last = d.get("last")
        chg = d.get("change_pct")
        if key == "usdkrw":
            val = f"{last:,.1f}원" if last is not None else "-"
        elif key == "vix":
            val = f"{last:,.2f}" if last is not None else "-"
        else:
            val = f"{last:,.2f}" if last is not None else "-"
        chg_s = f" ({chg:+.2f}%)" if chg is not None else ""
        lines.append(f"- {label}: {val}{chg_s}")
    return "\n".join(lines)


# ──────────────────────────────────────────────
# 시스템 프롬프트
# ──────────────────────────────────────────────

_SYSTEM = """당신은 한국 주식 정보 서비스 'Axis'의 SNS(스레드) 카피라이터입니다.
계정 정체성은 "추천하지 않습니다. 양쪽 다 보여드립니다"입니다.
간밤 미국 증시 데이터를 받아, 한국 투자자가 아침에 1분 안에 읽는 '새벽 미국시장 브리핑'
스레드 글을 씁니다.

## 절대 원칙 (법적 안전 — 어기면 서비스가 위법)
- 금지: 추천/추천합니다, 사세요, 매수·매도, 매수가/목표가/손절가 등 가격 제시,
  "매수 신호/시그널", "반드시·확실히 오른다", "유망주" 등 권유·단정 표현
- 금지: 광고·홍보 문구, "가입하세요/구독하세요" 등 CTA, 서비스 자기홍보
- 허용: 지수 수치의 중립적 전달, '관찰', '참고', '~로 보입니다', 질문형
- 데이터에 없는 수치·종목은 창작 금지(주어진 지수·뉴스만 사용)

## 등락 '이유'(왜) + 근거 — 이 글의 핵심
크게 움직인 부분(예: 반도체 급락, 빅테크 약세)은 단순 보도가 아니라 **간단한 분석**을 한다:
1. **무슨 일**: 무엇이 얼마나 움직였나 (수치)
2. **왜(분석)**: 그 움직임의 **구체적 촉발 요인**을 헤드라인들에서 종합해 특정한다.
   - ❌ 금지(동어반복): "매도세가 우세", "투자심리 위축", "약세 흐름" 처럼 가격 현상을
     말만 바꾼 표현 — 이건 이유가 아니다.
   - ✅ 요구: 실제 촉발 재료를 이름으로 — 특정 기업/이슈/정책/지표.
     예: "오픈AI IPO 연기설에 AI·반도체 투심이 식음", "마이크론 실적 발표 경계감",
     "금리 우려", "특정 빅테크 실적 실망".
   - 여러 헤드라인이 같은 방향을 가리키면 묶어서 한 흐름으로 해석한다.
3. **근거**: 그 분석이 어디서 나왔는지 1개 정도 드러낸다(출처/사실).
   예: "(오픈AI IPO 연기설 보도)", "마이크론 실적 발표를 앞둔 점" 등.

## 환각 금지 (검증 브랜드의 생명선)
- 위 '왜/근거'는 **반드시 제공된 헤드라인 안에서만** 도출한다. 헤드라인에 없는 원인·종목·
  수치는 절대 창작하지 않는다.
- 근거가 약하면 단정하지 말고 "~로 보입니다 / ~영향으로 관찰됩니다"처럼 관찰형으로.
- 어떤 헤드라인도 원인을 설명하지 못하면, 추측 대신 "뚜렷한 재료는 확인되지 않았습니다"
  라고 솔직하게 적거나 원인 언급을 생략한다.

## 문체 (스레드 감성)
- 짧은 문장, 줄바꿈으로 호흡. 과한 이모지 금지(0~2개). 광고 티 0
- 사람이 담백하게 쓴 듯. 표/마크다운 금지
- **순한국어로만 작성**(한자·중국어·일본어 글자 금지). 영문 약어는 지수명(S&P500/SOXX/VIX)만 허용
- hook(첫 줄): 오늘 날짜 + 간밤 시장 분위기 한 줄 (예: "[6/26 새벽 미국장]")
- body: ① 주요 지수 등락 2~3줄 ② 가장 크게 움직인 부분의 '왜(분석)+근거' 2~3줄(핵심)
       ③ 국내 증시 관전포인트 1개 (중립·관찰) — **반드시 아래 '한국 증시 개장 상태'를 그대로 반영**.
          한국 증시는 낮(09:00~15:30)에 열린다. '오늘 밤 국내장' 같은 시간 표현은 금지.
          휴장일이면 '오늘 국내장'이라 쓰지 말고 '다음 거래일' 기준으로 적는다.
- 마지막 줄: "숫자는 마감 기준, 장 열리면 또 달라집니다" 류의 검증 뉘앙스 1줄(선택)
- 한국 증시 개장 여부를 임의로 가정하지 말 것 — 제공된 '한국 증시 개장 상태'만 따른다.
- hashtags: 2~4개(# 제외, 한국어 키워드: 미국증시/나스닥/코스피 등)
- watchpoints: **비워 둔다([])**. 국내장 관전포인트는 위 body ③에 이미 포함하므로 따로 만들지 않는다.
- 전체가 480자를 넘지 않도록(Threads 500자 제한 — 본문 면책 없음, 면책은 프로필 bio)"""


class BriefingAgent(BaseAgent):
    """Haiku 기반 새벽 미국시장 브리핑 생성기."""

    def __init__(self, claude=None):
        # 간판 콘텐츠(하루 1회) — 분석 깊이·한국어 품질을 위해 Sonnet 사용.
        # 비용은 1일 1건이라 ~30원/일 수준. (양쪽관점 종목글은 Haiku 유지)
        super().__init__(
            agent_name="briefing",
            model=MODEL_SONNET,
            system_prompt=_SYSTEM,
            claude=claude,
        )

    async def run(self, input_data=None):  # noqa: D401
        """BaseAgent 추상 메서드 충족 — 실제 진입점은 generate()."""
        raise NotImplementedError("BriefingAgent은 generate()를 사용하세요")

    async def generate(self, uid: str = "") -> Optional[dict]:
        """간밤 미국시장 브리핑 1편 생성. 실패 시 None."""
        snap = fetch_us_market_snapshot()
        if not snap:
            logger.warning("[briefing] 지수 스냅샷 비어 있음 — 생성 중단")
            return None

        # 간밤 미국 세션이 없으면(주말·미 공휴일 직후 = KST 월/일/공휴일 다음 아침 등) 묵은
        # 종가를 '간밤 미국장'으로 내보내지 않는다. NYSE 캘린더 + 데이터 신선도 2중 방어
        # (스케줄 화~토의 최종 안전망). 자동발행 신뢰도의 핵심 가드.
        stale, reason = us_session_is_stale(snap)
        if stale:
            logger.info(f"[briefing] 간밤 신규 미국 세션 없음({reason}) — 브리핑 생략")
            return None

        index_block = _fmt_index_lines(snap)
        news_block = _gather_news_block()
        today = datetime.now(timezone.utc).astimezone().strftime("%m/%d")
        kr_hint = kr_market_status_hint()

        user_msg = (
            f"# 오늘 날짜(한국)\n{today}\n\n"
            f"# 한국 증시 개장 상태 (반드시 반영 — 휴장일이면 '오늘 국내장' 표현 금지)\n{kr_hint}\n\n"
            f"# 간밤 미국 지수 (마감 기준)\n{index_block}\n"
            f"{news_block}\n"
            f"위 데이터로 '새벽 미국시장 브리핑' 스레드 글 한 편을 작성하세요. "
            f"hook 첫 줄에 [{today} 새벽 미국장] 형태를 넣고, 주어진 수치만 사용하세요."
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
            logger.warning(f"[briefing] 생성 실패: {e}")
            return None

        text = assemble_post(post)
        text, found = BaseAgent.filter_forbidden(text)
        if found:
            logger.warning(f"[briefing] 금지표현 필터됨: {found}")

        return {
            "kind": "briefing",
            "ticker": "",
            "name": "새벽 미국시장 브리핑",
            "market": "US",
            "is_kr": False,
            "fmt": "us_briefing",
            "fmt_label": "새벽 미국시장 브리핑",
            "text": text,
            "char_count": len(text),
            "filtered": found,
            "source": "haiku",
            "indices": snap,  # 검수 화면에서 원본 수치 참고용
        }


def _gather_news_block() -> str:
    """간밤 미국증시 한국어 헤드라인(등락 이유 근거) → 프롬프트 보강 블록.

    '뉴욕증시' 뉴스를 우선 사용(원인 포함). 비면 일반 경제 RSS로 폴백.
    """
    news: list[dict] = []
    try:
        from utils.news_rss import fetch_overnight_us_news

        news = fetch_overnight_us_news(limit=8) or []
    except Exception as e:
        logger.debug(f"[briefing] 미국증시 뉴스 실패: {e}")
    if not news:
        try:
            from utils.news_rss import fetch_market_news

            news = fetch_market_news(limit=6) or []
        except Exception as e:
            logger.debug(f"[briefing] 경제 뉴스 폴백 실패: {e}")
    if not news:
        return ""

    lines = [f"- [{n.get('source', '')}] {n.get('headline', '')}" for n in news[:8]]
    return (
        "\n# 간밤 미국증시 뉴스 헤드라인 (등락 '이유'의 근거 — 이 안에서만 인용)\n"
        + "\n".join(lines)
        + "\n"
    )


async def generate_briefing(uid: str = "") -> Optional[dict]:
    """편의 함수 — 브리핑 1편 생성."""
    return await BriefingAgent().generate(uid=uid)
