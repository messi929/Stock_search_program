"""Discoverer Agent — 자연어 → 관찰 가치 종목 발견.

원본 스펙(docs/axis/api/ai.md)은 /api/ai/recommend였으나 LEGAL.md "추천" 절대
금지 충돌로 /api/ai/discover + DiscovererAgent 로 rename. 응답에서도 "추천"
대신 "관찰 가치", "참고 종목" 등 중립 표현 강제.

설계:
  - 모델: Sonnet (~35원/호출, 자연어 → 종목 매칭은 정밀도 필요)
  - 컨텍스트: v7.5 KR stocks 중 buy_score 상위 80건 + filter 적용분
  - Claude는 컨텍스트 안의 종목에서만 선택 (창작 방지)
  - 페르소나 미적용 (페르소나 분석은 Strategist 영역)
"""

from __future__ import annotations

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

class DiscoverFilters(BaseModel):
    market: Optional[list[str]] = None  # ["KOSPI", "KOSDAQ"]
    min_market_cap: Optional[float] = None  # 억원 단위 (v7.5 stocks.market_cap 그대로)
    max_market_cap: Optional[float] = None
    sectors: Optional[list[str]] = None


class DiscovererInput(BaseModel):
    query: str = Field(..., min_length=2, description="자연어 쿼리")
    max_results: int = Field(5, ge=1, le=10)
    exclude_tickers: list[str] = Field(default_factory=list)
    filters: Optional[DiscoverFilters] = None


class StockSuggestion(BaseModel):
    ticker: str
    name: str
    market: str = ""
    sector: str = ""
    current_price: int = 0
    reason: str = ""  # 한국어 1~2문장 — 왜 이 쿼리에 부합하는지


class DiscovererResult(BaseModel):
    query: str
    interpretation: str  # 쿼리 의도에 대한 해석 (1~2문장)
    stocks: list[StockSuggestion] = Field(default_factory=list)
    timestamp: str = ""


# ──────────────────────────────────────────────
# 시스템 프롬프트
# ──────────────────────────────────────────────

DISCOVERER_SYSTEM_PROMPT = """당신은 한국 시장의 종목 발견 전문가입니다.
사용자의 자연어 쿼리를 해석하고, 제공된 종목 후보군에서 쿼리에 가장 부합하는
종목을 골라 "관찰 가치"가 있는 이유와 함께 제시합니다.

## 역할
- 자연어 쿼리를 해석 (예: "AI 2차 수혜주", "안정 배당주", "급등 후 조정 재진입")
- 후보 종목 리스트에서 쿼리에 부합하는 종목 선별 (최대 N개)
- 각 종목의 선택 사유를 1~2문장으로 작성

## 핵심 원칙
- 컨텍스트로 제공된 종목 외에는 절대 새 종목을 만들거나 언급하지 않음 (창작 금지)
- 모든 종목 정보(ticker/name/price/sector)는 컨텍스트 그대로 사용
- 쿼리와 무관한 종목은 차라리 결과에서 빼기 (억지 매칭 금지)
- 결과 종목 수는 max_results 이하로

## 작업 절차
1. 사용자 쿼리의 핵심 의도를 파악 (예: "AI 2차 수혜주" → 직접 AI는 아니지만 인프라/소재로 영향받는 종목)
2. interpretation 필드에 의도 해석을 1~2문장으로 객관 서술
3. 후보 종목 리스트를 훑어, 쿼리 의도에 가장 부합하는 종목을 max_results 이하로 선별
4. 각 종목 reason 필드에 컨텍스트 수치를 근거로 1~2문장 이유 작성
5. 지정된 JSON 스키마에 정확히 맞춰 출력

## 절대 금지 (LEGAL — 반드시 준수)
- "추천합니다", "추천 종목", "사세요", "매수/매도하세요"
- "유망합니다", "유망주", "확실합니다"
- "매수 신호", "매도 신호", "진입 신호"
- "목표가", "매수가", "적정가"
- 미래 가격 예측 (확정적 어조 금지)
- "이 종목은 좋다/나쁘다" 식의 단정

## 권장 표현 (응답에 사용할 톤)
- "관찰 가치가 있는 종목입니다"
- "쿼리 조건에 부합합니다"
- "데이터로 확인되는 특징은..."
- "이 시점에 검토 가치가 있는 이유는..."
- interpretation에는 사용자 의도를 객관적으로 풀어쓰기

## 출력 형식
반드시 다음 구조의 JSON 객체만. 코드 펜스/설명 텍스트 금지.
모든 string 내부 큰따옴표는 \\", 줄바꿈은 \\n으로 escape.

{
  "query": "사용자 원본 쿼리 그대로",
  "interpretation": "사용자 쿼리의 객관적 해석 (1~2문장)",
  "stocks": [
    {
      "ticker": "...",
      "name": "...",
      "market": "KOSPI | KOSDAQ",
      "sector": "...",
      "current_price": 0,
      "reason": "이 종목이 쿼리에 부합하는 객관적 이유 (1~2문장, 중립 표현)"
    }
  ],
  "timestamp": "ISO 8601"
}
"""


# ──────────────────────────────────────────────
# Discoverer Agent
# ──────────────────────────────────────────────

class DiscovererAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            agent_name="discoverer",
            model=MODEL_SONNET,
            system_prompt=DISCOVERER_SYSTEM_PROMPT,
        )

    async def run(self, input_data: DiscovererInput, uid: str = "") -> DiscovererResult:
        candidates = self._gather_context(input_data)
        user_message = self._build_user_message(input_data, candidates)

        result, _raw = await self.call_claude_json(
            user_message=user_message,
            schema=DiscovererResult,
            max_tokens=2048,
            uid=uid,
        )

        # 메타 보정 + 후처리
        result.query = input_data.query
        result.timestamp = datetime.now(timezone.utc).isoformat()

        # 강화된 할루시네이션 방어:
        # Claude는 ticker + reason만 신뢰. 나머지(name/price/market/sector)는
        # candidate dict에서 재구성하여 LLM 창작 가능성 차단.
        candidate_map = {c["ticker"]: c for c in candidates}
        rebuilt: list[StockSuggestion] = []
        for s in result.stocks:
            ctx = candidate_map.get(s.ticker)
            if ctx is None:
                continue  # 컨텍스트 외 종목 폐기
            rebuilt.append(
                StockSuggestion(
                    ticker=s.ticker,
                    name=str(ctx.get("name", "") or ""),
                    market=str(ctx.get("market", "") or ""),
                    sector=str(ctx.get("sector", "") or ""),
                    current_price=int(ctx.get("close", 0) or 0),
                    reason=s.reason,  # 사유만 LLM 응답 사용
                )
            )
            if len(rebuilt) >= input_data.max_results:
                break
        result.stocks = rebuilt

        return result

    # ──────────────────────────────────────────
    # 컨텍스트 수집
    # ──────────────────────────────────────────

    def _gather_context(self, input_data: DiscovererInput) -> list[dict]:
        """v7.5 KR stocks 중 buy_score 상위 80건 + filter 적용."""
        from agents.analyst import _get_kr_with_score

        try:
            df = _get_kr_with_score()
        except Exception as e:
            logger.warning(f"[discoverer] KR snapshot 로드 실패: {e}")
            return []
        if df.empty:
            return []

        # exclude
        if input_data.exclude_tickers:
            df = df[~df["ticker"].isin(input_data.exclude_tickers)]

        # filters
        if input_data.filters:
            f = input_data.filters
            if f.market:
                df = df[df["market"].isin(f.market)]
            if f.min_market_cap is not None and "market_cap" in df.columns:
                df = df[df["market_cap"] >= f.min_market_cap]
            if f.max_market_cap is not None and "market_cap" in df.columns:
                df = df[df["market_cap"] <= f.max_market_cap]
            if f.sectors and "sector" in df.columns:
                df = df[df["sector"].isin(f.sectors)]

        if df.empty:
            return []

        # 상위 buy_score 40개 (NEXT_STEPS.md:148 — 80→40으로 input 50% 절감)
        if "buy_score" in df.columns:
            df = df.nlargest(40, "buy_score")

        cols = [
            c
            for c in [
                "ticker", "name", "market", "sector", "close", "market_cap",
                "per", "pbr", "roe", "div_yield", "buy_score",
                "vs_high_52w", "vs_low_52w", "volume_ratio",
                "foreign_consecutive", "themes",
            ]
            if c in df.columns
        ]
        return df[cols].to_dict("records")

    # ──────────────────────────────────────────
    # User 메시지 구성
    # ──────────────────────────────────────────

    def _build_user_message(self, input_data: DiscovererInput, candidates: list[dict]) -> str:
        lines: list[str] = []
        lines.append(f"# 사용자 자연어 쿼리\n{input_data.query}")
        lines.append(f"\n# 결과 최대 종목 수\n{input_data.max_results}")

        if input_data.filters:
            f = input_data.filters
            filter_lines = []
            if f.market:
                filter_lines.append(f"market={f.market}")
            if f.min_market_cap is not None:
                filter_lines.append(f"min_market_cap={f.min_market_cap}")
            if f.max_market_cap is not None:
                filter_lines.append(f"max_market_cap={f.max_market_cap}")
            if f.sectors:
                filter_lines.append(f"sectors={f.sectors}")
            if filter_lines:
                lines.append(f"\n# 필터\n{' / '.join(filter_lines)}")

        if input_data.exclude_tickers:
            lines.append(f"\n# 제외 종목\n{', '.join(input_data.exclude_tickers)}")

        lines.append(f"\n# 후보 종목 ({len(candidates)}건, buy_score 상위)")
        if not candidates:
            lines.append("(후보 없음 — 빈 결과 반환)")
        else:
            for c in candidates:
                line = (
                    f"- {c.get('name', '')} ({c.get('ticker', '')}) "
                    f"{c.get('market', '')} / {c.get('sector', '')} | "
                    f"가격 {int(c.get('close', 0) or 0):,}원 | "
                    f"PER {c.get('per', 0):.1f} / PBR {c.get('pbr', 0):.2f} / ROE {c.get('roe', 0):.1f}% / "
                    f"buy_score {c.get('buy_score', 0):.1f} | "
                    f"52w고가대비 {c.get('vs_high_52w', 0):+.1f}% | "
                    f"외국인연속 {int(c.get('foreign_consecutive', 0) or 0)}일"
                )
                themes = c.get("themes")
                if themes:
                    line += f" | 테마 {themes}"
                lines.append(line)

        lines.append(
            "\n# 출력 지시\n"
            "위 후보 중에서만 쿼리에 부합하는 종목을 max_results 개 이내로 선별하세요. "
            "후보에 없는 종목을 만들어내면 안 됩니다. "
            "각 종목의 reason은 컨텍스트의 수치/특징을 근거로 1~2문장 한국어. "
            "JSON 외 다른 텍스트는 절대 포함하지 마세요."
        )
        return "\n".join(lines)
