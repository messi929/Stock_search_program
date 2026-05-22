"""Event Analyst Agent — 이벤트 드리븐 통계 분석 페르소나.

상세 스펙: docs/personas/event.md, docs/data_infra/event.md
WEEK_D.md Day 1~2 산출물.

핵심: Week C에서 만든 데이터 인프라(옵션/이벤트/공매도/LLM 추론)를 호출하여
4차원 확실성 점수 + 시나리오 분석 + 표본 신뢰도 적용된 응답 생성.

페르소나는 Strategist와 분리됨 — Event Analyst는 단일 페르소나로 직접 응답.

⚠️ LEGAL: 페르소나 프롬프트에 단정 금지 + 시스템 후처리에서 추가 필터링.
   응답에 fabrication 경고 자동 첨부 (event_inference_cache 결과 통합).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from loguru import logger
from pydantic import BaseModel, ConfigDict, Field

from agents.base import BaseAgent, DISCLAIMER
from utils.claude_client import MODEL_SONNET


# ──────────────────────────────────────────────
# 입출력 스키마
# ──────────────────────────────────────────────


class EventAnalystInput(BaseModel):
    """Event Analyst 입력.

    market은 자동 추론도 가능하지만 명시 권장 — 6자리 숫자 → KR, 영문 → US.
    """

    ticker: str
    market: str = "KR"  # "KR" | "US"
    event_type: Optional[str] = None  # "earnings" | "ipo_secondary" | "buyback" | "fomc" | ...
    event_target: Optional[str] = None  # 예: "RKLB Q1 2026 실적", "SpaceX IPO 2026 Q4"
    primary_ticker: Optional[str] = None  # 1차 수혜 (2차 수혜 분석 시)


class CertaintyBreakdown(BaseModel):
    source: float
    source_rationale: str = ""
    timing: float
    timing_rationale: str = ""
    probability: float
    probability_rationale: str = ""
    impact: float
    impact_rationale: str = ""
    final_score: float
    mode: str  # "Full Analysis" | "Cautious" | "Probabilistic Only" | "Refused"


class EventSummary(BaseModel):
    event_type: str
    event_target: str
    d_day: str = ""
    certainty_breakdown: CertaintyBreakdown
    badge: str = ""


class ImpactMapping(BaseModel):
    direct_beneficiary: dict[str, Any] = Field(default_factory=dict)
    secondary_beneficiaries: list[dict[str, Any]] = Field(default_factory=list)
    tertiary_beneficiaries: list[dict[str, Any]] = Field(default_factory=list)


class SignalBlock(BaseModel):
    available: bool = False
    interpretation: str = ""
    key_observations: list[str] = Field(default_factory=list)


class TopHolder(BaseModel):
    holder: str = ""
    pct_held: Optional[float] = None
    shares: Optional[int] = None
    value: Optional[int] = None
    date_reported: Optional[str] = None
    pct_change: Optional[float] = None


class InstitutionalOwnership(BaseModel):
    """미국 종목 기관 보유 스냅샷 (정보 제공용 — LLM 미경유 passthrough, 신호/점수 아님).

    분기 13F 기반 정적 스냅샷(약 45일 지연). 일별 수급과 다름.
    """

    model_config = ConfigDict(extra="ignore")

    available: bool = False
    institutions_pct: Optional[float] = None
    insiders_pct: Optional[float] = None
    institutions_float_pct: Optional[float] = None
    institutions_count: Optional[int] = None
    top_holders: list[TopHolder] = Field(default_factory=list)
    as_of: Optional[str] = None
    data_source: str = ""
    note: str = ""


class HistoricalStatistics(BaseModel):
    comparable_events_count: int = 0
    sample_reliability: str = "❌ 통계 미제시"
    comparable_events: list[dict[str, Any]] = Field(default_factory=list)
    fabrication_warning: str = ""


class ReferenceZones(BaseModel):
    current_position_vs_history: str = ""
    historical_volatility_lower_1sigma: str = ""
    historical_volatility_upper_1sigma: str = ""
    note: str = "통계 진술이며 매매 권유가 아닙니다"


class ScenarioCase(BaseModel):
    trigger: str = ""
    historical_pattern: str = ""
    probability: str = ""


class ScenarioAnalysis(BaseModel):
    bullish_case: ScenarioCase = Field(default_factory=ScenarioCase)
    base_case: ScenarioCase = Field(default_factory=ScenarioCase)
    bearish_case: ScenarioCase = Field(default_factory=ScenarioCase)


class EventAnalystResult(BaseModel):
    # ticker/market은 입력에서 강제 보정되므로 default 제공 (Claude 누락 시 검증 실패 회피).
    ticker: str = ""
    market: str = ""
    event_summary: EventSummary
    impact_mapping: ImpactMapping = Field(default_factory=ImpactMapping)
    volume_supply_analysis: SignalBlock = Field(default_factory=SignalBlock)
    options_signals: SignalBlock = Field(default_factory=SignalBlock)
    credit_short_signals: SignalBlock = Field(default_factory=SignalBlock)
    historical_statistics: HistoricalStatistics = Field(
        default_factory=HistoricalStatistics
    )
    reference_observation_zones: ReferenceZones = Field(
        default_factory=ReferenceZones
    )
    scenario_analysis: ScenarioAnalysis = Field(default_factory=ScenarioAnalysis)
    key_risks: list[str] = Field(default_factory=list)
    what_to_watch: list[str] = Field(default_factory=list)
    # US 종목 기관 보유 스냅샷 — LLM 미경유 passthrough(사실 정보), 신호 아님. KR/미보유 시 None.
    institutional_ownership: Optional[InstitutionalOwnership] = None
    summary_neutral: str = ""
    persona: str = "event"
    timestamp: str = ""


# ──────────────────────────────────────────────
# 완전성 검사 — Claude 응답 필드 누락 탐지
# ──────────────────────────────────────────────


def check_event_completeness(result: EventAnalystResult) -> list[str]:
    """Claude가 통째로 빠뜨려도 default_factory로 검증 통과하는 핵심 필드 탐지.

    반환 리스트가 비어있지 않으면 call_claude_json이 1회 재요청한다.
    사용자에게 빈 카드가 노출되는 것을 막기 위한 근본 방어선.
    """
    missing: list[str] = []

    if not result.summary_neutral.strip():
        missing.append("summary_neutral")

    sa = result.scenario_analysis
    if not any(
        case.trigger.strip() or case.historical_pattern.strip()
        for case in (sa.bullish_case, sa.base_case, sa.bearish_case)
    ):
        missing.append("scenario_analysis")

    if not result.reference_observation_zones.current_position_vs_history.strip():
        missing.append("reference_observation_zones")

    return missing


# ──────────────────────────────────────────────
# 모드 분기 (확실성 점수)
# ──────────────────────────────────────────────


def determine_mode(final_score: float) -> tuple[str, str]:
    """확실성 점수 → (mode, badge).

    페르소나 docs/personas/event.md의 분기 정책을 정확히 적용.
    """
    if final_score >= 9:
        return "Full Analysis", "🟢 확정 이벤트"
    if final_score >= 7:
        return "Full Analysis", "🟢 신뢰 가능 이벤트"
    if final_score >= 5:
        return "Cautious", "🟡 추정 이벤트, 일정 변동 가능"
    if final_score >= 3:
        return "Probabilistic Only", "🟡 시장 추측 단계"
    return "Refused", "🔴 분석 거부"


def calculate_final_score(source: float, timing: float, probability: float, impact: float) -> float:
    """4차원 가중 평균. 페르소나 프롬프트에 명시된 가중치(40/30/20/10)."""
    return source * 0.4 + timing * 0.3 + probability * 0.2 + impact * 0.1


def is_kr_ticker(ticker: str) -> bool:
    """6자리 숫자면 한국, 그 외면 미국."""
    s = str(ticker).strip()
    return len(s) == 6 and s.isdigit()


# ──────────────────────────────────────────────
# 시스템 프롬프트 로딩
# ──────────────────────────────────────────────


_PERSONAS_DIR = Path(__file__).resolve().parent.parent / "personas"


def _load_event_persona() -> str:
    path = _PERSONAS_DIR / "event.md"
    if not path.exists():
        logger.error(f"event 페르소나 파일 누락: {path}")
        return ""
    return path.read_text(encoding="utf-8")


# ──────────────────────────────────────────────
# Event Analyst Agent
# ──────────────────────────────────────────────


class EventAnalystAgent(BaseAgent):
    """이벤트 드리븐 통계 분석 페르소나.

    데이터 수집 단계(call Week C 모듈) → user message 구성 → Claude → JSON 파싱.

    Sonnet 사용 (Haiku는 4차원 점수 + 시나리오 분석에 부족, Opus는 비용 과대).
    """

    def __init__(self, claude=None):
        system = _load_event_persona()
        super().__init__(
            agent_name="event_analyst",
            model=MODEL_SONNET,
            system_prompt=system,
            claude=claude,
        )

    async def run(
        self, input_data: EventAnalystInput, uid: str = ""
    ) -> EventAnalystResult:
        # 1) 데이터 수집 (Week C 모듈 호출)
        bundle = await self._collect_data_bundle(input_data)

        # 2) 확실성 점수 0~2 사전 차단 (Refused 모드)
        if bundle.get("certainty_pre_check", 10) < 3:
            return self._refused_response(input_data, bundle)

        # 3) user message 구성
        user_message = self._build_user_message(input_data, bundle)

        # 4) Claude 호출 (JSON 파싱 + Pydantic 검증 + 완전성 재시도)
        result, raw = await self.call_claude_json(
            user_message=user_message,
            schema=EventAnalystResult,
            max_tokens=3500,
            uid=uid,
            completeness_check=check_event_completeness,
        )

        # 5) 메타 보정 — Claude가 ticker/timestamp를 부정확하게 줄 수 있음
        result.ticker = input_data.ticker
        result.market = input_data.market or ("KR" if is_kr_ticker(input_data.ticker) else "US")
        result.persona = "event"
        result.timestamp = datetime.now(timezone.utc).isoformat()

        # 6) 확실성 점수 → 모드/배지 강제 일관 (Claude가 부정확한 분기를 줄 수 있음)
        cb = result.event_summary.certainty_breakdown
        # final_score를 4차원으로 재계산 (강제 일관성)
        recalculated = calculate_final_score(
            cb.source, cb.timing, cb.probability, cb.impact
        )
        cb.final_score = round(recalculated, 2)
        mode, badge = determine_mode(cb.final_score)
        cb.mode = mode
        result.event_summary.badge = badge

        # 7) 표본 신뢰도 자동 라벨 (Claude가 누락 가능)
        sample_n = result.historical_statistics.comparable_events_count
        result.historical_statistics.sample_reliability = (
            self._classify_sample_reliability(sample_n)
        )

        # 8) fabrication 경고 자동 첨부 (LLM 추론 한계 명시)
        if not result.historical_statistics.fabrication_warning:
            result.historical_statistics.fabrication_warning = (
                "비교 사례 통계는 LLM 학습 데이터 기반 추정이며, "
                "각 사례의 실제 수치는 외부 검증을 권장합니다."
            )

        # 9) summary_neutral에 단정어 후처리 필터링
        filtered, found = self.filter_forbidden(result.summary_neutral)
        if found:
            logger.warning(
                f"[event_analyst] summary_neutral에 단정어 발견 — 필터링: {found}"
            )
            result.summary_neutral = filtered

        # 10) 기관 보유 스냅샷 직접 주입 (US — LLM 미경유 사실 passthrough, 신호 아님)
        io_data = bundle.get("institutional_ownership")
        if isinstance(io_data, dict) and io_data.get("available"):
            try:
                result.institutional_ownership = InstitutionalOwnership.model_validate(
                    io_data
                )
            except Exception as e:
                logger.debug(
                    f"[event_analyst] institutional_ownership 주입 실패: {type(e).__name__}"
                )

        return result

    # ──────────────────────────────────────────
    # 데이터 수집 (Week C 모듈 동원)
    # ──────────────────────────────────────────

    async def _collect_data_bundle(self, inp: EventAnalystInput) -> dict[str, Any]:
        """Week C 모듈을 호출하여 user message 구성용 데이터 묶음 생성.

        실패는 graceful — 일부 모듈이 실패해도 다른 모듈은 정상 진행.
        반환 dict에 각 항목별 available/error 표시.
        """
        from utils.data_collectors.event_metadata import (
            find_ipos_for_secondary,
            get_event_meta,
        )

        bundle: dict[str, Any] = {
            "ticker": inp.ticker,
            "market": inp.market,
            "event_type": inp.event_type,
            "event_target": inp.event_target,
            "primary_ticker": inp.primary_ticker,
        }

        market = inp.market or ("KR" if is_kr_ticker(inp.ticker) else "US")
        bundle["market"] = market

        # 1) 옵션 시그널 (미국 종목만 의미 있음)
        if market == "US":
            bundle["options"] = self._safe_call(
                "options_signals",
                self._fetch_options,
                inp.ticker,
            )
        else:
            bundle["options"] = {
                "available": False,
                "reason": "한국 개별 종목 옵션 데이터 미수집 (코스피200/VKOSPI는 시장 보조)",
            }

        # 2) 매크로 이벤트 메타 (event_type이 매크로 카테고리면)
        if inp.event_type:
            macro_meta = get_event_meta(inp.event_type.upper())
            if macro_meta:
                bundle["macro_meta"] = macro_meta

        # 3) IPO 2차 수혜 매핑 (event_type=ipo_secondary or primary_ticker 명시)
        if inp.event_type == "ipo_secondary" or inp.primary_ticker:
            ipo_matches = find_ipos_for_secondary(inp.ticker)
            if ipo_matches:
                bundle["ipo_secondary"] = ipo_matches

        # 4) 한국 공매도 (KR 종목)
        if market == "KR":
            bundle["short_selling"] = self._safe_call(
                "short_selling",
                self._fetch_short_selling,
                inp.ticker,
            )

        # 5) yfinance 실적/배당 (US 종목)
        if market == "US":
            bundle["yfinance_events"] = self._safe_call(
                "yfinance_events",
                self._fetch_yfinance_events,
                inp.ticker,
            )

        # 5b) 기관 보유 스냅샷 (US 종목, 정보 제공용 — LLM 미경유 passthrough)
        if market == "US":
            bundle["institutional_ownership"] = self._safe_call(
                "institutional_ownership",
                self._fetch_institutional_ownership,
                inp.ticker,
            )

        # 6) LLM 유사 이벤트 추론 (event_target과 primary 모두 있을 때)
        if inp.event_target and (inp.primary_ticker or inp.event_type):
            bundle["llm_similar_events"] = await self._safe_async_call(
                "llm_similar_events",
                self._fetch_similar_events,
                inp,
            )

        return bundle

    @staticmethod
    def _safe_call(name: str, fn, *args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            logger.warning(
                f"[event_analyst] {name} 수집 실패: {type(e).__name__}: {str(e)[:120]}"
            )
            return {"available": False, "error": f"{type(e).__name__}"}

    @staticmethod
    async def _safe_async_call(name: str, fn, *args, **kwargs):
        try:
            return await fn(*args, **kwargs)
        except Exception as e:
            logger.warning(
                f"[event_analyst] {name} 수집 실패: {type(e).__name__}: {str(e)[:120]}"
            )
            return {"available": False, "error": f"{type(e).__name__}"}

    def _fetch_options(self, ticker: str):
        from utils.data_collectors.options_signals import calculate_options_signals

        return calculate_options_signals(ticker)

    def _fetch_short_selling(self, ticker: str):
        # KoreaShortSellingAnalyzer.analyze_short_signals — db 접근 lazy.
        from utils.data_collectors.short_selling import KoreaShortSellingAnalyzer

        analyzer = KoreaShortSellingAnalyzer()
        return analyzer.analyze_short_signals(ticker)

    def _fetch_yfinance_events(self, ticker: str):
        from utils.data_collectors.yfinance_event_collector import (
            fetch_yfinance_events,
        )

        return fetch_yfinance_events(ticker)

    def _fetch_institutional_ownership(self, ticker: str):
        from utils.data_collectors.us_ownership import (
            fetch_us_institutional_ownership,
        )

        return fetch_us_institutional_ownership(ticker)

    async def _fetch_similar_events(self, inp: EventAnalystInput):
        from utils.data_collectors.event_inference_cache import (
            get_similar_events_cached,
        )

        return await get_similar_events_cached(
            event_type=inp.event_type or "unknown",
            event_target=inp.event_target or inp.ticker,
            primary=inp.primary_ticker or "",
            secondary_ticker=inp.ticker,
        )

    # ──────────────────────────────────────────
    # User message 구성
    # ──────────────────────────────────────────

    def _build_user_message(
        self, inp: EventAnalystInput, bundle: dict[str, Any]
    ) -> str:
        lines: list[str] = []
        lines.append(f"# 분석 대상\n티커: {inp.ticker} (시장: {bundle['market']})")
        if inp.event_type:
            lines.append(f"이벤트 타입: {inp.event_type}")
        if inp.event_target:
            lines.append(f"이벤트 대상: {inp.event_target}")
        if inp.primary_ticker:
            lines.append(f"1차 수혜: {inp.primary_ticker} (분석 대상은 2차 수혜)")

        # 옵션 시그널
        opt = bundle.get("options", {})
        if opt.get("available"):
            lines.append("\n# 옵션 시장 신호 (yfinance)")
            lines.append(f"- 만기일: {opt.get('expiration', 'N/A')}")
            lines.append(f"- Put/Call(거래량): {opt.get('put_call_ratio_volume')}")
            lines.append(f"- Put/Call(미결제): {opt.get('put_call_ratio_oi')}")
            lines.append(f"- ATM IV: {opt.get('atm_iv_pct')}%")
            lines.append(f"- 해석: {opt.get('interpretation', '')}")
        else:
            lines.append(f"\n# 옵션 시장 신호: 사용 불가 ({opt.get('reason', opt.get('error', ''))})")

        # 한국 공매도
        ss = bundle.get("short_selling")
        if ss:
            if ss.get("available", True) is False:
                lines.append(f"\n# 한국 공매도: 데이터 없음 ({ss.get('error', ss.get('reason', ''))})")
            else:
                lines.append("\n# 한국 공매도 (pykrx)")
                # short_signals 결과는 dict 형태로 가정 — 안전 추출
                for k in ("balance_30d_change_pct", "ratio_vs_market_cap", "policy_status", "interpretation"):
                    v = ss.get(k)
                    if v is not None:
                        lines.append(f"- {k}: {v}")

        # yfinance 실적/배당
        yf = bundle.get("yfinance_events")
        if yf:
            ne = yf.get("next_earnings")
            nd = yf.get("next_ex_dividend")
            if ne or nd:
                lines.append("\n# yfinance 실적/배당")
                if ne:
                    lines.append(f"- 다음 실적 발표: {ne.get('date')} (eps_est={ne.get('eps_estimate')})")
                if nd:
                    lines.append(f"- 다음 배당락: {nd.get('ex_date')} (금액={nd.get('amount')})")
                # 최근 실적 surprise (3건)
                eds = yf.get("earnings_dates", [])[:3]
                for ed in eds:
                    if ed.get("eps_reported") is not None:
                        lines.append(
                            f"- 과거 실적 {ed['date']}: 예상 {ed.get('eps_estimate')} → "
                            f"실제 {ed.get('eps_reported')} (서프라이즈 {ed.get('surprise_pct')}%)"
                        )

        # 매크로 메타
        mm = bundle.get("macro_meta")
        if mm:
            lines.append("\n# 매크로 이벤트 통계 메타")
            win = mm.get("typical_volatility_window", {})
            lines.append(
                f"- 통상 변동성 윈도우: {win.get('before', 'N/A')} ~ {win.get('after', 'N/A')}"
            )
            avg = mm.get("historical_avg_abs_return_pct")
            if avg is not None:
                lines.append(f"- 윈도우 평균 절댓값 수익률: {avg}% (S&P500/KOSPI 기준 추정)")
            std = mm.get("historical_std_dev_pct")
            if std is not None:
                lines.append(f"- 표준편차: {std}%")
            lines.append("⚠️ 위 통계는 추정값으로, 외부 검증 권장.")

        # IPO 2차 수혜 매핑
        ipos = bundle.get("ipo_secondary")
        if ipos:
            lines.append("\n# IPO 2차 수혜 큐레이션 (관리자 가설)")
            for ip in ipos:
                lines.append(
                    f"- {ip.get('company')} (예상: {ip.get('expected_market')} "
                    f"{ip.get('expected_date_range')}, certainty={ip.get('certainty_score')}/10): "
                    f"{ip.get('rationale')}"
                )

        # LLM 유사 이벤트
        sim = bundle.get("llm_similar_events")
        if sim and sim.get("comparable_events"):
            lines.append("\n# LLM 유사 이벤트 추론 (event_inference_cache)")
            lines.append(f"- 표본 수: {sim.get('sample_size')}")
            lines.append(f"- 신뢰도: {sim.get('sample_reliability', '')}")
            lines.append(f"- ⚠️ {sim.get('fabrication_warning', '외부 검증 권장')}")
            for ev in sim["comparable_events"][:5]:
                lines.append(
                    f"  · {ev.get('event', '?')} "
                    f"(secondary={ev.get('secondary')}, "
                    f"return={ev.get('secondary_d_minus_60_to_d_day_return_pct')}, "
                    f"confidence={ev.get('data_confidence')})"
                )

        lines.append(
            "\n# 출력 지시\n"
            "위 데이터로 시스템 프롬프트 JSON 스키마에 맞춰 응답하세요. "
            "4차원 확실성 점수(source/timing/probability/impact)를 각 0~10으로 산출하고, "
            "scenario_analysis(bullish/base/bearish 3개)·reference_observation_zones·"
            "summary_neutral을 **반드시** 채우세요 (생략 시 빈 카드 노출). "
            "표본 < 5건이면 historical_statistics에서 통계 미제시(정성만), "
            "5~9면 '표본 부족' 명시. 수치를 새로 만들지 말고 위 입력 그대로 사용."
        )
        return "\n".join(lines)

    # ──────────────────────────────────────────
    # 보조 헬퍼
    # ──────────────────────────────────────────

    @staticmethod
    def _classify_sample_reliability(sample_n: int) -> str:
        if sample_n < 5:
            return "❌ 통계 미제시"
        if sample_n < 10:
            return "⚠️ 표본 부족"
        return "✅ 통계 신뢰 가능"

    def _refused_response(
        self, inp: EventAnalystInput, bundle: dict[str, Any]
    ) -> EventAnalystResult:
        """확실성 0~2점 — 분석 거부 형태의 최소 응답."""
        market = bundle.get("market", "KR")
        return EventAnalystResult(
            ticker=inp.ticker,
            market=market,
            event_summary=EventSummary(
                event_type=inp.event_type or "unknown",
                event_target=inp.event_target or "",
                d_day="",
                certainty_breakdown=CertaintyBreakdown(
                    source=0, timing=0, probability=0, impact=0,
                    final_score=0.0, mode="Refused",
                ),
                badge="🔴 분석 거부",
            ),
            impact_mapping=ImpactMapping(),
            volume_supply_analysis=SignalBlock(),
            options_signals=SignalBlock(),
            credit_short_signals=SignalBlock(),
            historical_statistics=HistoricalStatistics(
                fabrication_warning="확실성 점수가 너무 낮아 통계 분석을 수행하지 않았습니다."
            ),
            reference_observation_zones=ReferenceZones(),
            scenario_analysis=ScenarioAnalysis(
                bullish_case=ScenarioCase(),
                base_case=ScenarioCase(),
                bearish_case=ScenarioCase(),
            ),
            key_risks=["확실성 점수 부족 — 분석 수행 불가"],
            what_to_watch=["이벤트 확정/일정 공식화 여부"],
            summary_neutral=(
                f"{inp.ticker}의 이벤트는 확실성 점수가 분석 임계 미달로, "
                "통계 분석을 수행하지 않았습니다. 공식 일정 확정 후 재분석 권장."
            ),
            persona="event",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
