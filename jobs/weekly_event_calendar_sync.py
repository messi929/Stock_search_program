"""주간 기업 이벤트 캘린더 동기화 Job.

WEEK_C.md Day 5 산출물.

실행 시나리오 (Cloud Run Job + Cloud Scheduler):
  - 매주 일요일 22:00 KST (다음 주 캘린더 미리 갱신)
  - 한국: DART 이벤트 (와치리스트 KR 종목, 최근 2주)
  - 미국: yfinance 실적/배당 + EDGAR 8-K (와치리스트 US 종목, 최근 2주)
  - Firestore corporate_events 컬렉션에 통합

⚠️ 의존성:
  - DART_API_KEY, EDGAR_USER_AGENT 환경변수 필수
  - 미설정 시 해당 소스만 skip (다른 소스는 정상 진행)
  - ticker → CIK 매핑은 SEC 공식 company_tickers.json에서 자동 구축
    (수동 dict 불필요. EDGAR_USER_AGENT만 있으면 됨)

사용 예:
  python -m jobs.weekly_event_calendar_sync --dry-run
  python -m jobs.weekly_event_calendar_sync --kr-tickers 005930,373220
  python -m jobs.weekly_event_calendar_sync --us-tickers AAPL,RKLB --window-days 14
  python -m jobs.weekly_event_calendar_sync --no-edgar   # KR/yfinance만
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from loguru import logger


DEFAULT_KR_TICKERS: tuple[str, ...] = (
    "005930",  # 삼성전자
    "000660",  # SK하이닉스
    "035720",  # 카카오
    "035420",  # NAVER
    "207940",  # 삼성바이오로직스
)

DEFAULT_US_TICKERS: tuple[str, ...] = (
    "AAPL",
    "MSFT",
    "GOOGL",
    "NVDA",
    "RKLB",
)


FIRESTORE_BATCH_LIMIT = 490
KR_EVENTS_COLLECTION = "corporate_events"
US_EVENTS_COLLECTION = "corporate_events"  # 동일 컬렉션, market 필드로 구분


@dataclass
class WeeklyStats:
    kr_tickers_attempted: int = 0
    kr_events_collected: int = 0
    us_tickers_attempted: int = 0
    us_yfinance_events: int = 0
    us_8k_events: int = 0
    docs_written: int = 0
    started_at: float = field(default_factory=time.time)

    def elapsed_sec(self) -> float:
        return time.time() - self.started_at

    def summary(self) -> dict[str, Any]:
        return {
            "kr_tickers": self.kr_tickers_attempted,
            "kr_events": self.kr_events_collected,
            "us_tickers": self.us_tickers_attempted,
            "us_yfinance_events": self.us_yfinance_events,
            "us_8k_events": self.us_8k_events,
            "docs_written": self.docs_written,
            "elapsed_sec": round(self.elapsed_sec(), 1),
        }


class _DryRunDb:
    def collection(self, name: str):
        return _DryRunCollection(name)

    def batch(self):
        return _DryRunBatch()


class _DryRunCollection:
    def __init__(self, name: str):
        self.name = name

    def document(self, doc_id: str):
        return _DryRunDoc(self.name, doc_id)


class _DryRunDoc:
    def __init__(self, collection: str, doc_id: str):
        self.path = f"{collection}/{doc_id}"


class _DryRunBatch:
    def __init__(self):
        self._ops = 0

    def set(self, doc_ref, data, merge=False):
        self._ops += 1

    def commit(self):
        logger.debug(f"[dry-run] events batch.commit (ops={self._ops})")


def _save_records(
    db: Any, collection: str, records: list[dict[str, Any]], stats: WeeklyStats
) -> int:
    if not records:
        return 0
    col_ref = db.collection(collection)
    now_iso = datetime.now().isoformat()
    written = 0
    for chunk_start in range(0, len(records), FIRESTORE_BATCH_LIMIT):
        chunk = records[chunk_start : chunk_start + FIRESTORE_BATCH_LIMIT]
        batch = db.batch()
        for rec in chunk:
            doc_id = rec.get("_doc_id")
            if not doc_id:
                continue
            payload = {k: v for k, v in rec.items() if k != "_doc_id"}
            payload["collected_at"] = now_iso
            batch.set(col_ref.document(doc_id), payload, merge=True)
        batch.commit()
        written += len(chunk)
        stats.docs_written += len(chunk)
    return written


def collect_kr_events(
    tickers: list[str],
    bgn_de: str,
    end_de: str,
    db: Any,
    stats: WeeklyStats,
) -> None:
    """DART 기업 이벤트 수집."""
    if not os.environ.get("DART_API_KEY"):
        logger.warning("DART_API_KEY 미설정 — 한국 기업 이벤트 수집 skip")
        return

    from utils.data_collectors.dart_client import DartClient
    from utils.data_collectors.dart_event_collector import DartEventCollector

    client = DartClient()
    collector = DartEventCollector(client=client, db=db)

    records: list[dict[str, Any]] = []
    for ticker in tickers:
        stats.kr_tickers_attempted += 1
        try:
            events = collector.fetch_events_for_ticker(ticker, bgn_de, end_de)
        except Exception as e:
            logger.warning(
                f"[KR] {ticker} 이벤트 수집 실패: "
                f"{type(e).__name__}: {str(e)[:120]}"
            )
            continue
        for ev in events:
            records.append(
                {
                    **ev,
                    "market": "KR",
                    "source": "dart",
                    "_doc_id": f"KR_{ev['stock_code']}_{ev['rcept_no']}",
                }
            )
        stats.kr_events_collected += len(events)

    _save_records(db, KR_EVENTS_COLLECTION, records, stats)


def collect_us_events(
    tickers: list[str],
    since_date: str,
    db: Any,
    stats: WeeklyStats,
    *,
    cik_lookup: dict[str, str] | None = None,
) -> None:
    """yfinance 실적/배당 + EDGAR 8-K 수집.

    Args:
        cik_lookup: ticker → CIK 매핑 (사전 구축 권장. None 시 EDGAR skip).
    """
    from utils.data_collectors.yfinance_event_collector import (
        fetch_yfinance_events,
    )

    edgar_client = None
    if os.environ.get("EDGAR_USER_AGENT") and cik_lookup:
        try:
            from utils.data_collectors.edgar_collector import EdgarClient

            edgar_client = EdgarClient()
        except ValueError as e:
            logger.warning(f"EDGAR 클라이언트 초기화 실패: {e}")

    records: list[dict[str, Any]] = []
    for ticker in tickers:
        stats.us_tickers_attempted += 1

        # 1) yfinance
        yf_data = fetch_yfinance_events(ticker)
        if yf_data.get("earnings_dates") or yf_data.get("dividends"):
            records.append(
                {
                    "ticker": ticker,
                    "market": "US",
                    "source": "yfinance",
                    **yf_data,
                    "_doc_id": f"US_{ticker}_yfinance_{datetime.now().strftime('%Y%m%d')}",
                }
            )
            stats.us_yfinance_events += len(yf_data.get("earnings_dates", [])) + len(
                yf_data.get("dividends", [])
            )

        # 2) EDGAR 8-K
        if edgar_client and cik_lookup:
            cik = cik_lookup.get(ticker)
            if not cik:
                logger.debug(f"[US] {ticker} CIK 매핑 없음 — 8-K skip")
                continue
            try:
                eight_ks = edgar_client.fetch_recent_8k(cik, since_date=since_date)
            except Exception as e:
                logger.warning(
                    f"[US] {ticker} 8-K 실패: {type(e).__name__}: {str(e)[:120]}"
                )
                continue
            for ev in eight_ks:
                records.append(
                    {
                        "ticker": ticker,
                        "market": "US",
                        "source": "edgar_8k",
                        **ev,
                        "_doc_id": f"US_{ticker}_{ev['accessionNumber']}",
                    }
                )
            stats.us_8k_events += len(eight_ks)

    _save_records(db, US_EVENTS_COLLECTION, records, stats)


def build_cik_lookup(us_tickers: list[str]) -> dict[str, str]:
    """US 티커 → CIK 매핑을 SEC 공식 company_tickers.json에서 자동 구축.

    수동 cik_lookup dict 유지가 불필요. EDGAR_USER_AGENT 미설정 또는
    네트워크 오류 시 빈 dict 반환 (EDGAR 8-K 단계는 graceful skip).
    """
    if not us_tickers:
        return {}
    if not os.environ.get("EDGAR_USER_AGENT"):
        logger.warning("EDGAR_USER_AGENT 미설정 — CIK 자동 매핑 skip")
        return {}
    try:
        from utils.data_collectors.edgar_collector import EdgarClient

        client = EdgarClient()
        lookup = client.fetch_ticker_to_cik(us_tickers)
        logger.info(f"CIK 자동 매핑: {len(lookup)}/{len(us_tickers)}종목")
        return lookup
    except Exception as e:
        logger.warning(
            f"CIK 자동 매핑 실패: {type(e).__name__}: {str(e)[:120]}"
        )
        return {}


def run_weekly_sync(
    *,
    kr_tickers: list[str],
    us_tickers: list[str],
    window_days: int = 14,
    cik_lookup: dict[str, str] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    stats = WeeklyStats()
    db = _DryRunDb() if dry_run else None
    if db is None:
        from screener.db.firebase_client import get_db

        db = get_db()

    today = datetime.now()
    bgn = (today - timedelta(days=window_days)).strftime("%Y%m%d")
    end = today.strftime("%Y%m%d")
    since_iso = (today - timedelta(days=window_days)).strftime("%Y-%m-%d")

    logger.info(
        f"주간 이벤트 동기화 시작 | window={window_days}일 | "
        f"KR={len(kr_tickers)}종목 | US={len(us_tickers)}종목 | dry_run={dry_run}"
    )

    collect_kr_events(kr_tickers, bgn, end, db, stats)
    collect_us_events(us_tickers, since_iso, db, stats, cik_lookup=cik_lookup)

    summary = stats.summary()
    summary["dry_run"] = dry_run

    logger.info("=" * 60)
    logger.info("주간 이벤트 동기화 완료")
    logger.info("=" * 60)
    for k, v in summary.items():
        logger.info(f"  {k}: {v}")

    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="주간 기업 이벤트 캘린더 동기화 (DART + EDGAR + yfinance)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--kr-tickers",
        default=None,
        help="콤마 구분 한국 6자리 종목코드. 미지정 시 기본 와치리스트.",
    )
    parser.add_argument(
        "--us-tickers",
        default=None,
        help="콤마 구분 미국 티커. 미지정 시 기본 와치리스트.",
    )
    parser.add_argument(
        "--window-days",
        type=int,
        default=14,
        help="수집 윈도우 (기본 14일)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Firestore 쓰기 skip",
    )
    parser.add_argument(
        "--no-edgar",
        action="store_true",
        help="EDGAR 8-K 단계 skip (CIK 자동 매핑 생략 — KR/yfinance만 수집)",
    )
    args = parser.parse_args(argv)

    kr = (
        [t.strip() for t in args.kr_tickers.split(",") if t.strip()]
        if args.kr_tickers
        else list(DEFAULT_KR_TICKERS)
    )
    us = (
        [t.strip().upper() for t in args.us_tickers.split(",") if t.strip()]
        if args.us_tickers
        else list(DEFAULT_US_TICKERS)
    )

    # ticker → CIK 매핑을 SEC 공식 데이터에서 자동 구축 (--no-edgar 시 생략).
    cik_lookup = {} if args.no_edgar else build_cik_lookup(us)

    run_weekly_sync(
        kr_tickers=kr,
        us_tickers=us,
        window_days=args.window_days,
        cik_lookup=cik_lookup,
        dry_run=args.dry_run,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
