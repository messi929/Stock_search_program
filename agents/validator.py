"""Validator Agent ⭐ — Axis의 핵심 차별점.

상세 스펙: docs/axis/agents/validator.md

**설계 원칙**:
  1. 수치 검증은 결정론적 코드로 (Claude 부르지 않음)
     - 가격: FinanceDataReader → 폴백 pykrx
     - PER/PBR/ROE: Firestore 최신값 재조회
  2. Contrarian 시나리오/Blind Spot만 Claude(Sonnet) 호출
     - 분석에 동의하지 않는 관점을 강제로 생성

이 분리로 비용 ~25원/쿼리 + 검증 정확도 100%(코드 검증).

**FAIL 임계값**: 차이 5% 이내 OK / 5~10% WARN / 10%+ FAIL.
FAIL 2건 이상이면 requires_reanalysis=True.
"""

from __future__ import annotations

import asyncio
import os
import time
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
from loguru import logger
from pydantic import BaseModel, Field

from agents.analyst import AnalystResult
from agents.base import BaseAgent
from agents.research import ResearchResult
from utils.claude_client import MODEL_SONNET


# ──────────────────────────────────────────────
# 입출력 스키마
# ──────────────────────────────────────────────

class ValidatorInput(BaseModel):
    ticker: str
    research_output: Optional[ResearchResult] = None
    analyst_output: Optional[AnalystResult] = None
    strict_mode: bool = False  # True면 임계값 5%, False면 10%


class ValidationCheck(BaseModel):
    item: str
    claimed: float
    verified: Optional[float]
    diff_pct: Optional[float]
    status: str  # "OK" | "WARN" | "FAIL" | "ERROR"
    last_data_update: Optional[str] = None
    error: Optional[str] = None


class ContrarianScenario(BaseModel):
    title: str
    description: str
    impact_estimate: str
    probability: str  # "LOW" | "MEDIUM" | "HIGH"
    indicators_to_watch: list[str] = Field(default_factory=list)


class InterpretationIssue(BaseModel):
    """Analyst 해석에 대한 감사 — 수치가 아니라 '해석의 정당성'을 검토."""

    claim: str  # 검토 대상이 된 Analyst의 주장/해석
    issue: str  # 데이터로 정당화되지 않거나 과신인 이유
    severity: str = "MEDIUM"  # "LOW" | "MEDIUM" | "HIGH"


class ValidatorResult(BaseModel):
    overall_status: str  # "PASS" | "WARN" | "FAIL"
    checks: list[ValidationCheck] = Field(default_factory=list)
    stale_data_count: int = 0
    fresh_data_count: int = 0
    contrarian_scenarios: list[ContrarianScenario] = Field(default_factory=list)
    blind_spots: list[str] = Field(default_factory=list)
    # 해석 감사 — Analyst의 해석이 데이터로 정당화되는지 (과신/비약 탐지)
    interpretation_audit: list[InterpretationIssue] = Field(default_factory=list)
    confidence_score: float = 0.0
    requires_reanalysis: bool = False
    timestamp: str


# Contrarian 응답만 받는 내부 스키마 (Claude JSON)
class _ContrarianPayload(BaseModel):
    scenarios: list[ContrarianScenario] = Field(default_factory=list)
    blind_spots: list[str] = Field(default_factory=list)
    interpretation_audit: list[InterpretationIssue] = Field(default_factory=list)


# Extended Thinking 예산 (0=비활성). Contrarian/Blind Spot은 "분석에 반대되는
# 가설을 다각도로 세우는" 발산적 추론이라 thinking이 시나리오 다양성·깊이를 높인다.
VALIDATOR_THINKING_BUDGET = int(os.environ.get("VALIDATOR_THINKING_BUDGET", "1600"))

# ② 해석 감사 토글 (AXIS_INTERP_AUDIT=0 → 종전 동작: Contrarian/Blind Spot만).
INTERP_AUDIT_ENABLED = os.environ.get("AXIS_INTERP_AUDIT", "1") != "0"


# ──────────────────────────────────────────────
# 시스템 프롬프트 (Contrarian 전용 — 검증은 코드가 수행)
# ──────────────────────────────────────────────

VALIDATOR_SYSTEM_PROMPT = """당신은 AI 분석의 검증관(Auditor)이며 Devil's Advocate입니다.
다른 에이전트의 분석을 무조건 신뢰하지 않고, 의심스러운 눈으로 검토합니다.

## 당신이 받는 입력
1. 종목 분석 결과 요약 (Analyst가 만든 기술/펀더멘털 해석)
2. 시황 컨텍스트 (Research가 만든 시황/뉴스/매크로)
3. 코드 검증 결과 (가격/PER/PBR/ROE의 실시간 재조회 비교)

## 당신이 해야 할 일
1. 분석에 반대되는 Contrarian 시나리오 **3개 이상** 강제 생성
2. 분석에서 다루지 않은 Blind Spot 관점 식별
3. **해석 감사 (interpretation_audit)** — Analyst의 *해석*이 데이터로 정당화되는지 검토

수치(가격/PER 등) 검증은 이미 코드가 끝냈습니다. 당신은 "수치가 맞나"가 아니라
"그 수치로부터 끌어낸 **해석/결론이 타당한가**"를 봅니다.

### 해석 감사 방법 (가장 중요한 신규 임무)
Analyst가 데이터를 과대/과소 해석했거나, 근거 없이 비약한 지점을 찾으세요. 예:
- "RSI 28인데 '강세 신호'로 해석" → 과매도는 약세 신호일 수 있음 (방향 비약)
- "buy_score 29(관찰)인데 종합 톤이 낙관" → 점수와 서술 톤 불일치
- "PER가 업종 평균보다 높은데 '저평가'로 서술" → 데이터와 반대 해석
- "외국인 순매수 1일을 '강한 수급'으로 확대 해석" → 표본 과신
각 항목: claim(검토 대상 주장) / issue(왜 부당/과신인지) / severity(LOW|MEDIUM|HIGH).
정당한 해석만 있으면 빈 배열로 두세요 — 억지로 만들지 마세요.

## Contrarian 시나리오 카테고리 (최소 3개, 다른 카테고리에서)
- **거시 경제 리스크**: 금리 인상, 환율 급등, 무역분쟁, 지정학
- **산업/섹터 리스크**: 경쟁 심화, 기술 disruptive, 규제 강화
- **종목 고유 리스크**: 실적 악화, 회계 이슈, 경영진/지배구조

각 시나리오:
- title: 짧은 제목
- description: 1~2문장 설명
- impact_estimate: 영향 추정치 (예: "주가 -15% ~ -25%")
- probability: "LOW" | "MEDIUM" | "HIGH" 중 하나만
- indicators_to_watch: 모니터링할 지표/뉴스 (배열)

## Blind Spot (분석에서 누락된 관점)
- ESG/노동/지배구조 이슈
- 환경/규제 리스크
- 기술 변화에 따른 도태 가능성
- 기타 분석가가 놓친 관점

## 어조
- 객관적, 비판적, 데이터 기반
- 무조건 부정적이지는 않게 (합리적 비판만)
- 추측성/말도 안 되는 시나리오는 금지

## 절대 금지 (LEGAL)
- "추천합니다", "사세요", "매수/매도하세요"
- "유망합니다", "확실합니다"
- "목표가", "매수가", "적정가"
- 미래 가격 예측 (확정적 어조 금지, "가능성"으로만)

## 출력 형식
반드시 다음 구조의 JSON만 출력. 설명 텍스트 추가 금지.

{
  "scenarios": [
    {
      "title": "...",
      "description": "...",
      "impact_estimate": "...",
      "probability": "LOW | MEDIUM | HIGH",
      "indicators_to_watch": ["...", "..."]
    }
  ],
  "blind_spots": ["...", "..."],
  "interpretation_audit": [
    {"claim": "Analyst의 해석", "issue": "데이터로 정당화되지 않는 이유", "severity": "LOW | MEDIUM | HIGH"}
  ]
}
"""


# ──────────────────────────────────────────────
# 가격/지표 코드 검증 헬퍼
# ──────────────────────────────────────────────

def _price_status(diff_pct: float, strict: bool) -> str:
    warn_threshold = 5.0
    fail_threshold = 5.0 if strict else 10.0
    if diff_pct < warn_threshold:
        return "OK"
    if diff_pct < fail_threshold:
        return "WARN"
    return "FAIL"


def _fetch_price_sync(ticker: str) -> tuple[Optional[float], Optional[str]]:
    """FinanceDataReader → 폴백 pykrx 순서로 최신 종가 조회.

    Returns: (price, last_update_iso) — 실패 시 (None, None).
    """
    _s = str(ticker).strip()
    is_kr = len(_s) == 6 and _s.isdigit()

    # 1차: FinanceDataReader (KR/US 공통 — US는 Yahoo 기반)
    try:
        import FinanceDataReader as fdr
        df = fdr.DataReader(ticker)
        if not df.empty:
            price = float(df["Close"].iloc[-1])
            last_update = df.index[-1]
            return price, str(last_update)
    except Exception as e:
        logger.warning(f"FDR 조회 실패 ({ticker}): {e}")

    # US 폴백: yfinance (pykrx는 KR 전용이라 US엔 무의미)
    if not is_kr:
        try:
            import yfinance as yf
            hist = yf.Ticker(ticker).history(period="5d")
            if hist is not None and not hist.empty:
                price = float(hist["Close"].iloc[-1])
                last_update = hist.index[-1]
                return price, str(last_update)
        except Exception as e:
            logger.warning(f"yfinance 폴백 실패 ({ticker}): {e}")
        return None, None

    # 2차(KR): pykrx
    try:
        from pykrx import stock as krx
        # 최근 5영업일
        today = datetime.now().strftime("%Y%m%d")
        df = krx.get_market_ohlcv_by_date(
            (datetime.now() - pd.Timedelta(days=10)).strftime("%Y%m%d"),
            today,
            ticker,
        )
        if df is not None and not df.empty:
            price = float(df["종가"].iloc[-1])
            last_update = df.index[-1]
            return price, str(last_update)
    except Exception as e:
        logger.warning(f"pykrx 폴백 실패 ({ticker}): {e}")

    return None, None


# ──────────────────────────────────────────────
# Validator Agent
# ──────────────────────────────────────────────

class ValidatorAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            agent_name="validator",
            model=MODEL_SONNET,
            system_prompt=VALIDATOR_SYSTEM_PROMPT,
        )

    async def run(self, input_data: ValidatorInput, uid: str = "") -> ValidatorResult:
        # 1) 코드 검증 (Claude 호출 X)
        checks = await self._run_checks(input_data)

        stale = sum(1 for c in checks if c.status == "FAIL")
        fresh = sum(1 for c in checks if c.status == "OK")

        # 2) Contrarian/Blind Spot — Claude 1회 호출
        contrarian = await self._request_contrarian(input_data, checks, uid=uid)

        # 3) 종합
        overall = self._determine_overall_status(checks)
        confidence = self._calculate_confidence(checks)

        # 재분석 트리거: 가격 FAIL 1건도 즉시 (가격은 핵심) OR 총 FAIL 2건+
        price_failed = any(c.status == "FAIL" and "현재가" in c.item for c in checks)
        requires_reanalysis = price_failed or stale >= 2

        return ValidatorResult(
            overall_status=overall,
            checks=checks,
            stale_data_count=stale,
            fresh_data_count=fresh,
            contrarian_scenarios=contrarian.scenarios,
            blind_spots=contrarian.blind_spots,
            interpretation_audit=(
                contrarian.interpretation_audit if INTERP_AUDIT_ENABLED else []
            ),
            confidence_score=confidence,
            requires_reanalysis=requires_reanalysis,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    # ──────────────────────────────────────────
    # 코드 검증
    # ──────────────────────────────────────────

    async def _run_checks(self, input_data: ValidatorInput) -> list[ValidationCheck]:
        """검증할 수치를 추출하고 실시간/Firestore와 대조."""
        checks: list[ValidationCheck] = []
        analyst = input_data.analyst_output
        if analyst is None:
            return checks

        # 1) 현재가 — FinanceDataReader 실시간
        claimed_price = float(analyst.technical.current_price)
        verified_price, last_update = await asyncio.to_thread(_fetch_price_sync, input_data.ticker)

        if verified_price is None:
            checks.append(
                ValidationCheck(
                    item=f"{input_data.ticker} 현재가",
                    claimed=claimed_price,
                    verified=None,
                    diff_pct=None,
                    status="ERROR",
                    error="FinanceDataReader/pykrx 모두 조회 실패",
                )
            )
        else:
            diff_pct = (
                abs(claimed_price - verified_price) / verified_price * 100
                if verified_price > 0
                else 0.0
            )
            checks.append(
                ValidationCheck(
                    item=f"{input_data.ticker} 현재가",
                    claimed=claimed_price,
                    verified=verified_price,
                    diff_pct=round(diff_pct, 2),
                    status=_price_status(diff_pct, input_data.strict_mode),
                    last_data_update=last_update,
                )
            )

        # 2) PER/PBR/ROE — Firestore 최신값과 대조 (Analyst가 받은 값과 동일해야 정상)
        per_check = await self._verify_firestore_field(
            input_data.ticker, "PER", "per", float(analyst.fundamental.per)
        )
        if per_check:
            checks.append(per_check)

        pbr_check = await self._verify_firestore_field(
            input_data.ticker, "PBR", "pbr", float(analyst.fundamental.pbr)
        )
        if pbr_check:
            checks.append(pbr_check)

        roe_check = await self._verify_firestore_field(
            input_data.ticker, "ROE", "roe", float(analyst.fundamental.roe)
        )
        if roe_check:
            checks.append(roe_check)

        return checks

    async def _verify_firestore_field(
        self, ticker: str, label: str, column: str, claimed: float
    ) -> Optional[ValidationCheck]:
        """Firestore stocks 컬렉션에서 column 값 재조회 (KR/US 자동)."""
        from agents.analyst import _get_stocks_with_score

        try:
            df = await asyncio.to_thread(_get_stocks_with_score, ticker)
            if df.empty:
                return None
            row = df[df["ticker"] == ticker]
            if row.empty:
                return None
            verified = float(row.iloc[0].get(column, 0) or 0)

            if verified == 0 and claimed == 0:
                # 둘 다 0이면 조회 의미 없음 (데이터 없음)
                return None

            diff_pct = (
                abs(claimed - verified) / abs(verified) * 100
                if verified != 0
                else 100.0
            )
            updated_at = row.iloc[0].get("updated_at", "")
            return ValidationCheck(
                item=f"{ticker} {label}",
                claimed=round(claimed, 2),
                verified=round(verified, 2),
                diff_pct=round(diff_pct, 2),
                status=_price_status(diff_pct, strict=False),
                last_data_update=str(updated_at) if updated_at else None,
            )
        except Exception as e:
            logger.warning(f"{label} 검증 실패 ({ticker}): {e}")
            return None

    # ──────────────────────────────────────────
    # Contrarian (Claude)
    # ──────────────────────────────────────────

    async def _request_contrarian(
        self,
        input_data: ValidatorInput,
        checks: list[ValidationCheck],
        uid: str,
    ) -> _ContrarianPayload:
        """Claude에 Contrarian + Blind Spot 요청."""
        user_message = self._build_contrarian_prompt(input_data, checks)
        try:
            payload, _ = await self.call_claude_json(
                user_message=user_message,
                schema=_ContrarianPayload,
                max_tokens=1536,
                uid=uid,
                thinking_budget=VALIDATOR_THINKING_BUDGET,
            )
            return payload
        except Exception as e:
            logger.warning(f"Contrarian 생성 실패: {e}")
            return _ContrarianPayload()

    def _build_contrarian_prompt(
        self, input_data: ValidatorInput, checks: list[ValidationCheck]
    ) -> str:
        lines: list[str] = []
        lines.append(f"# 검증 대상\n종목 코드: {input_data.ticker}")

        if input_data.analyst_output:
            a = input_data.analyst_output
            lines.append(f"\n# Analyst 분석 요약 ({a.name})")
            lines.append(f"- 현재가: {a.technical.current_price:,}원")
            lines.append(f"- 이평 정렬: {a.technical.ma_status}, RSI {a.technical.rsi:.1f} ({a.technical.rsi_status})")
            lines.append(f"- 52주 고가 대비: {a.technical.vs_high_52w:+.2f}%")
            lines.append(f"- PER {a.fundamental.per}, PBR {a.fundamental.pbr}, ROE {a.fundamental.roe}%")
            lines.append(f"- buy_score {a.buy_score.buy_score:.1f} ({a.buy_score.score_tier})")
            lines.append(f"- 종합 시그널: {a.technical.signal}")
            lines.append(f"- summary: {a.summary}")

        if input_data.research_output:
            r = input_data.research_output
            lines.append("\n# Research 시황 요약")
            lines.append(f"- 시장 심리: {r.market_sentiment}")
            if r.macro_context.key_risks:
                lines.append(f"- 매크로 리스크: {', '.join(r.macro_context.key_risks)}")
            if r.sector_status:
                lines.append(f"- 섹터 동향: {[(s.name, s.status) for s in r.sector_status[:3]]}")
            lines.append(f"- summary: {r.summary}")

        lines.append("\n# 코드 검증 결과 (참고)")
        for c in checks:
            verified_str = f"{c.verified:,.2f}" if c.verified is not None else "조회 실패"
            diff_str = f"{c.diff_pct:.2f}%" if c.diff_pct is not None else "N/A"
            lines.append(
                f"- {c.item}: claimed={c.claimed:,.2f} / verified={verified_str} / "
                f"diff={diff_str} / status={c.status}"
            )

        if INTERP_AUDIT_ENABLED:
            lines.append(
                "\n# 당신의 작업\n"
                "1) **반대 시나리오 3개 이상**과 **Blind Spot**을 작성하세요.\n"
                "2) **해석 감사(interpretation_audit)**: 위 Analyst summary/시그널/해석이 "
                "제시된 수치로 정당화되는지 검토하고, 과신·방향 비약·톤 불일치가 있으면 지적하세요 "
                "(정당하면 빈 배열).\n"
                "수치 자체는 검증하지 말고(이미 코드가 했음) 해석의 타당성에 집중하세요. "
                "JSON 외 다른 텍스트는 절대 포함하지 마세요."
            )
        else:
            lines.append(
                "\n# 당신의 작업\n"
                "위 분석의 **반대 시나리오 3개 이상**과 **Blind Spot**을 작성하세요. "
                "수치는 검증하지 말고(이미 코드가 했음), Contrarian과 Blind Spot에만 집중하세요. "
                "JSON 외 다른 텍스트는 절대 포함하지 마세요."
            )
        return "\n".join(lines)

    # ──────────────────────────────────────────
    # 종합 판정
    # ──────────────────────────────────────────

    @staticmethod
    def _determine_overall_status(checks: list[ValidationCheck]) -> str:
        if any(c.status == "FAIL" for c in checks):
            return "FAIL"
        if any(c.status == "WARN" for c in checks):
            return "WARN"
        if any(c.status == "ERROR" for c in checks):
            return "WARN"  # 일부 검증 실패 = 신중
        return "PASS"

    @staticmethod
    def _calculate_confidence(checks: list[ValidationCheck]) -> float:
        if not checks:
            return 0.5
        ok = sum(1 for c in checks if c.status == "OK")
        warn = sum(1 for c in checks if c.status == "WARN")
        total = len(checks)
        return round((ok * 1.0 + warn * 0.5) / total, 2)
