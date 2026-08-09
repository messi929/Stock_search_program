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

  - `pykrx.get_market_price_change`  — 전 종목 주간 시가/종가/등락률/**기간 누적 거래대금**
  - `pykrx.get_market_cap_by_ticker` — 기준일 시가총액(업종 가중·규모별 분위용)
  - `repository.load_stocks("kr")`    — 업종(sector)만. 느리게 변하므로 스냅샷으로 충분

## 왜 Firestore `history`를 쓰지 않는가 (2026-08-09 교체)

처음엔 `repository.load_history()`로 만들었는데 실측해보니 그 컬렉션이 열화돼 있었다:
해당 주 422종목뿐이고 시총 top100 중 29개만, **삼성전자·SK하이닉스가 아예 없었다.**
그 표본으로 뽑은 첫 리포트는 "대형주 +6.00%"라고 썼지만 실제로는 **-3.52%**였다.
정반대 결론이다.

pykrx는 한 번에 2,872종목을 1.2초에 주고 거래대금이 기간 누적이라, 커버리지와
'일간 값을 주간인 척 쓰던' 문제가 동시에 해결된다. 레거시 collector 의존도 사라진다.

⚠️ KRX_ID / KRX_PW 환경변수 필요(Secret Manager: `krx-id`, `krx-pw`).
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
# 이 개수보다 적으면 KRX가 부분 응답을 준 것으로 본다(정상은 2,800종목 안팎).
# 옛 history 방식에선 397종목도 통과해버렸다 — 그 표본엔 삼성전자가 없었다.
_MIN_TICKERS = 1_500
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


def _fetch_krx_weekly(start: date, end: date) -> pd.DataFrame:
    """pykrx 1회 호출로 **전 종목** 주간 등락 + 기간 누적 거래대금.

    Firestore `history` 컬렉션을 쓰지 않는 이유(2026-08-09 교체):
    그 컬렉션은 레거시 collector가 채우는데 열화돼 있었다 — 해당 주 422종목,
    시총 top100 중 29개, **삼성전자·SK하이닉스 누락**. 그 표본으로 주간 시장
    리포트를 쓰면 그냥 틀린 글이 된다.

    pykrx `get_market_price_change`는 한 번에 2,872종목을 1.2초에 주고,
    **거래대금이 기간 누적**이라 '일간 값을 주간인 척' 쓰던 문제도 같이 사라진다.

    ⚠️ KRX_ID/KRX_PW 환경변수가 필요하다(Secret Manager: krx-id/krx-pw).
       없으면 pykrx가 로그인 실패 후 빈 응답을 주므로 여기서 None 처리된다.
    """
    from pykrx import stock

    df = stock.get_market_price_change(
        start.strftime("%Y%m%d"), end.strftime("%Y%m%d"), market="ALL"
    )
    if df is None or df.empty:
        return pd.DataFrame()

    out = pd.DataFrame(
        {
            "ticker": df.index.astype(str),
            "name": df["종목명"].astype(str),
            "first": pd.to_numeric(df["시가"], errors="coerce"),
            "last": pd.to_numeric(df["종가"], errors="coerce"),
            "ret": pd.to_numeric(df["등락률"], errors="coerce"),
            "trading_value": pd.to_numeric(df["거래대금"], errors="coerce"),
        }
    ).dropna(subset=["ret", "last"])
    # 시가 0 = 그 주에 거래가 없던 종목(신규상장·거래정지). 등락률이 의미 없다.
    return out[out["first"] > 0].reset_index(drop=True)


def _fetch_krx_cap(on: date) -> pd.DataFrame:
    """기준일 시가총액(억원). 업종 시총가중·규모별 분위에 쓴다."""
    from pykrx import stock

    cap = stock.get_market_cap_by_ticker(on.strftime("%Y%m%d"), market="ALL")
    if cap is None or cap.empty:
        return pd.DataFrame()
    return pd.DataFrame(
        {
            "ticker": cap.index.astype(str),
            # repository의 market_cap과 단위를 맞춘다(억원).
            "market_cap": pd.to_numeric(cap["시가총액"], errors="coerce").fillna(0)
            / 1_0000_0000,
        }
    ).reset_index(drop=True)


def build_weekly_snapshot(end: Optional[date] = None) -> Optional[dict[str, Any]]:
    """주간 리포트의 사실 스냅샷. 수치가 부족하면 None(= 생성 거부)."""
    start, finish = _week_bounds(end)

    try:
        df = _fetch_krx_weekly(start, finish)
    except Exception as e:
        logger.warning(f"[premium_weekly] KRX 주간 시세 조회 실패: {e}")
        return None
    if len(df) < _MIN_TICKERS:
        logger.warning(
            f"[premium_weekly] 주간 등락 산출 종목 부족({len(df)} < {_MIN_TICKERS}) — 생성 거부. "
            f"KRX_ID/KRX_PW 설정과 KRX 점검 시간대를 확인할 것."
        )
        return None

    try:
        cap = _fetch_krx_cap(finish)
    except Exception as e:
        logger.warning(f"[premium_weekly] KRX 시총 조회 실패: {e}")
        return None
    if cap.empty:
        logger.warning("[premium_weekly] 시총 비어 있음 — 생성 거부")
        return None
    df = df.merge(cap, on="ticker", how="left")
    df["market_cap"] = df["market_cap"].fillna(0)

    # 업종은 느리게 변하므로 기존 스냅샷(네이버 수집분)을 그대로 붙인다.
    # 없어도 업종 섹션만 빠질 뿐 리포트는 성립하므로 실패를 치명으로 보지 않는다.
    try:
        from screener.db import repository

        stocks = repository.load_stocks("kr")
        if stocks is not None and not stocks.empty and "sector" in stocks.columns:
            df = df.merge(
                stocks[["ticker", "sector"]].drop_duplicates("ticker"),
                on="ticker",
                how="left",
            )
    except Exception as e:
        logger.warning(f"[premium_weekly] 업종 정보 결합 실패(업종 섹션 생략): {e}")
    if "sector" not in df.columns:
        df["sector"] = ""
    df["sector"] = df["sector"].fillna("")

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
    # 상/하위를 각각 잘라 쓰면 업종이 20개 남짓일 때 겹친다. 실제로 첫 실행에서 '제약'이
    # 상위·하위에 동시에 나왔다 — 그대로 두면 글이 자기모순을 쓴다.
    sectors_top = sectors[:_SECTOR_N]
    sectors_bottom = sectors[len(sectors_top):][-_SECTOR_N:][::-1]

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

    # ── 무결성 검사: 대표 종목이 표본에 있는가.
    # pykrx는 전 종목을 한 번에 주므로 예전 history 방식 같은 표본 편향은 구조적으로
    # 생기지 않는다. 다만 KRX가 부분 응답을 주는 경우(점검·장애)를 잡아야 해서
    # 시가총액 최상위가 실제로 들어있는지 확인한다.
    heavyweights = set(df.nlargest(30, "market_cap")["ticker"])
    covered = len(heavyweights)
    if df["market_cap"].sum() <= 0 or covered < 30:
        logger.warning(
            "[premium_weekly] 시총 결합 실패 — 업종·규모별 집계가 불가하므로 생성 거부"
        )
        return None

    # ── 파생값은 **코드가 계산해서 준다.**
    # 첫 실측(2026-08-09)에서 모델이 거래대금 상위 8개 합산을 54.01% 대신 58.01%로
    # 썼다. 가드가 잡긴 했지만, 애초에 LLM에게 덧셈을 시킬 이유가 없다.
    # (기호 위계를 코드가 붙이는 것과 같은 원칙 — 결정론적인 건 결정론적으로.)
    shares = [t["share"] for t in turnover]
    cum = {}
    for k in (2, 4, 8):
        if len(shares) >= k:
            cum[k] = round(sum(shares[:k]), 2)
    # 분모는 **전체 집계 종목**(보합 포함). up+down으로 나누면 보합이 빠져 비율이
    # 부풀고, 독자가 "2,872개 중 몇 %"로 읽는 것과 어긋난다.
    universe_cnt = len(df)
    derived = {
        "up_ratio": round(up / universe_cnt * 100, 1) if universe_cnt else 0.0,
        "flat": max(0, universe_cnt - up - down),
        "turnover_cum": cum,
        "size_gap": (
            round(size_buckets[0]["ret"] - size_buckets[-1]["ret"], 2)
            if len(size_buckets) >= 2
            else None
        ),
    }

    return {
        "market": "KR",
        "week_label": week_range_label(start, finish),
        "derived": derived,
        "start": start.isoformat(),
        "end": finish.isoformat(),
        "universe": int(len(df)),
        "sector_count": len(sectors),
        "breadth": {"up": up, "down": down},
        "sectors_top": sectors_top,
        "sectors_bottom": sectors_bottom,
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
        f"[집계 대상] 국내 상장 전 종목 {snap['universe']}개(코스피+코스닥, KRX 기준)",
        f"[등락 폭] 오른 종목 {snap['breadth']['up']}개 / 내린 종목 {snap['breadth']['down']}개",
        "",
        "[규모별 주간 등락 — 시총 가중]",
    ]
    L += [f"- {b['name']}: {b['ret']:+.2f}% ({b['n']}종목)" for b in snap.get("sizes", [])]

    # 업종 총 개수를 명시하지 않으면 모델이 "23개 업종 중" 같은 수를 지어낸다
    # (첫 실행에서 실제로 환각했다 — 학습데이터의 코스피 업종 수로 보인다).
    L += ["", f"[집계된 업종 수] {snap.get('sector_count', 0)}개"]
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
        L += ["", "[거래대금 상위 종목과 비중 — 해당 주 누적 기준]"]
        L += [
            f"- {t['name']}({t['ticker']}): 주간 전체 거래대금의 {t['share']:.2f}%"
            for t in snap["turnover"]
        ]

    # 파생값은 코드가 계산해 넘긴다 — 모델에게 덧셈을 시키면 틀린다(실측 확인).
    d = snap.get("derived") or {}
    if d:
        L += ["", "[미리 계산된 파생 수치 — 이 값을 그대로 쓸 것. 직접 더하지 말 것]"]
        L += [
            f"- 상승 종목 비율: 전체 집계 종목 대비 {d.get('up_ratio')}%"
            f" (보합 {d.get('flat', 0)}개 포함한 분모)"
        ]
        for k, v in (d.get("turnover_cum") or {}).items():
            L.append(f"- 거래대금 상위 {k}개 종목 합산 비중: {v:.2f}%")
        if d.get("size_gap") is not None:
            L.append(f"- 대형주와 소형주 등락 격차: {d['size_gap']:+.2f}%포인트")

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
  · **직접 덧셈하지 마세요.** 필요한 합계·비율·격차는 [미리 계산된 파생 수치]에
    이미 있습니다. 거기 없는 합계가 필요하면 그 문장을 쓰지 마세요.
  · 특히 **'전체 ○개 업종 중' 같은 총 개수를 지어내지 마세요.** [사실]에 적힌 수만 씁니다.
- '지수'라고 쓸 때는 **무엇의 지수인지 밝히세요.** [사실]에 코스피·코스닥 지수 포인트는
  없습니다. 규모별 집계를 '지수'로 부를 때는 반드시 '대형주 기준'처럼 한정합니다.
- 지수(코스피/코스닥) 포인트 값은 [사실]에 없으면 언급하지 마세요. 추측 금지입니다.
- **주가 수준으로 시가총액을 추론하지 마세요.** "주가가 5만 원이 넘으니 대형주일 것"은
  틀린 추론입니다. 주당 가격과 시총은 무관합니다. 규모 판단은 [사실]의 규모별 집계로만.
- 집계 대상은 **전체 시장이 아닙니다.** '코스피 전 종목', '국내 증시 전체'로 확대해
  쓰지 말고 '집계 대상 N종목 가운데'로 한정해 쓰세요.
- 없는 데이터를 아쉬워하는 문장도 쓰지 마세요. 있는 것으로만 완결합니다.

## 분량
경쟁 글은 17,000자입니다. 섹션당 최소 2,000자를 채우세요. 섹션 4~5개를 쓰되,
각 섹션에서 수치를 **다른 수치와 교차**시켜 파고들면 분량은 자연히 나옵니다.
같은 문장을 바꿔 쓰며 늘리는 것은 즉시 반려 사유입니다."""


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
