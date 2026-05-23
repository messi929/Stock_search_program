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
# ⚠️ 2026-05-23: KRX가 카테고리명 변경 — "외국인합계"(과거) → "외국인"(현재).
# 이전 이름은 KRX에서 rows=0 + KeyError 반환. 백필(2026-05-22)에서 외국인 전량 누락 → 재백필.
CORE_INVESTORS: tuple[str, ...] = ("외국인", "기관합계", "연기금등", "개인")

# pykrx → Firestore 필드명 매핑
INVESTOR_FIELD_PREFIX: dict[str, str] = {
    "외국인": "foreign",
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
# 분석 헬퍼 (Korean Specialist 페르소나가 호출)
# ──────────────────────────────────────────────


# 5년 = 거래일 약 1,250 / 달력일 1,825
DAYS_5Y_CALENDAR = 1825
# interpretation_signal 임계값
NEUTRAL_AVG_DIFF_PCT_POINTS = 0.5  # 평균 대비 차이 (%p)
NEUTRAL_NET_BUY_KRW = 100_000_000  # 30일 누적 순매수 절대값 (1억원)
MIN_DAYS_FOR_SIGNAL = 20  # 5년 추이 분석에 필요한 최소 데이터 일수


class KoreaSupplyAnalyzer:
    """Firestore historical_supply 컬렉션 기반 분석 함수 모음.

    Korean Specialist 페르소나가 호출하여 종목별 외국인/기관 수급 통계를 받음.
    KoreaSupplyCollector가 백필/증분으로 채워둔 데이터를 읽기 전용으로 활용.

    Args:
        db: Firestore 클라이언트 (None 시 lazy import).
        collection: 컬렉션 이름 (기본: historical_supply, KoreaSupplyCollector와 일치).
    """

    def __init__(self, db: Any | None = None, collection: str = "historical_supply") -> None:
        self._db = db
        self.collection = collection

    @property
    def db(self) -> Any:
        if self._db is None:
            from screener.db.firebase_client import get_db

            self._db = get_db()
        return self._db

    # ──────────────────────────────────────────────
    # Firestore 읽기 (composite index: ticker + date)
    # ──────────────────────────────────────────────

    def load_supply_history(self, ticker: str, days: int = 30) -> pd.DataFrame:
        """종목 수급 이력 N일치 조회.

        Args:
            ticker: 종목 코드
            days: 며칠치 (달력일 기준)

        Returns:
            DataFrame[date, foreign_holding_qty, foreign_exhaustion_pct,
                      foreign_net_buy_value, institution_net_buy_value, ...]
            date 오름차순 정렬. 빈 결과면 빈 DataFrame.
        """
        from datetime import timedelta

        from google.cloud.firestore_v1.base_query import FieldFilter

        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")

        try:
            docs = (
                self.db.collection(self.collection)
                .where(filter=FieldFilter("ticker", "==", ticker))
                .where(filter=FieldFilter("date", ">=", start_date))
                .stream()
            )
            records = [doc.to_dict() for doc in docs]
        except Exception as e:
            logger.warning(
                f"Firestore historical_supply 조회 실패 (ticker={ticker}): "
                f"{type(e).__name__}: {str(e)[:120]}"
            )
            return pd.DataFrame()

        if not records:
            return pd.DataFrame()

        df = pd.DataFrame(records)
        if "date" in df.columns:
            df = df.sort_values("date").reset_index(drop=True)
        return df

    # ──────────────────────────────────────────────
    # 5년 외국인 추이 + 통계 (korea_market.md §1.4)
    # ──────────────────────────────────────────────

    def get_foreign_5y_trend(self, ticker: str) -> dict[str, Any]:
        """종목별 5년 외국인 수급 추이 + 통계.

        Returns:
            {
                "ticker": "005930",
                "current_holding_pct": 55.12,
                "5y_avg_holding_pct": 53.4,
                "1y_change_pct_points": 1.4,
                "5y_max": 56.8,
                "5y_min": 49.2,
                "consecutive_buy_days": 4,
                "30d_net_buy": 8500000000,
                "dual_buy_days_30d": 12,
                "interpretation_signal": "increasing_above_avg",
                "data_points": 1240,
            }
            데이터 부족 시 일부 값 0 + signal="insufficient_data".
        """
        df = self.load_supply_history(ticker, days=DAYS_5Y_CALENDAR)

        if df.empty or len(df) < MIN_DAYS_FOR_SIGNAL:
            return {
                "ticker": ticker,
                "current_holding_pct": 0.0,
                "5y_avg_holding_pct": 0.0,
                "1y_change_pct_points": 0.0,
                "5y_max": 0.0,
                "5y_min": 0.0,
                "consecutive_buy_days": 0,
                "30d_net_buy": 0,
                "dual_buy_days_30d": 0,
                "interpretation_signal": "insufficient_data",
                "data_points": len(df),
            }

        # 보유 비중 통계 (foreign_exhaustion_pct가 있는 행만)
        if "foreign_exhaustion_pct" in df.columns:
            holding = df["foreign_exhaustion_pct"].dropna()
            holding = holding[holding > 0]  # 매매-only row는 0 → 제외
        else:
            holding = pd.Series(dtype=float)

        if len(holding) > 0:
            current_pct = float(holding.iloc[-1])
            avg_pct = float(holding.mean())
            max_pct = float(holding.max())
            min_pct = float(holding.min())
            # 1년 전 = 약 240 거래일 전 (없으면 첫 값)
            one_year_idx = max(0, len(holding) - 240)
            one_year_ago_pct = float(holding.iloc[one_year_idx])
            year_change = round(current_pct - one_year_ago_pct, 2)
        else:
            current_pct = avg_pct = max_pct = min_pct = year_change = 0.0

        # 매매 통계 (최근 30일)
        df_30d = df.tail(30) if len(df) > 30 else df
        consecutive = self._consecutive_buy_days_from_df(df_30d)
        net_buy_30d = self._net_buy_from_df(df_30d)
        dual_days = self._dual_buy_days_from_df(df_30d)

        signal = self._classify_signal(
            current_pct=current_pct,
            avg_pct=avg_pct,
            net_buy_30d=net_buy_30d,
            data_points=len(df),
        )

        return {
            "ticker": ticker,
            "current_holding_pct": round(current_pct, 2),
            "5y_avg_holding_pct": round(avg_pct, 2),
            "1y_change_pct_points": year_change,
            "5y_max": round(max_pct, 2),
            "5y_min": round(min_pct, 2),
            "consecutive_buy_days": consecutive,
            "30d_net_buy": net_buy_30d,
            "dual_buy_days_30d": dual_days,
            "interpretation_signal": signal,
            "data_points": len(df),
        }

    # ──────────────────────────────────────────────
    # 개별 헬퍼 (단독 호출 가능)
    # ──────────────────────────────────────────────

    def get_consecutive_buy_days(self, ticker: str, days_back: int = 30) -> int:
        """최근 외국인 연속 순매수일 (가장 최근부터 거꾸로 카운트).

        가장 최근 거래일이 순매도면 0 반환.
        """
        df = self.load_supply_history(ticker, days=days_back)
        return self._consecutive_buy_days_from_df(df)

    def get_30d_net_buy(self, ticker: str) -> int:
        """30일 외국인 누적 순매수 (원 단위 거래대금)."""
        df = self.load_supply_history(ticker, days=30)
        return self._net_buy_from_df(df)

    def get_dual_buy_signal(self, ticker: str, days_back: int = 30) -> dict[str, Any]:
        """외국인+기관 동시 순매수 신호.

        Returns:
            {"days": 12, "ratio": 0.4, "window": 30}
            ratio = days / 데이터 일수 (총 거래일이 windows보다 적을 수 있음)
        """
        df = self.load_supply_history(ticker, days=days_back)
        days = self._dual_buy_days_from_df(df)
        ratio = round(days / len(df), 3) if len(df) > 0 else 0.0
        return {"days": days, "ratio": ratio, "window": days_back}

    # ──────────────────────────────────────────────
    # 내부 계산 (DataFrame 기반, Firestore 의존 X)
    # ──────────────────────────────────────────────

    @staticmethod
    def _consecutive_buy_days_from_df(df: pd.DataFrame) -> int:
        """df에서 외국인 연속 순매수일을 가장 최근부터 카운트."""
        if df.empty or "foreign_net_buy_value" not in df.columns:
            return 0
        # date 오름차순이라고 가정 → 거꾸로 순회
        count = 0
        for v in reversed(df["foreign_net_buy_value"].tolist()):
            if v is None or v <= 0:
                break
            count += 1
        return count

    @staticmethod
    def _net_buy_from_df(df: pd.DataFrame) -> int:
        if df.empty or "foreign_net_buy_value" not in df.columns:
            return 0
        return int(df["foreign_net_buy_value"].fillna(0).sum())

    @staticmethod
    def _dual_buy_days_from_df(df: pd.DataFrame) -> int:
        if (
            df.empty
            or "foreign_net_buy_value" not in df.columns
            or "institution_net_buy_value" not in df.columns
        ):
            return 0
        f = df["foreign_net_buy_value"].fillna(0)
        i = df["institution_net_buy_value"].fillna(0)
        return int(((f > 0) & (i > 0)).sum())

    @staticmethod
    def _classify_signal(
        current_pct: float, avg_pct: float, net_buy_30d: int, data_points: int
    ) -> str:
        """interpretation_signal 5종 분류.

        - increasing_above_avg : 30일 순매수 + 보유 비중 평균 초과
        - increasing_below_avg : 30일 순매수 + 보유 비중 평균 미만
        - decreasing_above_avg : 30일 순매도 + 보유 비중 평균 초과
        - decreasing_below_avg : 30일 순매도 + 보유 비중 평균 미만
        - neutral              : 평균 차이 미미 + 30일 순매수 미미
        - insufficient_data    : 데이터 < MIN_DAYS_FOR_SIGNAL
        """
        if data_points < MIN_DAYS_FOR_SIGNAL:
            return "insufficient_data"

        avg_diff = current_pct - avg_pct
        is_neutral_avg = abs(avg_diff) < NEUTRAL_AVG_DIFF_PCT_POINTS
        is_neutral_flow = abs(net_buy_30d) < NEUTRAL_NET_BUY_KRW

        if is_neutral_avg and is_neutral_flow:
            return "neutral"

        flow_dir = "increasing" if net_buy_30d > 0 else "decreasing"
        avg_dir = "above_avg" if avg_diff > 0 else "below_avg"
        return f"{flow_dir}_{avg_dir}"


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
