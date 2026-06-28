"""빠른 요약(Instant) — 첫 분석 체감속도 개선.

무거운 4에이전트 파이프라인(~12s) 전에, 이미 메모리에 적재된 스크리너 스냅샷
(현재가/등락/RSI/스코어/섹터)으로 즉시 카드를 만들고, Haiku 1회 호출(~5원, ~2s)로
중립적 1~2줄 '첫인상' 요약을 만든다. ai.py /analyze 스트림이 본 파이프라인과
**동시에** 실행해 instant_snapshot/instant_summary SSE를 먼저 송출 → 사용자는 정밀
분석을 기다리는 동안 빈 화면 대신 즉시 맥락을 본다.

LEGAL: "추천"·"매수가"·"목표가"·"매수/매도 신호" 금지. 관찰·참고 표현만.
응답은 호출부(_sse)에서 filter_forbidden을 한 번 더 거친다(이중 안전).
"""

from __future__ import annotations

import math
import re
from typing import Optional

from loguru import logger


# ──────────────────────────────────────────────
# 스냅샷 (LLM 비호출 — 즉시)
# ──────────────────────────────────────────────

def build_instant_snapshot(ticker: str) -> Optional[dict]:
    """스크리너 in-memory 스냅샷에서 종목 1행 → 안전 필드 dict. 없으면 None.

    `_get_combined_df`(API _data_store, 또는 잡에서 load_from_firestore로 적재)를
    사용. 캐시 워밍 잡과 라이브가 동일 소스를 쓰므로 표시값이 일관된다.
    """
    if not ticker:
        return None
    try:
        from screener.api.routes import _get_combined_df

        df = _get_combined_df()
        if df is None or df.empty:
            return None
        m = df[df["ticker"].astype(str).str.upper() == ticker.upper()]
        if m.empty:
            return None
        row = m.iloc[0]
    except Exception as e:
        logger.debug(f"[instant] snapshot 조회 실패 {ticker}: {e}")
        return None

    def num(key: str, default=None):
        v = row.get(key)
        try:
            if v is None:
                return default
            f = float(v)
            if math.isnan(f):
                return default
            return f
        except (TypeError, ValueError):
            return default

    def text(key: str, default: str = "") -> str:
        v = row.get(key)
        return str(v) if v is not None else default

    is_kr = bool(re.match(r"^\d{6}$", ticker))
    return {
        "ticker": ticker.upper(),
        "name": text("name"),
        "market": text("market"),
        "is_kr": is_kr,
        "price": num("close"),
        "change_pct": num("change_pct"),
        "rsi": num("rsi"),
        "buy_score": num("buy_score"),
        "buy_grade": text("buy_grade"),
        "per": num("per"),
        "pbr": num("pbr"),
        "roe": num("roe"),
        "sector": text("sector"),
        "vs_high_52w": num("vs_high_52w"),
        "vs_low_52w": num("vs_low_52w"),
        "foreign_consecutive": int(num("foreign_consecutive", 0) or 0),
        "volume_ratio": num("volume_ratio"),
        # ── 기술 지표(이미 collector가 계산·저장. 마케팅/요약에서 인용) ──
        # 이동평균선 '실제 가격'(원/달러) — 기술 포맷이 구체적 가격대로 차트를 읽게 한다.
        "ma5": num("ma5"),
        "ma20": num("ma20"),
        "ma60": num("ma60"),
        "vs_ma20_pct": num("vs_ma20_pct"),
        "vs_ma60_pct": num("vs_ma60_pct"),
        "ma_aligned": int(num("ma_aligned", 0) or 0),
        "golden_cross": int(num("golden_cross", 0) or 0),
        "death_cross": int(num("death_cross", 0) or 0),
        "golden_cross_long": int(num("golden_cross_long", 0) or 0),
        "consecutive_gains": int(num("consecutive_gains", 0) or 0),
        "volume_trend": int(num("volume_trend", 0) or 0),
        "accumulation": int(num("accumulation", 0) or 0),
        "ma_squeeze": num("ma_squeeze"),
        "volatility_20d": num("volatility_20d"),
        "risk_grade": text("risk_grade"),
        # 데이터 기준 시각(ISO). 마케팅 글이 '오늘' 대신 정확한 일자로 쓰게 한다.
        "updated_at": text("updated_at"),
    }


def _is_subsequence(needle: str, hay: str) -> bool:
    """needle의 문자들이 hay 안에 순서대로 등장하는가. 'HD일렉트릭' ⊂ 'HD현대일렉트릭'."""
    it = iter(hay)
    return all(ch in it for ch in needle)


def resolve_ticker(query: str) -> Optional[str]:
    """입력(티커 또는 종목명) → 적재된 실제 티커. 못 찾으면 None.

    사용자가 '267260' 대신 'HD일렉트릭'(축약 종목명)을 넣어도 매칭되게 한다.
    우선순위: 티커 정확 → 종목명 정확 → 종목명 부분포함 → 서브시퀀스(공백·대소문자 무시).
    부분포함/서브시퀀스에서 후보가 여럿이면 **가장 짧은 이름**(가장 구체적)을 고른다.
    """
    if not query:
        return None
    q = query.strip()
    try:
        from screener.api.routes import _get_combined_df

        df = _get_combined_df()
        if df is None or df.empty:
            return None
        tcol = df["ticker"].astype(str)
        exact = df[tcol.str.upper() == q.upper()]
        if not exact.empty:
            return str(exact.iloc[0]["ticker"])
        if "name" not in df.columns:
            return None

        qn = q.upper().replace(" ", "")
        nnorm = df["name"].astype(str).str.upper().str.replace(" ", "", regex=False)

        name_exact = df[nnorm == qn]
        if not name_exact.empty:
            return str(name_exact.iloc[0]["ticker"])

        def _shortest(mask) -> Optional[str]:
            sub = df[mask]
            if sub.empty:
                return None
            idx = nnorm[sub.index].str.len().idxmin()
            return str(df.loc[idx, "ticker"])

        part = _shortest(nnorm.str.contains(re.escape(qn), na=False))
        if part:
            return part

        if len(qn) >= 3:
            subseq_mask = nnorm.apply(lambda nm: bool(nm) and _is_subsequence(qn, nm))
            sub = _shortest(subseq_mask)
            if sub:
                return sub
    except Exception as e:
        logger.debug(f"[instant] resolve_ticker 실패 {query}: {e}")
    return None


# ──────────────────────────────────────────────
# 빠른 요약 (Haiku 1회 — ~5원, ~2s)
# ──────────────────────────────────────────────

_INSTANT_SYSTEM = """당신은 한국/미국 주식의 '첫인상 요약'을 작성하는 중립 데이터 해설가입니다.
주어진 스냅샷 수치만으로 종목의 현재 상태를 2~3문장으로 담백하게 서술하세요.

규칙:
- 절대 금지: 추천/매수/매도/목표가/매수가/손절가/매수 신호 등 권유성 표현과 가격 제시
- 허용: '관찰', '참고', '현재 ~ 구간', 수치의 중립적 해석
- RSI 70+ 과열·30- 침체, 52주 고가 대비 위치, 외국인 연속 수급, 밸류(PER/PBR)를 사실 위주로
- 마지막에 정밀 분석이 곧 이어진다는 점을 짧게 언급('자세한 분석이 곧 표시됩니다' 류)
- 한국어, 군더더기 없이 2~3문장."""


# 경기민감(사이클) 업종 — 이익이 사이클을 크게 타 단일 PER/PBR이 신호를 거꾸로 줄 수
# 있는 업종군. 호황 이익 피크엔 PER이 낮게(저평가 착시), 불황 바닥엔 높게 보인다.
_CYCLICAL_KEYWORDS = (
    "반도체", "디스플레이", "화학", "정유", "에너지", "철강", "금속", "비철",
    "조선", "해운", "자동차", "건설", "기계", "운송",
)


def _is_cyclical(sector: str) -> bool:
    """섹터명이 경기민감 업종군에 속하는가(부분 일치)."""
    s = (sector or "").replace(" ", "")
    return any(k in s for k in _CYCLICAL_KEYWORDS)


def _cycle_note(s: dict) -> str:
    """사이클 업종이면 '단일 PER 함정' 경고 문구. 아니면 빈 문자열.

    호황기엔 이익 피크로 PER이 낮게(저평가 착시), 불황기엔 이익 저점으로 높게 보인다.
    """
    if not _is_cyclical(s.get("sector", "")):
        return ""
    note = (
        f"이 종목은 경기민감(사이클) 업종({s.get('sector')})이라 이익이 크게 출렁인다. "
        "단일 PER/PBR로 저평가·고평가를 단정하면 신호가 거꾸로 나올 수 있다"
    )
    try:
        per = float(s.get("per") or 0)
    except (TypeError, ValueError):
        per = 0.0
    if 0 < per <= 12:
        note += " — 낮은 PER이 호황기 '이익 피크'의 착시일 수 있으니 추세·수급과 함께 보라."
    elif per >= 25:
        note += " — 높은 PER이 불황기 '이익 저점'의 신호일 수 있으니 추세·수급과 함께 보라."
    else:
        note += ". 이익 사이클 위치에 따라 해석이 달라진다."
    return note


def _price_level(value: float, is_kr: bool) -> str:
    """가격 → 표기 문자열. KR=정수 '원', US=소수 '달러'."""
    return f"{value:,.0f}원" if is_kr else f"{value:,.2f}달러"


def _technical_facts(s: dict) -> list[str]:
    """이미 계산된 기술 지표 → 글에 인용할 수 있는 한국어 기술분석 팩트 목록.

    collector가 산출해 스냅샷에 들어온 추세·거래량·변동성 신호를 노출한다.
    **주요 가격대(이동평균선·52주 고저)를 '실제 가격(원/달러)'으로 먼저 제시**해
    기술 포맷이 구체적 가격으로 차트를 읽게 한다(이격 %만으론 가격이 추상적).
    LEGAL: 사실 기술(技術) 관찰만 — 목표가/매수가/손절가·'매수 신호' 등 처방/권유 금지.
    """
    t: list[str] = []
    is_kr = bool(s.get("is_kr"))
    price = s.get("price")

    # ── 주요 가격대(구체적 가격 — 기술 포맷 핵심) ──
    if s.get("ma20"):
        vs = f" (현재가 대비 {s['vs_ma20_pct']:+.1f}%)" if s.get("vs_ma20_pct") is not None else ""
        t.append(f"20일 이동평균선: {_price_level(s['ma20'], is_kr)}{vs}")
    elif s.get("vs_ma20_pct") is not None:
        t.append(f"20일 이동평균 대비: {s['vs_ma20_pct']:+.1f}%")
    if s.get("ma60"):
        vs = f" (현재가 대비 {s['vs_ma60_pct']:+.1f}%)" if s.get("vs_ma60_pct") is not None else ""
        t.append(f"60일 이동평균선: {_price_level(s['ma60'], is_kr)}{vs}")
    elif s.get("vs_ma60_pct") is not None:
        t.append(f"60일 이동평균 대비: {s['vs_ma60_pct']:+.1f}%")
    # 52주 고가/저가 — 현재가와 이격%로 절대 가격을 역산해 제시.
    if price and s.get("vs_high_52w") is not None:
        denom = 1 + s["vs_high_52w"] / 100
        if denom:
            t.append(f"52주 고가: {_price_level(price / denom, is_kr)} (현재가 {s['vs_high_52w']:+.1f}%)")
    if price and s.get("vs_low_52w"):
        denom = 1 + s["vs_low_52w"] / 100
        if denom:
            t.append(f"52주 저가: {_price_level(price / denom, is_kr)} (현재가 {s['vs_low_52w']:+.1f}%)")

    # ── 추세/거래량/변동성 신호 ──
    if s.get("ma_aligned"):
        t.append("이동평균 정배열(5일>20일>60일) — 단기 상승 추세 구조")
    if s.get("golden_cross"):
        t.append("최근(5일 내) 골든크로스 — MA5가 MA20을 상향 돌파")
    if s.get("death_cross"):
        t.append("최근(5일 내) 데드크로스 — MA5가 MA20을 하향 돌파")
    elif s.get("golden_cross_long"):
        t.append("최근 장기 골든크로스 — MA20이 MA60을 상향 돌파")
    if s.get("consecutive_gains"):
        t.append(f"{s['consecutive_gains']}일 연속 상승")
    if s.get("volume_trend"):
        t.append(f"거래량 {s['volume_trend']}일 연속 증가")
    if s.get("accumulation"):
        t.append("매집 의심 신호 — 거래량 증가 + 가격 안정 동반")
    ms = s.get("ma_squeeze")
    if ms is not None and 0 < ms < 2.0:
        t.append(f"이동평균 수렴(스프레드 {ms:.1f}%) — 변동성 응축 구간")
    if s.get("volatility_20d"):
        t.append(f"20일 변동성: {s['volatility_20d']:.1f}%")
    if s.get("risk_grade") and s["risk_grade"] != "데이터없음":
        t.append(f"변동성 등급: {s['risk_grade']}")
    return t


def _snapshot_facts(s: dict) -> str:
    """스냅샷 dict → LLM 입력용 한국어 팩트 목록.

    시세·밸류 기본 팩트에 더해, 이미 계산된 '기술적 분석' 섹션과 사이클 업종이면
    '사이클 주의' 섹션을 덧붙인다(마케팅 글의 so-what 심화 + 단일 PER 함정 방어).
    """
    unit = "원" if s.get("is_kr") else "달러"
    parts: list[str] = [f"종목: {s.get('name') or s.get('ticker')} ({s.get('ticker')})"]
    if s.get("sector"):
        parts.append(f"섹터: {s['sector']}")
    if s.get("price") is not None:
        chg = s.get("change_pct")
        chg_s = f" ({chg:+.2f}%)" if chg is not None else ""
        parts.append(f"현재가: {s['price']:,.0f}{unit}{chg_s}")
    if s.get("rsi") is not None:
        parts.append(f"RSI(14): {s['rsi']:.0f}")
    if s.get("vs_high_52w") is not None:
        parts.append(f"52주 고가 대비: {s['vs_high_52w']:+.1f}%")
    if s.get("per"):
        parts.append(f"PER: {s['per']:.1f}")
    if s.get("pbr"):
        parts.append(f"PBR: {s['pbr']:.2f}")
    if s.get("roe"):
        parts.append(f"ROE: {s['roe']:.1f}%")
    if s.get("foreign_consecutive"):
        parts.append(f"외국인 연속 순매수: {s['foreign_consecutive']}일")
    if s.get("volume_ratio"):
        parts.append(f"거래량비(평균 대비): {s['volume_ratio']:.1f}x")

    out = "다음 스냅샷으로 빠른 첫인상 요약을 작성하세요:\n" + "\n".join(
        "- " + p for p in parts
    )
    tech = _technical_facts(s)
    if tech:
        out += "\n\n## 기술적 분석\n" + "\n".join("- " + p for p in tech)
    note = _cycle_note(s)
    if note:
        out += "\n\n## 사이클 주의\n- " + note
    return out


async def instant_quick_take(snapshot: dict, uid: str = "") -> str:
    """스냅샷 → Haiku 1~2줄 중립 요약. 실패 시 빈 문자열(호출부에서 무시).

    ResponseCache가 (model, system, messages) 키로 캐싱 — 스냅샷에 현재가가 포함되어
    데이터가 갱신되면 키가 바뀌므로 신선도가 구조적으로 보장된다.
    """
    if not snapshot:
        return ""
    try:
        from utils.claude_client import MODEL_HAIKU, ClaudeClient

        client = ClaudeClient()
        result = await client.complete(
            agent="instant",
            model=MODEL_HAIKU,
            system=_INSTANT_SYSTEM,
            messages=[{"role": "user", "content": _snapshot_facts(snapshot)}],
            max_tokens=300,
            uid=uid,
        )
        return (result.get("content") or "").strip()
    except Exception as e:
        logger.debug(f"[instant] quick-take 실패: {e}")
        return ""
