"""지수 차트 분석 콘텐츠 생성기 — 스레드(Threads)용.

코스피/코스닥/나스닥/S&P500/반도체(SOXX) 등 '지수'의 차트 국면을 구체적 지수 레벨로
읽어 한 편의 관찰 글로 만든다. 더해 등락의 거시 배경 한 줄(RSS 헤드라인)을 곁들인다.

종목 store(스크리너 Firestore)에는 지수가 없으므로, FinanceDataReader 시계열에서
이동평균·52주 고저·RSI·추세를 **직접 계산**해 종목글과 같은 facts 형태로 만든 뒤,
marketer의 4단계 하네스(앵글→작가 best-of-N→편집→가드)를 그대로 재사용한다.

지수별로 개별 글을 뽑는다(글 1편 = 지수 1개). 관리자가 콘솔에서 골라 생성·검수.

LEGAL: 추천/매수·매도/목표가/진입가/손절가 절대 금지. 관찰·참고·중립 해석만.
면책은 계정 프로필(bio)에 상시 고지하므로 본문에는 넣지 않는다.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

from loguru import logger

from agents.marketer import MarketerAgent


# ──────────────────────────────────────────────
# 지수 레지스트리 — key = 우리 식별자, fdr = FinanceDataReader 심볼
# ──────────────────────────────────────────────

INDICES: dict[str, dict] = {
    "KS11": {"name": "코스피", "fdr": "KS11", "market": "KOSPI", "is_kr": True},
    "KQ11": {"name": "코스닥", "fdr": "KQ11", "market": "KOSDAQ", "is_kr": True},
    "IXIC": {"name": "나스닥", "fdr": "IXIC", "market": "US", "is_kr": False},
    "US500": {"name": "S&P500", "fdr": "US500", "market": "US", "is_kr": False},
    "SOXX": {"name": "필라델피아 반도체", "fdr": "SOXX", "market": "US", "is_kr": False},
}

INDEX_KEYS: tuple[str, ...] = tuple(INDICES.keys())


def list_indices() -> list[dict]:
    """프론트 선택용 지수 목록 [{key, name, is_kr}]."""
    return [
        {"key": k, "name": v["name"], "is_kr": bool(v["is_kr"])}
        for k, v in INDICES.items()
    ]


# ──────────────────────────────────────────────
# 포맷 가이드 — '차트 국면 + 거시 한 줄' (종목 FORMATS와 분리해 지수 전용)
# ──────────────────────────────────────────────

INDEX_FORMAT_LABEL = "지수 차트 (차트 + 거시 한 줄)"
INDEX_FORMAT_GUIDE = (
    "이 **지수**(코스피/코스닥/나스닥 등)의 '차트 국면'을 구체적 지수 레벨로 읽는다. "
    "facts의 현재 지수·20일/60일 이동평균·52주 고점/저점을 **숫자 그대로 짚으며**, "
    "추세(정배열·이격)·과열(RSI)·연속 등락이 지금 어떤 국면인지 관찰한다. "
    "지수는 '원/달러'가 아니라 '포인트(p)' 단위다 — 가격이 아니라 지수 레벨로 쓴다. "
    "여기에 'why' 한 줄을 더한다: facts의 '## 거시 맥락' 헤드라인에서 지금 이 자리에 온 "
    "배경(금리·반도체·빅테크·환율 등)을 **한 줄로만** 곁들인다(헤드라인 범위 안에서, 환각 금지). "
    "예: '코스피 2,712p, 20일선 2,680p 위. 60일선 2,640p와 격차 +2.7%, RSI 58로 중립권.' "
    "⚠️ 절대 금지: 목표 지수·진입가·'어디서 사라/팔라'. 관찰된 지수 '레벨'만 중립 사실로 "
    "('2,680p가 가까운 지지/저항으로 관찰' 식). 오른다/내린다 단정 금지, '앞으로 볼 것'으로 방향."
)


# ──────────────────────────────────────────────
# 지수 스냅샷 (LLM 비호출 — FinanceDataReader 시계열에서 직접 계산)
# ──────────────────────────────────────────────

def _wilder_rsi(closes, period: int = 14) -> Optional[float]:
    """Wilder's EMA 방식 RSI(14). 단일 종가 시리즈 → 마지막 값. 부족하면 None."""
    try:
        diff = closes.diff().dropna()
        if len(diff) < period:
            return None
        gain = diff.clip(lower=0)
        loss = (-diff).clip(lower=0)
        avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
        ag = float(avg_gain.iloc[-1])
        al = float(avg_loss.iloc[-1])
        if al == 0:
            return 100.0
        rs = ag / al
        return 100.0 - (100.0 / (1.0 + rs))
    except Exception:
        return None


def build_index_snapshot(key: str) -> Optional[dict]:
    """지수 1개 → 차트 facts용 dict. FDR 실패/데이터 부족 시 None."""
    meta = INDICES.get(key)
    if not meta:
        return None
    try:
        import FinanceDataReader as fdr
    except Exception as e:  # pragma: no cover
        logger.warning(f"[index_chart] FinanceDataReader import 실패: {e}")
        return None

    # 52주 고저 + MA60에 충분하도록 ~1.5년 시계열.
    start = (datetime.now().date() - timedelta(days=540)).isoformat()
    try:
        df = fdr.DataReader(meta["fdr"], start)
    except Exception as e:
        logger.warning(f"[index_chart] 지수 시계열 수집 실패 {key}({meta['fdr']}): {e}")
        return None
    if df is None or df.empty or "Close" not in df.columns:
        return None

    closes = df["Close"].dropna()
    if len(closes) < 60:  # MA60·추세 판단에 최소치
        logger.warning(f"[index_chart] 시계열 부족 {key}: {len(closes)}봉")
        return None

    price = float(closes.iloc[-1])
    change_pct = None
    if len(closes) >= 2:
        prev = float(closes.iloc[-2])
        change_pct = (price / prev - 1.0) * 100.0 if prev else None

    def _ma(n: int) -> Optional[float]:
        if len(closes) < n:
            return None
        return float(closes.rolling(n).mean().iloc[-1])

    ma5, ma20, ma60 = _ma(5), _ma(20), _ma(60)
    vs_ma20 = (price / ma20 - 1.0) * 100.0 if ma20 else None
    vs_ma60 = (price / ma60 - 1.0) * 100.0 if ma60 else None

    win = closes.iloc[-252:] if len(closes) >= 252 else closes
    high_52w = float(win.max())
    low_52w = float(win.min())
    vs_high = (price / high_52w - 1.0) * 100.0 if high_52w else None
    vs_low = (price / low_52w - 1.0) * 100.0 if low_52w else None

    # 연속 상승/하락 일수(부호 있는: +상승 / -하락)
    consec = 0
    chg = closes.diff().dropna()
    for v in reversed(chg.tolist()):
        if v > 0 and consec >= 0:
            consec += 1
        elif v < 0 and consec <= 0:
            consec -= 1
        else:
            break

    # 20일 변동성(일간수익률 표준편차, %)
    vol20 = None
    rets = closes.pct_change().dropna()
    if len(rets) >= 20:
        vol20 = float(rets.iloc[-20:].std() * 100.0)

    rsi = _wilder_rsi(closes)
    ma_aligned = bool(ma5 and ma20 and ma60 and ma5 > ma20 > ma60)
    last_date: date = closes.index[-1].date()

    return {
        "key": key,
        "name": meta["name"],
        "market": meta["market"],
        "is_kr": bool(meta["is_kr"]),
        "price": price,
        "change_pct": change_pct,
        "rsi": rsi,
        "ma5": ma5,
        "ma20": ma20,
        "ma60": ma60,
        "vs_ma20_pct": vs_ma20,
        "vs_ma60_pct": vs_ma60,
        "high_52w": high_52w,
        "low_52w": low_52w,
        "vs_high_52w": vs_high,
        "vs_low_52w": vs_low,
        "consecutive": consec,
        "ma_aligned": ma_aligned,
        "volatility_20d": vol20,
        "as_of": last_date,
    }


def _pt(v: Optional[float]) -> str:
    """지수 레벨 → '3,215.42p' 표기."""
    return f"{v:,.2f}p" if v is not None else "-"


def _as_of_label(snap: dict) -> str:
    """기준일 라벨 — KR='M월 D일', US='M월 D일(현지)'."""
    d = snap.get("as_of")
    if not isinstance(d, date):
        return ""
    return f"{d.month}월 {d.day}일" + ("" if snap.get("is_kr") else "(현지)")


def _index_facts(snap: dict, macro_line: str) -> str:
    """지수 스냅샷 → LLM 입력 facts(포인트 단위). + 거시 맥락 + 기준일."""
    as_of = _as_of_label(snap)
    parts: list[str] = [f"지수: {snap['name']}"]
    chg = snap.get("change_pct")
    chg_s = f" ({chg:+.2f}%)" if chg is not None else ""
    date_tail = f" [{as_of} 종가 기준]" if as_of else ""
    parts.append(f"현재 지수: {_pt(snap.get('price'))}{chg_s}{date_tail}")
    if snap.get("rsi") is not None:
        parts.append(f"RSI(14): {snap['rsi']:.0f}")

    tech: list[str] = []
    if snap.get("ma20"):
        vs = f" (현재 대비 {snap['vs_ma20_pct']:+.1f}%)" if snap.get("vs_ma20_pct") is not None else ""
        tech.append(f"20일 이동평균: {_pt(snap['ma20'])}{vs}")
    if snap.get("ma60"):
        vs = f" (현재 대비 {snap['vs_ma60_pct']:+.1f}%)" if snap.get("vs_ma60_pct") is not None else ""
        tech.append(f"60일 이동평균: {_pt(snap['ma60'])}{vs}")
    if snap.get("high_52w") and snap.get("vs_high_52w") is not None:
        tech.append(f"52주 고점: {_pt(snap['high_52w'])} (현재 {snap['vs_high_52w']:+.1f}%)")
    if snap.get("low_52w") and snap.get("vs_low_52w") is not None:
        tech.append(f"52주 저점: {_pt(snap['low_52w'])} (현재 {snap['vs_low_52w']:+.1f}%)")
    if snap.get("ma_aligned"):
        tech.append("이동평균 정배열(5일>20일>60일) — 단기 상승 추세 구조")
    c = snap.get("consecutive") or 0
    if c >= 2:
        tech.append(f"{c}일 연속 상승")
    elif c <= -2:
        tech.append(f"{abs(c)}일 연속 하락")
    if snap.get("volatility_20d") is not None:
        tech.append(f"20일 변동성: {snap['volatility_20d']:.1f}%")

    out = "다음 지수 차트 데이터로 글을 작성하세요:\n" + "\n".join("- " + p for p in parts)
    if tech:
        out += "\n\n## 기술적 분석(차트 국면)\n" + "\n".join("- " + p for p in tech)
    if macro_line:
        out += "\n\n## 거시 맥락 (등락 배경 — 이 헤드라인 범위 안에서만 한 줄로 인용)\n- " + macro_line

    if as_of:
        out += (
            f"\n\n# 기준일 (필수)\n이 수치는 {as_of} 종가 기준이다. "
            f"'오늘/지금/현재'가 아니라 '{as_of}'로 한 번만 표기하라."
        )
    else:
        out += (
            "\n\n# 기준일\n기준일 정보가 없다. '오늘/지금/현재' 시점어 없이 수치만 제시하라."
        )
    return out


def _macro_headline(snap: dict) -> str:
    """등락 배경 한 줄용 헤드라인 1개. 실패 시 ''.

    KR 지수(코스피/코스닥)는 지수명 기반 Google News 검색('코스피 마감' 등)으로
    지수와 직접 관련된 헤드라인을 끌어온다(일반 경제 RSS는 부동산 등 무관 기사 혼입).
    US 지수는 '뉴욕증시' 검색(fetch_overnight_us_news)을 쓴다.
    """
    name = snap.get("name", "")
    news: list[dict] = []
    try:
        if snap.get("is_kr"):
            from utils.news_rss import fetch_news_search

            news = fetch_news_search([f"{name} 마감", f"{name} 증시"], limit=4) or []
        else:
            from utils.news_rss import fetch_overnight_us_news

            news = fetch_overnight_us_news(limit=4) or []
    except Exception as e:
        logger.debug(f"[index_chart] 거시 헤드라인 수집 실패({name}): {e}")
    if not news:
        return ""
    n = news[0]
    src = n.get("source", "")
    head = n.get("headline", "")
    return f"[{src}] {head}" if src else head


# ──────────────────────────────────────────────
# 진입점
# ──────────────────────────────────────────────

async def generate_index_chart(key: str, uid: str = "") -> Optional[dict]:
    """지수 1개 차트 글 생성 — marketer 4단계 하네스 재사용. 실패 시 None."""
    snap = build_index_snapshot(key)
    if not snap or snap.get("ma20") is None or snap.get("price") is None:
        logger.warning(f"[index_chart] 스냅샷/지표 결손 — 생성 건너뜀 {key}")
        return None

    macro = _macro_headline(snap)
    facts = _index_facts(snap, macro)
    name = snap["name"]

    result_base = {
        "ticker": "",            # 지수는 종목코드 없음(검수 UI에서 ticker 숨김)
        "name": name,
        "market": snap["market"],
        "is_kr": bool(snap["is_kr"]),
        "kind": "index",         # 종목글/브리핑과 구분
        "source": "index-chart",
        "index_key": key,
    }

    agent = MarketerAgent()
    post = await agent._run_harness(
        facts=facts,
        guide=INDEX_FORMAT_GUIDE,
        name=name,
        fmt="index_chart",
        fmt_label=INDEX_FORMAT_LABEL,
        uid=uid,
        result_base=result_base,
        avoid_archetypes=None,
        enforce_watchpoints=True,
    )
    return post
