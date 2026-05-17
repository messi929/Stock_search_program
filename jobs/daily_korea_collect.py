"""한국 시장 외국인/기관 수급 일일 증분 수집 Job.

WEEK_A.md Day 2 산출물.

실행 시나리오 (Cloud Run Job + Cloud Scheduler):
  - 매일 16:30 KST 실행 (한국 장 마감 후, KRX 데이터 안정화)
  - 어제 1 영업일치만 신규 수집
  - 누락 감지: 최근 N영업일 중 Firestore에 doc 없는 날 자동 보충 (--gap-window)

사용 예:
  python -m jobs.daily_korea_collect                    # 기본: 어제 + gap 7영업일 검사
  python -m jobs.daily_korea_collect --gap-window 0    # gap 검사 끄고 어제만
  python -m jobs.daily_korea_collect --target 20251231 # 특정 일자 강제 수집
  python -m jobs.daily_korea_collect --dry-run

Cloud Run Job 등록 (참고, 실제 명령은 ROADMAP에서 확정):
  gcloud run jobs create axis-daily-korea-supply \\
    --image=<axis-staging image> \\
    --command=python --args=-m,jobs.daily_korea_collect \\
    --region=asia-northeast3 --max-retries=2

  gcloud scheduler jobs create http daily-korea-supply \\
    --schedule="30 16 * * 1-5" --time-zone="Asia/Seoul" \\
    --uri=<job-trigger-url>
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timedelta
from typing import Iterable

from loguru import logger

from jobs.backfill_korea_supply import _DryRunDb, list_business_days
from utils.data_collectors.korea_supply import KoreaSupplyCollector


def yesterday_business_day(today: datetime | None = None) -> str:
    """오늘 기준 가장 최근 영업일 (보통 어제, 월요일이면 금요일)."""
    today = today or datetime.now()
    # 가장 최근 평일 찾기 (today 자체는 제외 — 보통 16:30에 실행되어 오늘 데이터는 미반영)
    cur = today - timedelta(days=1)
    while cur.weekday() >= 5:  # 토(5), 일(6) skip
        cur -= timedelta(days=1)
    return cur.strftime("%Y%m%d")


def detect_missing_dates(
    target_dates: list[str],
    markets: Iterable[str],
    db,
    collection: str = "historical_supply",
    sample_ticker: str = "005930",
) -> list[str]:
    """target_dates 중 Firestore에 데이터가 없는 날짜만 반환.

    검사 효율을 위해 sample_ticker(시총 1위) 기준으로 doc 존재만 확인.
    실제 운영 시 ticker 마스터 100% 누락은 드물고, 대표 종목으로 충분.

    Args:
        target_dates: 검사할 날짜 리스트 (YYYYMMDD).
        markets: 시장 (KOSPI/KOSDAQ) — KOSPI에 sample_ticker가 있다고 가정.
        db: Firestore 클라이언트.
        sample_ticker: 누락 검사 기준 종목 (기본: 005930 삼성전자).

    Returns:
        Firestore에 doc 없는 날짜 리스트.
    """
    missing: list[str] = []
    col = db.collection(collection)

    for date in target_dates:
        doc_id = f"{sample_ticker}_{date}"
        try:
            doc = col.document(doc_id).get()
            exists = bool(doc.exists) if hasattr(doc, "exists") else False
        except Exception as e:
            logger.warning(
                f"Firestore exists 검사 실패 (doc_id={doc_id}): "
                f"{type(e).__name__}: {str(e)[:120]}"
            )
            exists = False

        if not exists:
            missing.append(date)

    return missing


def run_daily_collect(
    target_date: str,
    markets: Iterable[str],
    sleep_sec: float,
    dry_run: bool,
    gap_window: int,
) -> dict:
    """일일 증분 수집 실행.

    Args:
        target_date: 메인 타겟 일자 (YYYYMMDD)
        markets: ('KOSPI',) 또는 ('KOSPI', 'KOSDAQ')
        sleep_sec: pykrx 호출 간격
        dry_run: True면 Firestore 쓰기 skip
        gap_window: 누락 감지 영업일 수 (0이면 검사 끔)

    Returns:
        실행 통계 dict
    """
    db = _DryRunDb() if dry_run else None
    collector = KoreaSupplyCollector(db=db, sleep_sec=sleep_sec)

    # ── 단계 1: 누락 감지 ──
    dates_to_collect = [target_date]
    if gap_window > 0 and not dry_run:
        # 최근 gap_window 영업일 (target_date 포함하지 않고 이전)
        target_dt = datetime.strptime(target_date, "%Y%m%d")
        # 넉넉히 2배 윈도우 잡고 영업일만 자름
        from_dt = target_dt - timedelta(days=gap_window * 2)
        candidate = list_business_days(from_dt.strftime("%Y%m%d"), target_date)
        # target_date 제외하고 직전 영업일 gap_window개
        prior = [d for d in candidate if d < target_date][-gap_window:]
        if prior:
            missing = detect_missing_dates(prior, markets, collector.db)
            if missing:
                logger.info(f"누락 감지 (gap_window={gap_window}): {missing}")
                dates_to_collect = sorted(set(missing + [target_date]))
            else:
                logger.info(f"누락 감지: 최근 {len(prior)} 영업일 모두 정상")

    logger.info(
        f"일일 증분 시작: dates={dates_to_collect} | markets={list(markets)} | "
        f"sleep={sleep_sec}s | dry_run={dry_run}"
    )

    # ── 단계 2: 수집 ──
    total_docs = 0
    for date in dates_to_collect:
        for market in markets:
            try:
                docs = collector.collect_and_save_daily(
                    date, market=market, collection_phase="incremental"
                )
                total_docs += docs
            except Exception as e:
                logger.error(
                    f"collect_and_save_daily 실패 (date={date} market={market}): "
                    f"{type(e).__name__}: {str(e)[:120]}"
                )

    summary = {
        "target_date": target_date,
        "dates_collected": dates_to_collect,
        "markets": list(markets),
        "gap_window": gap_window,
        "total_docs": total_docs,
        "stats": collector.stats.summary(),
        "dry_run": dry_run,
    }
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="한국 시장 외국인/기관 수급 일일 증분 수집",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--target",
        default=None,
        help="대상 일자 (YYYYMMDD). 미지정 시 직전 영업일 자동 산정.",
    )
    parser.add_argument(
        "--market",
        choices=["KOSPI", "KOSDAQ", "both"],
        default="both",
        help="대상 시장",
    )
    parser.add_argument("--sleep", type=float, default=1.0, help="pykrx 호출 간 sleep 초")
    parser.add_argument(
        "--gap-window",
        type=int,
        default=7,
        help="누락 감지 영업일 수 (0 = 검사 끔). 백필 데이터 누락 자동 보충.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Firestore 쓰기 skip (호출 흐름만 검증). gap 검사도 자동 skip.",
    )
    args = parser.parse_args(argv)

    target = args.target or yesterday_business_day()
    markets = ("KOSPI", "KOSDAQ") if args.market == "both" else (args.market,)

    started = time.time()
    summary = run_daily_collect(
        target_date=target,
        markets=markets,
        sleep_sec=args.sleep,
        dry_run=args.dry_run,
        gap_window=args.gap_window,
    )
    elapsed = time.time() - started

    logger.info("=" * 60)
    logger.info("일일 증분 완료")
    logger.info("=" * 60)
    for k, v in summary.items():
        logger.info(f"  {k}: {v}")
    logger.info(f"  총 소요: {elapsed:.1f}초")
    return 0


if __name__ == "__main__":
    sys.exit(main())
