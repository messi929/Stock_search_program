"""한국 시장 공매도/대차잔고 수집 + 분석 모듈.

WEEK_A.md Day 5 산출물.

데이터 소스 (pykrx 1.x 검증):
  - get_shorting_balance_by_date(fromdate, todate, ticker) — 잔고 시계열
  - get_shorting_volume_by_date(fromdate, todate, ticker) — 거래량 시계열
  - get_shorting_status_by_date(fromdate, todate, ticker) — 종합

⚠️ 정책 변동 빈번 (2008/2011/2020/2023/2025) — data/short_selling_policy.json 수동 갱신.

Korean Specialist 페르소나가 활용:
  - 공매도 잔고 30일 추이 (감소 = 숏 커버링)
  - 시총 대비 비중
  - 정책 상태 (전면 재개/금지)
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
from loguru import logger


POLICY_FILE = Path(__file__).resolve().parents[2] / "data" / "short_selling_policy.json"

# pykrx 컬럼 (검증 완료)
PYKRX_BALANCE_QTY_COL = "공매도잔고"
PYKRX_BALANCE_AMOUNT_COL = "공매도금액"
PYKRX_RATIO_COL = "비중"  # 시총 대비
PYKRX_LISTED_SHARES_COL = "상장주식수"
PYKRX_MARKET_CAP_COL = "시가총액"


@dataclass
class ShortStats:
    total_calls: int = 0
    successful_calls: int = 0
    empty_responses: int = 0
    failed_calls: int = 0
    docs_written: int = 0
    started_at: float = field(default_factory=time.time)

    def elapsed_sec(self) -> float:
        return time.time() - self.started_at

    def summary(self) -> str:
        return (
            f"calls={self.total_calls} (ok={self.successful_calls}, "
            f"empty={self.empty_responses}, fail={self.failed_calls}) "
            f"docs={self.docs_written} elapsed={self.elapsed_sec():.1f}s"
        )


# ──────────────────────────────────────────────
# 정책 이력 (정적 데이터)
# ──────────────────────────────────────────────


_policy_cache: dict[str, Any] | None = None


def _load_policy() -> dict[str, Any]:
    global _policy_cache
    if _policy_cache is not None:
        return _policy_cache

    if not POLICY_FILE.exists():
        logger.warning(f"short_selling_policy.json 미존재: {POLICY_FILE}")
        _policy_cache = {"policy_history": [], "current_status": {}}
        return _policy_cache

    try:
        with open(POLICY_FILE, encoding="utf-8") as f:
            _policy_cache = json.load(f)
    except Exception as e:
        logger.error(f"short_selling_policy.json 파싱 실패: {e}")
        _policy_cache = {"policy_history": [], "current_status": {}}

    return _policy_cache


def reset_policy_cache() -> None:
    global _policy_cache
    _policy_cache = None


def get_current_policy_status() -> dict[str, Any]:
    """현재 공매도 정책 상태 (data/short_selling_policy.json:current_status)."""
    return _load_policy().get("current_status") or {}


def get_policy_history() -> list[dict[str, Any]]:
    """정책 변동 이력 list (date 오름차순)."""
    history = _load_policy().get("policy_history") or []
    return sorted(history, key=lambda r: r.get("date", ""))


# ──────────────────────────────────────────────
# Collector (pykrx 호출)
# ──────────────────────────────────────────────


class KoreaShortSellingCollector:
    """공매도 잔고/거래량 시계열 수집기.

    Args:
        db: Firestore 클라이언트 (None 시 lazy import).
        sleep_sec: pykrx 호출 간 sleep (KRX rate limit).
        pykrx_module: pykrx.stock 모듈 (테스트 mock 주입용).
        collection: Firestore 컬렉션 이름.
    """

    def __init__(
        self,
        db: Any | None = None,
        sleep_sec: float = 1.0,
        pykrx_module: Any | None = None,
        collection: str = "short_selling_history",
    ) -> None:
        self._db = db
        self.sleep_sec = sleep_sec
        self._pykrx = pykrx_module
        self.collection = collection
        self.stats = ShortStats()

    @property
    def db(self) -> Any:
        if self._db is None:
            from screener.db.firebase_client import get_db

            self._db = get_db()
        return self._db

    @property
    def pykrx(self) -> Any:
        if self._pykrx is None:
            from pykrx import stock

            self._pykrx = stock
        return self._pykrx

    def _sleep(self) -> None:
        time.sleep(self.sleep_sec)

    # ──────────────────────────────────────────────
    # 종목별 시계열 (잔고 + 거래량 종합)
    # ──────────────────────────────────────────────

    def collect_ticker_short_series(
        self, ticker: str, fromdate: str, todate: str
    ) -> pd.DataFrame:
        """특정 종목의 공매도 잔고 시계열.

        Returns:
            DataFrame[ticker, date, short_balance_qty, short_balance_value,
                      listed_shares, market_cap, short_ratio_pct]
            빈 결과면 빈 DataFrame.
        """
        ticker = str(ticker).zfill(6)
        self.stats.total_calls += 1
        try:
            df = self.pykrx.get_shorting_balance_by_date(
                fromdate=fromdate, todate=todate, ticker=ticker
            )
        except Exception as e:
            self.stats.failed_calls += 1
            logger.warning(
                f"공매도 잔고 호출 실패 ({ticker} {fromdate}~{todate}): "
                f"{type(e).__name__}: {str(e)[:120]}"
            )
            self._sleep()
            return pd.DataFrame()

        self._sleep()

        if df is None or df.empty:
            self.stats.empty_responses += 1
            return pd.DataFrame()

        self.stats.successful_calls += 1
        return self._normalize_balance_frame(df, ticker)

    @staticmethod
    def _normalize_balance_frame(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
        """pykrx 컬럼 → 영문 필드 정규화."""
        records: list[dict[str, Any]] = []
        for idx, row in df.iterrows():
            date_str = _to_date_str(idx)
            records.append(
                {
                    "ticker": ticker,
                    "date": date_str,
                    "short_balance_qty": _safe_int(row.get(PYKRX_BALANCE_QTY_COL)),
                    "short_balance_value": _safe_int(row.get(PYKRX_BALANCE_AMOUNT_COL)),
                    "listed_shares": _safe_int(row.get(PYKRX_LISTED_SHARES_COL)),
                    "market_cap": _safe_int(row.get(PYKRX_MARKET_CAP_COL)),
                    "short_ratio_pct": _safe_float(row.get(PYKRX_RATIO_COL)),
                }
            )
        return pd.DataFrame(records)

    # ──────────────────────────────────────────────
    # Firestore 저장
    # ──────────────────────────────────────────────

    def save_to_firestore(self, records: list[dict[str, Any]]) -> int:
        if not records:
            return 0

        col_ref = self.db.collection(self.collection)
        now_iso = datetime.now().isoformat()
        FIRESTORE_BATCH_LIMIT = 490
        written = 0

        for chunk_start in range(0, len(records), FIRESTORE_BATCH_LIMIT):
            chunk = records[chunk_start : chunk_start + FIRESTORE_BATCH_LIMIT]
            batch = self.db.batch()
            for rec in chunk:
                ticker = rec.get("ticker")
                date = rec.get("date")
                if not ticker or not date:
                    logger.warning(f"ticker/date 누락 → skip: {rec}")
                    continue
                doc_id = f"{ticker}_{date}"
                doc = dict(rec)
                doc["collected_at"] = now_iso
                doc["data_source"] = "pykrx_1.x"
                batch.set(col_ref.document(doc_id), doc, merge=True)
            batch.commit()
            written += len(chunk)
            self.stats.docs_written += len(chunk)

        return written

    def collect_and_save(self, ticker: str, fromdate: str, todate: str) -> int:
        df = self.collect_ticker_short_series(ticker, fromdate, todate)
        if df.empty:
            return 0
        return self.save_to_firestore(df.to_dict("records"))


# ──────────────────────────────────────────────
# Analyzer (Firestore 읽기 + 분석)
# ──────────────────────────────────────────────


class KoreaShortSellingAnalyzer:
    """공매도 데이터 분석 — 30일 추이 + 정책 상태 종합."""

    def __init__(
        self, db: Any | None = None, collection: str = "short_selling_history"
    ) -> None:
        self._db = db
        self.collection = collection

    @property
    def db(self) -> Any:
        if self._db is None:
            from screener.db.firebase_client import get_db

            self._db = get_db()
        return self._db

    def load_short_history(self, ticker: str, days: int = 30) -> pd.DataFrame:
        """종목 공매도 잔고 N일치."""
        from google.cloud.firestore_v1.base_query import FieldFilter

        ticker = str(ticker).zfill(6)
        from_date = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")

        try:
            docs = (
                self.db.collection(self.collection)
                .where(filter=FieldFilter("ticker", "==", ticker))
                .where(filter=FieldFilter("date", ">=", from_date))
                .stream()
            )
            records = [doc.to_dict() for doc in docs]
        except Exception as e:
            logger.warning(
                f"short_selling 조회 실패 ({ticker}): {type(e).__name__}: {str(e)[:120]}"
            )
            return pd.DataFrame()

        if not records:
            return pd.DataFrame()

        df = pd.DataFrame(records)
        if "date" in df.columns:
            df = df.sort_values("date").reset_index(drop=True)
        return df

    def analyze_short_signals(self, ticker: str, days: int = 30) -> dict[str, Any]:
        """30일 공매도 추이 + 정책 종합.

        Returns:
            {
                "ticker": "005930",
                "current_short_balance_qty": 12500000,
                "current_short_ratio_pct": 1.2,
                "30d_change_qty": -500000,            # 음수 = 숏 커버링
                "30d_change_pct_points": -0.3,        # 비중 변화 (%p)
                "ratio_classification": "낮음 (5% 미만)" | "중간" | "높음" | "매우 높음",
                "interpretation": "숏 커버링 진행 중" | "숏 베팅 증가" | "변화 미미" | "데이터 부족",
                "policy_status": {...},
                "data_points": 22,
            }
        """
        ticker = str(ticker).zfill(6)
        df = self.load_short_history(ticker, days=days)
        policy = get_current_policy_status()

        if df.empty:
            return {
                "ticker": ticker,
                "current_short_balance_qty": 0,
                "current_short_ratio_pct": 0.0,
                "30d_change_qty": 0,
                "30d_change_pct_points": 0.0,
                "ratio_classification": "데이터 없음",
                "interpretation": "데이터 부족",
                "policy_status": policy,
                "data_points": 0,
            }

        latest = df.iloc[-1]
        oldest = df.iloc[0]

        current_qty = int(latest.get("short_balance_qty") or 0)
        current_ratio = float(latest.get("short_ratio_pct") or 0)
        old_qty = int(oldest.get("short_balance_qty") or 0)
        old_ratio = float(oldest.get("short_ratio_pct") or 0)

        change_qty = current_qty - old_qty
        change_pct_points = round(current_ratio - old_ratio, 2)

        return {
            "ticker": ticker,
            "current_short_balance_qty": current_qty,
            "current_short_ratio_pct": round(current_ratio, 2),
            "30d_change_qty": change_qty,
            "30d_change_pct_points": change_pct_points,
            "ratio_classification": _classify_short_ratio(current_ratio),
            "interpretation": _interpret_short_trend(change_qty, len(df)),
            "policy_status": policy,
            "data_points": len(df),
        }


# ──────────────────────────────────────────────
# 분류 + 해석 헬퍼 (모듈 레벨, 순수 함수)
# ──────────────────────────────────────────────


def _classify_short_ratio(ratio_pct: float) -> str:
    if ratio_pct < 1:
        return "매우 낮음 (1% 미만)"
    elif ratio_pct < 3:
        return "낮음 (3% 미만)"
    elif ratio_pct < 5:
        return "중간 (3~5%)"
    elif ratio_pct < 10:
        return "높음 (5~10%)"
    else:
        return "매우 높음 (10% 이상)"


# 30일 잔고 변화 절대값 임계 (미미한 변화 vs 의미있는 변화)
SHORT_NEUTRAL_QTY_CHANGE = 100_000  # 10만주 이내는 noise


def _interpret_short_trend(change_qty: int, data_points: int) -> str:
    if data_points < 5:
        return "데이터 부족 (5일 미만)"
    if abs(change_qty) < SHORT_NEUTRAL_QTY_CHANGE:
        return "변화 미미"
    if change_qty < 0:
        return "숏 커버링 진행 중 (잔고 감소)"
    return "숏 베팅 증가 (잔고 증가)"


# ──────────────────────────────────────────────
# 유틸 (모듈 private)
# ──────────────────────────────────────────────


def _safe_int(v: Any) -> int:
    if v is None:
        return 0
    try:
        f = float(v)
        if f != f:
            return 0
        return int(f)
    except (TypeError, ValueError):
        return 0


def _safe_float(v: Any) -> float:
    if v is None:
        return 0.0
    try:
        f = float(v)
        if f != f:
            return 0.0
        return round(f, 4)
    except (TypeError, ValueError):
        return 0.0


def _to_date_str(idx: Any) -> str:
    if hasattr(idx, "strftime"):
        return idx.strftime("%Y%m%d")
    s = str(idx).replace("-", "").replace("/", "").strip()
    return s[:8]
