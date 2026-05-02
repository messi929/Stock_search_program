"""DART 자사주 정책 수집 + 분류 모듈.

WEEK_A.md Day 4 산출물.

자사주 액션 분류 (Korean Specialist 페르소나가 그대로 사용):
  - burn          : 주식소각 결정 → ★★★ 강한 주주환원
  - buy_decision  : 자기주식 취득 결정 → ★ 진행 중
  - buy_complete  : 자기주식 취득 결과보고 → ★ 완료
  - dispose       : 자기주식 처분 결정 → ☆ (ESOP/매각 — 제목으로 구분 어려움)
  - trust_contract: 신탁 계약 (자사주 매입 신탁) → ★ 간접 매입
  - unknown       : 분류 미해당

[기재정정] 접두사는 is_amendment=True로 마킹 (집계 시 중복 카운트 회피용).

Firestore 컬렉션: buyback_history
  Doc ID: {stock_code}_{rcept_no}
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd
from loguru import logger


# 분류 키워드 (우선순위 순서대로 검사 — 위쪽이 더 구체적)
BUYBACK_KEYWORDS = (
    ("burn", ("주식소각", "소각결정", "소각 결정")),
    ("buy_complete", ("자기주식취득결과보고", "자사주취득결과보고")),
    ("buy_decision", ("자기주식취득결정", "자사주취득결정", "자기주식 취득 결정")),
    ("dispose", ("자기주식처분", "자사주처분")),
    ("trust_contract", ("자기주식취득신탁계약", "자사주신탁", "신탁계약체결")),
)

# action → 가중치/등급
ACTION_META: dict[str, dict[str, Any]] = {
    "burn": {"weight": 3, "rating": "★★★"},
    "buy_decision": {"weight": 1, "rating": "★"},
    "buy_complete": {"weight": 1, "rating": "★"},
    "trust_contract": {"weight": 1, "rating": "★"},
    "dispose": {"weight": 0, "rating": "☆"},
    "unknown": {"weight": 0, "rating": "?"},
}

AMENDMENT_PREFIXES = ("[기재정정]", "[정정]", "[첨부정정]", "[첨부추가]")

# Firestore batch (screener.db.repository.py 와 동일)
FIRESTORE_BATCH_LIMIT = 490


@dataclass
class BuybackStats:
    total_disclosures: int = 0
    classified: int = 0
    docs_written: int = 0
    by_action: dict[str, int] = field(default_factory=dict)

    def bump(self, action: str) -> None:
        self.by_action[action] = self.by_action.get(action, 0) + 1


# ──────────────────────────────────────────────
# 분류 함수 (모듈 레벨, 순수 함수)
# ──────────────────────────────────────────────


def classify_buyback_action(report_nm: str) -> dict[str, Any]:
    """공시 제목으로 자사주 액션 분류.

    Args:
        report_nm: DART 공시 제목 (예: "주식소각결정", "[기재정정]주요사항보고서(자기주식취득결정)")

    Returns:
        {
            "action": "burn" | "buy_decision" | "buy_complete" |
                      "dispose" | "trust_contract" | "unknown",
            "weight": int (0~3),
            "rating": "★★★" | "★" | "☆" | "?",
            "is_amendment": bool,
            "matched_keyword": str | None,
        }
    """
    nm = report_nm or ""
    is_amendment = any(nm.startswith(p) for p in AMENDMENT_PREFIXES)

    for action, keywords in BUYBACK_KEYWORDS:
        for kw in keywords:
            if kw in nm:
                return {
                    "action": action,
                    "weight": ACTION_META[action]["weight"],
                    "rating": ACTION_META[action]["rating"],
                    "is_amendment": is_amendment,
                    "matched_keyword": kw,
                }

    return {
        "action": "unknown",
        "weight": ACTION_META["unknown"]["weight"],
        "rating": ACTION_META["unknown"]["rating"],
        "is_amendment": is_amendment,
        "matched_keyword": None,
    }


def is_buyback_disclosure(report_nm: str) -> bool:
    """자사주 관련 공시인지 빠른 판정 (필터링용)."""
    return classify_buyback_action(report_nm)["action"] != "unknown"


# ──────────────────────────────────────────────
# Collector 클래스 (DartClient + Firestore 의존)
# ──────────────────────────────────────────────


class DartBuybackCollector:
    """DART에서 자사주 공시를 수집하여 분류 + Firestore 저장.

    Args:
        client: DartClient 인스턴스.
        db: Firestore 클라이언트 (None 시 lazy import).
        collection: Firestore 컬렉션 이름.
    """

    def __init__(
        self,
        client,
        db: Any | None = None,
        collection: str = "buyback_history",
    ) -> None:
        self.client = client
        self._db = db
        self.collection = collection
        self.stats = BuybackStats()

    @property
    def db(self) -> Any:
        if self._db is None:
            from screener.db.firebase_client import get_db

            self._db = get_db()
        return self._db

    # ──────────────────────────────────────────────
    # 종목별 자사주 공시 수집
    # ──────────────────────────────────────────────

    def fetch_buyback_disclosures(
        self,
        stock_code: str,
        bgn_de: str,
        end_de: str,
    ) -> list[dict[str, Any]]:
        """종목 자사주 공시 수집 + 분류.

        Args:
            stock_code: 6자리 종목 코드 (예: "005930")
            bgn_de: 시작일 YYYYMMDD
            end_de: 종료일 YYYYMMDD

        Returns:
            분류된 공시 dict 리스트. corp_code 매핑 실패 시 빈 리스트.
        """
        stock_code = str(stock_code).zfill(6)
        corp_code = self.client.corp_code_for_stock(stock_code)
        if corp_code is None:
            logger.warning(f"corp_code 매핑 없음: stock_code={stock_code}")
            return []

        all_items = self.client.fetch_disclosures(
            corp_code=corp_code, bgn_de=bgn_de, end_de=end_de
        )
        self.stats.total_disclosures += len(all_items)

        classified: list[dict[str, Any]] = []
        for item in all_items:
            report_nm = item.get("report_nm", "")
            cls = classify_buyback_action(report_nm)
            if cls["action"] == "unknown":
                continue
            self.stats.classified += 1
            self.stats.bump(cls["action"])

            classified.append(
                {
                    "stock_code": stock_code,
                    "corp_code": corp_code,
                    "corp_name": item.get("corp_name", ""),
                    "rcept_no": item.get("rcept_no", ""),
                    "rcept_dt": item.get("rcept_dt", ""),
                    "report_nm": report_nm,
                    "action": cls["action"],
                    "weight": cls["weight"],
                    "rating": cls["rating"],
                    "is_amendment": cls["is_amendment"],
                    "matched_keyword": cls["matched_keyword"],
                    "flr_nm": item.get("flr_nm", ""),
                    "rm": item.get("rm", ""),
                }
            )

        return classified

    # ──────────────────────────────────────────────
    # Firestore 저장 (batch)
    # ──────────────────────────────────────────────

    def save_to_firestore(self, records: list[dict[str, Any]]) -> int:
        """공시 레코드를 buyback_history 컬렉션에 batch 저장.

        Doc ID = {stock_code}_{rcept_no} (rcept_no는 14자리 unique).
        """
        if not records:
            return 0

        col_ref = self.db.collection(self.collection)
        now_iso = datetime.now().isoformat()
        written = 0

        for chunk_start in range(0, len(records), FIRESTORE_BATCH_LIMIT):
            chunk = records[chunk_start : chunk_start + FIRESTORE_BATCH_LIMIT]
            batch = self.db.batch()

            for rec in chunk:
                stock_code = rec.get("stock_code")
                rcept_no = rec.get("rcept_no")
                if not stock_code or not rcept_no:
                    logger.warning(f"stock_code/rcept_no 누락 → skip: {rec}")
                    continue

                doc_id = f"{stock_code}_{rcept_no}"
                doc = dict(rec)
                doc["collected_at"] = now_iso
                doc["data_source"] = "dart_opendart_v1"

                batch.set(col_ref.document(doc_id), doc, merge=True)

            batch.commit()
            written += len(chunk)
            self.stats.docs_written += len(chunk)

        return written

    def collect_and_save(
        self, stock_code: str, bgn_de: str, end_de: str
    ) -> int:
        """fetch + save 통합 헬퍼."""
        records = self.fetch_buyback_disclosures(stock_code, bgn_de, end_de)
        return self.save_to_firestore(records)

    # ──────────────────────────────────────────────
    # 분석 헬퍼 (Firestore 읽기)
    # ──────────────────────────────────────────────

    def get_buyback_history(
        self, stock_code: str, years: int = 3
    ) -> list[dict[str, Any]]:
        """종목별 N년치 자사주 이력 조회 (Korean Specialist 페르소나용)."""
        from datetime import timedelta

        from google.cloud.firestore_v1.base_query import FieldFilter

        stock_code = str(stock_code).zfill(6)
        from_date = (datetime.now() - timedelta(days=365 * years)).strftime("%Y%m%d")

        try:
            docs = (
                self.db.collection(self.collection)
                .where(filter=FieldFilter("stock_code", "==", stock_code))
                .where(filter=FieldFilter("rcept_dt", ">=", from_date))
                .stream()
            )
            records = [doc.to_dict() for doc in docs]
        except Exception as e:
            logger.warning(
                f"buyback_history 조회 실패 (stock={stock_code}): "
                f"{type(e).__name__}: {str(e)[:120]}"
            )
            return []

        # rcept_dt 내림차순 (최근부터)
        records.sort(key=lambda r: r.get("rcept_dt", ""), reverse=True)
        return records

    def summarize_buyback_history(
        self, stock_code: str, years: int = 3
    ) -> dict[str, Any]:
        """자사주 이력 통계 요약.

        Returns:
            {
                "stock_code": "005930",
                "years": 3,
                "total_disclosures": 8,
                "by_action": {"burn": 1, "buy_decision": 2, "buy_complete": 2, ...},
                "has_burn": True,           # 소각 이력 있음 → 강한 주주환원
                "max_weight": 3,            # 최고 가중치 (3 = burn 있음)
                "latest_action": {...},     # 가장 최근 공시 1건
            }
        """
        history = self.get_buyback_history(stock_code, years=years)

        by_action: dict[str, int] = {}
        max_weight = 0
        for rec in history:
            if rec.get("is_amendment"):
                continue  # 정정 공시는 집계 제외
            action = rec.get("action", "unknown")
            by_action[action] = by_action.get(action, 0) + 1
            w = int(rec.get("weight", 0))
            if w > max_weight:
                max_weight = w

        return {
            "stock_code": str(stock_code).zfill(6),
            "years": years,
            "total_disclosures": len(history),
            "by_action": by_action,
            "has_burn": by_action.get("burn", 0) > 0,
            "max_weight": max_weight,
            "latest_action": history[0] if history else None,
        }
