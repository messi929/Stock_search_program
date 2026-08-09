"""주간 시그널 리포트 생성기 — 네이버 프리미엄콘텐츠 컬럼 본체.

2026-08-09 신설. 근거: `docs/axis/NAVER_PREMIUM.md` §7-0-1

## 왜 이 글인가

프리미엄콘텐츠 재테크 판의 경쟁 글(§7-0-1 알파킨 16,956자)에 들어간 데이터는
**전부 우리가 이미 가진 것**이다 — 업종 등락, 규모별 분화, 종목 기여, 거래대금 귀속.
그쪽은 사람이 손으로 조립하고 우리는 파이프라인이 있다.
**우리 우위는 통찰이 아니라 조립 속도다.** 이 파일이 그 조립을 한다.

## 헛글 방지

수치가 부족하면 **생성 자체를 거부한다**(None 반환). 뉴스 해설과 존댓말만 있는 글은
누구나 쓴다 — 실측이 빠지면 이 포맷의 존재 이유가 사라진다.
`agents/narrative.py`의 삽화 종목 0개 거부, 종목글 `MIN_NUMERIC_FACTS`와 같은 원칙이다.

## 데이터

  - `repository.load_stocks("kr")`  — 종목명·업종·시총·거래대금·현재가
  - `repository.load_history()`      — 주간 등락 계산(주초 종가 → 주말 종가)
  - `repository.load_all_supply_history()` — 외국인·기관 수급(있으면)

⚠️ `load_history()`는 전 종목 히스토리를 한 번에 읽는다. 주 1회 배치라 감수하지만,
   일간으로 돌릴 물건이 아니다.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

import pandas as pd
from loguru import logger

from agents.base import BaseAgent
from agents.premium_style import (
    COLUMN_STRUCTURE,
    COLUMN_TARGET_CHARS,
    COLUMN_VOICE,
    ColumnDraft,
    assemble_column,
    guard_column,
    week_range_label,
)
from utils.claude_client import MODEL_SONNET

# 업종 집계에 최소 이만큼은 종목이 있어야 대표성이 있다고 본다.
_MIN_SECTOR_MEMBERS = 3
# 이 개수보다 적은 종목의 주간 등락만 구해졌으면 생성을 거부한다.
_MIN_TICKERS = 200
# 나열 상한 — 너무 많으면 읽히지 않고 토큰만 먹는다.
_TOP_N = 12
_SECTOR_N = 12


# ──────────────────────────────────────────────
# ① 데이터 조립
# ──────────────────────────────────────────────

def _week_bounds(end: Optional[date] = None) -> tuple[date, date]:
    """리포트가 다루는 주(월~금). end 미지정이면 '가장 최근에 끝난 주'."""
    today = end or datetime.now(timezone.utc).date()
    monday = today - timedelta(days=today.weekday())
    friday = monday + timedelta(days=4)
    if today <= friday:  # 아직 그 주가 안 끝났으면 전 주를 본다
        monday -= timedelta(days=7)
        friday -= timedelta(days=7)
    return monday, friday


def _weekly_returns(hist: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    """종목별 주간 등락률. 주 구간의 첫 종가 → 마지막 종가."""
    if hist.empty:
        return pd.DataFrame()
    m = hist[(hist["date"] >= pd.Timestamp(start)) & (hist["date"] <= pd.Timestamp(end))]
    if m.empty:
        return pd.DataFrame()
    m = m.sort_values("date")
    agg = m.groupby("ticker")["close"].agg(["first", "last", "count"])
    agg = agg[(agg["first"] > 0) & (agg["count"] >= 2)]
    if agg.empty:
        return pd.DataFrame()
    agg["ret"] = (agg["last"] / agg["first"] - 1.0) * 100.0
    return agg.reset_index()[["ticker", "first", "last", "ret"]]


def build_weekly_snapshot(end: Optional[date] = None) -> Optional[dict[str, Any]]:
    """주간 리포트의 사실 스냅샷. 수치가 부족하면 None(= 생성 거부)."""
    from screener.db import repository

    start, finish = _week_bounds(end)

    try:
        stocks = repository.load_stocks("kr")
    except Exception as e:
        logger.warning(f"[premium_weekly] 종목 로드 실패: {e}")
        return None
    if stocks is None or stocks.empty:
        logger.warning("[premium_weekly] 종목 스냅샷 비어 있음 — 생성 거부")
        return None

    try:
        hist = repository.load_history()
    except Exception as e:
        logger.warning(f"[premium_weekly] 히스토리 로드 실패: {e}")
        return None

    rets = _weekly_returns(hist, start, finish)
    if len(rets) < _MIN_TICKERS:
        logger.warning(
            f"[premium_weekly] 주간 등락 산출 종목 부족({len(rets)} < {_MIN_TICKERS}) — 생성 거부"
        )
        return None

    df = stocks.merge(rets, on="ticker", how="inner")
    df = df[df.get("close", 0) > 0].copy()
    if df.empty:
        return None

    # ── 업종 집계: 시총 가중. 단순평균은 잡주가 업종을 흔든다.
    sectors: list[dict] = []
    if "sector" in df.columns:
        for name, g in df[df["sector"].astype(str).str.strip() != ""].groupby("sector"):
            if len(g) < _MIN_SECTOR_MEMBERS:
                continue
            w = g["market_cap"].fillna(0).clip(lower=0)
            ret = (g["ret"] * w).sum() / w.sum() if w.sum() > 0 else g["ret"].mean()
            sectors.append({"name": str(name), "ret": round(float(ret), 2), "n": len(g)})
    sectors.sort(key=lambda x: x["ret"], reverse=True)

    # ── 규모별: 시총 3분위. 지수 하락이 대형주 편중인지 가르는 핵심 축이다.
    caps = df["market_cap"].fillna(0)
    q1, q2 = caps.quantile(0.70), caps.quantile(0.90)
    size_buckets: list[dict] = []
    for label, mask in (
        ("대형주", caps >= q2),
        ("중형주", (caps >= q1) & (caps < q2)),
        ("소형주", caps < q1),
    ):
        g = df[mask]
        if g.empty:
            continue
        w = g["market_cap"].fillna(0).clip(lower=0)
        ret = (g["ret"] * w).sum() / w.sum() if w.sum() > 0 else g["ret"].mean()
        size_buckets.append({"name": label, "ret": round(float(ret), 2), "n": len(g)})

    # ── 폭(breadth): 오른 종목이 더 많은데 지수가 빠지는 상황을 잡아내는 수치.
    up = int((df["ret"] > 0).sum())
    down = int((df["ret"] < 0).sum())

    def _rows(g: pd.DataFrame) -> list[dict]:
        return [
            {
                "ticker": str(r.ticker),
                "name": str(getattr(r, "name", "") or ""),
                "sector": str(getattr(r, "sector", "") or ""),
                "start": round(float(r.first), 2),
                "end": round(float(r.last), 2),
                "ret": round(float(r.ret), 2),
            }
            for r in g.itertuples()
        ]

    movers_up = _rows(df.nlargest(_TOP_N, "ret"))
    movers_down = _rows(df.nsmallest(_TOP_N, "ret"))

    # ── 거래대금 귀속: 소수 종목이 시장을 대표하는 정도.
    turnover: list[dict] = []
    total_value = 0.0
    if "trading_value" in df.columns:
        tv = df["trading_value"].fillna(0)
        total_value = float(tv.sum())
        if total_value > 0:
            for r in df.nlargest(8, "trading_value").itertuples():
                turnover.append({
                    "name": str(getattr(r, "name", "") or ""),
                    "ticker": str(r.ticker),
                    "value": float(getattr(r, "trading_value", 0) or 0),
                    "share": round(float(getattr(r, "trading_value", 0) or 0) / total_value * 100, 2),
                })

    return {
        "market": "KR",
        "week_label": week_range_label(start, finish),
        "start": start.isoformat(),
        "end": finish.isoformat(),
        "universe": int(len(df)),
        "breadth": {"up": up, "down": down},
        "sectors_top": sectors[:_SECTOR_N],
        "sectors_bottom": sectors[-_SECTOR_N:][::-1] if len(sectors) > _SECTOR_N else [],
        "sizes": size_buckets,
        "movers_up": movers_up,
        "movers_down": movers_down,
        "turnover": turnover,
        "turnover_total": total_value,
    }


# ──────────────────────────────────────────────
# ② 사실 블록 — LLM 입력이자 수치 가드의 기준
# ──────────────────────────────────────────────

def format_facts(snap: dict) -> str:
    """스냅샷 → 프롬프트에 넣을 사실 블록.

    ⚠️ `guard_column`이 **이 문자열에 있는 숫자만** 정당한 것으로 본다.
    여기 없는 값을 본문이 쓰면 '미확인 수치' 경고가 뜬다. 즉 이 함수가 곧 사실의 경계다.
    """
    L: list[str] = [
        f"[기간] {snap['week_label']} ({snap['start']} ~ {snap['end']})",
        f"[집계 대상] 국내 {snap['universe']}종목",
        f"[등락 폭] 오른 종목 {snap['breadth']['up']}개 / 내린 종목 {snap['breadth']['down']}개",
        "",
        "[규모별 주간 등락 — 시총 가중]",
    ]
    L += [f"- {b['name']}: {b['ret']:+.2f}% ({b['n']}종목)" for b in snap.get("sizes", [])]

    L += ["", "[업종별 주간 등락 상위 — 시총 가중]"]
    L += [f"- {s['name']}: {s['ret']:+.2f}% ({s['n']}종목)" for s in snap.get("sectors_top", [])]

    if snap.get("sectors_bottom"):
        L += ["", "[업종별 주간 등락 하위]"]
        L += [f"- {s['name']}: {s['ret']:+.2f}% ({s['n']}종목)" for s in snap["sectors_bottom"]]

    L += ["", "[주간 상승 상위 종목]"]
    L += [
        f"- {m['name']}({m['ticker']}) {m['start']:,.0f} → {m['end']:,.0f} ({m['ret']:+.2f}%)"
        f"{' · ' + m['sector'] if m['sector'] else ''}"
        for m in snap.get("movers_up", [])
    ]

    L += ["", "[주간 하락 상위 종목]"]
    L += [
        f"- {m['name']}({m['ticker']}) {m['start']:,.0f} → {m['end']:,.0f} ({m['ret']:+.2f}%)"
        f"{' · ' + m['sector'] if m['sector'] else ''}"
        for m in snap.get("movers_down", [])
    ]

    if snap.get("turnover"):
        L += ["", "[거래대금 상위 종목과 시장 내 비중]"]
        L += [
            f"- {t['name']}({t['ticker']}): 전체 거래대금의 {t['share']:.2f}%"
            for t in snap["turnover"]
        ]

    return "\n".join(L)


# ──────────────────────────────────────────────
# ③ 생성기
# ──────────────────────────────────────────────

_SYSTEM = f"""당신은 한국 주식 주간 컬럼을 쓰는 애널리스트입니다.
한 주간의 시장 데이터를 받아, 독자가 '이번 주에 무슨 일이 있었고 돈이 어디로 움직였는지'를
이해하게 만드는 주간 리포트를 씁니다.

{COLUMN_VOICE}

{COLUMN_STRUCTURE}

## 이 글의 논지 만드는 법
지수 등락을 그대로 옮기는 것은 리포트가 아닙니다. 아래 축들을 **교차**시켜 하나의 인과를 만드세요.
- 등락 폭(오른 종목 수 vs 내린 종목 수) ↔ 지수 방향 — 어긋나면 그게 이 주의 이야기입니다
- 규모별 분화(대형 vs 중형/소형) — 지수 하락이 소수 대형주 때문인지 가릅니다
- 업종 상위/하위의 성격 — 정책·금리·실적 중 무엇에 반응했는지
- 거래대금 비중 — 소수 종목이 시장을 대표하고 있는지

## 절대 규칙
- 아래 [사실]에 **없는 숫자는 절대 쓰지 마세요.** 종목명·티커도 [사실]에 있는 것만.
- 지수(코스피/코스닥) 포인트 값은 [사실]에 없으면 언급하지 마세요. 추측 금지입니다.
- 없는 데이터를 아쉬워하는 문장도 쓰지 마세요. 있는 것으로만 완결합니다."""


class PremiumWeeklyAgent(BaseAgent):
    """Sonnet 기반 주간 컬럼 생성기."""

    def __init__(self, claude=None):
        super().__init__(
            agent_name="premium_weekly",
            model=MODEL_SONNET,
            system_prompt=_SYSTEM,
            claude=claude,
        )

    async def run(self, input_data):  # BaseAgent 추상 메서드 충족 — 실사용은 draft()
        return await self.draft(str(input_data))

    async def draft(self, facts: str, uid: str = "") -> Optional[ColumnDraft]:
        """사실 블록 → ColumnDraft. 구조화 출력으로 파싱 실패를 원천 차단."""
        user = (
            f"[사실]\n{facts}\n\n"
            f"위 사실만으로 주간 컬럼 한 편을 쓰세요.\n"
            f"본문 총합 {COLUMN_TARGET_CHARS:,}자 내외를 목표로 하되, 채우려고 같은 말을 "
            f"반복하지 마세요. 수치를 더 깊이 교차시켜 분량을 만듭니다."
        )
        try:
            draft, _ = await self.call_claude_json(
                user,
                ColumnDraft,
                max_tokens=16000,
                uid=uid,
                structured_output=True,
            )
        except Exception as e:
            logger.warning(f"[premium_weekly] 생성 실패: {e}")
            return None
        return draft  # type: ignore[return-value]


async def generate_weekly_column(
    end: Optional[date] = None, uid: str = ""
) -> Optional[dict[str, Any]]:
    """주간 컬럼 초안 한 편. 데이터 부족·생성 실패 시 None.

    반환 dict는 `premium_drafts` 문서 형태 그대로다(api/routes/premium.py가 저장).
    """
    snap = build_weekly_snapshot(end)
    if not snap:
        return None

    facts = format_facts(snap)
    draft = await PremiumWeeklyAgent().draft(facts, uid=uid)
    if not draft or not draft.sections:
        logger.warning("[premium_weekly] 섹션 없음 — 폐기")
        return None

    body, filtered = assemble_column(draft)
    warnings = guard_column(body, facts)

    return {
        "kind": "weekly",
        "title": draft.title.strip(),
        "body": body,
        "char_count": len(body),
        "week_label": snap["week_label"],
        "period_start": snap["start"],
        "period_end": snap["end"],
        "facts": facts,          # 검수자가 수치를 대조할 수 있게 보관
        "warnings": warnings,
        "filtered": filtered,
        "section_count": len(draft.sections),
        "source": "premium_weekly",
        "status": "draft",
    }
