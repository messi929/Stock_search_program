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
        "foreign_consecutive": int(num("foreign_consecutive", 0) or 0),
        "volume_ratio": num("volume_ratio"),
    }


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


def _snapshot_facts(s: dict) -> str:
    """스냅샷 dict → Haiku 입력용 한국어 팩트 목록."""
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
    return "다음 스냅샷으로 빠른 첫인상 요약을 작성하세요:\n" + "\n".join(
        "- " + p for p in parts
    )


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
