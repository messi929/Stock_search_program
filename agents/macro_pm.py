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
    name: Optional[str] = None  # 정확한 종목명 (환각 방지 — graph에서 주입)
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
# 완전성 검사 — Claude 응답 필드 누락 탐지
# ──────────────────────────────────────────────


def check_macro_completeness(result: MacroPmResult) -> list[str]:
    """default_factory로 검증 통과하는 핵심 필드의 실질 누락 탐지.

    macro_regime/weighting_used는 run() 후처리에서 정량 결과로 강제 보정되므로
    여기서는 LLM 고유 산출물인 cycle_analysis와 summary_neutral만 검사.
    """
    missing: list[str] = []

    if not result.summary_neutral.strip():
        missing.append("summary_neutral")

    ca = result.cycle_analysis
    if not any(
        cycle.stage.strip()
        for cycle in (
            ca.interest_rate,
            ca.business_cycle,
            ca.currency_cycle,
            ca.inflation_cycle,
        )
    ):
        missing.append("cycle_analysis")

    return missing


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
        primary_country = "US" if us_w >= 0.5 else "KR"
        bundle = self._fetch_macro_bundle(country=primary_country)

        # 2.5) 실측 지표(현재값) 수집 — LLM 수치 환각 방지용 그라운딩.
        #   프롬프트엔 사이클 stage 라벨만 들어가 LLM이 환율·금리 등 '현재값'을 학습
        #   기억에서 지어내던 문제(2026-06: USD/KRW 1,520원대를 1,400원으로 환각)를
        #   실측값 주입으로 차단. 매크로 서사는 본질적으로 US/KR 모두 언급하므로 양국 적재.
        actuals = self._collect_actuals(bundle, primary_country)

        # 3) user message 구성
        user_message = self._build_user_message(
            input_data, bundle, us_w, kr_w, rationale, actuals
        )

        # 4) Claude 호출 (JSON 파싱 + Pydantic 검증 + 완전성 재시도)
        result, _raw = await self.call_claude_json(
            user_message=user_message,
            schema=MacroPmResult,
            max_tokens=3000,
            uid=uid,
            completeness_check=check_macro_completeness,
            # 구조화 출력(강제 tool use) — 텍스트 파싱 flaky 제거(2026-06-07 근본 안정화).
            # 중첩 스키마($defs/$ref)도 tool input_schema로 그대로 수용. 가중치·regime은
            # run() 후처리가 정량값으로 강제하고, 4축·summary 충실도는 completeness가 보강.
            structured_output=True,
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

    def _collect_actuals(
        self, bundle: dict[str, Any], primary_country: str
    ) -> dict[str, dict[str, Any]]:
        """US/KR 실측 지표(raw_inputs)를 country별로 수집.

        primary는 bundle에 이미 적재된 raw_inputs 재사용(추가 read 없음), 나머지 1개국만
        추가 조회. Firestore 장애 시 가능한 만큼만 반환(best-effort).
        """
        actuals: dict[str, dict[str, Any]] = {}
        if bundle.get("raw_inputs"):
            actuals[primary_country] = bundle["raw_inputs"]
        other = "US" if primary_country == "KR" else "KR"
        try:
            other_inputs = self._load_macro_inputs(other)
            if other_inputs:
                actuals[other] = other_inputs
        except Exception as e:
            logger.debug(f"[macro_pm] {other} 실측 지표 로드 실패: {e}")
        return actuals

    @staticmethod
    def _format_actuals_country(country: str, raw: dict[str, Any]) -> list[str]:
        """한 국가의 실측 지표를 사람이 읽는 라인으로 변환. 값 없거나 0.0 fallback은 생략."""
        def num(key: str, allow_zero: bool = False):
            v = raw.get(key)
            if not isinstance(v, (int, float)):
                return None
            if v == 0 and not allow_zero:
                return None
            return float(v)

        is_kr = country == "KR"
        out: list[str] = []
        # 통화 — KR은 USD/KRW(원), US는 DXY 달러지수
        cur, c3, c12 = num("dxy_current"), num("dxy_3m_ago"), num("dxy_12m_ago")
        if cur is not None:
            label = "USD/KRW 환율(원)" if is_kr else "DXY 달러지수"
            seg = f"  - {label}: 현재 {cur:,.1f}"
            if c3 is not None:
                seg += f" / 3개월 전 {c3:,.1f}"
            if c12 is not None:
                seg += f" / 12개월 전 {c12:,.1f}"
            out.append(seg)
        # 정책금리
        rc, r3, r12 = num("rate_current"), num("rate_3m_ago"), num("rate_12m_ago")
        if rc is not None:
            rate_label = "한국은행 기준금리" if is_kr else "연방기금금리"
            seg = f"  - {rate_label}: 현재 {rc:.2f}%"
            if r3 is not None:
                seg += f" / 3개월 전 {r3:.2f}%"
            if r12 is not None:
                seg += f" / 12개월 전 {r12:.2f}%"
            out.append(seg)
        # 인플레이션 — YoY 타당 범위(-5~30%)만 인용. 범위 밖은 지수 레벨 등
        #   파이프라인 오매핑일 가능성이 커 환각 유발 → 주입 생략(known issue).
        def plausible_yoy(v):
            return v is not None and -5.0 <= v <= 30.0

        cpi = num("cpi_yoy")
        if plausible_yoy(cpi):
            out.append(f"  - CPI(전년비): {cpi:.2f}%")
        core = num("core_cpi_yoy")
        if plausible_yoy(core):
            out.append(f"  - Core CPI(전년비): {core:.2f}%")
        # 경기
        gdp = num("gdp_yoy")
        if gdp is not None:
            out.append(f"  - GDP(전년비): {gdp:.2f}%")
        un = num("unemployment_current")
        if un is not None:
            out.append(f"  - 실업률: {un:.2f}%")
        sp = raw.get("spread_10y_2y")
        if isinstance(sp, (int, float)) and sp != 0:
            out.append(f"  - 10Y-2Y 국채 스프레드: {float(sp):.2f}%p")
        return out

    def _load_macro_inputs(self, country: str) -> dict[str, Any]:
        """Firestore macro_indicators에서 cycle_detector 입력 로드.

        jobs.monthly_regime_calc.build_cycle_inputs를 재사용 — macro_indicators의
        indicator_key를 cycle_detector REQUIRED_INPUTS로 매핑하고 3m/12m 전 값까지
        구성한다. 지표가 부족하면 누락 필드는 0.0 fallback(+ missing 로그)되어 사이클
        신뢰도가 낮게 나온다. Firestore 미접근/오류 시 빈 dict(→ "데이터 누적 중").
        본 메서드는 단위 테스트에서 mock 권장.
        """
        try:
            from jobs.monthly_regime_calc import build_cycle_inputs

            from screener.db.firebase_client import get_db

            inputs, missing = build_cycle_inputs(get_db(), country)
            if missing:
                logger.info(
                    f"[macro_pm] 매크로 지표 {len(missing)}개 누락(0.0 fallback): "
                    f"{missing[:6]}"
                )
            return inputs or {}
        except Exception as e:
            logger.warning(
                f"[macro_pm] _load_macro_inputs 실패: {type(e).__name__}: {str(e)[:120]}"
            )
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
        actuals: dict[str, dict[str, Any]] | None = None,
    ) -> str:
        lines: list[str] = []
        lines.append("# 분석 요청")
        if inp.ticker:
            label = f"{inp.name} ({inp.ticker})" if inp.name else inp.ticker
            lines.append(f"종목: {label} (시장: {inp.market or '미상'})")
            if inp.name:
                lines.append(
                    f"⚠️ 이 종목의 정확한 이름은 '{inp.name}'입니다. "
                    f"다른 회사로 추정하지 말고 반드시 이 종목명을 사용하세요."
                )
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

        # 실측 지표(현재값) — LLM 수치 환각 방지 그라운딩
        actuals = actuals or {}
        actual_lines: list[str] = []
        for ctry in ("KR", "US"):
            raw = actuals.get(ctry)
            if not raw:
                continue
            ctry_lines = self._format_actuals_country(ctry, raw)
            if ctry_lines:
                actual_lines.append(f"[{ctry}]")
                actual_lines.extend(ctry_lines)
        if actual_lines:
            lines.append(
                "\n# 실측 지표 — 현재값 (수집 데이터, YoY·전년비 등은 최근 발표 기준)"
            )
            lines.extend(actual_lines)
            lines.append(
                "→ transition_signals_to_monitor의 current(현재값)·trigger_level을 "
                "포함한 **모든 환율·금리·물가 수치는 위 실측값에서만 인용**할 것. "
                "위에 없는 수치는 임의로 만들지 말고, 값이 없으면 정성 서술로 대체."
            )
        else:
            lines.append(
                "\n# 실측 지표 사용 불가 → 환율·금리·물가의 구체적 '현재 수치'를 "
                "임의로 제시하지 말 것 (정성 서술만)."
            )

        lines.append(
            "\n# 출력 지시\n"
            "위 정량 결과를 그대로 사용하여 제공된 구조화 출력 도구를 호출해 결과를 제출. "
            "regime은 위 정량 결과와 일치해야 하며, 사이클 4축의 stage 단어를 그대로 사용. "
            "cycle_analysis 4축과 summary_neutral은 **반드시** 채울 것 (생략 시 빈 카드 노출). "
            "weighting_used는 위 정량 가중치 그대로. "
            "수치 인용은 위 '실측 지표' 값만 사용 — 학습 기억의 환율·금리 수치 생성 절대 금지. "
            "단정어 사용 금지 — '관찰', '통상 패턴', '역사적 통계' 등 중립 표현."
        )
        return "\n".join(lines)
