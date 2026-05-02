"""Korean Specialist Agent — 한국 시장 구조적 특수성 페르소나.

상세 스펙: docs/personas/korean.md, docs/data_infra/korea_market.md
WEEK_D.md Day 3 산출물.

핵심: Week A 데이터 인프라를 모두 호출.
  - korea_supply.py (외국인/기관 수급)
  - chaebol_groups.json (재벌 그룹 매핑)
  - holding_company.py (지주사 NAV)
  - dart_buyback.py (자사주 정책)
  - valueup_index.py (밸류업 편입)
  - governance_score.py (5변수 거버넌스)
  - short_selling.py (공매도)

⚠️ 종목이 한국이 아니면 거부 응답 (페르소나 적용 불가).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from loguru import logger
from pydantic import BaseModel, Field

from agents.base import BaseAgent
from agents.event_analyst import is_kr_ticker
from utils.claude_client import MODEL_SONNET


# ──────────────────────────────────────────────
# 입출력 스키마
# ──────────────────────────────────────────────


class KoreanSpecialistInput(BaseModel):
    ticker: str
    main_theme: Optional[str] = None  # 사용자가 명시한 테마 (옵션)


class KoreaSpecificScore(BaseModel):
    foreign_supply: float = 0.0
    governance: float = 0.0
    valueup_alignment: float = 0.0
    theme_position: float = 0.0
    policy_friendliness: float = 0.0
    weighted_total: float = 0.0
    interpretation: str = ""


class KoreanSpecialistResult(BaseModel):
    korea_specific_analysis: dict[str, Any] = Field(default_factory=dict)
    foreign_supply_analysis: dict[str, Any] = Field(default_factory=dict)
    chaebol_structure_analysis: dict[str, Any] = Field(default_factory=dict)
    value_up_analysis: dict[str, Any] = Field(default_factory=dict)
    theme_cycle_analysis: dict[str, Any] = Field(default_factory=dict)
    policy_risk_analysis: dict[str, Any] = Field(default_factory=dict)
    korea_specific_score: KoreaSpecificScore
    what_to_watch_korea_specific: list[str] = Field(default_factory=list)
    summary_neutral: str = ""
    persona: str = "korean"
    timestamp: str = ""


# ──────────────────────────────────────────────
# 가중 평균 (5변수 → weighted_total)
# ──────────────────────────────────────────────

# 외국인 수급(35%), 거버넌스(20%), 밸류업(20%), 테마(15%), 정책(10%) — 상관 무관 가중.
WEIGHTS = {
    "foreign_supply": 0.35,
    "governance": 0.20,
    "valueup_alignment": 0.20,
    "theme_position": 0.15,
    "policy_friendliness": 0.10,
}


def calculate_weighted_total(score: KoreaSpecificScore) -> float:
    total = (
        score.foreign_supply * WEIGHTS["foreign_supply"]
        + score.governance * WEIGHTS["governance"]
        + score.valueup_alignment * WEIGHTS["valueup_alignment"]
        + score.theme_position * WEIGHTS["theme_position"]
        + score.policy_friendliness * WEIGHTS["policy_friendliness"]
    )
    return round(total, 2)


# ──────────────────────────────────────────────
# 시스템 프롬프트 로딩
# ──────────────────────────────────────────────


_PERSONAS_DIR = Path(__file__).resolve().parent.parent / "personas"


def _load_korean_persona() -> str:
    path = _PERSONAS_DIR / "korean.md"
    if not path.exists():
        logger.error(f"korean 페르소나 파일 누락: {path}")
        return ""
    return path.read_text(encoding="utf-8")


# ──────────────────────────────────────────────
# Korean Specialist Agent
# ──────────────────────────────────────────────


class KoreanSpecialistAgent(BaseAgent):
    def __init__(self, claude=None):
        system = _load_korean_persona()
        super().__init__(
            agent_name="korean_specialist",
            model=MODEL_SONNET,
            system_prompt=system,
            claude=claude,
        )

    async def run(
        self, input_data: KoreanSpecialistInput, uid: str = ""
    ) -> KoreanSpecialistResult:
        ticker = str(input_data.ticker).zfill(6)
        if not is_kr_ticker(ticker):
            return self._refused_non_korean(ticker)

        # 1) Week A 데이터 수집
        bundle = self._collect_korea_bundle(ticker)

        # 2) user message + Claude
        user_message = self._build_user_message(input_data, bundle)
        result, _raw = await self.call_claude_json(
            user_message=user_message,
            schema=KoreanSpecialistResult,
            max_tokens=2200,
            uid=uid,
        )

        # 3) 메타 보정
        result.persona = "korean"
        result.timestamp = datetime.now(timezone.utc).isoformat()
        # ticker는 한국 6자리 강제
        if "ticker" not in result.korea_specific_analysis or not result.korea_specific_analysis["ticker"]:
            result.korea_specific_analysis["ticker"] = ticker

        # 4) weighted_total 정량 재계산 (가중치 강제)
        s = result.korea_specific_score
        s.weighted_total = calculate_weighted_total(s)

        # 5) 거버넌스 자체 평가 disclaimer 강제 첨부 (Claude 누락 대비)
        chaebol = result.chaebol_structure_analysis
        if "governance_disclaimer" not in chaebol or not chaebol["governance_disclaimer"]:
            chaebol["governance_disclaimer"] = (
                "거버넌스 점수는 5변수 정량 자체 평가이며, "
                "외부 평가기관(KCGS 등) 의견과 다를 수 있습니다."
            )

        # 6) summary_neutral 단정어 후처리
        filtered, found = self.filter_forbidden(result.summary_neutral)
        if found:
            logger.warning(f"[korean_specialist] summary_neutral 단정어 필터링: {found}")
            result.summary_neutral = filtered

        return result

    # ──────────────────────────────────────────
    # 데이터 수집 (Week A 모듈 동원)
    # ──────────────────────────────────────────

    def _collect_korea_bundle(self, ticker: str) -> dict[str, Any]:
        """Week A 6 모듈을 호출하여 user message 구성용 dict 생성.

        실패는 graceful — 모든 모듈이 부분 실패해도 응답 생성 가능.
        """
        bundle: dict[str, Any] = {"ticker": ticker}

        # 1) 밸류업 인덱스 편입
        bundle["valueup"] = self._safe_call(
            "valueup", self._fetch_valueup, ticker
        )

        # 2) 재벌 그룹 매핑
        bundle["chaebol"] = self._safe_call(
            "chaebol", self._fetch_chaebol, ticker
        )

        # 3) 거버넌스 자체 평가 (5변수)
        bundle["governance"] = self._safe_call(
            "governance", self._fetch_governance, ticker
        )

        # 4) 자사주 정책 이력 (3년)
        bundle["buyback"] = self._safe_call(
            "buyback", self._fetch_buyback_summary, ticker
        )

        # 5) 공매도 30일 추이
        bundle["short_selling"] = self._safe_call(
            "short_selling", self._fetch_short_selling, ticker
        )

        # 6) 외국인/기관 수급 (Firestore historical_supply — Week A Day 1~2)
        bundle["supply"] = self._safe_call(
            "supply", self._fetch_supply, ticker
        )

        return bundle

    @staticmethod
    def _safe_call(name: str, fn, *args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            logger.warning(
                f"[korean_specialist] {name} 수집 실패: "
                f"{type(e).__name__}: {str(e)[:120]}"
            )
            return {"available": False, "error": f"{type(e).__name__}"}

    def _fetch_valueup(self, ticker: str):
        from utils.data_collectors.valueup_index import is_in_valueup_index

        return is_in_valueup_index(ticker)

    def _fetch_chaebol(self, ticker: str):
        from utils.data_collectors.governance_score import find_chaebol_group

        return find_chaebol_group(ticker) or {"is_chaebol": False}

    def _fetch_governance(self, ticker: str):
        from utils.data_collectors.governance_score import KoreaGovernanceAnalyzer

        return KoreaGovernanceAnalyzer().calculate_governance_score(ticker)

    def _fetch_buyback_summary(self, ticker: str):
        # DartClient를 직접 만들 수 없으면(API 키 누락 등) graceful 처리됨
        from utils.data_collectors.dart_buyback import DartBuybackCollector
        from utils.data_collectors.dart_client import DartClient

        client = DartClient()
        collector = DartBuybackCollector(client=client)
        return collector.summarize_buyback_history(ticker, years=3)

    def _fetch_short_selling(self, ticker: str):
        from utils.data_collectors.short_selling import KoreaShortSellingAnalyzer

        return KoreaShortSellingAnalyzer().analyze_short_signals(ticker, days=30)

    def _fetch_supply(self, ticker: str):
        # historical_supply Firestore 컬렉션 — Week A Day 1~2.
        # interpret_supply_signal 같은 통합 메서드는 없으므로 3개 호출 후 병합.
        from utils.data_collectors.korea_supply import KoreaSupplyAnalyzer

        analyzer = KoreaSupplyAnalyzer()
        consec = analyzer.get_consecutive_buy_days(ticker, days_back=30)
        net30 = analyzer.get_30d_net_buy(ticker)
        dual = analyzer.get_dual_buy_signal(ticker, days_back=30)
        return {
            "available": True,
            "foreign_consecutive_buy_days": consec,
            "foreign_net_buy_30d": net30,
            "institution_dual_buy_days": dual.get("days", 0),
            "institution_dual_buy_ratio": dual.get("ratio", 0.0),
        }

    # ──────────────────────────────────────────
    # User message 구성
    # ──────────────────────────────────────────

    def _build_user_message(
        self, inp: KoreanSpecialistInput, bundle: dict[str, Any]
    ) -> str:
        ticker = bundle["ticker"]
        lines: list[str] = [f"# 분석 대상\n티커: {ticker}"]
        if inp.main_theme:
            lines.append(f"테마(사용자 입력): {inp.main_theme}")

        # 외국인/기관 수급
        supply = bundle.get("supply", {})
        if supply and not supply.get("error"):
            lines.append("\n# Step 1. 외국인/기관 수급 (korea_supply)")
            for k in (
                "foreign_consecutive_buy_days",
                "foreign_net_buy_30d",
                "institution_dual_buy_days",
                "institution_dual_buy_ratio",
            ):
                v = supply.get(k)
                if v is not None:
                    lines.append(f"- {k}: {v}")
        else:
            lines.append(
                f"\n# Step 1. 외국인/기관 수급: 데이터 부재 ({supply.get('error', supply.get('reason', ''))})"
            )

        # 재벌 + 지주사 + 거버넌스
        chaebol = bundle.get("chaebol", {})
        gov = bundle.get("governance", {})
        lines.append("\n# Step 2. 재벌 구조 + 거버넌스")
        if chaebol.get("is_chaebol"):
            lines.append(
                f"- 재벌 그룹: {chaebol.get('group_name', 'N/A')} "
                f"(공정위 분류 {chaebol.get('rank', 'N/A')}위)"
            )
        else:
            lines.append("- 재벌 그룹: 비재벌 (또는 매핑 없음)")
        if gov and not gov.get("error"):
            lines.append(
                f"- 거버넌스 점수 (자체 5변수 모델): {gov.get('total_score', 'N/A')}/10 "
                f"(등급: {gov.get('grade', 'N/A')})"
            )
            lines.append(f"- 평가 method: {gov.get('method', '5변수 정량')}")
            lines.append(
                f"- ⚠️ {gov.get('disclaimer', '외부 평가기관 의견과 다를 수 있음')}"
            )

        # 밸류업 부합도
        vu = bundle.get("valueup", {})
        bb = bundle.get("buyback", {})
        lines.append("\n# Step 3. 밸류업 부합도")
        if vu and not vu.get("error"):
            included = vu.get("included", False)
            lines.append(f"- 밸류업 인덱스 편입: {'YES' if included else 'NO'}")
            if vu.get("note"):
                lines.append(f"  · {vu['note']}")
        if bb and not bb.get("error"):
            lines.append(
                f"- 자사주 3년 통계: total={bb.get('total_disclosures', 0)}건, "
                f"by_action={bb.get('by_action', {})}"
            )
            if bb.get("has_burn"):
                lines.append("  · 소각 이력 있음 (★★★ 강한 주주환원)")

        # 공매도 / 정책 리스크
        ss = bundle.get("short_selling", {})
        lines.append("\n# Step 5. 정책 리스크 (공매도 등)")
        if ss and not ss.get("error"):
            for k in (
                "current_short_ratio_pct",
                "ratio_classification",
                "interpretation",
                "policy_status",
            ):
                v = ss.get(k)
                if v is not None:
                    lines.append(f"- {k}: {v}")

        lines.append(
            "\n# 출력 지시\n"
            "위 데이터로 시스템 프롬프트 JSON 스키마에 맞춰 응답하세요. "
            "각 도메인 점수(0~10)를 정량적으로 매기고, weighted_total은 시스템이 후처리로 재계산하니 비워두거나 추정만 적으세요. "
            "단정어 사용 금지 — '관찰', '통상 패턴' 등 중립 표현만. "
            "거버넌스는 자체 평가임을 명시 (governance_disclaimer 필드 채울 것). "
            "수치는 위 입력 그대로 사용, 새 수치 만들지 마세요."
        )
        return "\n".join(lines)

    # ──────────────────────────────────────────
    # 비한국 종목 거부
    # ──────────────────────────────────────────

    def _refused_non_korean(self, ticker: str) -> KoreanSpecialistResult:
        return KoreanSpecialistResult(
            korea_specific_analysis={
                "ticker": ticker,
                "note": "한국 종목이 아니므로 Korean Specialist 페르소나 적용 불가",
            },
            korea_specific_score=KoreaSpecificScore(),
            summary_neutral=(
                f"{ticker}는 한국 종목이 아닙니다. "
                "Korean Specialist는 6자리 KOSPI/KOSDAQ 종목코드만 지원합니다."
            ),
            persona="korean",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
