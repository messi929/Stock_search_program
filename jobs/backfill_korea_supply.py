"""한국 시장 외국인/기관 수급 5년 백필 Job.

WEEK_A.md Day 1 산출물.

실행 모드:
  - sample : 100 종목 × 7일 검증 (Day 1 — 2~3분 소요, 500여 doc)
  - full   : 전체 종목 × 5년 백필 (Day 2 종료 후 야간 — ~3시간, ~1.25M doc)

사용 예:
  python -m jobs.backfill_korea_supply --mode sample
  python -m jobs.backfill_korea_supply --mode sample --dry-run
  python -m jobs.backfill_korea_supply --mode full --from 20210101 --to 20251231
  python -m jobs.backfill_korea_supply --mode sample --market KOSPI

KRX rate limit: 1초/호출 엄격 준수 (KRX는 과도한 호출 시 "LOGOUT"으로 IP 차단).
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timedelta
from typing import Iterable

import pandas as pd
from loguru import logger


# ──────────────────────────────────────────────
# 거래일 / 종목 목록 헬퍼
# ──────────────────────────────────────────────


def _parse_date(s: str) -> datetime:
    return datetime.strptime(s, "%Y%m%d")


def _format_date(d: datetime) -> str:
    return d.strftime("%Y%m%d")


def list_business_days(fromdate: str, todate: str, pykrx_module=None) -> list[str]:
    """기간 내 한국 영업일 목록 (pykrx 보유 시 정확, 미보유 시 평일만 반환).

    pykrx의 get_previous_business_days는 1.x에서 일부 케이스 버그 있음 →
    KOSPI 종목 시세로 휴장일 검출이 가장 정확하지만 호출량이 많음.
    백필 1회용이므로 평일 기준으로 시작 → 빈 응답 시 자연 skip 처리됨.
    """
    start = _parse_date(fromdate)
    end = _parse_date(todate)
    days: list[str] = []
    cur = start
    while cur <= end:
        if cur.weekday() < 5:  # 월~금
            days.append(_format_date(cur))
        cur += timedelta(days=1)
    return days


def select_sample_tickers(n: int = 100, market: str = "KOSPI") -> list[str]:
    """시총 상위 n개 종목 (FDR 활용 — 기존 시스템 패턴 재사용).

    FDR이 막히면 pykrx fallback. 둘 다 실패 시 빈 리스트 반환 → 호출 측에서 fail-fast.
    """
    try:
        import FinanceDataReader as fdr

        df = fdr.StockListing(market)
        if df is not None and len(df) > 0 and "Marcap" in df.columns:
            top = df.nlargest(n, "Marcap")
            tickers = [str(t).zfill(6) for t in top["Code"].tolist()]
            logger.info(f"FDR sample tickers ({market}): {len(tickers)} (top by Marcap)")
            return tickers
    except Exception as e:
        logger.warning(f"FDR StockListing 실패: {type(e).__name__}: {str(e)[:120]}")

    # Fallback: pykrx 종목 리스트 (시총 정렬 X)
    try:
        from pykrx import stock

        today = datetime.now().strftime("%Y%m%d")
        tickers = stock.get_market_ticker_list(date=today, market=market)
        if tickers:
            logger.warning("FDR fallback → pykrx (시총 정렬 X, 첫 n개 사용)")
            return [str(t).zfill(6) for t in tickers[:n]]
    except Exception as e:
        logger.error(f"pykrx ticker_list 실패: {type(e).__name__}: {str(e)[:120]}")

    logger.error("종목 목록 확보 실패 (FDR + pykrx 모두 실패)")
    return []


# ──────────────────────────────────────────────
# 백필 실행
# ──────────────────────────────────────────────


def run_backfill(
    fromdate: str,
    todate: str,
    markets: Iterable[str],
    sample_tickers: list[str] | None,
    sleep_sec: float,
    dry_run: bool,
    investors: Iterable[str] | None = None,
) -> dict:
    """백필 실행.

    Args:
        fromdate, todate: YYYYMMDD
        markets: ('KOSPI',) 또는 ('KOSPI', 'KOSDAQ')
        sample_tickers: None이면 보유 시계열 skip, 리스트면 해당 종목들만 보유 시계열 수집
        sleep_sec: pykrx 호출 간격
        dry_run: True면 Firestore 쓰기 skip (호출만 진행, 카운트 보고)
        investors: 수집 대상 투자자 카테고리 subset. None=CORE_INVESTORS 전체.
                   예: ("외국인",) — 외국인만 재백필(다른 카테고리는 merge=True로 보존됨).

    Returns:
        실행 통계 dict
    """
    from utils.data_collectors.korea_supply import CORE_INVESTORS, KoreaSupplyCollector

    # dry-run에서는 db 호출이 발생하지 않도록 mock 주입
    db = _DryRunDb() if dry_run else None
    collector = KoreaSupplyCollector(
        db=db, sleep_sec=sleep_sec, investors=tuple(investors) if investors else CORE_INVESTORS
    )

    business_days = list_business_days(fromdate, todate)
    total_days = len(business_days)
    logger.info(
        f"백필 시작: {fromdate}~{todate} | 영업일 {total_days} | 시장 {list(markets)} | "
        f"sleep={sleep_sec}s | dry_run={dry_run}"
    )

    # ── 단계 1: 일자별 매매 데이터 (방식 A) ──
    daily_total_docs = 0
    for i, date in enumerate(business_days, 1):
        for market in markets:
            try:
                docs = collector.collect_and_save_daily(date, market=market)
                daily_total_docs += docs
            except Exception as e:
                logger.error(
                    f"collect_and_save_daily 실패 (date={date} market={market}): "
                    f"{type(e).__name__}: {str(e)[:120]}"
                )

        if i % 5 == 0 or i == total_days:
            pct = (i / total_days) * 100
            logger.info(
                f"[방식A] day {i}/{total_days} ({pct:.1f}%) | docs={daily_total_docs} | "
                f"{collector.stats.summary()}"
            )

    # ── 단계 2: 외국인 보유 시계열 (방식 B) — sample_tickers 있을 때만 ──
    holding_total_docs = 0
    if sample_tickers:
        logger.info(f"[방식B] 외국인 보유 시계열 수집 시작: {len(sample_tickers)} 종목")
        for j, ticker in enumerate(sample_tickers, 1):
            try:
                docs = collector.collect_and_save_holding_series(ticker, fromdate, todate)
                holding_total_docs += docs
            except Exception as e:
                logger.error(
                    f"collect_and_save_holding_series 실패 (ticker={ticker}): "
                    f"{type(e).__name__}: {str(e)[:120]}"
                )

            if j % 20 == 0 or j == len(sample_tickers):
                pct = (j / len(sample_tickers)) * 100
                logger.info(
                    f"[방식B] {j}/{len(sample_tickers)} ({pct:.1f}%) | docs={holding_total_docs}"
                )

    # ── 결과 ──
    summary = {
        "fromdate": fromdate,
        "todate": todate,
        "markets": list(markets),
        "business_days": total_days,
        "sample_tickers": len(sample_tickers) if sample_tickers else 0,
        "daily_docs": daily_total_docs,
        "holding_docs": holding_total_docs,
        "stats": collector.stats.summary(),
        "dry_run": dry_run,
    }
    return summary


class _DryRunDb:
    """Firestore mock — db.collection().document() / db.batch() 인터페이스만 흉내."""

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
        logger.debug(f"[dry-run] batch.commit (ops={self._ops})")
        return None


# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="한국 시장 외국인/기관 수급 백필",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--mode",
        choices=["sample", "full"],
        default="sample",
        help="sample=100종목×7일 검증, full=전체×5년",
    )
    parser.add_argument(
        "--market",
        choices=["KOSPI", "KOSDAQ", "both"],
        default="both",
        help="대상 시장",
    )
    parser.add_argument("--from", dest="fromdate", default=None, help="YYYYMMDD (full 모드)")
    parser.add_argument("--to", dest="todate", default=None, help="YYYYMMDD (full 모드)")
    parser.add_argument("--sleep", type=float, default=1.0, help="pykrx 호출 간 sleep 초")
    parser.add_argument("--sample-size", type=int, default=100, help="sample 종목 수")
    parser.add_argument("--sample-days", type=int, default=7, help="sample 모드 영업일 수")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Firestore 쓰기 skip (호출/파싱만 검증)",
    )
    parser.add_argument(
        "--investors",
        default=None,
        help=(
            "수집할 투자자 카테고리 쉼표구분(예: '외국인' 또는 '외국인,기관합계'). "
            "기본값(미지정)=CORE_INVESTORS 전체. 외국인만 재백필 시 '외국인' 지정."
        ),
    )
    args = parser.parse_args(argv)
    investors_filter = (
        tuple(s.strip() for s in args.investors.split(",") if s.strip()) if args.investors else None
    )

    # 모드별 기본 기간 결정
    if args.mode == "sample":
        end = datetime.now() - timedelta(days=1)
        # sample_days만큼 영업일 확보 위해 약 2배 윈도우 잡고 list_business_days로 자름
        start = end - timedelta(days=args.sample_days * 2)
        fromdate = args.fromdate or _format_date(start)
        todate = args.todate or _format_date(end)

        all_days = list_business_days(fromdate, todate)
        if len(all_days) > args.sample_days:
            # 끝에서 N개 영업일만 사용
            fromdate = all_days[-args.sample_days]
            todate = all_days[-1]

        sample_tickers = select_sample_tickers(args.sample_size, market="KOSPI")
        if not sample_tickers:
            logger.error("sample 모드: 종목 목록 확보 실패 → exit")
            return 2

    else:  # full
        fromdate = args.fromdate or "20210101"
        todate = args.todate or _format_date(datetime.now() - timedelta(days=1))
        # full 모드는 보유 시계열 skip (전체 종목 × 5년 = 비현실적 호출량)
        # 별도 Job/스크립트로 분리 권장
        sample_tickers = None

    markets = ("KOSPI", "KOSDAQ") if args.market == "both" else (args.market,)

    started = time.time()
    summary = run_backfill(
        fromdate=fromdate,
        todate=todate,
        markets=markets,
        sample_tickers=sample_tickers,
        sleep_sec=args.sleep,
        dry_run=args.dry_run,
        investors=investors_filter,
    )
    elapsed = time.time() - started

    logger.info("=" * 60)
    logger.info("백필 완료")
    logger.info("=" * 60)
    for k, v in summary.items():
        logger.info(f"  {k}: {v}")
    logger.info(f"  총 소요: {elapsed:.1f}초 ({elapsed/60:.1f}분)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
