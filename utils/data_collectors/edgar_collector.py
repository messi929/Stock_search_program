"""SEC EDGAR 8-K 등 미국 기업 주요 공시 수집 모듈.

WEEK_C.md Day 2 산출물 (Event Analyst 페르소나용).

데이터 소스: SEC EDGAR submissions API (https://data.sec.gov/submissions/CIK{...}.json)

⚠️ User-Agent 필수 — 누락 시 즉시 차단.
   환경변수 EDGAR_USER_AGENT 또는 인자로 전달 (이메일 포함 권장).
   예: "Axis Research <ops@example.com>"

⚠️ Rate limit: SEC 공식 권장 10 req/sec. 본 모듈은 0.15s sleep 보수적.

8-K Item 분류 (event_subtype):
  - 1.01 / 1.02   : 계약 체결/해지 (M&A 가능)
  - 2.01          : 자산 취득/처분 (M&A 확정)
  - 2.02          : 실적 발표
  - 5.02          : 경영진 / 이사회 변경
  - 7.01 / 8.01   : Reg FD / Other Events
  - 9.01          : 첨부 자료 (대부분 단독 사용 X)
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx
from loguru import logger


EDGAR_BASE = "https://data.sec.gov"
DEFAULT_RATE_LIMIT_SEC = 0.15  # ~6.7 req/sec (SEC 권장 10 이내, 보수적)


# 8-K Item 코드 분류
EIGHT_K_ITEM_CATEGORY: dict[str, str] = {
    "1.01": "ma_contract",
    "1.02": "ma_contract_termination",
    "1.03": "bankruptcy",
    "2.01": "asset_acquisition_disposal",
    "2.02": "earnings_release",
    "2.03": "off_balance_obligation",
    "2.04": "trigger_obligation",
    "2.05": "exit_disposal",
    "2.06": "impairment",
    "3.01": "delisting_notice",
    "3.02": "unregistered_sales",
    "3.03": "material_modification",
    "4.01": "auditor_change",
    "4.02": "non_reliance_on_financials",
    "5.01": "control_change",
    "5.02": "officer_director_change",
    "5.03": "bylaws_amendment",
    "5.07": "shareholder_vote",
    "7.01": "reg_fd",
    "8.01": "other_events",
    "9.01": "exhibits",
}


@dataclass
class EdgarStats:
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    items_classified: int = 0
    started_at: float = field(default_factory=time.time)

    def elapsed_sec(self) -> float:
        return time.time() - self.started_at


class EdgarClient:
    """SEC EDGAR submissions API 클라이언트.

    Args:
        user_agent: User-Agent 헤더 (이메일 포함). None 시 환경변수 EDGAR_USER_AGENT 사용.
                    둘 다 없으면 ValueError (SEC 정책상 차단되므로 미리 차단).
        rate_limit_sec: 호출 간 sleep.
        http_client: httpx.Client (테스트 mock 주입).
    """

    def __init__(
        self,
        user_agent: str | None = None,
        rate_limit_sec: float = DEFAULT_RATE_LIMIT_SEC,
        http_client: Any | None = None,
    ) -> None:
        ua = user_agent or os.environ.get("EDGAR_USER_AGENT", "").strip()
        if not ua:
            raise ValueError(
                "EDGAR_USER_AGENT 미설정. SEC는 User-Agent에 이메일 포함을 요구하며, "
                "누락 시 즉시 차단됩니다. 예: 'Axis Research <ops@example.com>'"
            )
        if "@" not in ua:
            logger.warning(
                "EDGAR_USER_AGENT에 이메일이 없어 보입니다. SEC 정책 위반 가능."
            )
        self.user_agent = ua
        self.rate_limit_sec = rate_limit_sec
        self._http = http_client or httpx.Client(
            timeout=30,
            headers=self._headers(),
        )
        self.stats = EdgarStats()

    def _headers(self) -> dict[str, str]:
        return {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
            # SEC 권장: Host 헤더 명시 (httpx가 자동이지만 명시적으로)
            "Accept-Encoding": "gzip, deflate",
        }

    def _sleep(self) -> None:
        time.sleep(self.rate_limit_sec)

    @staticmethod
    def _normalize_cik(cik: str | int) -> str:
        """CIK를 10자리 zero-padded로 정규화."""
        s = str(cik).strip()
        # CIK 또는 "CIK0000320193" 형태 모두 허용
        s = re.sub(r"^CIK", "", s, flags=re.IGNORECASE)
        s = s.lstrip("0")
        if not s.isdigit():
            raise ValueError(f"잘못된 CIK: {cik!r}")
        return s.zfill(10)

    def fetch_submissions(self, cik: str | int) -> dict[str, Any]:
        """submissions JSON 조회 (최근 1000건).

        Returns:
            SEC 원본 응답 dict (recent.* 필드 포함).
            네트워크/포맷 오류 시 빈 dict.
        """
        cik_padded = self._normalize_cik(cik)
        url = f"{EDGAR_BASE}/submissions/CIK{cik_padded}.json"
        self.stats.total_calls += 1
        try:
            r = self._http.get(url, headers=self._headers())
            # 헤더 누락 차단 시 보통 403
            if r.status_code == 403:
                self.stats.failed_calls += 1
                logger.error(
                    "EDGAR 403 — User-Agent 차단 가능성. "
                    f"현재 UA: {self.user_agent!r}"
                )
                self._sleep()
                return {}
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            self.stats.failed_calls += 1
            logger.warning(
                f"EDGAR submissions 호출 실패 (cik={cik_padded}): "
                f"{type(e).__name__}: {str(e)[:160]}"
            )
            self._sleep()
            return {}

        self.stats.successful_calls += 1
        self._sleep()
        return data

    def fetch_recent_8k(
        self,
        cik: str | int,
        since_date: str | None = None,
    ) -> list[dict[str, Any]]:
        """최근 8-K 공시 목록 (Item 분류 포함).

        Args:
            cik: SEC CIK.
            since_date: 이 날짜(YYYY-MM-DD) 이후만. None = 전체 최근분.

        Returns:
            [{"accessionNumber", "filingDate", "form", "items", "primaryDocument",
              "items_decoded": [(code, category), ...]}]
        """
        data = self.fetch_submissions(cik)
        if not data:
            return []

        recent = (data.get("filings") or {}).get("recent") or {}
        forms = recent.get("form", [])
        accession = recent.get("accessionNumber", [])
        filing_dates = recent.get("filingDate", [])
        items_list = recent.get("items", [])
        primary_docs = recent.get("primaryDocument", [])

        n = min(len(forms), len(accession), len(filing_dates))
        results: list[dict[str, Any]] = []
        for i in range(n):
            if forms[i] != "8-K":
                continue
            fd = filing_dates[i] if i < len(filing_dates) else ""
            if since_date and fd < since_date:
                continue
            raw_items = items_list[i] if i < len(items_list) else ""
            items_decoded = decode_8k_items(raw_items)
            self.stats.items_classified += len(items_decoded)
            results.append(
                {
                    "accessionNumber": accession[i],
                    "filingDate": fd,
                    "form": forms[i],
                    "items": raw_items,
                    "items_decoded": items_decoded,
                    "primaryDocument": (
                        primary_docs[i] if i < len(primary_docs) else ""
                    ),
                    "cik": data.get("cik"),
                    "name": data.get("name"),
                    "tickers": data.get("tickers", []),
                }
            )

        return results


# ──────────────────────────────────────────────
# 8-K Item 디코딩
# ──────────────────────────────────────────────


# Item 코드는 "X.YY" (X=한 자리). "10.01" 같은 비SEC 패턴이 "0.01"로
# 잘못 매칭되지 않도록 앞에 (?<!\d) 가드를 둠.
_ITEM_RE = re.compile(r"(?<!\d)(\d\.\d{2})(?!\d)")


def decode_8k_items(items_str: str) -> list[tuple[str, str]]:
    """SEC items 문자열에서 코드 추출 → 카테고리 매핑.

    예: "2.02,9.01" → [("2.02", "earnings_release"), ("9.01", "exhibits")]
    """
    if not items_str:
        return []
    codes = _ITEM_RE.findall(items_str)
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for code in codes:
        if code in seen:
            continue
        seen.add(code)
        category = EIGHT_K_ITEM_CATEGORY.get(code, "unknown")
        out.append((code, category))
    return out


def has_material_event(items_decoded: list[tuple[str, str]]) -> bool:
    """8-K Items 중 단순 첨부(9.01)/Reg FD(7.01) 외에 실질 이벤트가 있는지.

    9.01 또는 7.01만 있으면 보조 공시일 가능성 높음.
    """
    if not items_decoded:
        return False
    boilerplate = {"7.01", "8.01", "9.01"}
    for code, _cat in items_decoded:
        if code not in boilerplate:
            return True
    return False
