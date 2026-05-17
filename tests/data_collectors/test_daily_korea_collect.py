"""jobs/daily_korea_collect.py 단위 테스트.

핵심 검증:
  1. yesterday_business_day: 주말/평일 별 직전 영업일 산정
  2. detect_missing_dates: Firestore exists 검사 + 누락 리스트 반환
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from jobs.daily_korea_collect import detect_missing_dates, yesterday_business_day


# ──────────────────────────────────────────────
# yesterday_business_day
# ──────────────────────────────────────────────


def test_yesterday_business_day_from_tuesday_returns_monday():
    today = datetime(2025, 12, 30)  # 화요일
    assert yesterday_business_day(today) == "20251229"  # 월요일


def test_yesterday_business_day_from_monday_returns_friday():
    today = datetime(2025, 12, 29)  # 월요일
    assert yesterday_business_day(today) == "20251226"  # 직전 금요일


def test_yesterday_business_day_from_sunday_returns_friday():
    today = datetime(2025, 12, 28)  # 일요일
    assert yesterday_business_day(today) == "20251226"  # 직전 금요일


def test_yesterday_business_day_from_saturday_returns_friday():
    today = datetime(2025, 12, 27)  # 토요일
    assert yesterday_business_day(today) == "20251226"  # 직전 금요일


# ──────────────────────────────────────────────
# detect_missing_dates
# ──────────────────────────────────────────────


def _mk_db_with_existing(existing_doc_ids: set[str]) -> MagicMock:
    """Firestore mock: existing_doc_ids에 있는 doc만 exists=True."""
    db = MagicMock()

    def _document_factory(doc_id: str):
        doc = SimpleNamespace(exists=(doc_id in existing_doc_ids))
        getter = MagicMock()
        getter.get.return_value = doc
        return getter

    db.collection.return_value.document.side_effect = _document_factory
    return db


def test_detect_missing_dates_all_present():
    """모든 날짜의 sample_ticker doc이 존재하면 빈 리스트."""
    target_dates = ["20251229", "20251230", "20251231"]
    existing = {f"005930_{d}" for d in target_dates}
    db = _mk_db_with_existing(existing)

    missing = detect_missing_dates(target_dates, ["KOSPI"], db)

    assert missing == []


def test_detect_missing_dates_partial_missing():
    """일부 누락 시 누락 날짜만 반환."""
    target_dates = ["20251229", "20251230", "20251231"]
    existing = {"005930_20251229", "005930_20251231"}  # 30일 누락
    db = _mk_db_with_existing(existing)

    missing = detect_missing_dates(target_dates, ["KOSPI"], db)

    assert missing == ["20251230"]


def test_detect_missing_dates_all_missing():
    target_dates = ["20251229", "20251230"]
    db = _mk_db_with_existing(set())  # 아무것도 존재 X

    missing = detect_missing_dates(target_dates, ["KOSPI"], db)

    assert missing == ["20251229", "20251230"]


def test_detect_missing_dates_handles_firestore_exception():
    """Firestore 호출 예외 시 해당 date는 missing으로 분류 (안전 측)."""
    db = MagicMock()
    db.collection.return_value.document.side_effect = ConnectionError("network")

    missing = detect_missing_dates(["20251230"], ["KOSPI"], db)

    assert missing == ["20251230"]


def test_detect_missing_dates_custom_sample_ticker():
    """sample_ticker 인자로 다른 종목 지정 가능."""
    target_dates = ["20251230"]
    existing = {"000660_20251230"}  # SK하이닉스만 존재
    db = _mk_db_with_existing(existing)

    missing_default = detect_missing_dates(target_dates, ["KOSPI"], db)
    missing_custom = detect_missing_dates(
        target_dates, ["KOSPI"], db, sample_ticker="000660"
    )

    assert missing_default == ["20251230"]  # 005930이 없어서 missing 분류
    assert missing_custom == []  # 000660은 있어서 not missing
