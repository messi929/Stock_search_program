"""한국 시장 외국인/기관 수급 수집기 (pykrx 기반).

WEEK_A.md Day 1-2 산출물.

수집 데이터 (korea_market.md §1.3):
  - 외국인 보유 비중 (보유수량/한도수량/한도소진률) — 종목별 시계열
  - 4개 핵심 투자자 카테고리 매매 (거래대금) — 일자별 전체 종목

호출 패턴:
  - 방식 A: get_market_net_purchases_of_equities_by_ticker(fromdate, todate, market, investor)
           → 일자×시장×투자자 1회 호출 = 그 시장의 모든 종목 데이터
  - 방식 B: get_exhaustion_rates_of_foreign_investment_by_date(fromdate, todate, ticker)
           → 종목 1회 호출 = 해당 종목의 기간 시계열

KRX rate limit: 1초/호출 권장 (차단 회피).
KRX는 과도한 호출 시 "LOGOUT" 응답으로 IP 차단하므로 sleep 엄격 준수.

Firestore 컬렉션:
  historical_supply
    Doc ID: {ticker}_{date} (예: "005930_20251231")
    필드: korea_market.md §1.3 스키마
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable

import pandas as pd
from loguru import logger

# pykrx는 호출 시점에 import (테스트에서 mock 주입 용이)


# 핵심 4개 투자자 카테고리 (korea_market.md §1.2 권장 — 9개 → 4개로 축소)
# pykrx 1.x 기준 valid 값 (collector.py:638~641 참고: "외국인" + "기관합계" 사용 중)
CORE_INVESTORS: tuple[str, ...] = ("외국인합계", "기관합계", "연기금등", "개인")

# pykrx → Firestore 필드명 매핑
INVESTOR_FIELD_PREFIX: dict[str, str] = {
    "외국인합계": "foreign",
    "기관합계": "institution",
    "연기금등": "pension",
    "개인": "individual",
}

# pykrx 매매 데이터 컬럼 (collector.py:656에서 검증된 컬럼명)
PYKRX_NET_BUY_VALUE_COL = "순매수거래대금"
PYKRX_BUY_VALUE_COL = "매수거래대금"
PYKRX_SELL_VALUE_COL = "매도거래대금"

# 외국인 보유 데이터 컬럼 (pykrx 1.x)
PYKRX_HOLDING_QTY_COL = "보유수량"
PYKRX_LIMIT_QTY_COL = "한도수량"
PYKRX_EXHAUSTION_COL = "한도소진률"

# Firestore batch write 한도 (안전 마진, screener.db.repository와 동일)
FIRESTORE_BATCH_LIMIT = 490


@dataclass
class CollectorStats:
    """수집 실행 통계 (로깅/모니터링용)."""

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


class KoreaSupplyCollector:
    """외국인/기관 수급 수집기.

    Args:
        db: Firestore 클라이언트 (None 시 screener.db.firebase_client.get_db() 사용).
            테스트에서 mock 주입 가능.
        sleep_sec: pykrx 호출 간 sleep 초 (KRX rate limit 회피).
        pykrx_module: pykrx.stock 모듈 (None 시 lazy import). 테스트 mock 주입용.
        markets: 수집 대상 시장 (기본: KOSPI + KOSDAQ).
        investors: 수집 대상 투자자 카테고리 (기본: CORE_INVESTORS 4종).
    """

    def __init__(
        self,
        db: Any | None = None,
        sleep_sec: float = 1.0,
        pykrx_module: Any | None = None,
        markets: Iterable[str] = ("KOSPI", "KOSDAQ"),
        investors: Iterable[str] = CORE_INVESTORS,
    ) -> None:
        self._db = db
        self.sleep_sec = sleep_sec
        self._pykrx = pykrx_module
        self.markets = tuple(markets)
        self.investors = tuple(investors)
        self.stats = CollectorStats()

    # ──────────────────────────────────────────────
    # 의존성 lazy 초기화 (테스트 격리 + Firestore 인증 지연)
    # ──────────────────────────────────────────────

    @property
    def db(self) -> Any:
        if self._db is None:
            from screener.db.firebase_client import get_db

            self._db = get_db()
        return self._db

    @property
    def pykrx(self) -> Any:
        if self._pykrx is None:
            from pykrx import stock as pykrx_stock

            self._pykrx = pykrx_stock
        return self._pykrx

    def _sleep(self) -> None:
        """KRX rate limit (1초/호출). 테스트에서 patch 가능."""
        time.sleep(self.sleep_sec)

    # ──────────────────────────────────────────────
    # 방식 A: 일자별 전체 종목 매매 (4개 투자자 카테고리)
    # ──────────────────────────────────────────────

    def collect_daily_snapshot(self, date: str, market: str = "KOSPI") -> pd.DataFrame:
        """특정 일자, 특정 시장의 4개 카테고리별 매매 데이터를 모든 종목에 대해 수집.

        Args:
            date: YYYYMMDD
            market: KOSPI | KOSDAQ

        Returns:
            DataFrame[ticker, date, foreign_buy_value, foreign_sell_value, foreign_net_buy_value,
                      institution_*, pension_*, individual_*]
            빈 결과 시 빈 DataFrame (에러 X — 휴장일/KRX 빈응답 가능성 정상 처리).
        """
        per_investor: dict[str, pd.DataFrame] = {}

        for investor in self.investors:
            self.stats.total_calls += 1
            try:
                df = self.pykrx.get_market_net_purchases_of_equities_by_ticker(
                    fromdate=date, todate=date, market=market, investor=investor
                )
            except Exception as e:
                self.stats.failed_calls += 1
                logger.warning(
                    f"pykrx 호출 실패 (date={date} market={market} investor={investor}): "
                    f"{type(e).__name__}: {str(e)[:120]}"
                )
                self._sleep()
                continue

            if df is None or df.empty:
                self.stats.empty_responses += 1
                logger.debug(f"빈 응답 (date={date} market={market} investor={investor})")
            else:
                self.stats.successful_calls += 1
                per_investor[investor] = df

            self._sleep()

        if not per_investor:
            return pd.DataFrame()

        return self._merge_investor_frames(per_investor, date, market)

    @staticmethod
    def _merge_investor_frames(
        per_investor: dict[str, pd.DataFrame], date: str, market: str
    ) -> pd.DataFrame:
        """투자자별 DataFrame을 종목 단위로 병합.

        pykrx 반환 형식:
          index = 종목 티커
          columns = ['매도거래량', '매수거래량', '순매수거래량',
                     '매도거래대금', '매수거래대금', '순매수거래대금'] (1.x 기준)
        """
        merged: dict[str, dict[str, Any]] = {}

        for investor, df in per_investor.items():
            prefix = INVESTOR_FIELD_PREFIX.get(investor)
            if prefix is None:
                # 미정의 투자자는 컬럼 prefix를 정규화하여 사용 (한글 → 영어 X, 안전하게 raw 사용)
                continue

            net_col = PYKRX_NET_BUY_VALUE_COL if PYKRX_NET_BUY_VALUE_COL in df.columns else None
            buy_col = PYKRX_BUY_VALUE_COL if PYKRX_BUY_VALUE_COL in df.columns else None
            sell_col = PYKRX_SELL_VALUE_COL if PYKRX_SELL_VALUE_COL in df.columns else None

            for ticker, row in df.iterrows():
                rec = merged.setdefault(str(ticker), {"ticker": str(ticker), "date": date, "market": market})
                if net_col is not None:
                    rec[f"{prefix}_net_buy_value"] = _safe_int(row.get(net_col))
                if buy_col is not None:
                    rec[f"{prefix}_buy_value"] = _safe_int(row.get(buy_col))
                if sell_col is not None:
                    rec[f"{prefix}_sell_value"] = _safe_int(row.get(sell_col))

        if not merged:
            return pd.DataFrame()

        return pd.DataFrame(list(merged.values()))

    # ──────────────────────────────────────────────
    # 방식 B: 종목별 외국인 보유 시계열
    # ──────────────────────────────────────────────

    def collect_ticker_holding_series(
        self, ticker: str, fromdate: str, todate: str
    ) -> pd.DataFrame:
        """특정 종목의 외국인 보유 비중 시계열.

        Args:
            ticker: 종목 코드 (예: "005930")
            fromdate: YYYYMMDD
            todate: YYYYMMDD

        Returns:
            DataFrame[ticker, date, foreign_holding_qty, foreign_limit_qty, foreign_exhaustion_pct]
            빈 결과 시 빈 DataFrame.
        """
        self.stats.total_calls += 1
        try:
            df = self.pykrx.get_exhaustion_rates_of_foreign_investment_by_date(
                fromdate=fromdate, todate=todate, ticker=ticker
            )
        except Exception as e:
            self.stats.failed_calls += 1
            logger.warning(
                f"pykrx 보유 시계열 실패 (ticker={ticker} {fromdate}~{todate}): "
                f"{type(e).__name__}: {str(e)[:120]}"
            )
            self._sleep()
            return pd.DataFrame()

        self._sleep()

        if df is None or df.empty:
            self.stats.empty_responses += 1
            return pd.DataFrame()

        self.stats.successful_calls += 1
        return self._normalize_holding_frame(df, ticker)

    @staticmethod
    def _normalize_holding_frame(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
        """pykrx 보유 시계열 → Firestore 스키마 정규화.

        pykrx 반환:
          index = pd.DatetimeIndex (날짜)
          columns = ['상장주식수', '보유수량', '지분율', '한도수량', '한도소진률'] (1.x 기준)
        """
        records: list[dict[str, Any]] = []
        for idx, row in df.iterrows():
            date_str = _to_date_str(idx)
            records.append(
                {
                    "ticker": ticker,
                    "date": date_str,
                    "foreign_holding_qty": _safe_int(row.get(PYKRX_HOLDING_QTY_COL)),
                    "foreign_limit_qty": _safe_int(row.get(PYKRX_LIMIT_QTY_COL)),
                    "foreign_exhaustion_pct": _safe_float(row.get(PYKRX_EXHAUSTION_COL)),
                }
            )
        return pd.DataFrame(records)

    # ──────────────────────────────────────────────
    # Firestore 저장
    # ──────────────────────────────────────────────

    def save_to_firestore(
        self,
        records: list[dict[str, Any]],
        collection: str = "historical_supply",
        collection_phase: str = "backfill",
    ) -> int:
        """레코드 리스트를 Firestore에 batch 저장.

        Doc ID = {ticker}_{date} (예: "005930_20251231").
        490개씩 batch commit (FIRESTORE_BATCH_LIMIT).
        같은 Doc ID에 대해 merge=True로 부분 업데이트.

        Args:
            records: 저장할 레코드 dict 리스트 (각 dict에 'ticker', 'date' 필수).
            collection: Firestore 컬렉션 이름 (기본: historical_supply).
            collection_phase: 메타 필드 — backfill | incremental.

        Returns:
            저장된 doc 수.
        """
        if not records:
            return 0

        col_ref = self.db.collection(collection)
        now_iso = datetime.now().isoformat()
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
                doc = dict(rec)  # copy
                # 메타 필드 자동 추가
                try:
                    parsed = datetime.strptime(str(date), "%Y%m%d")
                    doc["year"] = parsed.year
                    doc["month"] = parsed.month
                except ValueError:
                    pass
                doc["collected_at"] = now_iso
                doc["data_source"] = "pykrx_1.x"
                doc["collection_phase"] = collection_phase

                batch.set(col_ref.document(doc_id), doc, merge=True)

            batch.commit()
            written += len(chunk)
            self.stats.docs_written += len(chunk)
            logger.debug(f"Firestore batch commit: {len(chunk)} docs (collection={collection})")

        return written

    # ──────────────────────────────────────────────
    # 편의 메서드: 일자×시장 → Firestore 저장 통합
    # ──────────────────────────────────────────────

    def collect_and_save_daily(
        self, date: str, market: str = "KOSPI", collection_phase: str = "backfill"
    ) -> int:
        """일자×시장의 매매 데이터를 수집하여 Firestore에 저장.

        Returns:
            저장된 doc 수 (0 = 휴장일/빈 응답).
        """
        df = self.collect_daily_snapshot(date, market=market)
        if df.empty:
            return 0
        records = df.to_dict("records")
        return self.save_to_firestore(records, collection_phase=collection_phase)

    def collect_and_save_holding_series(
        self,
        ticker: str,
        fromdate: str,
        todate: str,
        collection_phase: str = "backfill",
    ) -> int:
        """종목 외국인 보유 시계열을 수집하여 Firestore에 저장.

        Returns:
            저장된 doc 수.
        """
        df = self.collect_ticker_holding_series(ticker, fromdate, todate)
        if df.empty:
            return 0
        records = df.to_dict("records")
        return self.save_to_firestore(records, collection_phase=collection_phase)


# ──────────────────────────────────────────────
# 유틸 (모듈 private)
# ──────────────────────────────────────────────


def _safe_int(v: Any) -> int:
    """NaN/None/문자열 → 0. Firestore는 NaN 저장 불가."""
    if v is None:
        return 0
    try:
        f = float(v)
        if f != f:  # NaN check
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
    """pd.Timestamp/datetime/str → YYYYMMDD."""
    if hasattr(idx, "strftime"):
        return idx.strftime("%Y%m%d")
    s = str(idx).replace("-", "").replace("/", "").strip()
    return s[:8]
