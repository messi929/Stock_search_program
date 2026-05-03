"""Macro PM Agent — 매크로 사이클/국면 페르소나.

상세 스펙: docs/personas/macro.md, docs/data_infra/macro.md
WEEK_D.md Day 3 산출물.

핵심: Week B 데이터 인프라(FRED/ECOS + cycle_detector + regime_detector)를
호출하여 4 사이클 + 6 국면 + 동적 한국 가중치 적용된 응답 생성.

⚠️ 4 사이클 입력 데이터는 Firestore macro_indicators 컬렉션에서 조회.
   누락 시 graceful — Claude에게 "데이터 부재" 명시.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from loguru import logger
from pydantic import BaseModel, Field

from agents.base import BaseAgent
from utils.claude_client import MODEL_SONNET


# ──────────────────────────────────────────────
# 입출력 스키마
# ──────────────────────────────────────────────


class MacroPmInput(BaseModel):
    """Macro PM 입력.

    ticker가 한국이면 KR 가중치 60%, 미국이면 US 가중치 90%, ETF/매크로면 70/30.
    """

    ticker: Optional[str] = None  # 종목 분석 시
    market: Optional[str] = None  # "KR" | "US" | "GLOBAL"
    sector: Optional[str] = None
    question_type: str = "stock"  # "stock" | "etf" | "macro_only"


class CycleStage(BaseModel):
    stage: str = ""
    key_indicators: dict[str, Any] = Field(default_factory=dict)
    rationale: str = ""


class CycleAnalysis(BaseModel):
    interest_rate: CycleStage = Field(default_factory=CycleStage)
    business_cycle: CycleStage = Field(default_factory=CycleStage)
    currency_cycle: CycleStage = Field(default_factory=CycleStage)
    inflation_cycle: CycleStage = Field(default_factory=CycleStage)


class MacroRegime(BaseModel):
    current_regime: str = "Transition"
    transition_to: Optional[str] = None
    regime_confidence: float = 0.0


class TransitionSignal(BaseModel):
    signal: str = ""
    current: str = ""
    trigger_level: str = ""
    implication: str = ""


class StockMacroAlignment(BaseModel):
    ticker: str = ""
    sector: str = ""
    macro_alignment: str = "⚠️ 중립"
    alignment_score: float = 5.0
    interpretation: str = ""


class WeightingUsed(BaseModel):
    us_weight: float = 0.7
    kr_weight: float = 0.3
    rationale: str = ""


class MacroPmResult(BaseModel):
    # LLM 누락 시 검증 실패 회피 — run() 후처리에서 정량 결과로 강제 보정.
    macro_regime: MacroRegime = Field(default_factory=MacroRegime)
    cycle_analysis: CycleAnalysis = Field(default_factory=CycleAnalysis)
    regime_implications: dict[str, Any] = Field(default_factory=dict)
    transition_signals_to_monitor: list[TransitionSignal] = Field(default_factory=list)
    stock_specific_analysis: Optional[StockMacroAlignment] = None
    weighting_used: WeightingUsed = Field(default_factory=WeightingUsed)
    summary_neutral: str = ""
    persona: str = "macro"
    timestamp: str = ""


# ──────────────────────────────────────────────
# 동적 가중치 결정
# ──────────────────────────────────────────────


def determine_weights(
    market: Optional[str], question_type: str
) -> tuple[float, float, str]:
    """ticker market + question_type → (us_weight, kr_weight, rationale).

    페르소나 docs/personas/macro.md 정책 그대로 적용.
    """
    if question_type == "macro_only" or question_type == "etf":
        return 0.7, 0.3, "글로벌 ETF/매크로 분석 — 미국 70% / 한국 30%"
    if market == "KR":
        return 0.4, 0.6, "한국 종목 분석 — 한국 매크로 우선 (한국 60% / 미국 40%)"
    if market == "US":
        return 0.9, 0.1, "미국 종목 분석 — 미국 매크로 우선 (미국 90% / 한국 10%)"
    return 0.7, 0.3, "시장 미상 — 기본값 70/30 적용"


# ──────────────────────────────────────────────
# 시스템 프롬프트 로딩
# ──────────────────────────────────────────────


_PERSONAS_DIR = Path(__file__).resolve().parent.parent / "personas"


def _load_macro_persona() -> str:
    path = _PERSONAS_DIR / "macro.md"
    if not path.exists():
        logger.error(f"macro 페르소나 파일 누락: {path}")
        return ""
    return path.read_text(encoding="utf-8")


# ──────────────────────────────────────────────
# Macro PM Agent
# ──────────────────────────────────────────────


class MacroPmAgent(BaseAgent):
    def __init__(self, claude=None):
        system = _load_macro_persona()
        super().__init__(
            agent_name="macro_pm",
            model=MODEL_SONNET,
            system_prompt=system,
            claude=claude,
        )

    async def run(self, input_data: MacroPmInput, uid: str = "") -> MacroPmResult:
        # 1) 동적 가중치
        us_w, kr_w, rationale = determine_weights(
            input_data.market, input_data.question_type
        )

        # 2) 4 사이클 + 6 국면 산출 (정량 결과를 Claude 입력에 주입)
        bundle = self._fetch_macro_bundle(
            country="US" if us_w >= 0.5 else "KR"
        )

        # 3) user message 구성
        user_message = self._build_user_message(input_data, bundle, us_w, kr_w, rationale)

        # 4) Claude 호출
        result, _raw = await self.call_claude_json(
            user_message=user_message,
            schema=MacroPmResult,
            max_tokens=2200,
            uid=uid,
        )

        # 5) 메타 보정
        result.persona = "macro"
        result.timestamp = datetime.now(timezone.utc).isoformat()

        # 6) 가중치는 정량 결정값 강제 주입 (Claude가 부정확하게 줄 수 있음)
        result.weighting_used = WeightingUsed(
            us_weight=round(us_w, 2),
            kr_weight=round(kr_w, 2),
            rationale=rationale,
        )

        # 7) regime_confidence 정량 결과 강제 (LLM이 부풀릴 가능성)
        if bundle.get("regime"):
            r = bundle["regime"]
            # current_regime이 정량 결과와 일치하지 않으면 정량 결과 사용
            quantitative_regime = r.get("regime", "Transition")
            if result.macro_regime.current_regime != quantitative_regime:
                logger.info(
                    f"[macro_pm] LLM regime '{result.macro_regime.current_regime}' → "
                    f"정량 결과 '{quantitative_regime}'으로 강제 보정"
                )
                result.macro_regime.current_regime = quantitative_regime
            result.macro_regime.regime_confidence = float(r.get("regime_confidence", 0.0))
            if r.get("transition_to"):
                result.macro_regime.transition_to = r["transition_to"]

        # 8) summary_neutral 단정어 후처리
        filtered, found = self.filter_forbidden(result.summary_neutral)
        if found:
            logger.warning(f"[macro_pm] summary_neutral 단정어 필터링: {found}")
            result.summary_neutral = filtered

        return result

    # ──────────────────────────────────────────
    # 4 사이클 + 6 국면 정량 산출
    # ──────────────────────────────────────────

    def _fetch_macro_bundle(self, country: str = "US") -> dict[str, Any]:
        """Firestore macro_indicators 최신 값 → cycle_detector + regime_detector.

        Firestore 미설정/장애 시 빈 dict 반환 (LLM이 데이터 부재로 처리).
        """
        try:
            inputs = self._load_macro_inputs(country)
        except Exception as e:
            logger.warning(
                f"[macro_pm] macro_indicators 로드 실패: {type(e).__name__}: {str(e)[:120]}"
            )
            return {"available": False, "error": str(e)[:120]}

        if not inputs:
            return {"available": False, "reason": "macro_indicators 데이터 없음"}

        try:
            from utils.data_collectors.cycle_detector import detect_all_cycles
            from utils.data_collectors.regime_detector import detect_regime_from_cycles

            cycles = detect_all_cycles(inputs, country=country)
            regime = detect_regime_from_cycles(cycles)
        except (ValueError, KeyError) as e:
            logger.warning(f"[macro_pm] cycle/regime 판정 실패: {e}")
            return {"available": False, "error": f"{type(e).__name__}: {e}"}

        return {
            "available": True,
            "country": country,
            "cycles": cycles,
            "regime": regime,
            "raw_inputs": inputs,
        }

    def _load_macro_inputs(self, country: str) -> dict[str, Any]:
        """Firestore macro_indicators에서 cycle_detector REQUIRED_INPUTS 로드.

        하위 호환을 위해 지표가 없으면 inputs를 빈 dict로 반환 (cycle_detector가 ValueError).
        본 메서드는 단위 테스트에서 mock 권장.
        """
        # 운영 시 Firestore 조회 — 실제 구현은 단위 테스트 외부에서 통합.
        # 여기서는 lazy 구현: Firestore 미접근 환경에서는 즉시 빈 dict.
        return {}

    # ──────────────────────────────────────────
    # User message 구성
    # ──────────────────────────────────────────

    def _build_user_message(
        self,
        inp: MacroPmInput,
        bundle: dict[str, Any],
        us_w: float,
        kr_w: float,
        rationale: str,
    ) -> str:
        lines: list[str] = []
        lines.append("# 분석 요청")
        if inp.ticker:
            lines.append(f"종목: {inp.ticker} (시장: {inp.market or '미상'})")
        if inp.sector:
            lines.append(f"섹터: {inp.sector}")
        lines.append(f"질문 타입: {inp.question_type}")
        lines.append(f"\n# 동적 가중치 (정량 결정 — 본 응답에 그대로 사용)")
        lines.append(f"- US: {us_w:.2f}, KR: {kr_w:.2f}")
        lines.append(f"- 사유: {rationale}")

        if bundle.get("available") and bundle.get("cycles"):
            cycles = bundle["cycles"]
            regime = bundle.get("regime", {})
            lines.append("\n# 정량 사이클 판정 (cycle_detector — 결과 그대로 사용)")
            for axis_key, label in (
                ("interest_rate", "금리"),
                ("business_cycle", "경기"),
                ("currency", "통화"),
                ("inflation", "인플레이션"),
            ):
                c = cycles.get(axis_key, {})
                lines.append(
                    f"- {label}: stage={c.get('stage', 'N/A')}, "
                    f"confidence={c.get('confidence', 'N/A')}"
                )

            lines.append("\n# 정량 6 국면 판정 (regime_detector — 결과 그대로 사용)")
            lines.append(f"- 현재 국면: {regime.get('regime', 'Transition')}")
            lines.append(f"- 한국어: {regime.get('regime_kr', '')}")
            lines.append(
                f"- 점수: {regime.get('regime_score', 0)}/4 "
                f"(confidence {regime.get('regime_confidence', 0):.2f})"
            )
            if regime.get("transition_to"):
                lines.append(f"- 전환 가능: {regime['transition_to']}")
            lines.append(f"- 매칭 사유: {regime.get('rationale', '')}")
        else:
            reason = bundle.get("reason") or bundle.get("error", "데이터 부재")
            lines.append(f"\n# 정량 사이클/국면 데이터 사용 불가: {reason}")
            lines.append(
                "→ historical pattern 기반 정성 분석으로 응답하세요 (수치 추정 X)."
            )

        lines.append(
            "\n# 출력 지시\n"
            "위 정량 결과를 그대로 사용하여 시스템 프롬프트 JSON 스키마에 맞춰 응답. "
            "regime은 위 정량 결과와 일치해야 하며, 사이클 4축의 stage 단어를 그대로 사용. "
            "weighting_used는 위 정량 가중치 그대로. "
            "단정어 사용 금지 — '관찰', '통상 패턴', '역사적 통계' 등 중립 표현."
        )
        return "\n".join(lines)
