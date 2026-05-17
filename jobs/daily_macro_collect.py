"""매크로 지표 일일 수집 Job (FRED + ECOS).

WEEK_B.md Day 5 산출물.

실행 시나리오 (Cloud Run Job + Cloud Scheduler):
  - 매일 06:00 KST (미국 장 마감 직후, FRED 갱신 시간 직후) 실행
  - FRED 12 시리즈 + ECOS 6 verified 시리즈 = 18개 일일 수집
  - Firestore macro_indicators 컬렉션 저장
  - 변동 큰 지표 (정책금리 변경 등) 감지 → 로그 (알림은 v1.1)

사용 예:
  python -m jobs.daily_macro_collect                    # 어제 ~ 오늘 데이터
  python -m jobs.daily_macro_collect --dry-run         # Firestore 쓰기 skip
  python -m jobs.daily_macro_collect --series fed_funds_rate  # 단일 시리즈
  python -m jobs.daily_macro_collect --window-days 7    # 최근 7일 윈도우

Cloud Run Job 등록 (참고):
  gcloud run jobs create axis-daily-macro-collect \\
    --image=<axis-staging image> \\
    --command=python --args=-m,jobs.daily_macro_collect \\
    --set-secrets=FRED_API_KEY=fred-api-key:latest,ECOS_API_KEY=ecos-api-key:latest \\
    --region=asia-northeast3 --max-retries=2

  gcloud scheduler jobs create http daily-macro \\
    --schedule="0 21 * * *" --time-zone="UTC" \\
    --uri=<job-trigger-url>  # 06:00 KST = 21:00 UTC 전날
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from loguru import logger

from utils.data_collectors.ecos_client import (
    ECOSClient,
    get_verified_codes as get_verified_ecos_codes,
)
from utils.data_collectors.fred_client import FRED_SERIES, FREDClient


# 변동 큰 지표 감지 임계 — indicator_key별 분리 + 비교 방식 명시.
# 단위 일관성 위해 (indicator_key별 또는 fallback 카테고리별).
# comparison: "absolute" (값 차이) | "relative_pct" (%) | "absolute_pp" (%p)
SIGNIFICANT_CHANGE_RULES: dict[str, dict[str, Any]] = {
    # 정책금리 — 절대값 10bp
    "fed_funds_rate": {"threshold": 0.10, "comparison": "absolute_pp"},
    "base_rate": {"threshold": 0.10, "comparison": "absolute_pp"},
    # 통화 — DXY는 절대값(인덱스 100기준), USD/KRW는 % 변화
    "dxy_broad": {"threshold": 0.5, "comparison": "absolute"},
    "usd_krw": {"threshold": 1.0, "comparison": "relative_pct"},  # 1% 이상 변동
    # 인플레 — CPI 인덱스 0.5%p YoY 변화 의미. 그러나 본 임계는 단순 absolute
    # (단일 일자 비교용 — YoY 비교는 별도 분석 단계)
    "cpi_all": {"threshold": 1.0, "comparison": "absolute"},
    # 원자재 — 5% 변동
    "oil_wti": {"threshold": 5.0, "comparison": "relative_pct"},
}

# 카테고리별 fallback (indicator_key 미등록 시)
SIGNIFICANT_CHANGE_FALLBACK_BY_CATEGORY: dict[str, dict[str, Any]] = {
    "interest_rate": {"threshold": 0.10, "comparison": "absolute_pp"},
    "currency": {"threshold": 1.0, "comparison": "relative_pct"},
    "inflation": {"threshold": 1.0, "comparison": "absolute"},
    "business_cycle": {"threshold": 1.0, "comparison": "absolute"},
    "commodity": {"threshold": 5.0, "comparison": "relative_pct"},
}


FIRESTORE_BATCH_LIMIT = 490
FIRESTORE_COLLECTION = "macro_indicators"


@dataclass
class JobStats:
    fred_series_attempted: int = 0
    fred_series_succeeded: int = 0
    ecos_series_attempted: int = 0
    ecos_series_succeeded: int = 0
    docs_written: int = 0
    significant_changes: list[dict[str, Any]] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)

    def elapsed_sec(self) -> float:
        return time.time() - self.started_at

    def summary(self) -> dict[str, Any]:
        return {
            "fred": f"{self.fred_series_succeeded}/{self.fred_series_attempted}",
            "ecos": f"{self.ecos_series_succeeded}/{self.ecos_series_attempted}",
            "docs_written": self.docs_written,
            "significant_changes": len(self.significant_changes),
            "elapsed_sec": round(self.elapsed_sec(), 1),
        }


# ──────────────────────────────────────────────
# Firestore mock (dry-run용 — backfill_korea_supply 패턴)
# ──────────────────────────────────────────────


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
        logger.debug(f"[dry-run] batch.commit (ops={self._ops})")


# ──────────────────────────────────────────────
# 변동 감지
# ──────────────────────────────────────────────


def detect_significant_change(
    indicator_key: str, category: str, records: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """records (date 오름차순) 중 마지막 두 데이터의 변화가 임계 초과인지.

    indicator_key별 rule 우선, 미등록 시 카테고리 fallback.

    Returns:
        {indicator_key, comparison, prev_value, curr_value, change, threshold} 또는 None.
    """
    if len(records) < 2:
        return None

    rule = SIGNIFICANT_CHANGE_RULES.get(indicator_key) or \
        SIGNIFICANT_CHANGE_FALLBACK_BY_CATEGORY.get(category)
    if rule is None:
        return None

    threshold = rule["threshold"]
    comparison = rule["comparison"]

    sorted_records = sorted(records, key=lambda r: r.get("date", ""))
    prev = sorted_records[-2]
    curr = sorted_records[-1]
    prev_val = prev.get("value")
    curr_val = curr.get("value")

    if prev_val is None or curr_val is None:
        return None

    # 비교 방식별 change 계산
    if comparison == "relative_pct":
        if prev_val == 0:
            return None
        change_metric = (curr_val - prev_val) / prev_val * 100
    else:  # absolute or absolute_pp
        change_metric = curr_val - prev_val

    if abs(change_metric) < threshold:
        return None

    return {
        "indicator_key": indicator_key,
        "category": category,
        "comparison": comparison,
        "prev_date": prev.get("date"),
        "prev_value": prev_val,
        "curr_date": curr.get("date"),
        "curr_value": curr_val,
        "change": round(change_metric, 4),
        "threshold": threshold,
    }


# ──────────────────────────────────────────────
# Firestore 저장
# ──────────────────────────────────────────────


def save_records_to_firestore(
    db: Any, records: list[dict[str, Any]], stats: JobStats
) -> int:
    """records → macro_indicators 컬렉션 batch save.

    Doc ID = {indicator_key}_{date} (예: "fed_funds_rate_20260501").
    """
    if not records:
        return 0

    col_ref = db.collection(FIRESTORE_COLLECTION)
    written = 0

    for chunk_start in range(0, len(records), FIRESTORE_BATCH_LIMIT):
        chunk = records[chunk_start : chunk_start + FIRESTORE_BATCH_LIMIT]
        batch = db.batch()
        for rec in chunk:
            indicator = rec.get("indicator_key")
            date = rec.get("date")
            if not indicator or not date:
                logger.warning(f"indicator_key/date 누락 → skip: {rec}")
                continue
            doc_id = f"{indicator}_{date}"
            batch.set(col_ref.document(doc_id), rec, merge=True)
        batch.commit()
        written += len(chunk)
        stats.docs_written += len(chunk)

    return written


# ──────────────────────────────────────────────
# FRED 수집
# ──────────────────────────────────────────────


def collect_fred(
    db: Any,
    fred_client: FREDClient,
    series_keys: list[str] | None,
    window_days: int,
    stats: JobStats,
) -> None:
    keys = series_keys if series_keys else list(FRED_SERIES.keys())
    obs_start = (datetime.now() - timedelta(days=window_days)).strftime("%Y-%m-%d")

    for key in keys:
        meta = FRED_SERIES.get(key)
        if meta is None:
            logger.warning(f"FRED_SERIES에 없는 키: {key} → skip")
            continue

        stats.fred_series_attempted += 1
        try:
            series = fred_client.get_series(meta["series_id"], observation_start=obs_start)
        except Exception as e:
            logger.warning(f"FRED {key} 실패: {type(e).__name__}: {str(e)[:120]}")
            continue

        if series.empty:
            logger.debug(f"FRED {key} 빈 응답")
            continue

        records = fred_client.normalize_to_records(key, series)
        if not records:
            continue

        stats.fred_series_succeeded += 1

        # 변동 감지
        change = detect_significant_change(key, meta["category"], records)
        if change:
            logger.info(f"[변동 감지 — FRED] {change}")
            stats.significant_changes.append({"source": "FRED", **change})

        save_records_to_firestore(db, records, stats)


# ──────────────────────────────────────────────
# ECOS 수집
# ──────────────────────────────────────────────


def collect_ecos(
    db: Any,
    ecos_client: ECOSClient,
    series_keys: list[str] | None,
    window_days: int,
    stats: JobStats,
) -> None:
    verified = get_verified_ecos_codes()
    keys = series_keys if series_keys else list(verified.keys())
    keys = [k for k in keys if k in verified]  # verified만 사용

    end_date = datetime.now()
    start_date = end_date - timedelta(days=window_days)

    for key in keys:
        meta = verified[key]
        stats.ecos_series_attempted += 1

        # freq별 ISO 형식 입력 — get_series_by_axis_key가 변환
        try:
            rows = ecos_client.get_series_by_axis_key(
                key,
                start_date.strftime("%Y-%m-%d"),
                end_date.strftime("%Y-%m-%d"),
            )
        except Exception as e:
            logger.warning(f"ECOS {key} 실패: {type(e).__name__}: {str(e)[:120]}")
            continue

        if not rows:
            logger.debug(f"ECOS {key} 빈 응답")
            continue

        records = ecos_client.normalize_to_records(key, rows)
        if not records:
            continue

        stats.ecos_series_succeeded += 1

        # 변동 감지
        change = detect_significant_change(key, meta["category"], records)
        if change:
            logger.info(f"[변동 감지 — ECOS] {change}")
            stats.significant_changes.append({"source": "ECOS", **change})

        save_records_to_firestore(db, records, stats)


# ──────────────────────────────────────────────
# 메인 실행
# ──────────────────────────────────────────────


def run_daily_collect(
    series_keys: list[str] | None = None,
    window_days: int = 7,
    dry_run: bool = False,
) -> dict[str, Any]:
    """일일 매크로 수집 실행.

    Args:
        series_keys: 특정 시리즈 키만 수집 (None = 전체 verified)
        window_days: 수집 기간 (기본 7일 — 누락 보충)
        dry_run: True면 Firestore 쓰기 skip

    Returns:
        실행 통계 dict.
    """
    stats = JobStats()
    db = _DryRunDb() if dry_run else None

    if db is None:
        from screener.db.firebase_client import get_db

        db = get_db()

    fred_client = FREDClient()
    ecos_client = ECOSClient()

    logger.info(
        f"매크로 일일 수집 시작 | window={window_days}일 | "
        f"dry_run={dry_run} | series_keys={series_keys or 'all'}"
    )

    collect_fred(db, fred_client, series_keys, window_days, stats)
    collect_ecos(db, ecos_client, series_keys, window_days, stats)

    summary = stats.summary()
    summary["dry_run"] = dry_run

    logger.info("=" * 60)
    logger.info("매크로 일일 수집 완료")
    logger.info("=" * 60)
    for k, v in summary.items():
        logger.info(f"  {k}: {v}")

    if stats.significant_changes:
        logger.info(f"  변동 감지 ({len(stats.significant_changes)}건):")
        for ch in stats.significant_changes:
            logger.info(f"    - {ch}")

    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="매크로 지표 일일 수집 (FRED + ECOS)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--series",
        action="append",
        default=None,
        help="특정 시리즈 키만 수집 (반복 가능). 미지정 시 전체 verified",
    )
    parser.add_argument(
        "--window-days",
        type=int,
        default=7,
        help="수집 윈도우 (기본 7일 — 직전 1주일 누락 보충 포함)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Firestore 쓰기 skip (호출/파싱만 검증)",
    )
    args = parser.parse_args(argv)

    summary = run_daily_collect(
        series_keys=args.series,
        window_days=args.window_days,
        dry_run=args.dry_run,
    )

    # 변동 감지가 있더라도 exit 0 (Cloud Scheduler retry는 "실패" 시그널이라 비적절).
    # 알림은 Cloud Logging severity=NOTICE로 분리 — Pub/Sub 또는 Sink로 트리거 가능.
    if summary.get("significant_changes", 0) > 0:
        logger.bind(severity="NOTICE").info(
            f"매크로 변동 감지 {summary['significant_changes']}건 — "
            "Cloud Logging NOTICE 로 분리 알림 (Pub/Sub Sink 권장)"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
