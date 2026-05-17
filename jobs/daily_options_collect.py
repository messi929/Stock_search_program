"""일일 옵션 시그널 + 미국 공매도 수집 Job.

WEEK_C.md Day 5 산출물.

실행 시나리오 (Cloud Run Job + Cloud Scheduler):
  - 매일 06:30 KST (미국 장 마감 후 yfinance 갱신 안정화 직후)
  - 와치리스트 미국 종목 옵션 시그널 + yfinance 공매도 정보
  - Firestore options_signals 컬렉션에 저장
  - VKOSPI 시장 변동성 보조 지표

사용 예:
  python -m jobs.daily_options_collect                       # 기본 와치리스트
  python -m jobs.daily_options_collect --tickers AAPL,RKLB  # 명시 종목
  python -m jobs.daily_options_collect --dry-run

⚠️ yfinance 차단/지연 발생 가능 → 종목별 try/except, 부분 실패 허용.
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from loguru import logger

from utils.data_collectors.options_signals import (
    calculate_options_signals,
    calculate_vkospi_signal,
    clear_cache as clear_options_cache,
)


# 기본 와치리스트 (운영 시 Firestore에서 동적 로드 가능 — v1.1)
DEFAULT_TICKERS: tuple[str, ...] = (
    "AAPL",
    "MSFT",
    "GOOGL",
    "AMZN",
    "NVDA",
    "TSLA",
    "RKLB",
    "ASTS",
    "PLTR",
    "META",
)


FIRESTORE_BATCH_LIMIT = 490
FIRESTORE_COLLECTION = "options_signals"


@dataclass
class JobStats:
    tickers_attempted: int = 0
    tickers_succeeded: int = 0
    tickers_no_options: int = 0
    docs_written: int = 0
    vkospi_available: bool = False
    started_at: float = field(default_factory=time.time)

    def elapsed_sec(self) -> float:
        return time.time() - self.started_at

    def summary(self) -> dict[str, Any]:
        return {
            "tickers": f"{self.tickers_succeeded}/{self.tickers_attempted}",
            "no_options": self.tickers_no_options,
            "docs_written": self.docs_written,
            "vkospi": self.vkospi_available,
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
        logger.debug(f"[dry-run] options batch.commit (ops={self._ops})")


def _save_records(db: Any, records: list[dict[str, Any]], stats: JobStats) -> int:
    if not records:
        return 0

    col_ref = db.collection(FIRESTORE_COLLECTION)
    written = 0

    for chunk_start in range(0, len(records), FIRESTORE_BATCH_LIMIT):
        chunk = records[chunk_start : chunk_start + FIRESTORE_BATCH_LIMIT]
        batch = db.batch()
        for rec in chunk:
            ticker = rec.get("ticker")
            date = rec.get("date")
            if not ticker or not date:
                continue
            doc_id = f"{ticker}_{date}"
            batch.set(col_ref.document(doc_id), rec, merge=True)
        batch.commit()
        written += len(chunk)
        stats.docs_written += len(chunk)

    return written


def run_daily_options(
    tickers: list[str],
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    stats = JobStats()
    db = _DryRunDb() if dry_run else None
    if db is None:
        from screener.db.firebase_client import get_db

        db = get_db()

    today = datetime.now().strftime("%Y%m%d")

    # 캐시는 일일 Job에서는 새로 시작 (이전 실행 잔여 제거)
    clear_options_cache()

    records: list[dict[str, Any]] = []
    for ticker in tickers:
        stats.tickers_attempted += 1
        signal = calculate_options_signals(ticker)
        if not signal.get("available"):
            stats.tickers_no_options += 1
            logger.info(
                f"[options skip] {ticker}: {signal.get('reason', 'unknown')}"
            )
            continue
        stats.tickers_succeeded += 1
        records.append(
            {
                **signal,
                "date": today,
            }
        )

    # VKOSPI 보조
    vkospi = calculate_vkospi_signal()
    stats.vkospi_available = bool(vkospi.get("available"))
    if stats.vkospi_available:
        records.append(
            {
                "ticker": "VKOSPI",
                "date": today,
                **vkospi,
            }
        )

    _save_records(db, records, stats)

    summary = stats.summary()
    summary["dry_run"] = dry_run

    logger.info("=" * 60)
    logger.info("일일 옵션 수집 완료")
    logger.info("=" * 60)
    for k, v in summary.items():
        logger.info(f"  {k}: {v}")

    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="일일 옵션 시그널 + VKOSPI 수집",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--tickers",
        default=None,
        help="콤마 구분 미국 티커 리스트. 미지정 시 기본 와치리스트.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Firestore 쓰기 skip",
    )
    args = parser.parse_args(argv)

    tickers: list[str]
    if args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    else:
        tickers = list(DEFAULT_TICKERS)

    summary = run_daily_options(tickers, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
