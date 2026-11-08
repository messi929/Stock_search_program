"""매크로 일정 자동 수집 — 공식 출처에서 받아 macro_calendar 형식으로 합친다.

출처 (2026-11 확인):
  - FOMC      : federalreserve.gov 일정 페이지 (다음 해 일정까지 공개)
  - BOK_RATE  : bok.or.kr 통화정책방향 결정회의 연도별 페이지
  - US_CPI / US_EMPLOYMENT / US_GDP : FRED release/dates API
               (BLS 일정 페이지는 자동 요청을 403으로 막는다)
  - KR_CPI    : 국가데이터처(mods.go.kr) 통계공표일정 — 올해 분만 공개

원칙:
  - 출처별로 독립 수집. 하나가 실패해도 그 유형의 기존 일정은 그대로 둔다.
  - 수집 결과가 비정상적으로 적으면(파싱 깨짐 의심) 실패로 본다.
  - 받은 범위(연도 또는 날짜 구간) 안의 같은 유형 일정만 교체한다.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Callable

import httpx
from loguru import logger

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)
_TIMEOUT = 30.0

FOMC_URL = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
BOK_URL = (
    "https://www.bok.or.kr/portal/singl/crncyPolicyDrcMtg/listYear.do"
    "?menuNo=200755&mtgSe=A&pYear={year}"
)
KOSTAT_URL = "https://mods.go.kr/lcofNewsPln.es?mid=a60303000000"
FRED_DATES_URL = "https://api.stlouisfed.org/fred/release/dates"

# FRED release_id → (type, 이름 접두, 전월분 표기 여부)
FRED_RELEASES: dict[str, tuple[int, str, bool]] = {
    "US_CPI": (10, "미국 CPI 발표", True),
    "US_EMPLOYMENT": (50, "미국 고용보고서", True),
    "US_GDP": (53, "미국 GDP 발표", False),
}

# 연간 회의 수가 정해진 유형의 최소 건수 (이보다 적으면 파싱 실패로 본다)
_MIN_PER_YEAR = {"FOMC": 6, "BOK_RATE": 6, "KR_CPI": 10}

_MONTHS = {
    m: i
    for i, m in enumerate(
        ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"],
        start=1,
    )
}


@dataclass
class FetchResult:
    """한 출처의 수집 결과. window 안의 같은 유형 일정이 events로 교체된다."""

    type: str
    events: list[dict[str, Any]] = field(default_factory=list)
    window: tuple[str, str] | None = None  # (시작일, 종료일) ISO
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.window is not None


def _get(url: str, **kw: Any) -> httpx.Response:
    resp = httpx.get(
        url,
        headers={"User-Agent": _UA, "Accept-Language": "ko,en;q=0.8"},
        timeout=_TIMEOUT,
        follow_redirects=True,
        **kw,
    )
    resp.raise_for_status()
    return resp


def _ev(d: date, type_: str, country: str, name: str, source: str) -> dict[str, Any]:
    return {"date": d.isoformat(), "type": type_, "country": country, "name": name, "source": source}


def _year_window(years: set[int]) -> tuple[str, str]:
    return (f"{min(years)}-01-01", f"{max(years)}-12-31")


def _check_per_year(type_: str, events: list[dict[str, Any]], years: set[int]) -> str | None:
    """연도별 건수가 너무 적으면 오류 메시지. 정상이면 None."""
    minimum = _MIN_PER_YEAR.get(type_)
    if not minimum:
        return None
    for y in years:
        n = sum(1 for e in events if e["date"].startswith(str(y)))
        if n < minimum:
            return f"{y}년 {n}건(최소 {minimum}) — 페이지 구조 변경 의심"
    return None


# ──────────────────────────────────────────────
# FOMC
# ──────────────────────────────────────────────

_FOMC_TOKEN = re.compile(
    r"(?P<year>20\d{2}) FOMC Meetings"
    r"|fomc-meeting__month[^>]*>\s*(?:<strong>)?\s*(?P<month>[A-Za-z/]+)"
    r"|fomc-meeting__date[^>]*>\s*(?P<date>[^<]+)"
)


def parse_fomc(html: str, min_year: int) -> list[dict[str, Any]]:
    """Fed 일정 페이지 → 결정일(회의 마지막 날) 목록. min_year 이상만.

    날짜 표기 예: "27-28", "17-18*"(SEP 동반), 월 "Apr/May" + "30-1",
    "22 (notation vote)"·"(unscheduled)" 같은 비정례 회의는 건너뛴다.
    """
    events: list[dict[str, Any]] = []
    year: int | None = None
    month_tok: str | None = None
    for m in _FOMC_TOKEN.finditer(html):
        if m.group("year"):
            year = int(m.group("year"))
            month_tok = None
        elif m.group("month"):
            month_tok = m.group("month")
        elif m.group("date") and year and month_tok:
            raw = m.group("date").strip()
            month_name, raw_date = month_tok, raw
            month_tok = None
            if year < min_year or "(" in raw_date:
                continue
            sep = raw_date.endswith("*")
            last_day = re.findall(r"\d+", raw_date)
            last_month = month_name.split("/")[-1][:3].lower()
            if not last_day or last_month not in _MONTHS:
                continue
            d = date(year, _MONTHS[last_month], int(last_day[-1]))
            name = f"FOMC 정책결정회의 ({d.month}월)" + (" + SEP 발표" if sep else "")
            events.append(_ev(d, "FOMC", "US", name, "federalreserve.gov"))
    return sorted(events, key=lambda e: e["date"])


def fetch_fomc(today: date) -> FetchResult:
    res = FetchResult("FOMC")
    try:
        events = parse_fomc(_get(FOMC_URL).text, min_year=today.year)
        years = {int(e["date"][:4]) for e in events}
        if not years:
            raise ValueError("일정 0건")
        res.error = _check_per_year("FOMC", events, years)
        res.events, res.window = events, _year_window(years)
    except Exception as e:
        res.error = f"{type(e).__name__}: {e}"
    return res


# ──────────────────────────────────────────────
# 한국은행 금통위 (통화정책방향 결정회의)
# ──────────────────────────────────────────────

_BOK_ROW = re.compile(r'<th scope="row">\s*(\d{1,2})월\s*(\d{1,2})일')


def parse_bok(html: str, year: int) -> list[dict[str, Any]]:
    return [
        _ev(
            date(year, int(mo), int(dy)),
            "BOK_RATE",
            "KR",
            f"한국은행 금통위 기준금리 결정 ({int(mo)}월)",
            "bok.or.kr",
        )
        for mo, dy in _BOK_ROW.findall(html)
    ]


def fetch_bok(today: date) -> FetchResult:
    """올해와 내년 페이지. 내년 페이지가 아직 비어 있으면 올해만 교체한다."""
    res = FetchResult("BOK_RATE")
    try:
        events: list[dict[str, Any]] = []
        years: set[int] = set()
        for y in (today.year, today.year + 1):
            got = parse_bok(_get(BOK_URL.format(year=y)).text, y)
            if got:
                events += got
                years.add(y)
            elif y == today.year:
                raise ValueError(f"{y}년 일정 0건 — 페이지 구조 변경 의심")
        res.error = _check_per_year("BOK_RATE", events, years)
        res.events, res.window = sorted(events, key=lambda e: e["date"]), _year_window(years)
    except Exception as e:
        res.error = f"{type(e).__name__}: {e}"
    return res


# ──────────────────────────────────────────────
# 미국 CPI·고용·GDP (FRED release dates)
# ──────────────────────────────────────────────


def _prev_month(d: date) -> int:
    return 12 if d.month == 1 else d.month - 1


def fetch_fred(type_: str, today: date, api_key: str | None = None) -> FetchResult:
    """오늘 이후 공개된 발표일. 창은 [오늘, 마지막 발표일]."""
    res = FetchResult(type_)
    release_id, label, prev_month = FRED_RELEASES[type_]
    key = api_key or os.environ.get("FRED_API_KEY")
    if not key:
        res.error = "FRED_API_KEY 없음"
        return res
    try:
        data = _get(
            FRED_DATES_URL,
            params={
                "release_id": release_id,
                "api_key": key,
                "file_type": "json",
                "realtime_start": today.isoformat(),
                "realtime_end": "9999-12-31",
                "include_release_dates_with_no_data": "true",
                "sort_order": "asc",
                "limit": 50,
            },
        ).json()
        days = sorted(
            {date.fromisoformat(r["date"]) for r in data.get("release_dates", [])}
        )
        days = [d for d in days if d >= today]
        events = [
            _ev(
                d,
                type_,
                "US",
                f"{label} ({_prev_month(d)}월분)" if prev_month else label,
                "FRED",
            )
            for d in days
        ]
        if not events:
            # 공개된 향후 일정이 없을 뿐일 수 있어 기존 값을 지우지 않는다
            res.error = "향후 발표일 0건"
            return res
        res.events, res.window = events, (today.isoformat(), days[-1].isoformat())
    except Exception as e:
        res.error = f"{type(e).__name__}: {str(e).replace(key, '***')}"
    return res


# ──────────────────────────────────────────────
# 한국 CPI (국가데이터처 통계공표일정)
# ──────────────────────────────────────────────

_KOSTAT_ROW = re.compile(
    r"(20\d{2})-(\d{2})-(\d{2})\s*\(\s*[가-힣]\s*\)"  # 2026-12-02( 수 )
    r"(?:(?!20\d{2}-\d{2}-\d{2}).){0,300}?"  # 같은 행 안에서
    r"\d{4}년\s*(\d{1,2})월(?:\s*및\s*연간)?\s*소비자\s*물가\s*동향",
    re.S,
)


def parse_kostat_cpi(html: str) -> list[dict[str, Any]]:
    text = re.sub(r"<[^>]+>", " ", html)
    out = {}
    for y, mo, dy, ref in _KOSTAT_ROW.findall(text):
        d = date(int(y), int(mo), int(dy))
        out[d] = _ev(d, "KR_CPI", "KR", f"한국 CPI 발표 ({int(ref)}월분)", "mods.go.kr")
    return [out[d] for d in sorted(out)]


def fetch_kostat_cpi(today: date) -> FetchResult:
    res = FetchResult("KR_CPI")
    try:
        events = parse_kostat_cpi(_get(KOSTAT_URL).text)
        years = {int(e["date"][:4]) for e in events}
        if not years:
            raise ValueError("소비자물가동향 0건 — 페이지 구조 변경 의심")
        res.error = _check_per_year("KR_CPI", events, years)
        res.events, res.window = events, _year_window(years)
    except Exception as e:
        res.error = f"{type(e).__name__}: {e}"
    return res


# ──────────────────────────────────────────────
# 전체 수집 + 병합
# ──────────────────────────────────────────────


def fetch_all(today: date | None = None) -> list[FetchResult]:
    today = today or datetime.now().date()
    fetchers: list[Callable[[], FetchResult]] = [
        lambda: fetch_fomc(today),
        lambda: fetch_bok(today),
        lambda: fetch_kostat_cpi(today),
        *[(lambda t=t: fetch_fred(t, today)) for t in FRED_RELEASES],
    ]
    results = []
    for f in fetchers:
        r = f()
        if r.ok:
            logger.info(f"[macro-cal] {r.type}: {len(r.events)}건 (범위 {r.window[0]}~{r.window[1]})")
        else:
            logger.error(f"[macro-cal] {r.type} 수집 실패: {r.error}")
        results.append(r)
    return results


def merge_events(
    base: list[dict[str, Any]], results: list[FetchResult]
) -> tuple[list[dict[str, Any]], dict[str, dict[str, list[str]]]]:
    """성공한 출처의 범위 안 같은 유형 일정을 교체한다.

    Returns:
        (병합된 일정, 유형별 변경 {"added": [...], "removed": [...]})
    """
    events = list(base)
    changes: dict[str, dict[str, list[str]]] = {}
    for r in results:
        if not r.ok or not r.window:
            continue
        lo, hi = r.window
        in_window = lambda e: e.get("type") == r.type and lo <= e.get("date", "") <= hi  # noqa: E731
        old = {e["date"] for e in events if in_window(e)}
        new = {e["date"] for e in r.events}
        events = [e for e in events if not in_window(e)] + r.events
        added, removed = sorted(new - old), sorted(old - new)
        if added or removed:
            changes[r.type] = {"added": added, "removed": removed}
    events.sort(key=lambda e: (e.get("date", ""), e.get("type", "")))
    return events, changes
