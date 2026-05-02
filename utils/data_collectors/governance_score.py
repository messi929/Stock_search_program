"""한국 종목 자체 거버넌스 점수 (5변수 정량 모델).

WEEK_A.md Day 5 산출물.

⚠️ 외부 평가기관(KCGS 등) 미참조 — 자체 평가 모델.
모든 응답에 method/disclaimer 명시 (Korean Specialist 페르소나에서 그대로 노출).

5개 변수 (각 0~2점, 합계 0~10):
  1. buyback_policy           — buyback_history (Day 4) 활용
  2. dividend_consistency     — Firestore stocks/{ticker}.div_yield + div_years
  3. circular_ownership       — chaebol_groups.json (Day 3) 활용
  4. controlling_shareholder  — DART 분기보고서 미연동 (estimated, 향후 보완)
  5. audit_opinion            — DART 감사보고서 미연동 (estimated, 향후 보완)

데이터 완전성 표시 (`data_completeness` 필드):
  - "verified": 실제 수집된 데이터 기반
  - "estimated": 추정값 (보수적 기본 점수)
  - "unavailable": 데이터 없음 (0점)

등급 변환: S(10) > A+(9) > A(8) > B+(7) > B(6) > C(4-5) > D(0-3)
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from loguru import logger


# Day 3 데이터
CHAEBOL_DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "chaebol_groups.json"


# ──────────────────────────────────────────────
# 등급 변환
# ──────────────────────────────────────────────


def score_to_grade(score: int) -> str:
    """0~10점 → 등급 라벨."""
    if score >= 10:
        return "S"
    elif score == 9:
        return "A+"
    elif score == 8:
        return "A"
    elif score == 7:
        return "B+"
    elif score == 6:
        return "B"
    elif score >= 4:
        return "C"
    else:
        return "D"


# ──────────────────────────────────────────────
# 재벌 그룹 데이터 헬퍼 (chaebol_groups.json)
# ──────────────────────────────────────────────


_chaebol_cache: dict[str, Any] | None = None


def _load_chaebol_data() -> dict[str, Any]:
    """data/chaebol_groups.json 로드 + 캐시."""
    global _chaebol_cache
    if _chaebol_cache is not None:
        return _chaebol_cache

    if not CHAEBOL_DATA_FILE.exists():
        logger.warning(f"chaebol_groups.json 미존재: {CHAEBOL_DATA_FILE}")
        _chaebol_cache = {}
        return _chaebol_cache

    try:
        with open(CHAEBOL_DATA_FILE, encoding="utf-8") as f:
            _chaebol_cache = json.load(f)
    except Exception as e:
        logger.error(f"chaebol_groups.json 파싱 실패: {e}")
        _chaebol_cache = {}

    return _chaebol_cache


def reset_chaebol_cache() -> None:
    """테스트용."""
    global _chaebol_cache
    _chaebol_cache = None


def find_chaebol_group(ticker: str) -> dict[str, Any] | None:
    """종목이 속한 재벌 그룹 찾기. 미소속 시 None."""
    ticker = str(ticker).zfill(6)
    data = _load_chaebol_data()
    for group_name, info in data.items():
        if group_name.startswith("_"):
            continue
        # holding_company 또는 core_companies에 ticker 매칭
        if info.get("holding_company") == ticker:
            return {**info, "group_name": group_name, "membership_role": "holding"}
        for c in info.get("core_companies") or []:
            if c.get("ticker") == ticker:
                return {**info, "group_name": group_name, "membership_role": "subsidiary"}
    return None


# ──────────────────────────────────────────────
# 5개 변수 평가 함수 (모듈 레벨)
# ──────────────────────────────────────────────


def evaluate_buyback_policy(buyback_summary: dict[str, Any] | None) -> dict[str, Any]:
    """자사주 정책 점수 (0~2).

    Args:
        buyback_summary: DartBuybackCollector.summarize_buyback_history 결과 dict.
                         None이면 데이터 없음 (0점).
    """
    if buyback_summary is None:
        return {
            "score": 0,
            "completeness": "unavailable",
            "reason": "buyback_history 데이터 없음",
        }

    if buyback_summary.get("has_burn"):
        return {
            "score": 2,
            "completeness": "verified",
            "reason": f"3년 내 주식소각 {buyback_summary.get('by_action', {}).get('burn', 0)}건",
        }

    by_action = buyback_summary.get("by_action") or {}
    bought = by_action.get("buy_decision", 0) + by_action.get("buy_complete", 0)
    if bought > 0:
        return {
            "score": 1,
            "completeness": "verified",
            "reason": f"3년 내 자사주 취득 {bought}건 (소각 없음)",
        }

    return {
        "score": 0,
        "completeness": "verified",
        "reason": "3년 내 자사주 정책 활동 없음",
    }


def evaluate_dividend(stock_data: dict[str, Any] | None) -> dict[str, Any]:
    """배당 일관성 점수 (0~2).

    Args:
        stock_data: Firestore stocks/{ticker}.to_dict() 결과.
                    div_yield, div_years (5년 연속 지급 횟수) 활용.
    """
    if stock_data is None:
        return {
            "score": 0,
            "completeness": "unavailable",
            "reason": "stocks 데이터 없음",
        }

    div_yield = float(stock_data.get("div_yield") or 0)
    div_years = int(stock_data.get("div_years") or 0)
    div_growth = float(stock_data.get("div_growth") or 0)

    if div_yield <= 0:
        return {
            "score": 0,
            "completeness": "verified",
            "reason": "최근 배당 없음 (div_yield=0)",
        }

    # 5년 연속 + 증가 → 2점
    if div_years >= 5 and div_growth > 0:
        return {
            "score": 2,
            "completeness": "verified",
            "reason": f"5년 연속 배당 + 증가 추세 (div_yield={div_yield:.2f}%, growth={div_growth:.1f}%)",
        }
    # 5년 연속 → 1점
    if div_years >= 5:
        return {
            "score": 1,
            "completeness": "verified",
            "reason": f"5년 연속 배당 (성장 정체, div_yield={div_yield:.2f}%)",
        }
    # 배당은 있으나 연속성/이력 부족
    if div_years > 0:
        return {
            "score": 1,
            "completeness": "partial",
            "reason": f"{div_years}년 배당 (5년 미만)",
        }
    return {
        "score": 1,
        "completeness": "partial",
        "reason": f"당해 배당 있음 (div_yield={div_yield:.2f}%, 이력 데이터 부족)",
    }


def evaluate_circular_ownership(ticker: str) -> dict[str, Any]:
    """순환출자 점수 (0~2).

    chaebol_groups.json 활용:
      - 재벌 + 순환출자 해소 → 2점 verified
      - 재벌 + 순환출자 미해소 → 0점 verified
      - chaebol 데이터 미커버 (공정위 88개 중 11~88위 또는 비재벌) → estimated 1점 (중립)
        ※ 10대 외 종목을 "비재벌 가정 → 2점 만점"으로 처리하면 SK/롯데/한진 등 누락
          그룹 종목이 부당하게 만점 받음. 보수적으로 1점(중립)으로 평가.
    """
    group = find_chaebol_group(ticker)
    if group is None:
        return {
            "score": 1,
            "completeness": "estimated",
            "reason": "chaebol_groups.json 미커버 — 10대 외 그룹/비재벌 미평가 (보수적 중립 1점)",
        }

    if group.get("circular_ownership_resolved"):
        return {
            "score": 2,
            "completeness": "verified",
            "reason": f"{group['group_name']} 그룹 — 순환출자 해소 완료",
        }

    return {
        "score": 0,
        "completeness": "verified",
        "reason": f"{group['group_name']} 그룹 — 순환출자 잔존",
    }


def evaluate_controlling_shareholder(ticker: str) -> dict[str, Any]:
    """지배주주 지분율 점수 (0~2). DART 분기보고서 미연동 → estimated.

    적정 범위: 15~40% (너무 낮으면 적대적 인수 위험, 너무 높으면 소액주주 권리 침해 위험).
    """
    return {
        "score": 1,
        "completeness": "estimated",
        "reason": "DART 분기보고서 지배주주 데이터 미연동 — 보수적 기본 1점 (향후 보완 예정)",
    }


def evaluate_audit_opinion(ticker: str) -> dict[str, Any]:
    """감사 의견 이력 점수 (0~2). DART 감사보고서 미연동 → estimated.

    상장 유지 종목은 대부분 '적정' 의견 → 보수적 2점 가정.
    한정/부적정/의견거절 발생 시 별도 alert 시스템에서 감점 처리.
    """
    return {
        "score": 2,
        "completeness": "estimated",
        "reason": "DART 감사보고서 미연동 — 상장 유지 가정으로 기본 2점 (향후 보완 예정)",
    }


# ──────────────────────────────────────────────
# 종합 거버넌스 점수 계산 (Analyzer 클래스)
# ──────────────────────────────────────────────


class KoreaGovernanceAnalyzer:
    """5변수 거버넌스 점수 자체 평가.

    Args:
        db: Firestore 클라이언트 (None 시 lazy import) — stocks 컬렉션 조회.
        buyback_collector: DartBuybackCollector — buyback_history 요약 활용.
                          None이면 매번 새 인스턴스 생성 (의존성 주입 우선).
    """

    METHOD_LABEL = "자체 평가 (5변수 정량 모델)"
    DISCLAIMER = "외부 평가기관(KCGS 등) 의견과 다를 수 있습니다."
    EXTERNAL_REFERENCE = "KCGS 등급 미참조"

    def __init__(self, db: Any | None = None, buyback_collector: Any | None = None) -> None:
        self._db = db
        self._buyback_collector = buyback_collector

    @property
    def db(self) -> Any:
        if self._db is None:
            from screener.db.firebase_client import get_db

            self._db = get_db()
        return self._db

    @property
    def buyback_collector(self) -> Any:
        if self._buyback_collector is None:
            from utils.data_collectors.dart_buyback import DartBuybackCollector
            from utils.data_collectors.dart_client import DartClient

            self._buyback_collector = DartBuybackCollector(client=DartClient(), db=self._db)
        return self._buyback_collector

    # ──────────────────────────────────────────────
    # Firestore 조회 헬퍼
    # ──────────────────────────────────────────────

    def get_stock_data(self, ticker: str) -> dict[str, Any] | None:
        """stocks/{ticker} 문서 dict."""
        try:
            doc = self.db.collection("stocks").document(str(ticker).zfill(6)).get()
        except Exception as e:
            logger.warning(
                f"stocks 조회 실패 (ticker={ticker}): {type(e).__name__}: {str(e)[:120]}"
            )
            return None
        if not getattr(doc, "exists", False):
            return None
        return doc.to_dict() or {}

    # ──────────────────────────────────────────────
    # 종합 평가
    # ──────────────────────────────────────────────

    def calculate_governance_score(self, ticker: str) -> dict[str, Any]:
        """종목별 거버넌스 점수 (0~10) + 등급 + 5변수 분해 + 메타.

        Returns:
            {
                "ticker": "005930",
                "total_score": 8,
                "grade": "A",
                "components": {
                    "buyback_policy": {"score": 2, "completeness": "verified", "reason": "..."},
                    "dividend_consistency": {...},
                    "circular_ownership": {...},
                    "controlling_shareholder_ratio": {...},
                    "audit_opinion_history": {...},
                },
                "data_completeness_summary": {"verified": 3, "estimated": 2, "unavailable": 0},
                "rationale": "...",
                "method": "자체 평가 (5변수 정량 모델)",
                "disclaimer": "외부 평가기관(KCGS 등) 의견과 다를 수 있습니다.",
                "external_reference": "KCGS 등급 미참조",
                "computed_at": "...",
            }
        """
        ticker = str(ticker).zfill(6)

        # 1) buyback (Day 4 데이터 재사용)
        try:
            buyback_summary = self.buyback_collector.summarize_buyback_history(ticker, years=3)
        except Exception as e:
            logger.warning(f"buyback summarize 실패 ({ticker}): {e}")
            buyback_summary = None

        # 2) dividend
        stock_data = self.get_stock_data(ticker)

        components = {
            "buyback_policy": evaluate_buyback_policy(buyback_summary),
            "dividend_consistency": evaluate_dividend(stock_data),
            "circular_ownership": evaluate_circular_ownership(ticker),
            "controlling_shareholder_ratio": evaluate_controlling_shareholder(ticker),
            "audit_opinion_history": evaluate_audit_opinion(ticker),
        }

        # verified vs estimated 점수 분리 (페르소나가 변별력 가지도록)
        # estimated 변수는 모든 종목에 동일 보너스 → total_score만 보면 변별력 약화
        verified_score = sum(
            int(c["score"]) for c in components.values()
            if c.get("completeness") in ("verified", "partial")
        )
        estimated_score = sum(
            int(c["score"]) for c in components.values()
            if c.get("completeness") == "estimated"
        )
        verified_max = sum(
            2 for c in components.values()
            if c.get("completeness") in ("verified", "partial")
        )
        total_score = verified_score + estimated_score  # 하위 호환

        # 데이터 완전성 집계
        completeness_summary = {"verified": 0, "estimated": 0, "partial": 0, "unavailable": 0}
        for c in components.values():
            key = c.get("completeness", "unknown")
            completeness_summary[key] = completeness_summary.get(key, 0) + 1

        # rationale (간략 요약)
        weak_spots = [k for k, v in components.items() if v["score"] == 0]
        rationale_parts = [
            f"총점 {total_score}/10 ({score_to_grade(total_score)})",
            f"검증 점수 {verified_score}/{verified_max} (실데이터)",
        ]
        if weak_spots:
            rationale_parts.append(f"약점: {', '.join(weak_spots)}")
        if completeness_summary["estimated"] >= 2:
            rationale_parts.append(
                f"DART 미연동 변수 {completeness_summary['estimated']}개 (보완 필요, 점수에 보수 가정 포함)"
            )

        # disclaimer를 rationale 앞에 prepend하여 페르소나 출력 시 누락 방지
        disclaimer_inline = f"[자체평가 — {self.DISCLAIMER}] "

        return {
            "ticker": ticker,
            "total_score": total_score,
            "verified_score": verified_score,
            "verified_max_score": verified_max,
            "estimated_score": estimated_score,
            "grade": score_to_grade(total_score),
            "components": components,
            "data_completeness_summary": completeness_summary,
            "rationale": disclaimer_inline + " | ".join(rationale_parts),
            "method": self.METHOD_LABEL,
            "disclaimer": self.DISCLAIMER,
            "external_reference": self.EXTERNAL_REFERENCE,
            "computed_at": datetime.now().isoformat(),
        }
