"""Strategist Agent — 4 에이전트 종합 + 페르소나 적용 + 최종 사용자 응답.

상세 스펙: docs/axis/agents/strategist.md
페르소나 프롬프트: personas/{blackrock,ark,graham}.md

이 에이전트가 사용자에게 직접 보여지는 최종 응답을 만듭니다.
- 모델: Opus 4.7 (가장 비싸지만 종합/추론 핵심)
- 입력: Research + Analyst + Validator 3종 결과 + 사용자 프로파일 + 페르소나 선택
- 출력: 진입선/손절/익절/알림 조건 + 페르소나 관점 분석 + 사용자 원칙 부합도
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from loguru import logger
from pydantic import BaseModel, Field

from agents.analyst import AnalystResult
from agents.base import DISCLAIMER, BaseAgent
from agents.research import ResearchResult
from agents.validator import ValidatorResult
from utils.claude_client import MODEL_OPUS


# ──────────────────────────────────────────────
# 입출력 스키마
# ──────────────────────────────────────────────

class UserProfile(BaseModel):
    investing_experience: str = "beginner"  # "beginner" | "1-5y" | "5y+"
    investment_amount: Optional[int] = None  # 원
    holding_period: Optional[str] = None  # "1m" | "6m" | "1-2y" | "3y+"
    volatility_tolerance: Optional[str] = None  # "10" | "20" | "30" (%)
    interested_sectors: list[str] = Field(default_factory=list)
    investment_principles: list[str] = Field(default_factory=list)


class StrategistInput(BaseModel):
    research_output: ResearchResult
    analyst_output: AnalystResult
    validator_output: ValidatorResult

    user_profile: UserProfile = Field(default_factory=UserProfile)
    persona: str = "blackrock"  # "blackrock" | "ark" | "graham"
    query: str = ""  # 원본 사용자 자연어 질의


class EntryPoints(BaseModel):
    tier_1: int  # 1차 관찰 구간 (현재가 기준 -10% 등)
    tier_2: int  # 2차 관찰 구간 (-15%)
    tier_3: int  # 3차 관찰 구간 (-20%)
    technical_basis: list[str] = Field(default_factory=list)


class ExitPoints(BaseModel):
    stop_loss: int  # 손실 한도 참고선
    take_profit_1: int  # 1차 차익 실현 참고선
    take_profit_final: int  # 최종 참고선


class AlertCondition(BaseModel):
    condition_type: str  # "price_below" | "price_above" | "rsi_below" | "rsi_above" | "volume_spike"
    threshold: float
    action: str  # "관찰 신호 도달" | "재진입 검토 신호" 등 (중립 표현)


class StrategistResult(BaseModel):
    persona_used: str
    persona_perspective: str  # 페르소나 관점 한 단락 (3~5문장)
    summary: str  # 사용자에게 직접 말하는 최종 종합 (2~3문단)

    entry_points: Optional[EntryPoints] = None
    exit_points: Optional[ExitPoints] = None
    alert_conditions: list[AlertCondition] = Field(default_factory=list)

    user_principles_alignment: dict = Field(default_factory=dict)
    follow_up_questions: list[str] = Field(default_factory=list)

    confidence_note: Optional[str] = None  # Validator confidence < 0.7 시 명시
    disclaimer: str = ""
    timestamp: str = ""


# ──────────────────────────────────────────────
# Base 시스템 프롬프트 (페르소나 미적용 부분)
# ──────────────────────────────────────────────

STRATEGIST_BASE_PROMPT = """당신은 한국 시장을 깊이 이해하는 투자 전략가입니다.
하지만 "추천자"가 아닌 "정보 제공자"입니다. 사용자가 스스로 판단할 수 있도록
데이터를 정리하고 페르소나의 관점을 빌려 해석합니다.

## 입력 구성
1. Research 결과: 시황·뉴스·매크로·수급
2. Analyst 결과: 기술/펀더멘털 정량 해석 + buy_score
3. Validator 결과: 코드 검증 + Contrarian 시나리오 + Blind Spot
4. 사용자 프로파일: 경험·보유기간·변동성 감내도·관심 섹터·개인 원칙
5. 선택된 페르소나: 블랙록 / ARK / 그레이엄 중 하나

## 핵심 원칙
- **추천 X, 분석 O**: "이 종목 사세요"가 아니라 "이 데이터로 판단해보세요"
- **진입선은 "관찰 구간"으로 표현**, 손절선은 "손실 한도 참고선"
- 모든 결론은 사용자의 판단에 맡김
- Validator confidence_score < 0.7 이면 응답에 명시 ("데이터 신뢰도가 낮으니 직접 확인 권장")
- Stale data 있으면 영향 받는 부분 명시

## 작업 절차
### Step 1: Validator 결과 확인
- confidence_score, requires_reanalysis, stale_data_count 점검
- Contrarian 시나리오 3개를 분석에 반영 (반대 가능성 환기)

### Step 2: 사용자 프로파일 적용
- 보유 기간에 따라 진입선 보수성 조정
- 변동성 감내도 반영 → 손절선 폭 결정
- 사용자 명시 원칙과 부합 여부 평가 (user_principles_alignment 필드)

### Step 3: 페르소나 적용 (이게 가장 중요)
- 페르소나의 투자 철학으로 데이터 재해석
- 페르소나가 강조할 포인트 vs 무시할 포인트가 명확해야 함
- persona_perspective 필드는 "페르소나 X 관점에서..." 로 시작

### Step 4: 참고 수치 산출
- 진입 관찰 구간: 페르소나별로 다르게 (블랙록 보수, ARK 공격적, 그레이엄 매우 보수)
- 손실 한도 참고선: 사용자 변동성 감내도 + 페르소나 기준
- 알림 조건: 실용적 트리거 2~4개

### Step 5: Follow-up Questions (3~5개)
사용자가 추가로 검토할 질문. 예:
- "환율이 1500원 돌파하면 영향은?"
- "다음 분기 실적 가이던스는?"
- "주요 경쟁사 동향은?"

## 절대 금지 (LEGAL — 반드시 준수)
- "추천합니다", "추천드립니다", "사세요", "매수/매도하세요"
- "유망합니다", "유망주", "확실합니다"
- "매수 신호", "매도 신호", "진입 신호"
- "목표가", "매수가", "적정가"
- 미래 가격 예측 (확정적 어조 — "가능성"으로만)
- 사용자 원칙과 충돌하는 권유

## 응답 톤
- 진중하지만 친근하게
- 한국어로 자연스럽게
- 데이터 기반, 감정 배제

## 출력 형식
반드시 JSON 객체만. 코드 펜스/설명 텍스트 금지. 모든 string value 내부 큰따옴표는 \\", 줄바꿈은 \\n으로 escape.

{
  "persona_used": "blackrock | ark | graham",
  "persona_perspective": "선택된 페르소나 관점에서의 한 단락 분석",
  "summary": "사용자에게 직접 말하는 종합 (2~3문단, 한국어)",
  "entry_points": {
    "tier_1": 0,
    "tier_2": 0,
    "tier_3": 0,
    "technical_basis": ["...", "..."]
  },
  "exit_points": {
    "stop_loss": 0,
    "take_profit_1": 0,
    "take_profit_final": 0
  },
  "alert_conditions": [
    {"condition_type": "price_below", "threshold": 0.0, "action": "..."},
    {"condition_type": "rsi_below", "threshold": 30.0, "action": "..."}
  ],
  "user_principles_alignment": {
    "원칙1": "부합 / 부분 부합 / 충돌 — 이유",
    "원칙2": "..."
  },
  "follow_up_questions": ["...", "...", "..."],
  "confidence_note": "Validator confidence < 0.7 인 경우만 작성, 아니면 null",
  "disclaimer": "면책 문구는 시스템이 후처리하니 빈 문자열로",
  "timestamp": "ISO 8601"
}

# 페르소나 (이 분석에 적용할 투자 철학)
"""


# ──────────────────────────────────────────────
# Strategist Agent
# ──────────────────────────────────────────────

_PERSONAS_DIR = Path(__file__).resolve().parent.parent / "personas"
VALID_PERSONAS = ("blackrock", "ark", "graham")


def _load_personas() -> dict[str, str]:
    """personas/*.md를 dict로 로드. 시작 시 1회."""
    personas: dict[str, str] = {}
    for name in VALID_PERSONAS:
        path = _PERSONAS_DIR / f"{name}.md"
        if path.exists():
            personas[name] = path.read_text(encoding="utf-8")
        else:
            logger.warning(f"페르소나 파일 누락: {path}")
            personas[name] = ""
    return personas


class StrategistAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            agent_name="strategist",
            model=MODEL_OPUS,
            system_prompt=STRATEGIST_BASE_PROMPT,  # 실제 호출 시 페르소나 결합
        )
        self._personas = _load_personas()

    def _build_full_system(self, persona: str) -> str:
        """Base + 페르소나별 markdown을 결합."""
        if persona not in self._personas:
            persona = "blackrock"
        return f"{STRATEGIST_BASE_PROMPT}\n{self._personas[persona]}"

    async def run(self, input_data: StrategistInput, uid: str = "") -> StrategistResult:
        # 1) 페르소나별 전체 system 구성
        full_system = self._build_full_system(input_data.persona)

        # 2) user message 구성
        user_message = self._build_user_message(input_data)

        # 3) Claude Opus 호출
        result, raw = await self.call_claude_json(
            user_message=user_message,
            schema=StrategistResult,
            max_tokens=2560,
            uid=uid,
            system=full_system,
        )

        # 4) 메타 보정
        result.persona_used = input_data.persona
        result.timestamp = datetime.now(timezone.utc).isoformat()
        result.disclaimer = DISCLAIMER

        # 5) Validator confidence 체크 → confidence_note 자동 보강
        if input_data.validator_output.confidence_score < 0.7 and not result.confidence_note:
            result.confidence_note = (
                f"⚠️ 데이터 검증 신뢰도 {input_data.validator_output.confidence_score:.2f} "
                f"(임계값 0.70 미달). 분석 결과를 직접 확인하시고 신중히 판단하세요."
            )

        return result

    # ──────────────────────────────────────────
    # User 메시지 구성
    # ──────────────────────────────────────────

    def _build_user_message(self, input_data: StrategistInput) -> str:
        a = input_data.analyst_output
        r = input_data.research_output
        v = input_data.validator_output
        u = input_data.user_profile

        lines: list[str] = []
        lines.append(f"# 사용자 원본 질의\n{input_data.query or '(없음 — 자유 분석)'}")
        lines.append(f"\n# 적용 페르소나\n{input_data.persona}")

        # 사용자 프로파일
        lines.append("\n# 사용자 프로파일")
        lines.append(f"- 경력: {u.investing_experience}")
        if u.investment_amount:
            lines.append(f"- 투자 가능 금액: {u.investment_amount:,}원")
        if u.holding_period:
            lines.append(f"- 보유 기간 선호: {u.holding_period}")
        if u.volatility_tolerance:
            lines.append(f"- 변동성 감내도: {u.volatility_tolerance}%")
        if u.interested_sectors:
            lines.append(f"- 관심 섹터: {', '.join(u.interested_sectors)}")
        if u.investment_principles:
            lines.append("- 투자 원칙:")
            for p in u.investment_principles:
                lines.append(f"  • {p}")

        # Research 요약
        lines.append("\n# Research 요약")
        lines.append(f"- 시장 심리: {r.market_sentiment}")
        if r.macro_context.fomc_next:
            lines.append(f"- 다음 FOMC: {r.macro_context.fomc_next}")
        if r.macro_context.key_risks:
            lines.append(f"- 주요 리스크: {'; '.join(r.macro_context.key_risks[:5])}")
        if r.macro_context.key_opportunities:
            lines.append(f"- 주요 기회: {'; '.join(r.macro_context.key_opportunities[:5])}")
        if r.sector_status:
            lines.append("- 섹터 상태:")
            for s in r.sector_status[:5]:
                lines.append(f"  • {s.name}: {s.status} (참여: {s.rally_participation})")
        lines.append(f"- summary: {r.summary}")

        # Analyst 결과
        lines.append("\n# Analyst 결과")
        lines.append(f"- 종목: {a.name} ({a.ticker})")
        lines.append(f"- 현재가: {a.technical.current_price:,}원")
        lines.append(f"- 이평 정렬: {a.technical.ma_status} (MA5 {a.technical.ma5:,} / MA20 {a.technical.ma20:,} / MA60 {a.technical.ma60:,})")
        lines.append(f"- RSI {a.technical.rsi:.1f} ({a.technical.rsi_status}), 52w 고가 대비 {a.technical.vs_high_52w:+.1f}%, 52w 저가 대비 {a.technical.vs_low_52w:+.1f}%")
        lines.append(f"- 종합 시그널: {a.technical.signal}")
        lines.append(f"- PER {a.fundamental.per}, PBR {a.fundamental.pbr}, ROE {a.fundamental.roe}%, 배당수익률 {a.fundamental.div_yield}%")
        lines.append(f"- 펀더멘털 판단: {a.fundamental.valuation_judgment}")
        lines.append(f"- buy_score {a.buy_score.buy_score:.1f} (구간: {a.buy_score.score_tier})")
        lines.append(f"  → {a.buy_score.interpretation}")
        if a.buy_score.contributing_factors:
            lines.append(f"  기여 요인: {'; '.join(a.buy_score.contributing_factors[:5])}")
        if a.peer_comparison:
            lines.append(f"- Peer 비교: {len(a.peer_comparison)}종목")
            for p in a.peer_comparison[:3]:
                lines.append(
                    f"  • {p.get('name', '')} PER {p.get('per', 0):.1f} / PBR {p.get('pbr', 0):.1f} / ROE {p.get('roe', 0):.1f}%"
                )
        lines.append(f"- summary: {a.summary}")

        # Validator 결과
        lines.append("\n# Validator 결과")
        lines.append(f"- 종합 상태: {v.overall_status}, confidence={v.confidence_score}")
        lines.append(f"- fresh={v.fresh_data_count}, stale={v.stale_data_count}, requires_reanalysis={v.requires_reanalysis}")
        if v.contrarian_scenarios:
            lines.append(f"- Contrarian 시나리오 {len(v.contrarian_scenarios)}개:")
            for s in v.contrarian_scenarios[:5]:
                lines.append(f"  • [{s.probability}] {s.title}: {s.description}")
        if v.blind_spots:
            lines.append(f"- Blind Spots: {'; '.join(v.blind_spots[:5])}")

        lines.append(
            "\n# 출력 지시\n"
            "위 모든 정보를 종합하여, 적용 페르소나의 관점으로 사용자에게 직접 말하는 최종 분석을 작성하세요. "
            "사용자 원칙별 부합 여부는 user_principles_alignment에 명시. "
            "Contrarian 시나리오를 분석에 반영. "
            "Validator confidence가 낮으면 confidence_note 작성. "
            "JSON 외 다른 텍스트는 절대 포함하지 마세요."
        )
        return "\n".join(lines)
