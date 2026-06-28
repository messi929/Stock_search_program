"""밸류에이션 밴드 + 이익(EPS) 사이클 — 경기민감주 PER 함정 방어 (1b/1c).

현황 PER/PBR 단일값은 경기민감주(반도체 등)에서 신호가 거꾸로 나온다(호황 이익피크에
PER이 낮게 보이는 착시). 그래서 **PER/PBR을 자기 역사 밴드 안에서** 보고, **EPS가
사이클의 어디(피크/저점)에 있는지**를 함께 본다.

데이터: pykrx `get_market_fundamental_by_date` (일별 [BPS, PER, PBR, EPS, DIV, DPS]).
무거운 히스토리는 백필 잡이 종목별로 한 번 당겨 '밴드 요약'(분위수 + EPS 요약)만
Firestore `fundamental_band/{ticker}`에 적재한다. 생성 시점에는 이 작은 요약만 읽는다.

LEGAL: 추천/목표가 아님. 관찰·해석만.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd
from loguru import logger

# pykrx 펀더멘탈 컬럼(확정): BPS PER PBR EPS DIV DPS
_FUND_COLS = ("BPS", "PER", "PBR", "EPS", "DIV", "DPS")


def fetch_fundamental_history(
    ticker: str, fromdate: str, todate: str
) -> Optional[pd.DataFrame]:
    """pykrx 일별 펀더멘탈 히스토리. KRX 점검/결손 시 None(graceful).

    Args:
        ticker: 6자리 종목코드
        fromdate, todate: 'YYYYMMDD'
    Returns:
        DataFrame[BPS,PER,PBR,EPS,DIV,DPS] (date index) 또는 None.
    """
    try:
        from pykrx import stock

        df = stock.get_market_fundamental_by_date(fromdate, todate, ticker)
        if df is None or df.empty or "PER" not in df.columns:
            # KRX 펀더멘탈 엔드포인트 야간점검 등 → 빈 응답. 호출부에서 skip.
            logger.debug(f"[fund_band] 빈 응답 {ticker} ({fromdate}~{todate})")
            return None
        return df
    except Exception as e:
        logger.debug(f"[fund_band] pykrx 실패 {ticker}: {type(e).__name__}: {e}")
        return None


def _quantiles(s: pd.Series) -> Optional[dict]:
    """양(+)의 값만으로 분위수 요약. 표본<30이면 None(밴드 신뢰 불가)."""
    s = pd.to_numeric(s, errors="coerce")
    s = s[s > 0].dropna()
    if len(s) < 30:
        return None
    return {
        "min": round(float(s.min()), 2),
        "p25": round(float(s.quantile(0.25)), 2),
        "median": round(float(s.median()), 2),
        "p75": round(float(s.quantile(0.75)), 2),
        "max": round(float(s.max()), 2),
    }


def compute_band(df: pd.DataFrame, ticker: str) -> Optional[dict]:
    """펀더멘탈 히스토리 → 밴드 요약(분위수 + EPS 사이클 요약). 표본 부족 시 None.

    순수 함수(네트워크 무관) — 합성 데이터로 단위 검증 가능.
    """
    if df is None or df.empty or "PER" not in df.columns:
        return None

    per = _quantiles(df["PER"])
    pbr = _quantiles(df["PBR"]) if "PBR" in df.columns else None
    if not per and not pbr:
        return None

    band: dict = {
        "ticker": ticker,
        "samples": int(len(df)),
        "per": per,
        "pbr": pbr,
    }

    # ── EPS 사이클(1c): 추세 + 피크 근접도 ──
    if "EPS" in df.columns:
        eps = pd.to_numeric(df["EPS"], errors="coerce").dropna()
        if len(eps) >= 30:
            latest = float(eps.iloc[-1])
            eps_max = float(eps.max())
            eps_min = float(eps.min())
            # 1년 전(≈252거래일) 대비 추세. 데이터 짧으면 가장 오래된 값 대비.
            prev = float(eps.iloc[-252]) if len(eps) > 252 else float(eps.iloc[0])
            trend_pct = round((latest / prev - 1.0) * 100, 1) if prev else None
            # 자기 역사 최대 대비 위치(피크=1.0 근처). 이익 피크 판정용.
            vs_max = round((latest / eps_max) * 100, 1) if eps_max > 0 else None
            band["eps"] = {
                "latest": round(latest, 1),
                "min": round(eps_min, 1),
                "max": round(eps_max, 1),
                "trend_pct": trend_pct,   # 1년 전 대비 %
                "vs_max_pct": vs_max,     # 역사 최대 대비 %(100 근처=이익 피크)
            }
    return band


def _pos_in_band(value: float, q: dict) -> str:
    """현재값이 밴드(분위수) 어디에 있는지 한국어 라벨."""
    if value <= q["p25"]:
        return "하단권(저평가 구간)"
    if value <= q["median"]:
        return "중하단"
    if value <= q["p75"]:
        return "중상단"
    return "상단권(고평가 구간)"


def band_facts(band: Optional[dict], cur_per: Optional[float], cur_pbr: Optional[float]) -> str:
    """밴드 요약 + 현재 PER/PBR → 마케팅 facts용 '## 밸류에이션 밴드' 블록.

    현재값을 자기 역사 분위수에 비춰 '하단/상단' 위치와 EPS 사이클 위치를 제시한다.
    밴드 없으면 빈 문자열.
    """
    if not band:
        return ""
    lines: list[str] = []
    per_q = band.get("per")
    if per_q and cur_per and cur_per > 0:
        lines.append(
            f"- PER {cur_per:.1f} — 최근 범위 {per_q['min']}~{per_q['max']}, "
            f"중앙값 {per_q['median']} → {_pos_in_band(cur_per, per_q)}"
        )
    elif per_q:
        lines.append(f"- PER 역사 범위 {per_q['min']}~{per_q['max']}, 중앙값 {per_q['median']}")
    pbr_q = band.get("pbr")
    if pbr_q and cur_pbr and cur_pbr > 0:
        lines.append(
            f"- PBR {cur_pbr:.2f} — 최근 범위 {pbr_q['min']}~{pbr_q['max']}, "
            f"중앙값 {pbr_q['median']} → {_pos_in_band(cur_pbr, pbr_q)}"
        )
    eps = band.get("eps")
    if eps:
        bits = []
        if eps.get("trend_pct") is not None:
            arrow = "증가" if eps["trend_pct"] > 0 else ("감소" if eps["trend_pct"] < 0 else "보합")
            bits.append(f"1년 전 대비 {eps['trend_pct']:+.0f}% {arrow}")
        if eps.get("vs_max_pct") is not None:
            if eps["vs_max_pct"] >= 90:
                bits.append("역사적 최고 부근(이익 피크 구간)")
            elif eps["vs_max_pct"] <= 30:
                bits.append("역사적 저점권(이익 바닥 구간)")
            else:
                bits.append(f"역사 최대의 {eps['vs_max_pct']:.0f}% 수준")
        if bits:
            lines.append(f"- 주당순이익(EPS): {', '.join(bits)}")
    if not lines:
        return ""
    samples = band.get("samples", 0)
    return (
        f"## 밸류에이션 밴드 (최근 {samples}거래일 기준)\n"
        + "\n".join(lines)
        + "\n(현황 단일 PER/PBR의 함정 방어: 자기 역사 안에서 비싼지/싼지, 이익 사이클 어디인지)"
    )


def cycle_assessment(band: Optional[dict], cur_per: Optional[float]) -> str:
    """경기민감주에서 'PER + EPS 사이클'을 결합한 한 줄 경고(있을 때만).

    저PER인데 이익이 피크 → 함정 가능. 고PER인데 이익이 바닥 → 회복 초입 가능.
    """
    if not band:
        return ""
    eps = band.get("eps")
    per_q = band.get("per")
    if not eps or eps.get("vs_max_pct") is None or not per_q or not cur_per:
        return ""
    low_per = cur_per <= per_q["median"]
    high_per = cur_per >= per_q["p75"]
    peak_eps = eps["vs_max_pct"] >= 90
    trough_eps = eps["vs_max_pct"] <= 30
    if low_per and peak_eps:
        return (
            "PER이 역사 하단인데 EPS는 사상 최고 부근 — 전형적 '이익 피크의 낮은 PER' 함정 "
            "신호일 수 있다(이익이 꺾이면 PER은 다시 뛴다)."
        )
    if high_per and trough_eps:
        return (
            "PER이 역사 상단인데 EPS는 바닥권 — '이익 저점의 높은 PER'로, 이익이 돌면 "
            "PER이 빠르게 낮아질 수 있는 회복 초입 구도일 수 있다."
        )
    return ""
