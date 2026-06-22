"""Strategist Agent — 4 에이전트 종합 + 시간축 관점 적용 + 최종 사용자 응답.

상세 스펙: docs/axis/agents/strategist.md / 설계: docs/axis/HORIZONS.md
관점 프롬프트: personas/horizons/{short,short_mid,mid,long}.md

이 에이전트가 사용자에게 직접 보여지는 최종 응답을 만듭니다.
- 모델: Sonnet 4.6 (2026-06-02 Opus 4.7→전환, A/B 검증 후 — docs/axis/UNIT_ECONOMICS.md)
- 입력: Research + Analyst + Validator 3종 결과 + 사용자 프로파일 + 시간축 관점(horizon)
- 출력: 관찰 구간/참고선/알림 조건 + 관점별 해석 + 사용자 원칙 부합도

페르소나(블랙록/ARK/그레이엄)는 2026-06-22 horizon 관점으로 전면 대체됨.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from loguru import logger
from pydantic import BaseModel, Field

from agents.analyst import AnalystResult
from agents.base import DISCLAIMER, BaseAgent
from agents.research import ResearchResult
from agents.validator import ValidatorResult
from utils.claude_client import MODEL_SONNET


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
    # (레거시 캐리어) 더 이상 프롬프트에 영향 없음 — graph 분기 호환용으로만 잔존.
    persona: str = "blackrock"
    # 시간축 관점 — 1차 축. horizon emphasis 프롬프트(personas/horizons/*.md)를 적용.
    #   "short" | "short_mid" | "mid" | "long". 빈 값이면 "mid"로 기본 처리.
    horizon: str = ""
    # 결정론적 매크로 컨텍스트(LLM 미호출) — 중기/장기 관점에서 매크로 그라운딩 주입(Phase 1b).
    macro_context: str = ""
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
데이터를 정리하고 선택된 시간축 관점에 맞춰 해석합니다.

## 입력 구성
1. Research 결과: 시황·뉴스·매크로·수급
2. Analyst 결과: 기술/펀더멘털 정량 해석 + buy_score
3. Validator 결과: 코드 검증 + Contrarian 시나리오 + Blind Spot
4. 사용자 프로파일: 경험·보유기간·변동성 감내도·관심 섹터·개인 원칙
5. 적용 관점(시간축): 단기 / 단중기 / 중기 / 장기 중 하나 (아래 관점 지침 참고)

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

### Step 3: 관점(시간축) 적용 (이게 가장 중요)
- 아래 "관점 지침"의 시간축 렌즈로 데이터를 재해석
- 그 관점에서 강조할 포인트 vs 배경으로 둘 포인트가 명확해야 함
- persona_perspective 필드는 "[관점명] 관점에서..." 로 시작 (실무자 실명 금지)

### Step 4: 참고 수치 산출 (관점에 맞게 차등 — 시간축에 따라 관찰 구간의 근거·폭이 달라져야 함)

**진입 관찰 구간 (entry_points)** — 관점 지침의 근거 기준에 맞춰:
- 단기/단중기: 기술적 레벨(지지·저항·이동평균·변동성 밴드) 중심, 좁은 폭
- 중기/장기: 밸류에이션 밴드(역사적 PER/PBR)·실적 경로·52주 범위 중심, 넓은 폭
- tier1/tier2/tier3는 현재가 아래로 단계적. 종목 변동성·기술선·저점 데이터로 조정.

**손실 한도 참고선 (stop_loss)** — 사용자 변동성 감내도 + 관점:
- 단기는 좁게(기술적 이탈 기준), 장기는 넓게(구조적 훼손 기준). 변동성 감내도로 가감.

**차익 실현 참고선 (take_profit_1, take_profit_final)** — 관점별 시계관:
- 단기/단중기: 기술적 목표·직전 고점 부근, 짧은 회복 폭
- 중기/장기: 밸류에이션 정상화·구조적 성장 반영, 넓은 회복 폭
- % 는 현재가 기준 가이드. 종목 historical 변동·valuation·섹터 평균 등으로 조정.

**알림 조건**: 실용적 트리거 2~4개.

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
- 분석 방법론의 실무자 실명(그레이엄·버핏·오닐·린치·미너비니 등) 노출

## 응답 톤
- 진중하지만 친근하게
- 한국어로 자연스럽게
- 데이터 기반, 감정 배제

## 출력 형식
반드시 JSON 객체만. 코드 펜스/설명 텍스트 금지. 모든 string value 내부 큰따옴표는 \\", 줄바꿈은 \\n으로 escape.

{
  "persona_used": "short | short_mid | mid | long",
  "persona_perspective": "선택된 시간축 관점에서의 한 단락 분석",
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

# 관점 지침 (이 분석에 적용할 시간축 렌즈)
"""


# ──────────────────────────────────────────────
# Strategist Agent
# ──────────────────────────────────────────────

_PERSONAS_DIR = Path(__file__).resolve().parent.parent / "personas"

# 시간축 관점 — 1차 축. personas/horizons/{key}.md 로 emphasis 프롬프트 로드.
_HORIZONS_DIR = _PERSONAS_DIR / "horizons"
VALID_HORIZONS = ("short", "short_mid", "mid", "long")
DEFAULT_HORIZON = "mid"

# Extended Thinking 예산 (0=비활성). Strategist는 4종 입력 종합 + 페르소나 적용 +
# 사용자 원칙 정합 판단까지 다단계 추론이라 thinking 효과가 가장 큰 노드.
# env로 A/B 토글 가능 (STRATEGIST_THINKING_BUDGET=0 → 종전 동작).
STRATEGIST_THINKING_BUDGET = int(os.environ.get("STRATEGIST_THINKING_BUDGET", "3200"))


def _load_horizons() -> dict[str, str]:
    """personas/horizons/*.md를 dict로 로드. 시작 시 1회."""
    horizons: dict[str, str] = {}
    for name in VALID_HORIZONS:
        path = _HORIZONS_DIR / f"{name}.md"
        if path.exists():
            horizons[name] = path.read_text(encoding="utf-8")
        else:
            logger.warning(f"관점(horizon) 파일 누락: {path}")
            horizons[name] = ""
    return horizons


class StrategistAgent(BaseAgent):
    def __init__(self):
        # 모델: Sonnet 4.6 (2026-06-02 Opus 4.7→전환). A/B 검증상 종합/페르소나
        # 품질 동등 이상 + 건당 비용 76%↓(~300원→~72원). 상세: docs/axis/UNIT_ECONOMICS.md
        super().__init__(
            agent_name="strategist",
            model=MODEL_SONNET,
            system_prompt=STRATEGIST_BASE_PROMPT,  # 실제 호출 시 관점 결합
        )
        self._horizons = _load_horizons()

    def _normalize_horizon(self, horizon: str) -> str:
        """빈 값·미상 horizon은 기본값(mid)으로 보정."""
        return horizon if horizon in VALID_HORIZONS else DEFAULT_HORIZON

    def _build_full_system(self, horizon: str = "") -> str:
        """Base + 시간축 관점(horizon) emphasis markdown 결합.

        결정(A): 방법론 라벨만 노출, 실무자 실명은 내부 앵커로만(출력 마스킹).
        """
        horizon = self._normalize_horizon(horizon)
        _hz_label = {
            "short": "단기", "short_mid": "단중기",
            "mid": "중기", "long": "장기",
        }.get(horizon, horizon)
        guard = (
            "\n\n## 출력 표기 규칙\n"
            "- 분석 방법론의 실무자 실명(예: 그레이엄·버핏·오닐·린치·미너비니)을 "
            f"출력에 노출하지 말 것. '{_hz_label} 관점' 또는 방법론 명칭"
            "(모멘텀·추세 / 어닝 모멘텀 / GARP / 가치·해자)으로만 표현.\n"
            f"- persona_perspective에도 실명 대신 '{_hz_label} 관점'으로 서술."
        )
        return f"{STRATEGIST_BASE_PROMPT}\n{self._horizons.get(horizon, '')}{guard}"

    async def run(self, input_data: StrategistInput, uid: str = "") -> StrategistResult:
        # 1) 시간축 관점(horizon)으로 전체 system 구성 (빈 값이면 mid)
        full_system = self._build_full_system(input_data.horizon)

        # 2) user message 구성
        user_message = self._build_user_message(input_data)

        # 3) Claude 호출 (Sonnet 4.6)
        # max_tokens 2560 — Sonnet은 서술이 풍부해 1500이면 마지막 필드(alert_conditions)가
        # 잘림(A/B 검증 확인). 단가 1/5라 2560도 건당 ~85원으로 Opus 대비 저렴.
        result, raw = await self.call_claude_json(
            user_message=user_message,
            schema=StrategistResult,
            max_tokens=2560,
            uid=uid,
            system=full_system,
            thinking_budget=STRATEGIST_THINKING_BUDGET,
        )

        # 4) 메타 보정 — 적용 관점(horizon)을 persona_used에 기록
        result.persona_used = self._normalize_horizon(input_data.horizon)
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
        _hz = self._normalize_horizon(input_data.horizon)
        _hz_label = {
            "short": "단기 (수일~1개월)",
            "short_mid": "단중기 (1~3개월)",
            "mid": "중기 (3개월~1년)",
            "long": "장기 (1년+)",
        }.get(_hz, _hz)
        lines.append(f"\n# 적용 관점(시간축)\n{_hz_label}")

        # 중기/장기 관점 — 결정론적 매크로 사이클/실측 데이터 그라운딩(Phase 1b).
        if input_data.macro_context:
            lines.append(f"\n{input_data.macro_context}")

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
        audit = getattr(v, "interpretation_audit", None) or []
        if audit:
            lines.append(f"- 해석 감사 {len(audit)}건 (Analyst 해석의 과신/비약 — 종합 시 보정 필수):")
            for a in audit[:5]:
                lines.append(f"  • [{a.severity}] {a.claim} → {a.issue}")

        lines.append(
            "\n# 출력 지시\n"
            "위 모든 정보를 종합하여, 적용 관점(시간축)의 렌즈로 사용자에게 직접 말하는 최종 분석을 작성하세요. "
            "사용자 원칙별 부합 여부는 user_principles_alignment에 명시. "
            "Contrarian 시나리오를 분석에 반영. "
            "해석 감사 지적이 있으면, Analyst 해석을 그대로 받지 말고 해당 부분을 보정/완화해 서술하세요 "
            "(과신·방향 비약을 반복하지 말 것). "
            "Validator confidence가 낮으면 confidence_note 작성. "
            "JSON 외 다른 텍스트는 절대 포함하지 마세요."
        )
        return "\n".join(lines)
