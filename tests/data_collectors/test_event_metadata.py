"""Day 3 산출물 단위 테스트 — JSON 스키마 + 로더 헬퍼."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from utils.data_collectors.event_metadata import (
    clear_cache,
    find_ipos_for_secondary,
    get_event_meta,
    get_high_certainty_ipos,
    load_macro_event_metadata,
    load_upcoming_ipos,
)


@pytest.fixture(autouse=True)
def _reset_cache():
    clear_cache()
    yield
    clear_cache()


# ──────────────────────────────────────────────
# 1. macro_event_metadata.json 스키마
# ──────────────────────────────────────────────


def test_macro_meta_loads():
    data = load_macro_event_metadata()
    assert "events" in data
    assert isinstance(data["events"], dict)
    assert len(data["events"]) >= 6


def test_macro_meta_required_event_types_present():
    """macro_calendar.json의 핵심 type이 모두 메타에 등록되어야 함."""
    data = load_macro_event_metadata()
    events = data["events"]
    for et in ("FOMC", "BOK_RATE", "US_CPI", "KR_CPI", "US_GDP", "US_EMPLOYMENT"):
        assert et in events, f"{et} 메타 누락"


def test_macro_meta_event_required_fields():
    """각 이벤트는 country + typical_volatility_window + 평균 수익률 필드 보유."""
    data = load_macro_event_metadata()
    for event_type, meta in data["events"].items():
        assert "country" in meta, f"{event_type} country 누락"
        assert meta["country"] in ("US", "KR", "GLOBAL"), f"{event_type} country 잘못"
        assert "typical_volatility_window" in meta, f"{event_type} window 누락"
        win = meta["typical_volatility_window"]
        assert "before" in win and "after" in win
        assert "historical_avg_abs_return_pct" in meta
        assert isinstance(meta["historical_avg_abs_return_pct"], (int, float))


def test_macro_meta_fabrication_warning_exists():
    """LEGAL: fabrication 경고는 반드시 있어야 함."""
    data = load_macro_event_metadata()
    assert "fabrication_warning" in data
    assert "추정" in data["fabrication_warning"] or "검증" in data["fabrication_warning"]


def test_get_event_meta_returns_fomc_data():
    meta = get_event_meta("FOMC")
    assert meta["country"] == "US"
    assert "typical_volatility_window" in meta


def test_get_event_meta_unknown_returns_empty():
    assert get_event_meta("NOT_EXISTING") == {}


# ──────────────────────────────────────────────
# 2. upcoming_ipo.json 스키마
# ──────────────────────────────────────────────


def test_ipo_loads():
    data = load_upcoming_ipos()
    assert "items" in data
    assert isinstance(data["items"], list)
    assert len(data["items"]) >= 5  # 최소 5개 큐레이션


def test_ipo_required_fields():
    data = load_upcoming_ipos()
    for item in data["items"]:
        assert "company" in item
        assert "expected_market" in item
        assert "expected_date_range" in item
        assert "certainty_score" in item
        assert isinstance(item["certainty_score"], int)
        assert 0 <= item["certainty_score"] <= 10
        assert "secondary_beneficiaries" in item
        assert isinstance(item["secondary_beneficiaries"], list)
        assert "added_at" in item


def test_ipo_fabrication_warning_exists():
    """LEGAL: fabrication + no_recommendation_disclaimer 둘 다 있어야 함."""
    data = load_upcoming_ipos()
    assert "fabrication_warning" in data
    assert "no_recommendation_disclaimer" in data
    assert "추천이 아닙니다" in data["no_recommendation_disclaimer"]


def test_ipo_dates_are_iso():
    """added_at은 ISO YYYY-MM-DD 형식."""
    import re

    data = load_upcoming_ipos()
    iso = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    for item in data["items"]:
        assert iso.match(item["added_at"]), f"added_at 형식 잘못: {item['added_at']}"


# ──────────────────────────────────────────────
# 3. 조회 헬퍼
# ──────────────────────────────────────────────


def test_find_ipos_for_secondary_match_us_ticker():
    """SpaceX → RKLB 매핑."""
    out = find_ipos_for_secondary("RKLB")
    assert len(out) >= 1
    assert any(it["company"] == "SpaceX" for it in out)


def test_find_ipos_for_secondary_match_kr_code():
    """6자리 한국 종목코드도 매칭 동작."""
    # data/upcoming_ipo.json: 카카오뱅크(323410) 또는 카카오(035720)
    out = find_ipos_for_secondary("323410")
    # 케이뱅크 IPO에 매핑되어 있어야 함
    assert any("케이뱅크" in it.get("company", "") for it in out)


def test_find_ipos_no_match():
    out = find_ipos_for_secondary("NOTHING_TICKER_XYZ")
    assert out == []


def test_high_certainty_filter():
    """certainty_score >= 7 IPO만 추출."""
    high = get_high_certainty_ipos(min_score=7)
    for it in high:
        assert it["certainty_score"] >= 7
    # 모든 IPO 통과 X (5건 중 일부만 7+)
    all_items = load_upcoming_ipos()["items"]
    assert len(high) <= len(all_items)


# ──────────────────────────────────────────────
# 4. JSON 파일 자체 무결성
# ──────────────────────────────────────────────


def test_macro_meta_json_is_valid_unicode():
    p = Path(__file__).resolve().parents[2] / "data" / "macro_event_metadata.json"
    with open(p, encoding="utf-8") as f:
        json.load(f)


def test_ipo_json_is_valid_unicode():
    p = Path(__file__).resolve().parents[2] / "data" / "upcoming_ipo.json"
    with open(p, encoding="utf-8") as f:
        json.load(f)
