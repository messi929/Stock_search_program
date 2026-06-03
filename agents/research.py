"""Research Agent — 시황·뉴스·매크로·수급 통합.

상세 스펙: docs/axis/agents/research.md

데이터 소스:
  - 외국인/기관 수급: screener.db.repository.load_stocks (기존 v7.5)
  - 테마 동향: screener.db.repository.load_themes (기존 v7.5)
  - 매크로 이벤트: data/macro_events.json (수동 큐레이션 — Week 2 후반 채움)
  - 뉴스 RSS: 향후 Naver RSS 추가 (Week 2 후반)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd
from loguru import logger
from pydantic import BaseModel, Field

from agents.base import BaseAgent
from utils.claude_client import MODEL_HAIKU


# ──────────────────────────────────────────────
# 입출력 스키마
# ──────────────────────────────────────────────

class ResearchInput(BaseModel):
    query: str = Field(..., description="사용자 자연어 쿼리")
    ticker: Optional[str] = Field(None, description="특정 종목 컨텍스트")
    name: Optional[str] = Field(None, description="정확한 종목명 (환각 방지)")
    sector: Optional[str] = Field(None, description="섹터 컨텍스트")
    timeframe_days: int = Field(7, description="분석 기간(일)")


class NewsItem(BaseModel):
    headline: str
    source: str
    published_at: str
    impact: str  # "positive" | "negative" | "neutral"
    relevance_score: float  # 0~1


class MacroContext(BaseModel):
    fomc_next: Optional[str] = None
    key_risks: list[str] = Field(default_factory=list)
    key_opportunities: list[str] = Field(default_factory=list)


class SectorStatus(BaseModel):
    name: str
    status: str  # "강세" | "약세" | "횡보"
    key_drivers: list[str] = Field(default_factory=list)
    rally_participation: str = ""  # "참여 중" | "소외" | "급등 후 조정"


class ResearchResult(BaseModel):
    market_sentiment: str  # "낙관적" | "신중" | "비관적"
    relevant_news: list[NewsItem] = Field(default_factory=list)
    macro_context: MacroContext = Field(default_factory=MacroContext)
    sector_status: list[SectorStatus] = Field(default_factory=list)
    foreign_inst_flow: dict = Field(default_factory=dict)
    summary: str
    timestamp: str  # ISO 8601


# ──────────────────────────────────────────────
# 시스템 프롬프트
# ──────────────────────────────────────────────

RESEARCH_SYSTEM_PROMPT = """당신은 한국 증시 전문 시황 분석가입니다.
블룸버그 터미널 스타일의 객관적 데이터 중심 보고서를 작성합니다.

## 역할
- 시황, 뉴스, 매크로 이벤트의 사실 관계 정리
- 주관적 판단/추천은 절대 하지 않음
- 기관/외국인 수급 흐름 추적

## 작업 절차
1. 입력된 query를 분석하여 어떤 정보가 필요한지 판단
2. 제공된 컨텍스트(수급 데이터, 테마, 매크로 이벤트)에서 관련 정보 추출
3. 시장 심리와 섹터 동향 종합
4. 지정된 JSON 스키마에 맞춰 출력

## 출력 원칙
- 모든 사실에 출처 명시 (네이버뉴스, 한경, 매경 등)
- 시점 표시 ("4월 22일 종가 기준" 등)
- 모호한 표현 금지 ("약", "대략" 사용 X — 정확한 수치)
- 언급한 종목/수치는 모두 검증 가능해야 함

## 절대 금지 (법적 안전)
- "추천합니다", "추천드립니다" 등 권유성 표현
- "사세요", "매수 신호", "매도 신호" 등 거래 시그널
- "유망합니다", "확실합니다" 등 단정
- "목표가", "매수가" 등 확정적 가격 제시
- 미래 가격 예측 (확정적 어조)

## 권장 표현
- "관찰됩니다" / "확인됩니다" / "보고되었습니다"
- "데이터에 따르면..."
- "관찰 가치가 있습니다"
- "참고 범위" / "관찰 구간"

## 출력 형식 (JSON 스키마)
반드시 다음 구조의 JSON만 출력하세요. 설명 텍스트 절대 추가 금지.

{
  "market_sentiment": "낙관적 | 신중 | 비관적",
  "relevant_news": [
    {
      "headline": "...",
      "source": "한경 | 매경 | 연합 | 네이버뉴스 | ...",
      "published_at": "YYYY-MM-DD",
      "impact": "positive | negative | neutral",
      "relevance_score": 0.0
    }
  ],
  "macro_context": {
    "fomc_next": "YYYY-MM-DD 또는 null",
    "key_risks": ["...", "..."],
    "key_opportunities": ["...", "..."]
  },
  "sector_status": [
    {
      "name": "반도체",
      "status": "강세 | 약세 | 횡보",
      "key_drivers": ["...", "..."],
      "rally_participation": "참여 중 | 소외 | 급등 후 조정"
    }
  ],
  "foreign_inst_flow": {
    "top_buy_sectors": ["...", "..."],
    "top_sell_sectors": ["...", "..."]
  },
  "summary": "2~3문장 요약 (한국어)",
  "timestamp": "ISO 8601"
}

면책 문구는 시스템이 자동으로 후처리하니, 당신은 콘텐츠에만 집중하세요.
"""


# ──────────────────────────────────────────────
# Macro 이벤트 로드 (data/macro_events.json)
# ──────────────────────────────────────────────

_MACRO_EVENTS_PATH = Path(__file__).resolve().parent.parent / "data" / "macro_events.json"


def _load_macro_events() -> list[dict]:
    """매크로 이벤트 캘린더 로드. 파일 없으면 빈 리스트."""
    if not _MACRO_EVENTS_PATH.exists():
        return []
    try:
        with _MACRO_EVENTS_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"macro_events.json 로드 실패: {e}")
        return []


# ──────────────────────────────────────────────
# Research Agent
# ──────────────────────────────────────────────

class ResearchAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            agent_name="research",
            model=MODEL_HAIKU,
            system_prompt=RESEARCH_SYSTEM_PROMPT,
        )

    async def run(self, input_data: ResearchInput, uid: str = "") -> ResearchResult:
        """시황 분석 실행."""
        context = self._gather_context(input_data)
        user_message = self._build_user_message(input_data, context)

        result_model, _raw = await self.call_claude_json(
            user_message=user_message,
            schema=ResearchResult,
            max_tokens=2048,
            uid=uid,
        )

        # timestamp 보정 (Claude가 부정확한 값을 줄 수 있음)
        result_model.timestamp = datetime.now(timezone.utc).isoformat()
        return result_model

    # ──────────────────────────────────────────
    # Context 수집
    # ──────────────────────────────────────────

    def _gather_context(self, input_data: ResearchInput) -> dict:
        """기존 Firestore 데이터에서 분석용 컨텍스트 구성."""
        context: dict = {}

        # 1) 외국인 연속 순매수 상위 (기존 v7.5 buy_score/foreign_consecutive 활용)
        #    US 종목이면 us 스냅샷 로드 (수급 컬럼은 없을 수 있어 graceful)
        try:
            kr = self._load_market_stocks(input_data.ticker)
            if not kr.empty and "foreign_consecutive" in kr.columns:
                top_foreign = (
                    kr[kr["foreign_consecutive"].fillna(0) > 0]
                    .nlargest(15, "foreign_consecutive")
                    [["ticker", "name", "foreign_consecutive", "sector"]]
                    .to_dict("records")
                    if "sector" in kr.columns
                    else kr.nlargest(15, "foreign_consecutive")
                    [["ticker", "name", "foreign_consecutive"]]
                    .to_dict("records")
                )
                context["top_foreign_buy"] = top_foreign

            if not kr.empty and "inst_consecutive" in kr.columns:
                context["top_inst_buy"] = (
                    kr[kr["inst_consecutive"].fillna(0) > 0]
                    .nlargest(15, "inst_consecutive")
                    [["ticker", "name", "inst_consecutive"]]
                    .to_dict("records")
                )
        except Exception as e:
            logger.warning(f"수급 컨텍스트 로드 실패: {e}")

        # 2) 테마 (기존 v7.5)
        try:
            from screener.db.repository import load_themes
            themes, stock_themes, _ = load_themes()
            context["themes"] = list(themes.values())[:50]  # 토큰 절약: 상위 50개
            if input_data.ticker and input_data.ticker in stock_themes:
                context["ticker_themes"] = stock_themes[input_data.ticker]
        except Exception as e:
            logger.warning(f"테마 로드 실패: {e}")

        # 3) 매크로 이벤트
        context["macro_events"] = _load_macro_events()

        # 4) 뉴스 — 향후 Naver RSS 추가 (Week 2 후반)
        context["news_stub"] = (
            "뉴스 데이터 소스는 Week 2 후반 추가 예정. "
            "지금은 Claude의 일반 시장 지식과 컨텍스트로 추론하세요."
        )

        return context

    @staticmethod
    def _load_market_stocks(ticker: Optional[str] = None) -> pd.DataFrame:
        """ticker가 속한 시장 종목 로드 (실패 시 빈 DataFrame).

        6자리 숫자=KR, 그 외=US. ticker 미지정 시 KR.
        """
        s = str(ticker or "").strip()
        market = "kr" if (len(s) == 6 and s.isdigit()) else ("us" if s else "kr")
        try:
            from screener.db.repository import load_stocks
            return load_stocks(market)
        except Exception as e:
            logger.warning(f"{market} 종목 로드 실패: {e}")
            return pd.DataFrame()

    # ──────────────────────────────────────────
    # Prompt 구성
    # ──────────────────────────────────────────

    def _build_user_message(self, input_data: ResearchInput, context: dict) -> str:
        """Claude에 전달할 user 메시지 구성."""
        lines: list[str] = []
        lines.append(f"# 사용자 쿼리\n{input_data.query}")

        if input_data.ticker:
            _lbl = (
                f"{input_data.name} ({input_data.ticker})"
                if input_data.name
                else input_data.ticker
            )
            lines.append(f"\n# 컨텍스트 종목\n{_lbl}")
        if input_data.sector:
            lines.append(f"\n# 컨텍스트 섹터\n{input_data.sector}")

        lines.append(f"\n# 분석 기간\n최근 {input_data.timeframe_days}일")
        lines.append(f"\n# 현재 시각 (UTC)\n{datetime.now(timezone.utc).isoformat()}")

        # Firestore 컨텍스트
        if "top_foreign_buy" in context:
            lines.append("\n# 외국인 연속 순매수 상위 (최근 영업일 기준)")
            for i, row in enumerate(context["top_foreign_buy"][:10], 1):
                lines.append(
                    f"{i}. {row.get('name', '')} ({row.get('ticker', '')}) "
                    f"— {row.get('foreign_consecutive', 0)}일 연속"
                )

        if "top_inst_buy" in context:
            lines.append("\n# 기관 연속 순매수 상위")
            for i, row in enumerate(context["top_inst_buy"][:10], 1):
                lines.append(
                    f"{i}. {row.get('name', '')} ({row.get('ticker', '')}) "
                    f"— {row.get('inst_consecutive', 0)}일 연속"
                )

        if context.get("ticker_themes"):
            lines.append(f"\n# {input_data.ticker} 소속 테마")
            lines.append(", ".join(context["ticker_themes"]))

        if context.get("macro_events"):
            lines.append("\n# 다가오는 매크로 이벤트")
            for ev in context["macro_events"][:10]:
                lines.append(
                    f"- {ev.get('date', '')} {ev.get('event', '')} "
                    f"(영향: {ev.get('impact', 'unknown')})"
                )

        lines.append(f"\n# 뉴스 안내\n{context.get('news_stub', '')}")

        lines.append(
            "\n# 출력\n위 컨텍스트를 바탕으로 시스템 프롬프트의 JSON 스키마에 정확히 맞춰 응답하세요. "
            "JSON 외 다른 텍스트는 절대 포함하지 마세요."
        )
        return "\n".join(lines)
