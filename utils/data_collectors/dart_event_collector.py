"""DART 기업 이벤트 분류 + 수집 모듈.

WEEK_C.md Day 2 산출물 (Event Analyst 페르소나용).

dart_buyback.py가 자사주 한정이라면, 이 모듈은 더 넓은 카테고리를 분류:
  - performance      : 분기/반기/사업보고서                → ★★ 실적 이벤트
  - buyback          : 자사주 (취득/소각/처분/신탁)        → dart_buyback과 의미 호환
  - ma_decision      : 합병/분할/영업양수도                → ★★★ 구조 변화
  - new_shares       : 유상증자/무상증자                   → ★ 희석 / ☆ 중립
  - convertible_bond : 전환사채/신주인수권부사채            → ★ 잠재 희석
  - stock_split      : 액면분할/병합                       → ☆ 중립
  - dividend_decision: 배당 결정                          → ★ 주주환원
  - unknown          : 분류 미해당

dart_buyback.py와의 관계:
  - 자사주 정밀 분류는 dart_buyback.classify_buyback_action() 그대로 사용 (변경 X).
  - 본 모듈은 더 넓은 이벤트를 1차 분류하고, action="buyback"인 경우만 buyback 모듈로 디스패치.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from loguru import logger

from utils.data_collectors.dart_buyback import (
    classify_buyback_action,
    is_amendment_prefix,
)


# ──────────────────────────────────────────────
# 카테고리 분류
# ──────────────────────────────────────────────

# 우선순위 순서. 위쪽이 더 구체적/강한 신호.
EVENT_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    # M&A 구조 변화
    (
        "ma_decision",
        (
            "회사합병결정",
            "회사분할결정",
            "회사합병",
            "회사분할",
            "영업양수결정",
            "영업양도결정",
            "영업양수도결정",
            "주식교환",
            "주식이전",
        ),
    ),
    # 자사주 — buyback 모듈로 위임
    (
        "buyback",
        (
            "주식소각",
            "자기주식취득결과보고",
            "자기주식취득결정",
            "자사주취득결정",
            "자기주식처분",
            "자기주식취득신탁계약",
        ),
    ),
    # 전환사채/BW (잠재 희석)
    (
        "convertible_bond",
        (
            "전환사채발행결정",
            "신주인수권부사채발행결정",
            "교환사채발행결정",
        ),
    ),
    # 유/무상증자
    (
        "new_shares",
        (
            "유상증자결정",
            "무상증자결정",
            "유무상증자결정",
        ),
    ),
    # 액면분할/병합
    (
        "stock_split",
        ("주식분할결정", "주식병합결정", "액면분할", "액면병합"),
    ),
    # 배당
    (
        "dividend_decision",
        ("현금ㆍ현물배당결정", "현금배당결정", "주식배당결정"),
    ),
    # 정기 실적 보고
    (
        "performance",
        ("사업보고서", "반기보고서", "분기보고서"),
    ),
)


EVENT_RATING: dict[str, dict[str, Any]] = {
    "ma_decision": {"weight": 3, "rating": "★★★"},
    "buyback": {"weight": 2, "rating": "★★"},  # 세부 등급은 dart_buyback에서
    "performance": {"weight": 2, "rating": "★★"},
    "convertible_bond": {"weight": 1, "rating": "★"},
    "new_shares": {"weight": 1, "rating": "★"},
    "dividend_decision": {"weight": 1, "rating": "★"},
    "stock_split": {"weight": 0, "rating": "☆"},
    "unknown": {"weight": 0, "rating": "?"},
}


def classify_event(report_nm: str) -> dict[str, Any]:
    """공시 제목으로 이벤트 카테고리 분류.

    Args:
        report_nm: DART 공시 제목 (정정 prefix 포함 가능)

    Returns:
        {
            "event_type": str,
            "weight": int,
            "rating": str,
            "is_amendment": bool,
            "matched_keyword": str | None,
            "buyback_subtype": str | None,  # event_type=="buyback"일 때만
        }
    """
    nm = report_nm or ""
    is_amendment = is_amendment_prefix(nm)

    matched: tuple[str, str] | None = None
    for event_type, keywords in EVENT_KEYWORDS:
        for kw in keywords:
            if kw in nm:
                matched = (event_type, kw)
                break
        if matched:
            break

    if matched is None:
        return {
            "event_type": "unknown",
            "weight": EVENT_RATING["unknown"]["weight"],
            "rating": EVENT_RATING["unknown"]["rating"],
            "is_amendment": is_amendment,
            "matched_keyword": None,
            "buyback_subtype": None,
        }

    event_type, kw = matched
    result: dict[str, Any] = {
        "event_type": event_type,
        "weight": EVENT_RATING[event_type]["weight"],
        "rating": EVENT_RATING[event_type]["rating"],
        "is_amendment": is_amendment,
        "matched_keyword": kw,
        "buyback_subtype": None,
    }

    # buyback이면 더 세분 분류 (dart_buyback 위임)
    if event_type == "buyback":
        sub = classify_buyback_action(nm)
        result["buyback_subtype"] = sub["action"]
        # buyback 세분 등급 사용 (소각=★★★ 등)
        result["weight"] = sub["weight"]
        result["rating"] = sub["rating"]

    return result


# ──────────────────────────────────────────────
# Collector (DartClient + Firestore 활용)
# ──────────────────────────────────────────────


FIRESTORE_BATCH_LIMIT = 490


@dataclass
class EventStats:
    total_disclosures: int = 0
    classified: int = 0
    docs_written: int = 0
    by_event_type: dict[str, int] = field(default_factory=dict)

    def bump(self, event_type: str) -> None:
        self.by_event_type[event_type] = self.by_event_type.get(event_type, 0) + 1


class DartEventCollector:
    """DART 기업 이벤트 수집 + 분류 + Firestore 저장.

    Firestore 컬렉션: corporate_events (Doc ID = {stock_code}_{rcept_no})
    """

    def __init__(
        self,
        client,
        db: Any | None = None,
        collection: str = "corporate_events",
    ) -> None:
        self.client = client
        self._db = db
        self.collection = collection
        self.stats = EventStats()

    @property
    def db(self) -> Any:
        if self._db is None:
            from screener.db.firebase_client import get_db

            self._db = get_db()
        return self._db

    def fetch_events_for_ticker(
        self,
        stock_code: str,
        bgn_de: str,
        end_de: str,
        event_types: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """종목별 기업 이벤트 분류 + 반환.

        Args:
            stock_code: 6자리 종목코드.
            bgn_de/end_de: YYYYMMDD.
            event_types: 필터 (예: ["ma_decision", "buyback"]). None = 전체.
        """
        stock_code = str(stock_code).zfill(6)
        corp_code = self.client.corp_code_for_stock(stock_code)
        if corp_code is None:
            logger.warning(f"corp_code 매핑 없음: stock_code={stock_code}")
            return []

        items = self.client.fetch_disclosures(
            corp_code=corp_code, bgn_de=bgn_de, end_de=end_de
        )
        self.stats.total_disclosures += len(items)

        type_filter = set(event_types) if event_types else None
        results: list[dict[str, Any]] = []
        for item in items:
            report_nm = item.get("report_nm", "")
            cls = classify_event(report_nm)
            if cls["event_type"] == "unknown":
                continue
            if type_filter and cls["event_type"] not in type_filter:
                continue
            self.stats.classified += 1
            self.stats.bump(cls["event_type"])

            results.append(
                {
                    "stock_code": stock_code,
                    "corp_code": corp_code,
                    "corp_name": item.get("corp_name", ""),
                    "rcept_no": item.get("rcept_no", ""),
                    "rcept_dt": item.get("rcept_dt", ""),
                    "report_nm": report_nm,
                    "event_type": cls["event_type"],
                    "weight": cls["weight"],
                    "rating": cls["rating"],
                    "is_amendment": cls["is_amendment"],
                    "matched_keyword": cls["matched_keyword"],
                    "buyback_subtype": cls["buyback_subtype"],
                    "flr_nm": item.get("flr_nm", ""),
                    "rm": item.get("rm", ""),
                }
            )

        return results

    def save_to_firestore(self, records: list[dict[str, Any]]) -> int:
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
                if not stock_code or not rcept_no or not str(rcept_no).strip():
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
        self,
        stock_code: str,
        bgn_de: str,
        end_de: str,
        event_types: list[str] | None = None,
    ) -> int:
        records = self.fetch_events_for_ticker(stock_code, bgn_de, end_de, event_types)
        return self.save_to_firestore(records)
