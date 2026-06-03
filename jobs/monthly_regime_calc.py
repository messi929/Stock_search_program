"""매크로 사이클 + 국면 월별 재계산 Job.

WEEK_B.md Day 5 산출물.

실행 시나리오:
  - 매월 1일 06:00 KST 정기 실행
  - 매크로 발표 직후 트리거 (FOMC/BOK/CPI/GDP — Cloud Scheduler 별도)
  - Firestore macro_indicators에서 최신 매크로 지표 읽기
  - cycle_detector.detect_all_cycles() + regime_detector.detect_regime_from_cycles()
  - 결과를 macro_regime_history 컬렉션 저장 (Doc ID = "{country}_{date}")
  - 국면 전환 감지 시 로그 (알림은 v1.1)

사용 예:
  python -m jobs.monthly_regime_calc
  python -m jobs.monthly_regime_calc --dry-run
  python -m jobs.monthly_regime_calc --country KR

Cloud Run Job 등록:
  gcloud run jobs create axis-monthly-regime \\
    --image=<axis-staging image> \\
    --command=python --args=-m,jobs.monthly_regime_calc \\
    --region=asia-northeast3 --max-retries=2

  gcloud scheduler jobs create http monthly-regime \\
    --schedule="0 21 1 * *" --time-zone="UTC"  # 매월 1일 06:00 KST
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from loguru import logger

from utils.data_collectors.cycle_detector import detect_all_cycles
from utils.data_collectors.regime_detector import detect_regime_from_cycles


REGIME_HISTORY_COLLECTION = "macro_regime_history"
INDICATOR_COLLECTION = "macro_indicators"

# 사이클 입력에 필요한 indicator_key 매핑.
# ⚠️ 일부 필드 (KR unemployment, KR gdp_yoy unverified)는 미수집 → None fallback + warning.
#    monthly Job 사용자는 결과 데이터 누락 (cycle 결과 부정확) 가능성 인지.
CYCLE_INPUT_FIELDS: dict[str, dict[str, str]] = {
    "US": {
        "rate_current": "fed_funds_rate",
        "rate_3m_ago": "fed_funds_rate",
        "rate_12m_ago": "fed_funds_rate",
        "spread_10y_2y": "yield_spread_10y_2y",
        "gdp_yoy": "gdp_yoy_us",  # FRED_SERIES에 추가됨 (A191RL1Q225SBEA, freq=Q)
        "industrial_production_yoy": "industrial_production",
        "unemployment_current": "unemployment_rate",
        "unemployment_12m_ago": "unemployment_rate",
        "cpi_yoy": "cpi_all",
        "core_cpi_yoy": "cpi_core",
        "dxy_current": "dxy_broad",
        "dxy_3m_ago": "dxy_broad",
        "dxy_12m_ago": "dxy_broad",
    },
    "KR": {
        "rate_current": "base_rate",
        "rate_3m_ago": "base_rate",
        "rate_12m_ago": "base_rate",
        "gdp_yoy": "gdp_yoy",  # 2026-06-04 verified: ECOS 902Y015/KOR (전년동기대비)
        "industrial_production_yoy": "industrial_production",
        "unemployment_current": "kr_unemployment_rate",  # 2026-06-04 verified: ECOS 901Y027/I61BC
        "unemployment_12m_ago": "kr_unemployment_rate",
        "cpi_yoy": "cpi_total",
        "dxy_current": "usd_krw",  # 한국은 USD/KRW 환율로 통화 사이클 대용
        "dxy_3m_ago": "usd_krw",
        "dxy_12m_ago": "usd_krw",
    },
}

# 누락 데이터 인지용 — 결과 dict에 첨부
DATA_QUALITY_KNOWN_GAPS: dict[str, list[str]] = {
    "US": [],  # 모두 수집 가능
    "KR": [
        "gdp_yoy (ECOS 200Y002 verified=False — 한국은행 분류 개편)",
        "unemployment_current/12m_ago (ECOS_CODES 미수집)",
    ],
}


@dataclass
class JobStats:
    countries_processed: int = 0
    cycles_calculated: int = 0
    regimes_calculated: int = 0
    transitions_detected: list[dict[str, Any]] = field(default_factory=list)
    docs_written: int = 0
    started_at: float = field(default_factory=time.time)

    def elapsed_sec(self) -> float:
        return time.time() - self.started_at

    def summary(self) -> dict[str, Any]:
        return {
            "countries_processed": self.countries_processed,
            "cycles_calculated": self.cycles_calculated,
            "regimes_calculated": self.regimes_calculated,
            "transitions_detected": len(self.transitions_detected),
            "docs_written": self.docs_written,
            "elapsed_sec": round(self.elapsed_sec(), 1),
        }


# ──────────────────────────────────────────────
# Firestore mock (dry-run)
# ──────────────────────────────────────────────


class _DryRunDb:
    def __init__(self):
        self._ops = 0

    def collection(self, name: str):
        return _DryRunCollection(name, self)

    def batch(self):
        return _DryRunBatch(self)


class _DryRunCollection:
    def __init__(self, name: str, db: _DryRunDb):
        self.name = name
        self._db = db

    def document(self, doc_id: str):
        return _DryRunDoc(self.name, doc_id, self._db)

    def where(self, *args, **kwargs):
        return self  # chainable

    def order_by(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def stream(self):
        return iter([])  # dry-run: 빈 결과


class _DryRunDoc:
    def __init__(self, collection: str, doc_id: str, db: _DryRunDb):
        self.path = f"{collection}/{doc_id}"
        self._db = db

    def get(self):
        from types import SimpleNamespace
        return SimpleNamespace(exists=False, to_dict=lambda: {})


class _DryRunBatch:
    def __init__(self, db: _DryRunDb):
        self._ops = 0
        self._db = db

    def set(self, doc_ref, data, merge=False):
        self._ops += 1

    def commit(self):
        logger.debug(f"[dry-run] regime batch.commit (ops={self._ops})")


# ──────────────────────────────────────────────
# 매크로 지표 조회 (Firestore macro_indicators)
# ──────────────────────────────────────────────


def _fetch_latest_value(db: Any, indicator_key: str, days_back: int = 30) -> float | None:
    """indicator_key의 가장 최근 값 조회 (date 내림차순 1건)."""
    from google.cloud.firestore_v1.base_query import FieldFilter

    from_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y%m%d")

    try:
        docs = (
            db.collection(INDICATOR_COLLECTION)
            .where(filter=FieldFilter("indicator_key", "==", indicator_key))
            .where(filter=FieldFilter("date", ">=", from_date))
            .stream()
        )
        values = [(doc.to_dict() or {}) for doc in docs]
    except Exception as e:
        logger.warning(
            f"macro_indicators 조회 실패 ({indicator_key}): "
            f"{type(e).__name__}: {str(e)[:120]}"
        )
        return None

    if not values:
        return None

    # date 내림차순 → 가장 최근
    sorted_vals = sorted(values, key=lambda r: r.get("date", ""), reverse=True)
    val = sorted_vals[0].get("value")
    try:
        return float(val) if val is not None else None
    except (TypeError, ValueError):
        return None


def _fetch_value_at_offset(
    db: Any, indicator_key: str, days_offset: int, window_days: int = 14
) -> float | None:
    """N일 전 시점의 가장 가까운 값.

    Args:
        days_offset: target = today - days_offset
        window_days: target ± window_days 안에서 가장 가까운 record (분기 데이터는 ±45일 권장)
    """
    from google.cloud.firestore_v1.base_query import FieldFilter

    target_date = datetime.now() - timedelta(days=days_offset)
    target_str = target_date.strftime("%Y%m%d")
    window_start = (target_date - timedelta(days=window_days)).strftime("%Y%m%d")
    window_end = (target_date + timedelta(days=window_days)).strftime("%Y%m%d")

    try:
        docs = (
            db.collection(INDICATOR_COLLECTION)
            .where(filter=FieldFilter("indicator_key", "==", indicator_key))
            .where(filter=FieldFilter("date", ">=", window_start))
            .where(filter=FieldFilter("date", "<=", window_end))
            .stream()
        )
        values = [(doc.to_dict() or {}) for doc in docs]
    except Exception:
        return None

    if not values:
        return None

    # target_date에 가장 가까운 record
    closest = min(values, key=lambda r: abs(_to_int_date(r.get("date", "")) - int(target_str)))
    val = closest.get("value")
    try:
        return float(val) if val is not None else None
    except (TypeError, ValueError):
        return None


def _to_int_date(s: str) -> int:
    try:
        return int(str(s)[:8])
    except (TypeError, ValueError):
        return 0


# ──────────────────────────────────────────────
# 사이클 입력 빌드
# ──────────────────────────────────────────────


def build_cycle_inputs(
    db: Any, country: str
) -> tuple[dict[str, Any] | None, list[str]]:
    """Firestore에서 매크로 지표를 읽어 cycle_detector 입력 dict 구성.

    Returns:
        (inputs dict, missing_fields list)
        - inputs: 사이클 입력 dict (None일 때 누락 필드는 0.0 또는 fallback)
        - missing_fields: 실제 데이터 누락된 필드명 리스트 (사용자 보고용)
        둘 다 None인 경우는 country 미지원 시.
    """
    mapping = CYCLE_INPUT_FIELDS.get(country)
    if mapping is None:
        logger.error(f"지원하지 않는 country: {country}")
        return None, []

    inputs: dict[str, Any] = {}
    missing: list[str] = []

    def _fetch_or_track(field_name: str, key: str, fallback: float = 0.0) -> float:
        """fetch 시도 + None이면 missing 추적."""
        # 분기·월간 데이터는 date가 기간 시작일(분기 1/1, 월 1일)이고 발표가
        # 1~2개월 지연되므로 윈도우를 넉넉히 잡아야 최신값을 잡는다.
        meta_freq = _infer_freq_for_key(key)
        days_back = 200 if meta_freq == "Q" else 95 if meta_freq == "M" else 30
        v = _fetch_latest_value(db, key, days_back=days_back)
        if v is None:
            missing.append(field_name)
            return fallback
        return v

    def _fetch_offset_or_track(
        field_name: str, key: str, days_offset: int, fallback: float = 0.0
    ) -> float:
        meta_freq = _infer_freq_for_key(key)
        # 분기 ±60일, 월간 ±25일, 그 외 ±14일
        win = 60 if meta_freq == "Q" else 25 if meta_freq == "M" else 14
        v = _fetch_value_at_offset(db, key, days_offset, window_days=win)
        if v is None:
            missing.append(f"{field_name} (offset={days_offset}d)")
            return fallback
        return v

    # 정책금리 — 현재/3M전/12M전
    rate_key = mapping["rate_current"]
    inputs["rate_current"] = _fetch_or_track("rate_current", rate_key)
    inputs["rate_3m_ago"] = _fetch_offset_or_track(
        "rate_3m_ago", rate_key, 90, fallback=inputs["rate_current"]
    )
    inputs["rate_12m_ago"] = _fetch_offset_or_track(
        "rate_12m_ago", rate_key, 365, fallback=inputs["rate_current"]
    )

    # 스프레드 (US만)
    if "spread_10y_2y" in mapping:
        inputs["spread_10y_2y"] = _fetch_latest_value(db, mapping["spread_10y_2y"])

    # GDP / 산업생산 / 실업률 / CPI / DXY
    inputs["gdp_yoy"] = _fetch_or_track("gdp_yoy", mapping["gdp_yoy"])
    inputs["industrial_production_yoy"] = _fetch_or_track(
        "industrial_production_yoy", mapping["industrial_production_yoy"]
    )
    inputs["unemployment_current"] = _fetch_or_track(
        "unemployment_current", mapping["unemployment_current"]
    )
    inputs["unemployment_12m_ago"] = _fetch_offset_or_track(
        "unemployment_12m_ago",
        mapping["unemployment_12m_ago"],
        365,
        fallback=inputs["unemployment_current"],
    )
    inputs["cpi_yoy"] = _fetch_or_track("cpi_yoy", mapping["cpi_yoy"])
    if "core_cpi_yoy" in mapping:
        inputs["core_cpi_yoy"] = _fetch_latest_value(db, mapping["core_cpi_yoy"])

    inputs["dxy_current"] = _fetch_or_track("dxy_current", mapping["dxy_current"])
    inputs["dxy_3m_ago"] = _fetch_offset_or_track(
        "dxy_3m_ago", mapping["dxy_3m_ago"], 90, fallback=inputs["dxy_current"]
    )
    inputs["dxy_12m_ago"] = _fetch_offset_or_track(
        "dxy_12m_ago", mapping["dxy_12m_ago"], 365, fallback=inputs["dxy_current"]
    )

    if missing:
        logger.warning(
            f"{country} cycle 입력 누락 필드 {len(missing)}개 (0.0 fallback): {missing}"
        )

    return inputs, missing


def _infer_freq_for_key(indicator_key: str) -> str:
    """indicator_key → freq 추정 (FRED_SERIES + ECOS_CODES 둘 다 검색)."""
    from utils.data_collectors.fred_client import FRED_SERIES
    from utils.data_collectors.ecos_client import ECOS_CODES

    if indicator_key in FRED_SERIES:
        return FRED_SERIES[indicator_key].get("frequency", "M")
    if indicator_key in ECOS_CODES:
        return ECOS_CODES[indicator_key].get("freq", "M")
    return "M"


# ──────────────────────────────────────────────
# 국면 전환 감지
# ──────────────────────────────────────────────


def detect_regime_transition(
    db: Any, country: str, current_regime: str, exclude_date: str | None = None
) -> dict[str, Any] | None:
    """가장 최근 저장된 국면과 비교 — 전환 여부.

    Args:
        exclude_date: 비교 대상에서 제외할 date (예: 같은 일자 재실행 시
                      방금 저장한 doc을 비교 대상으로 쓰지 않도록).

    Returns:
        {previous_regime, current_regime, transition_date} 또는 None.
    """
    from google.cloud.firestore_v1.base_query import FieldFilter

    try:
        docs = (
            db.collection(REGIME_HISTORY_COLLECTION)
            .where(filter=FieldFilter("country", "==", country))
            .stream()
        )
        records = [(doc.to_dict() or {}) for doc in docs]
    except Exception as e:
        logger.warning(f"regime_history 조회 실패: {e}")
        return None

    # 같은 일자 재실행 보호: exclude_date에 해당하는 record 제외
    if exclude_date:
        records = [r for r in records if r.get("date") != exclude_date]

    if not records:
        return None

    sorted_records = sorted(records, key=lambda r: r.get("calculated_at", ""), reverse=True)
    previous = sorted_records[0].get("regime")

    if previous and previous != current_regime:
        return {
            "previous_regime": previous,
            "current_regime": current_regime,
            "transition_date": datetime.now().isoformat(),
            "country": country,
        }
    return None


# ──────────────────────────────────────────────
# 메인 실행
# ──────────────────────────────────────────────


def run_monthly_regime_calc(
    countries: list[str], dry_run: bool = False
) -> dict[str, Any]:
    """월별 사이클 + 국면 재계산.

    Args:
        countries: ["US"] | ["KR"] | ["US", "KR"]
        dry_run: True면 Firestore 쓰기 skip
    """
    stats = JobStats()

    if dry_run:
        db = _DryRunDb()
    else:
        from screener.db.firebase_client import get_db

        db = get_db()

    logger.info(f"매크로 국면 재계산 시작 | countries={countries} | dry_run={dry_run}")

    now_iso = datetime.now().isoformat()
    today_str = datetime.now().strftime("%Y%m%d")

    for country in countries:
        stats.countries_processed += 1
        logger.info(f"--- {country} 처리 ---")

        inputs, missing_fields = build_cycle_inputs(db, country)
        if inputs is None:
            logger.warning(f"{country}: 사이클 입력 빌드 실패 → skip")
            continue

        try:
            cycles = detect_all_cycles(inputs, country=country)
        except Exception as e:
            logger.error(f"{country} 사이클 계산 실패: {type(e).__name__}: {e}")
            continue
        stats.cycles_calculated += 1

        try:
            regime = detect_regime_from_cycles(cycles)
        except Exception as e:
            logger.error(f"{country} 국면 계산 실패: {type(e).__name__}: {e}")
            continue
        stats.regimes_calculated += 1

        logger.info(
            f"{country} 국면: {regime['regime']} (score={regime['regime_score']}/4, "
            f"confidence={regime['regime_confidence']})"
        )

        # 전환 감지 (같은 일자 재실행 시 방금 저장한 doc 제외)
        transition = detect_regime_transition(
            db, country, regime["regime"], exclude_date=today_str
        )
        if transition:
            logger.info(f"[국면 전환 감지] {transition}")
            stats.transitions_detected.append(transition)

        # Firestore 저장 (데이터 품질 정보 포함 — 사용자에게 신뢰도 신호)
        doc = {
            "country": country,
            "date": today_str,
            "regime": regime["regime"],
            "regime_kr": regime.get("regime_kr"),
            "regime_score": regime["regime_score"],
            "regime_confidence": regime["regime_confidence"],
            "transition_to": regime.get("transition_to"),
            "all_scores": regime.get("all_scores"),
            "cycles": {
                axis: {"stage": result["stage"], "confidence": result["confidence"]}
                for axis, result in cycles.items()
            },
            "calculated_at": now_iso,
            "transition_event": transition,
            # 데이터 품질 추적
            "missing_fields": missing_fields,
            "known_data_gaps": DATA_QUALITY_KNOWN_GAPS.get(country, []),
            "data_quality_score": round(
                1.0 - (len(missing_fields) / 13),  # 13개 필수 입력
                2,
            ),
        }
        doc_id = f"{country}_{today_str}"
        try:
            db.collection(REGIME_HISTORY_COLLECTION).document(doc_id)  # mock 대비
            batch = db.batch()
            batch.set(db.collection(REGIME_HISTORY_COLLECTION).document(doc_id), doc, merge=True)
            batch.commit()
            stats.docs_written += 1
        except Exception as e:
            logger.error(f"{country} regime_history 저장 실패: {e}")

    summary = stats.summary()
    summary["dry_run"] = dry_run

    logger.info("=" * 60)
    logger.info("매크로 국면 재계산 완료")
    logger.info("=" * 60)
    for k, v in summary.items():
        logger.info(f"  {k}: {v}")

    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="매크로 사이클 + 국면 월별 재계산",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--country",
        choices=["US", "KR", "both"],
        default="both",
        help="대상 국가 (both = 둘 다)",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    countries = ["US", "KR"] if args.country == "both" else [args.country]
    summary = run_monthly_regime_calc(countries=countries, dry_run=args.dry_run)
    return 0 if summary["regimes_calculated"] > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
