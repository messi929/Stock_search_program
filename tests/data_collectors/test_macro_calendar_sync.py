"""매크로 일정 자동 수집 — 파서·병합·로더 단위 테스트 (네트워크 없음)."""

from __future__ import annotations

from datetime import date

import pytest

from utils.data_collectors import macro_calendar_sync as mcs
from utils.data_collectors import regime_detector as rd

FOMC_HTML = """
<h4>2026 FOMC Meetings</h4>
<div class="fomc-meeting__month col-xs-5"><strong>January</strong></div>
<div class="fomc-meeting__date col-xs-4">27-28</div>
<div class="fomc-meeting__month col-xs-5"><strong>March</strong></div>
<div class="fomc-meeting__date col-xs-4">17-18*</div>
<div class="fomc-meeting__month col-xs-5"><strong>Apr/May</strong></div>
<div class="fomc-meeting__date col-xs-4">30-1</div>
<div class="fomc-meeting__month col-xs-5"><strong>August</strong></div>
<div class="fomc-meeting__date col-xs-4">22 (notation vote)</div>
<h4>2025 FOMC Meetings</h4>
<div class="fomc-meeting__month col-xs-5"><strong>December</strong></div>
<div class="fomc-meeting__date col-xs-4">9-10*</div>
<h4>2027 FOMC Meetings</h4>
<div class="fomc-meeting__month col-xs-5"><strong>January</strong></div>
<div class="fomc-meeting__date col-xs-4">26-27</div>
"""


def test_parse_fomc_uses_last_day_and_skips_unscheduled():
    ev = mcs.parse_fomc(FOMC_HTML, min_year=2026)
    assert [e["date"] for e in ev] == ["2026-01-28", "2026-03-18", "2026-05-01", "2027-01-27"]
    assert ev[1]["name"].endswith("+ SEP 발표")
    assert "SEP" not in ev[0]["name"]
    assert all(e["type"] == "FOMC" and e["country"] == "US" for e in ev)


def test_parse_bok_rows():
    html = '<th scope="row">01월 15일(목)</th><td>x</td><th scope="row">11월 26일(목)</th>'
    ev = mcs.parse_bok(html, 2026)
    assert [e["date"] for e in ev] == ["2026-01-15", "2026-11-26"]
    assert ev[1]["name"] == "한국은행 금통위 기준금리 결정 (11월)"


def test_parse_kostat_cpi_only_cpi_rows():
    html = """
    <tr><td>2026-02-03( 화 )</td><td>2026년 1월 소비자물가 동향</td></tr>
    <tr><td>2026-02-11( 수 )</td><td>2026년 1월 고용동향</td></tr>
    <tr><td>2026-12-31( 목 )</td><td>2026년 12월 및 연간 소비자물가동향</td></tr>
    """
    ev = mcs.parse_kostat_cpi(html)
    assert [(e["date"], e["name"]) for e in ev] == [
        ("2026-02-03", "한국 CPI 발표 (1월분)"),
        ("2026-12-31", "한국 CPI 발표 (12월분)"),
    ]


def test_check_per_year_flags_broken_page():
    few = [{"date": "2026-01-28"}]
    assert mcs._check_per_year("FOMC", few, {2026}) is not None
    eight = [{"date": f"2026-{m:02d}-01"} for m in range(1, 9)]
    assert mcs._check_per_year("FOMC", eight, {2026}) is None


def _r(type_, dates, window, error=None):
    return mcs.FetchResult(
        type=type_,
        events=[{"date": d, "type": type_, "country": "US", "name": type_} for d in dates],
        window=window,
        error=error,
    )


def test_merge_replaces_only_inside_window_and_type():
    base = [
        {"date": "2025-12-10", "type": "FOMC"},  # 범위 밖 → 유지
        {"date": "2026-12-17", "type": "FOMC"},  # 범위 안 → 교체
        {"date": "2026-11-26", "type": "BOK_RATE"},  # 다른 유형 → 유지
    ]
    merged, changes = mcs.merge_events(
        base, [_r("FOMC", ["2026-12-09"], ("2026-01-01", "2026-12-31"))]
    )
    assert [(e["date"], e["type"]) for e in merged] == [
        ("2025-12-10", "FOMC"),
        ("2026-11-26", "BOK_RATE"),
        ("2026-12-09", "FOMC"),
    ]
    assert changes == {"FOMC": {"added": ["2026-12-09"], "removed": ["2026-12-17"]}}


def test_merge_keeps_existing_when_source_failed():
    base = [{"date": "2026-11-13", "type": "US_CPI"}]
    merged, changes = mcs.merge_events(base, [_r("US_CPI", [], None, error="403")])
    assert merged == base and changes == {}


def test_fetch_fred_without_key(monkeypatch):
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    r = mcs.fetch_fred("US_CPI", date(2026, 11, 8))
    assert not r.ok and "FRED_API_KEY" in r.error


def test_fetch_fred_masks_key_in_error(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("bad url ...api_key=SECRET123...")

    monkeypatch.setattr(mcs, "_get", boom)
    r = mcs.fetch_fred("US_CPI", date(2026, 11, 8), api_key="SECRET123")
    assert "SECRET123" not in r.error


def test_fetch_bok_tolerates_empty_next_year(monkeypatch):
    rows = "".join(f'<th scope="row">{m:02d}월 10일(목)</th>' for m in range(1, 9))

    class Resp:
        def __init__(self, text):
            self.text = text

    monkeypatch.setattr(
        mcs, "_get", lambda url, **k: Resp(rows if "pYear=2026" in url else "<html></html>")
    )
    r = mcs.fetch_bok(date(2026, 11, 8))
    assert r.ok and r.window == ("2026-01-01", "2026-12-31") and len(r.events) == 8


class TestLoaderRemote:
    def setup_method(self):
        rd.reset_calendar_cache()

    def teardown_method(self):
        rd.reset_calendar_cache()

    def test_remote_preferred_when_enabled(self, monkeypatch):
        monkeypatch.setenv("MACRO_CALENDAR_REMOTE", "1")
        remote = {"_meta": {"synced_at": "x"}, "events": [{"date": "2099-01-01", "type": "FOMC"}]}
        monkeypatch.setattr(rd, "_fetch_remote_calendar", lambda: remote)
        assert rd._load_calendar() is remote

    def test_file_fallback_when_remote_missing(self, monkeypatch):
        monkeypatch.setenv("MACRO_CALENDAR_REMOTE", "1")
        monkeypatch.setattr(rd, "_fetch_remote_calendar", lambda: None)
        assert rd._load_calendar().get("events")

    def test_remote_disabled_never_called(self, monkeypatch):
        def fail():
            raise AssertionError("remote should not be called")

        monkeypatch.setattr(rd, "_fetch_remote_calendar", fail)
        assert rd._load_calendar().get("events")

    def test_cache_expires_after_ttl(self, monkeypatch):
        monkeypatch.setenv("MACRO_CALENDAR_REMOTE", "1")
        calls = []
        monkeypatch.setattr(
            rd, "_fetch_remote_calendar",
            lambda: calls.append(1) or {"events": [{"date": "2099-01-01", "type": "FOMC"}]},
        )
        rd._load_calendar()
        rd._load_calendar()
        assert len(calls) == 1
        monkeypatch.setattr(rd, "_calendar_loaded_at", rd._calendar_loaded_at - rd._CALENDAR_TTL_SEC - 1)
        rd._load_calendar()
        assert len(calls) == 2


@pytest.mark.integration
def test_live_sources_parse():
    """실제 출처 접근 확인 — pytest --run-integration"""
    today = date.today()
    assert mcs.fetch_fomc(today).ok
    assert mcs.fetch_bok(today).ok
    assert mcs.fetch_kostat_cpi(today).ok
