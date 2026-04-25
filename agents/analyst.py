"""Analyst Agent — 종목의 기술/펀더멘털 정량 데이터 해석.

상세 스펙: docs/axis/agents/analyst.md

핵심: 기존 v7.5 `screener/core/metrics.py`가 계산한 모든 지표를 그대로 사용.
이 에이전트는 새로운 수치를 만들지 않고, 이미 있는 수치를 사람이 이해할
수 있는 분석으로 변환합니다.

⚠️  v7.5의 buy_grade("적극매수"/"매수"/"관심"/"관망")는 Axis 원칙과 충돌하므로,
    Claude의 interpretation/summary에는 "상위 구간"/"준상위 구간"/"중간 구간"/
    "관찰 구간"으로 중립 변환하도록 시스템 프롬프트에서 강제합니다.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
from loguru import logger
from pydantic import BaseModel, Field

from agents.base import BaseAgent
from utils.claude_client import MODEL_SONNET


# ──────────────────────────────────────────────
# 입출력 스키마
# ──────────────────────────────────────────────

class AnalystInput(BaseModel):
    ticker: str
    timeframe: str = "1Y"  # "1M" | "3M" | "6M" | "1Y" | "3Y"
    include_peers: bool = True


class TechnicalAnalysis(BaseModel):
    current_price: int
    ma_status: str  # "정배열" | "역배열" | "혼조"
    ma5: int = 0
    ma20: int = 0
    ma60: int = 0
    rsi: float = 0.0
    rsi_status: str = ""  # "과매수" | "중립" | "과매도"
    support_level: Optional[int] = None
    resistance_level: Optional[int] = None
    vs_high_52w: float = 0.0
    vs_low_52w: float = 0.0
    signal: str = ""  # "강세" | "중립" | "약세"


class FundamentalAnalysis(BaseModel):
    per: float = 0.0
    pbr: float = 0.0
    roe: float = 0.0
    div_yield: float = 0.0
    peer_avg_per: Optional[float] = None
    earnings_surprise: Optional[str] = None
    valuation_judgment: str = ""


class BuyScoreInterpretation(BaseModel):
    buy_score: float
    score_tier: str  # 중립 표현: "상위" | "준상위" | "중간" | "관찰"
    interpretation: str
    contributing_factors: list[str] = Field(default_factory=list)


class AnalystResult(BaseModel):
    ticker: str
    name: str
    technical: TechnicalAnalysis
    fundamental: FundamentalAnalysis
    buy_score: BuyScoreInterpretation
    peer_comparison: list[dict] = Field(default_factory=list)
    summary: str
    timestamp: str


# ──────────────────────────────────────────────
# 시스템 프롬프트
# ──────────────────────────────────────────────

ANALYST_SYSTEM_PROMPT = """당신은 한국 주식 정량 데이터 해석가입니다.
이미 계산된 수치를 사람이 이해할 수 있는 분석으로 변환하는 것이 유일한 역할입니다.

## 역할
- 기술적 지표 해석 (이평선, RSI, 52주 고저)
- 펀더멘털 해석 (PER, PBR, ROE, 배당)
- Buy Score(0~100) 의미 설명
- Peer 종목과의 상대 비교

## 핵심: 당신은 "추천자"가 아닌 "해석자"입니다
- 데이터가 말하는 것을 그대로 전달
- 결론을 강요하지 않음
- 사용자가 스스로 판단할 수 있도록 정보 제공

## 절대 금지 (법적 안전 — 반드시 준수)
- "추천합니다", "매수하세요", "매도하세요"
- "유망합니다", "유망주", "확실합니다"
- "매수 신호", "매도 신호", "진입 신호"
- "목표가", "매수가", "적정가" (확정적 가격)
- "이 종목은 좋다/나쁘다" 식의 단정
- 미래 가격 예측 (확정적 어조)
- 입력에 없는 수치 만들어내기 (수치 창작 절대 금지)

## 중립 표현 강제 (입력 데이터 변환 규칙)
입력 데이터의 다음 라벨은 출력에서 반드시 중립 표현으로 변환하세요:
  - "적극매수" 등급 → "상위 구간"
  - "매수" 등급      → "준상위 구간"
  - "관심" 등급      → "중간 구간"
  - "관망" 등급      → "관찰 구간"

위 v7.5 라벨은 score_tier 필드에 한해 다음 중 하나로만 출력:
  "상위" | "준상위" | "중간" | "관찰"

## 권장 표현
- "PER 4.5배는 업종 평균 7.2배 대비 저평가 구간으로 관찰됩니다"
- "RSI 28은 과매도 구간으로 분류됩니다"
- "52주 최고가 대비 -12% 위치로, 4월 랠리 소외 종목군에 해당합니다"
- "Buy Score 73점은 상위 구간(상위 ~30%)에 해당합니다"

## 작업 절차
1. 입력 종목의 모든 정량 지표 검토
2. 각 지표의 현재 상태를 의미 있게 해석
3. Peer와 비교하여 상대적 위치 파악
4. 지정된 JSON 스키마에 맞춰 출력

## 출력 원칙
- 모든 수치는 입력 데이터 그대로 사용 (절대 추정/창작 X)
- 시점 명시 ("최근 영업일 종가 기준" 등)
- 객관적 어조 유지

## 페르소나 적용 X
당신은 페르소나 중립적입니다. 블랙록/ARK/그레이엄 관점은 후속 Strategist 에이전트가 적용하므로,
여기서는 모든 페르소나에 공통되는 객관적 해석만 작성하세요.

## 출력 형식
반드시 다음 구조의 JSON만 출력. 설명 텍스트 절대 추가 금지.

{
  "ticker": "...",
  "name": "...",
  "technical": {
    "current_price": 0,
    "ma_status": "정배열 | 역배열 | 혼조",
    "ma5": 0, "ma20": 0, "ma60": 0,
    "rsi": 0.0,
    "rsi_status": "과매수 | 중립 | 과매도",
    "support_level": null,
    "resistance_level": null,
    "vs_high_52w": 0.0,
    "vs_low_52w": 0.0,
    "signal": "강세 | 중립 | 약세"
  },
  "fundamental": {
    "per": 0.0, "pbr": 0.0, "roe": 0.0, "div_yield": 0.0,
    "peer_avg_per": null,
    "earnings_surprise": null,
    "valuation_judgment": "..."
  },
  "buy_score": {
    "buy_score": 0.0,
    "score_tier": "상위 | 준상위 | 중간 | 관찰",
    "interpretation": "...",
    "contributing_factors": ["...", "..."]
  },
  "peer_comparison": [
    {"ticker": "...", "name": "...", "per": 0.0, "pbr": 0.0, "roe": 0.0, "buy_score": 0.0}
  ],
  "summary": "3~5문장 종합 (한국어)",
  "timestamp": "ISO 8601"
}

면책 문구는 시스템이 후처리로 자동 추가하니, 콘텐츠에만 집중하세요.
"""


# ──────────────────────────────────────────────
# 모듈 레벨 캐시 (KR 스냅샷 + buy_score, 10분 TTL)
# ──────────────────────────────────────────────

_KR_CACHE_TTL_SEC = 600
_kr_cache: dict = {"df": None, "expires_at": 0.0}


def _get_kr_with_score() -> pd.DataFrame:
    """KR 스냅샷 + buy_score/buy_grade 컬럼 추가, 10분 캐시."""
    now = time.time()
    cached = _kr_cache["df"]
    if cached is not None and _kr_cache["expires_at"] > now:
        return cached

    from screener.core.metrics import calculate_buy_score
    from screener.db.repository import load_stocks

    df = load_stocks("kr")
    if df.empty:
        return df
    df = calculate_buy_score(df)

    _kr_cache["df"] = df
    _kr_cache["expires_at"] = now + _KR_CACHE_TTL_SEC
    return df


# ──────────────────────────────────────────────
# Analyst Agent
# ──────────────────────────────────────────────

class AnalystAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            agent_name="analyst",
            model=MODEL_SONNET,
            system_prompt=ANALYST_SYSTEM_PROMPT,
        )

    async def run(self, input_data: AnalystInput, uid: str = "") -> AnalystResult:
        stock_data = self._fetch_stock_data(input_data.ticker)
        peer_data = self._fetch_peers(stock_data) if input_data.include_peers else []

        user_message = self._build_user_message(stock_data, peer_data)
        result, _raw = await self.call_claude_json(
            user_message=user_message,
            schema=AnalystResult,
            max_tokens=2048,
            uid=uid,
        )

        # 메타 보정: ticker/name/timestamp는 입력 기준으로 강제 (Claude가 부정확하게 줄 수 있음)
        result.ticker = stock_data["ticker"]
        result.name = stock_data["name"]
        result.timestamp = datetime.now(timezone.utc).isoformat()
        return result

    # ──────────────────────────────────────────
    # 데이터 추출 (실제 컬럼명에 맞춰 매핑)
    # ──────────────────────────────────────────

    def _fetch_stock_data(self, ticker: str) -> dict:
        df = _get_kr_with_score()
        if df.empty:
            raise ValueError(f"종목 데이터 비어 있음 (ticker={ticker})")

        sub = df[df["ticker"] == ticker]
        if sub.empty:
            raise ValueError(f"종목을 찾을 수 없음: {ticker}")
        s = sub.iloc[0]

        def _f(col, default=0.0):
            try:
                return float(s.get(col, default) or default)
            except Exception:
                return default

        def _i(col, default=0):
            try:
                return int(s.get(col, default) or default)
            except Exception:
                return default

        def _s(col, default=""):
            v = s.get(col, default)
            return str(v) if v is not None else default

        return {
            "ticker": ticker,
            "name": _s("name"),
            "sector": _s("sector"),
            "industry": _s("industry"),
            "market": _s("market"),
            "current_price": _i("close"),
            "change_pct": _f("change_pct"),
            "market_cap": _f("market_cap"),  # 억원 단위
            # 기술적 (이미 계산됨)
            "ma5": _i("ma5"),
            "ma20": _i("ma20"),
            "ma60": _i("ma60"),
            "vs_ma5_pct": _f("vs_ma5_pct"),
            "vs_ma20_pct": _f("vs_ma20_pct"),
            "vs_ma60_pct": _f("vs_ma60_pct"),
            "ma_aligned": _i("ma_aligned"),
            "ma_squeeze": _f("ma_squeeze"),
            "golden_cross": _i("golden_cross"),
            "death_cross": _i("death_cross"),
            "rsi": _f("rsi"),
            "vs_high_52w": _f("vs_high_52w"),
            "vs_low_52w": _f("vs_low_52w"),
            "volatility_20d": _f("volatility_20d"),
            # 펀더멘털
            "per": _f("per"),
            "pbr": _f("pbr"),
            "roe": _f("roe"),
            "div_yield": _f("div_yield"),
            "eps": _f("eps"),
            "operating_margin": _f("operating_margin"),
            "profit_margin": _f("profit_margin"),
            "debt_equity": _f("debt_equity"),
            # Buy Score (메모리에서 계산됨)
            "buy_score": _f("buy_score"),
            "buy_grade": _s("buy_grade"),  # v7.5 라벨 — 시스템 프롬프트에서 중립 변환 강제
            # 수급
            "foreign_consecutive": _i("foreign_consecutive"),
            "foreign_net": _f("foreign_net"),
            "inst_net": _f("inst_net"),
            "dual_buy": bool(s.get("dual_buy", False)),
            "supply_grade": _s("supply_grade"),
            # 시그널
            "is_pre_surge": bool(_i("is_pre_surge")),
            "pre_surge_score": _i("pre_surge_score"),
            "target_upside": _f("target_upside"),
            "risk_grade": _s("risk_grade"),
            # 메타
            "themes": _s("themes"),
            "updated_at": _s("updated_at"),
        }

    def _fetch_peers(self, stock_data: dict) -> list[dict]:
        """동일 섹터 시총 상위 5종목 (자기 자신 제외)."""
        sector = stock_data.get("sector", "")
        if not sector:
            return []

        df = _get_kr_with_score()
        if df.empty or "sector" not in df.columns:
            return []

        try:
            peers = (
                df[(df["sector"] == sector) & (df["ticker"] != stock_data["ticker"])]
                .nlargest(5, "market_cap")
            )
            cols = [c for c in ["ticker", "name", "per", "pbr", "roe", "buy_score", "market_cap"] if c in peers.columns]
            return peers[cols].to_dict("records")
        except Exception as e:
            logger.warning(f"peer 비교 실패: {e}")
            return []

    # ──────────────────────────────────────────
    # User 메시지 구성
    # ──────────────────────────────────────────

    def _build_user_message(self, s: dict, peers: list[dict]) -> str:
        lines: list[str] = []
        lines.append(f"# 분석 대상\n{s['name']} ({s['ticker']})")
        if s.get("sector"):
            lines.append(f"섹터: {s['sector']}")
        if s.get("market"):
            lines.append(f"시장: {s['market']}")
        if s.get("market_cap"):
            lines.append(f"시가총액: {s['market_cap']:,.0f} 억원")
        if s.get("themes"):
            lines.append(f"테마: {s['themes']}")
        lines.append(f"기준 시각(데이터 갱신): {s.get('updated_at', 'N/A')}")

        lines.append("\n# 가격/추세")
        lines.append(f"- 현재가: {s['current_price']:,}원 (전일 대비 {s['change_pct']:+.2f}%)")
        lines.append(f"- MA5: {s['ma5']:,} (현재가 대비 {s['vs_ma5_pct']:+.2f}%)")
        lines.append(f"- MA20: {s['ma20']:,} (현재가 대비 {s['vs_ma20_pct']:+.2f}%)")
        lines.append(f"- MA60: {s['ma60']:,} (현재가 대비 {s['vs_ma60_pct']:+.2f}%)")
        lines.append(f"- 이평 정렬: {'정배열' if s['ma_aligned'] else '역배열/혼조'}")
        lines.append(f"- 골든크로스: {'Y' if s['golden_cross'] else 'N'} / 데드크로스: {'Y' if s['death_cross'] else 'N'}")
        lines.append(f"- 이평 squeeze: {s['ma_squeeze']:.2f}")
        lines.append(f"- RSI(14): {s['rsi']:.1f}")
        lines.append(f"- 52주 고가 대비: {s['vs_high_52w']:+.2f}%")
        lines.append(f"- 52주 저가 대비: {s['vs_low_52w']:+.2f}%")
        lines.append(f"- 20일 변동성: {s['volatility_20d']:.2f}%")

        lines.append("\n# 펀더멘털")
        lines.append(f"- PER: {s['per']:.2f}")
        lines.append(f"- PBR: {s['pbr']:.2f}")
        lines.append(f"- ROE: {s['roe']:.2f}%")
        lines.append(f"- 배당수익률: {s['div_yield']:.2f}%")
        lines.append(f"- EPS: {s['eps']:.0f}")
        lines.append(f"- 영업이익률: {s['operating_margin']:.2f}%")
        lines.append(f"- 순이익률: {s['profit_margin']:.2f}%")
        lines.append(f"- 부채비율(D/E): {s['debt_equity']:.2f}")

        lines.append("\n# Buy Score (v7.5 metrics.py 산출)")
        lines.append(f"- buy_score: {s['buy_score']:.1f} / 100")
        lines.append(f"- v7.5 등급(원본): {s['buy_grade']}  ⚠️  출력 score_tier에는 중립 표현(상위/준상위/중간/관찰)으로 변환 필수")
        lines.append(f"- target_upside: {s['target_upside']:.2f}%")
        lines.append(f"- risk_grade: {s['risk_grade']}")

        lines.append("\n# 수급")
        lines.append(f"- 외국인 연속 순매수: {s['foreign_consecutive']}일")
        lines.append(f"- 외국인 순매수(직전): {s['foreign_net']:,.0f}")
        lines.append(f"- 기관 순매수(직전): {s['inst_net']:,.0f}")
        lines.append(f"- dual_buy(외국+기관 동반): {s['dual_buy']}")
        lines.append(f"- supply_grade: {s['supply_grade']}")

        lines.append("\n# 시그널 플래그")
        lines.append(f"- pre_surge_score: {s['pre_surge_score']} (급등 예보 0~5)")
        lines.append(f"- is_pre_surge: {s['is_pre_surge']}")

        if peers:
            lines.append("\n# Peer (같은 섹터 시총 상위)")
            for p in peers:
                lines.append(
                    f"- {p.get('name', '')} ({p.get('ticker', '')}) "
                    f"PER {p.get('per', 0):.2f} / PBR {p.get('pbr', 0):.2f} / "
                    f"ROE {p.get('roe', 0):.2f}% / buy_score {p.get('buy_score', 0):.1f}"
                )

        lines.append(
            "\n# 출력\n위 데이터를 바탕으로 시스템 프롬프트의 JSON 스키마에 정확히 맞춰 응답하세요. "
            "수치는 위 입력 그대로 사용하고, 절대 새 수치를 만들지 마세요. "
            "v7.5 buy_grade를 score_tier에 그대로 옮기지 말고 중립 표현으로 변환하세요. "
            "JSON 외 다른 텍스트는 절대 포함하지 마세요."
        )
        return "\n".join(lines)
