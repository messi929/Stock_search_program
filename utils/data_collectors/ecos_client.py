"""ECOS (한국은행 경제통계) API 클라이언트.

WEEK_B.md Day 2 산출물 — Macro PM + Korean Specialist 페르소나용 한국 매크로 인프라.

데이터 소스:
  - ECOS OpenAPI (https://ecos.bok.or.kr/api/)
  - 일일 호출 한도 100,000건
  - HTTP REST (전용 라이브러리 없음 → httpx 직접)

핵심 8개 통계 (ECOS_CODES):
  금리 3: 기준금리(M) / 국고채 3년(D) / 국고채 10년(D)
  경기 2: GDP 성장률(Q) / 산업생산(M)
  인플레 2: CPI 총지수(M) / 근원물가(M)
  통화 1: 원/달러 환율(D)

⚠️ ECOS는 시리즈가 아닌 "통계표 + 통계항목" 구조.
   stat_code(4자리) + item_code1(가변) + freq(D/M/Q/A) + 날짜 조합이 정확해야 응답.
   잘못된 조합은 빈 결과 또는 RESULT 에러 반환.

⚠️ freq별 날짜 형식 다름:
   - D: YYYYMMDD
   - M: YYYYMM
   - Q: YYYY+분기숫자 (Q1=YYYY1, Q2=YYYY2, ..., Q4=YYYY4)
   - A: YYYY

⚠️ 보안: API 키는 .env에서만. 로그/예외 시 mask_api_key_in_str로 마스킹.
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


ECOS_BASE_URL = "https://ecos.bok.or.kr/api"
DEFAULT_PAGE_SIZE = 1000  # ECOS API는 한 번에 최대 10,000건이지만 1K씩 끊는 게 안전
RATE_LIMIT_SEC = 0.3  # ECOS 일일 100K 한도, 매너 0.3초/호출


# ──────────────────────────────────────────────
# 핵심 통계 매핑 (axis_key → ECOS 통계표/항목/주기)
# ──────────────────────────────────────────────
# 출처: ECOS 사이트 (https://ecos.bok.or.kr/) 통계표 코드 조회.
# ⚠️ ECOS 통계 코드는 분기마다 변경 가능 → 분기 1회 검증 권장.

# ECOS 통계 코드는 한국은행 분류 개편으로 변경됨. 본 매핑은 2026-05-02 실호출 검증 완료.
# 분기 1회 ECOS StatisticItemList API로 코드 유효성 재확인 권장 (spec macro.md §2.4).
ECOS_CODES: dict[str, dict[str, str]] = {
    # 금리 (interest_rate)
    "base_rate": {
        "stat_code": "722Y001",
        "item_code1": "0101000",
        "item_code2": "?",
        "freq": "M",
        "category": "interest_rate",
        "description": "한국은행 기준금리 (월별, %)",
        "verified": True,
        "verified_at": "2026-05-02",
    },
    "treasury_3y": {
        # ⚠️ 2026-05 검증: 721Y001/5020000 → 빈 응답. 817Y002 (일별 시장금리)로 변경.
        "stat_code": "817Y002",
        "item_code1": "010200000",
        "item_code2": "?",
        "freq": "D",
        "category": "interest_rate",
        "description": "국고채(3년) 일별 수익률 (%)",
        "verified": True,
        "verified_at": "2026-05-02",
    },
    "treasury_10y": {
        # ⚠️ 2026-05 검증: 721Y001/5050000 → 빈 응답. 817Y002 (일별 시장금리)로 변경.
        "stat_code": "817Y002",
        "item_code1": "010210000",
        "item_code2": "?",
        "freq": "D",
        "category": "interest_rate",
        "description": "국고채(10년) 일별 수익률 (%)",
        "verified": True,
        "verified_at": "2026-05-02",
    },
    # 경기 (business_cycle)
    "gdp_yoy": {
        # 2026-06-04 재검증: 902Y015(주요국 경제성장률)/KOR → 한국 실질 GDP 성장률(분기, %).
        # StatisticSearch 확인: 2026Q1=1.694%, 2025Q4=-0.161% (전년동기대비 수준).
        "stat_code": "902Y015",
        "item_code1": "KOR",
        "item_code2": "?",
        "freq": "Q",
        "category": "business_cycle",
        "description": "한국 실질 GDP 성장률 전년동기대비 (분기, %) — 주요국 경제성장률 통계",
        "verified": True,
        "verified_at": "2026-06-04",
    },
    "kr_unemployment_rate": {
        # 2026-06-04 검증: 901Y027(경제활동인구)/I61BC(실업률, %) → 202604=2.9%.
        # 키 'kr_' 접두 — FRED unemployment_rate(UNRATE, US)와 indicator_key 충돌 방지.
        "stat_code": "901Y027",
        "item_code1": "I61BC",
        "item_code2": "?",
        "freq": "M",
        "category": "business_cycle",
        "description": "한국 실업률 (월별, %) — 경제활동인구조사",
        "verified": True,
        "verified_at": "2026-06-04",
    },
    "industrial_production": {
        # ⚠️ 2026-05 검증: I31AA → 미존재. AB00 (광공업) 사용.
        # item_code2="1" = 원계열 (vs "2" 계절조정).
        "stat_code": "901Y033",
        "item_code1": "AB00",
        "item_code2": "1",
        "freq": "M",
        "category": "business_cycle",
        "description": "광공업 생산지수 — 원계열 (월별, 2020=100)",
        "verified": True,
        "verified_at": "2026-05-02",
    },
    # 인플레 (inflation)
    "cpi_total": {
        "stat_code": "901Y009",
        "item_code1": "0",
        "item_code2": "?",
        "freq": "M",
        "category": "inflation",
        "description": "소비자물가지수 총지수 (월별, 2020=100)",
        "verified": True,
        "verified_at": "2026-05-02",
    },
    "cpi_core": {
        # ⚠️ 2026-05 검증: 901Y009/QA → INFO-200 (item_code 변경 가능성).
        # 신규 item_code 미확정 — 별도 PR에서 StatisticItemList로 갱신 필요.
        "stat_code": "901Y009",
        "item_code1": "QA",
        "item_code2": "?",
        "freq": "M",
        "category": "inflation",
        "description": "근원물가 (식품/에너지 제외, 월별) — ⚠️ item_code 갱신 필요",
        "verified": False,
        "verified_note": "item_code 무효 (2026-05-02 검증). cpi_total은 정상이므로 stat_code는 유효.",
    },
    # 통화 (currency)
    "usd_krw": {
        "stat_code": "731Y001",
        "item_code1": "0000001",
        "item_code2": "?",
        "freq": "D",
        "category": "currency",
        "description": "원/달러 평균환율 (일별, KRW)",
        "verified": True,
        "verified_at": "2026-05-02",
    },
}


def get_verified_codes() -> dict[str, dict[str, str]]:
    """verified=True인 ECOS_CODES만 반환 (운영 사용)."""
    return {k: v for k, v in ECOS_CODES.items() if v.get("verified", False)}


def get_unverified_codes() -> dict[str, dict[str, str]]:
    """verified=False인 ECOS_CODES (갱신 필요 항목)."""
    return {k: v for k, v in ECOS_CODES.items() if not v.get("verified", False)}


# ──────────────────────────────────────────────
# 보안 — API 키 마스킹 (DART/FRED 패턴 통일)
# ──────────────────────────────────────────────


# ECOS 키는 보통 20자 영숫자 (대문자/숫자 조합)
_ECOS_KEY_BARE_RE = re.compile(r"\b[A-Z0-9]{20}\b")
# URL 경로에 키가 들어가는 패턴 (/api/StatisticSearch/{key}/...)
_ECOS_KEY_URL_RE = re.compile(r"/(StatisticSearch|StatisticTableList|StatisticItemList|KeyStatisticList)/[A-Z0-9]{16,32}/")


def mask_api_key_in_str(s: str) -> str:
    """문자열에서 ECOS API 키 노출을 마스킹 (로그/예외 메시지용).

    URL 경로 + bare 20자 영숫자 패턴 둘 다 처리.
    """
    s = _ECOS_KEY_URL_RE.sub(r"/\1/***/", s)
    s = _ECOS_KEY_BARE_RE.sub("***", s)
    return s


# ──────────────────────────────────────────────
# 통계
# ──────────────────────────────────────────────


@dataclass
class ECOSStats:
    total_calls: int = 0
    successful_calls: int = 0
    empty_responses: int = 0
    failed_calls: int = 0
    started_at: float = field(default_factory=time.time)

    def elapsed_sec(self) -> float:
        return time.time() - self.started_at

    def summary(self) -> str:
        return (
            f"calls={self.total_calls} (ok={self.successful_calls}, "
            f"empty={self.empty_responses}, fail={self.failed_calls}) "
            f"elapsed={self.elapsed_sec():.1f}s"
        )


# ──────────────────────────────────────────────
# freq별 날짜 형식 변환
# ──────────────────────────────────────────────


def to_ecos_date_format(date_str: str, freq: str) -> str:
    """ISO/표준 날짜를 ECOS freq 형식으로 변환.

    Args:
        date_str: "YYYY-MM-DD" / "YYYYMMDD" / "YYYYMM" / "YYYY-Q1" 등
        freq: D / M / Q / A

    Returns:
        ECOS 호출용 형식:
          D → YYYYMMDD
          M → YYYYMM
          Q → YYYY{1~4}  (예: 2024-Q3 → "20243")
          A → YYYY
    """
    s = str(date_str).replace("-", "").replace("/", "").strip().upper()

    if freq == "D":
        # 8자리 필요. 6자리(YYYYMM) 입력이면 월말 추정 어려움 → 그대로 8자리 가정
        return s[:8] if len(s) >= 8 else s.ljust(8, "0")
    if freq == "M":
        # 6자리 (YYYYMM)
        return s[:6] if len(s) >= 6 else s.ljust(6, "0")
    if freq == "Q":
        # ECOS 분기 형식 = "YYYYQn" (예: 2025Q1). ISO 날짜는 월에서 분기 산출.
        def _validate_q(q: str) -> str:
            if q not in {"1", "2", "3", "4"}:
                raise ValueError(f"분기는 1~4만 유효: {q!r}")
            return q

        if "Q" in date_str.upper():
            year, q = date_str.upper().split("Q")
            return f"{year.replace('-', '').strip()[:4]}Q{_validate_q(q.strip()[:1])}"
        # YYYYMMDD/YYYYMM → 월(2자리)에서 분기 산출
        if len(s) >= 6 and s[:6].isdigit():
            q = (int(s[4:6]) - 1) // 3 + 1
            return f"{s[:4]}Q{q}"
        return f"{s[:4]}Q1"
    if freq == "A":
        return s[:4]
    raise ValueError(f"지원하지 않는 freq: {freq!r} (D/M/Q/A 중 하나)")


# ──────────────────────────────────────────────
# 클라이언트
# ──────────────────────────────────────────────


class ECOSClient:
    """ECOS API 호출 래퍼 (httpx sync).

    Args:
        api_key: ECOS API 키 (None 시 환경변수 ECOS_API_KEY 사용).
        base_url: ECOS API base URL.
        sleep_sec: 호출 간 sleep.
        http_client: httpx.Client (테스트 mock 주입용).
        page_size: 페이지당 행 수 (기본 1000, ECOS 최대 10000).
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = ECOS_BASE_URL,
        sleep_sec: float = RATE_LIMIT_SEC,
        http_client: Any | None = None,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> None:
        self.api_key = api_key or os.environ.get("ECOS_API_KEY", "")
        if not self.api_key:
            logger.warning("ECOS_API_KEY 미설정 — 호출 시 인증 오류 발생")
        self.base_url = base_url.rstrip("/")
        self.sleep_sec = sleep_sec
        self._http = http_client or httpx.Client(timeout=30)
        self.page_size = page_size
        self.stats = ECOSStats()

    def _sleep(self) -> None:
        time.sleep(self.sleep_sec)

    # ──────────────────────────────────────────────
    # 통계 시계열 조회 (페이지네이션 자동)
    # ──────────────────────────────────────────────

    def get_statistic_search(
        self,
        stat_code: str,
        freq: str,
        start: str,
        end: str,
        item_code1: str = "?",
        item_code2: str = "?",
        item_code3: str = "?",
        max_pages: int = 50,
    ) -> list[dict[str, Any]]:
        """통계 시계열 조회.

        Args:
            stat_code: 4자리 통계표 코드 (예: "722Y001")
            freq: D | M | Q | A
            start: ECOS 형식 (D=YYYYMMDD, M=YYYYMM, Q=YYYY+1~4, A=YYYY)
            end: 동일 형식
            item_code1: 통계항목 코드 (없으면 "?")
            max_pages: 안전 상한

        Returns:
            row dict 리스트. 빈 결과/에러 시 [].
        """
        if not self.api_key:
            logger.error("ECOS_API_KEY 없음 — 호출 불가")
            return []

        all_rows: list[dict[str, Any]] = []
        start_idx = 1

        for page in range(max_pages):
            end_idx = start_idx + self.page_size - 1
            url = (
                f"{self.base_url}/StatisticSearch/{self.api_key}/json/kr/"
                f"{start_idx}/{end_idx}/{stat_code}/{freq}/{start}/{end}/"
                f"{item_code1}/{item_code2}/{item_code3}"
            )

            self.stats.total_calls += 1
            try:
                r = self._http.get(url)
                r.raise_for_status()
                data = r.json()
            except Exception as e:
                self.stats.failed_calls += 1
                logger.warning(
                    f"ECOS 호출 실패 (stat={stat_code}, page={page}): "
                    f"{type(e).__name__}: {mask_api_key_in_str(str(e))[:160]}"
                )
                self._sleep()
                break

            # ECOS 정상: {"StatisticSearch": {"row": [...], "list_total_count": N}}
            # ECOS 에러 코드:
            #   INFO-100: 인증키 미입력
            #   INFO-150: 잘못된 인증키
            #   INFO-200: 조회 결과 없음 (정상 케이스)
            #   INFO-300: 필수 파라미터 누락
            #   ERROR-*  : 시스템 에러
            if "RESULT" in data:
                result = data["RESULT"]
                code = result.get("CODE", "")
                # 메시지에 키 echo 가능성 → 마스킹
                masked_message = mask_api_key_in_str(str(result.get("MESSAGE", "")))

                if code == "INFO-200":
                    logger.debug(f"ECOS: 조회 결과 없음 (stat={stat_code} {start}~{end})")
                elif code in ("INFO-100", "INFO-150") or code.startswith("ERROR"):
                    # 인증/시스템 에러 — failed로 분류 + error 로그 (운영 진단용)
                    self.stats.failed_calls += 1
                    self.stats.successful_calls -= 0  # 명시 (이번 호출 실패)
                    logger.error(
                        f"ECOS 인증/시스템 에러: code={code!r}, "
                        f"message={masked_message[:160]!r}, stat={stat_code}"
                    )
                else:
                    logger.warning(
                        f"ECOS API 비정상 응답: code={code!r}, "
                        f"message={masked_message[:160]!r}"
                    )
                self._sleep()
                break

            ss = data.get("StatisticSearch")
            if not ss:
                self.stats.empty_responses += 1
                logger.debug(f"ECOS 응답 비어있음 (stat={stat_code})")
                self._sleep()
                break

            self.stats.successful_calls += 1
            rows = ss.get("row", []) or []
            all_rows.extend(rows)

            # 페이지 끝 도달
            try:
                total = int(ss.get("list_total_count", len(rows)))
            except (TypeError, ValueError):
                total = len(rows)

            if end_idx >= total or not rows:
                self._sleep()
                break

            start_idx = end_idx + 1
            self._sleep()

        return all_rows

    # ──────────────────────────────────────────────
    # axis_key 기반 편의 호출
    # ──────────────────────────────────────────────

    def get_series_by_axis_key(
        self, axis_key: str, start: str, end: str
    ) -> list[dict[str, Any]]:
        """ECOS_CODES 키로 시계열 조회 + freq 자동 변환.

        Args:
            axis_key: ECOS_CODES 키 (예: "base_rate")
            start: ISO/표준 날짜 — freq에 맞춰 자동 변환
            end: 동일

        Returns:
            row dict 리스트.
        """
        meta = ECOS_CODES.get(axis_key)
        if meta is None:
            logger.warning(f"ECOS_CODES에 없는 키: {axis_key}")
            return []

        start_fmt = to_ecos_date_format(start, meta["freq"])
        end_fmt = to_ecos_date_format(end, meta["freq"])

        return self.get_statistic_search(
            stat_code=meta["stat_code"],
            freq=meta["freq"],
            start=start_fmt,
            end=end_fmt,
            item_code1=meta["item_code1"],
            item_code2=meta.get("item_code2", "?"),
        )

    # ──────────────────────────────────────────────
    # Firestore 스키마 정규화
    # ──────────────────────────────────────────────

    def normalize_to_records(
        self, axis_key: str, rows: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """ECOS row 리스트 → Firestore macro_indicators 컬렉션용 record.

        ECOS row 필드 (대표):
          - TIME: 날짜 (YYYYMMDD/YYYYMM/YYYY+분기/YYYY)
          - DATA_VALUE: 값 (str)
          - ITEM_NAME1: 항목명
          - UNIT_NAME: 단위
          - STAT_CODE / ITEM_CODE1
        """
        meta = ECOS_CODES.get(axis_key)
        if meta is None:
            logger.warning(f"normalize_to_records: 미등록 키 {axis_key}")
            return []
        if not rows:
            return []

        now_iso = datetime.now().isoformat()
        records: list[dict[str, Any]] = []

        for row in rows:
            time_str = (row.get("TIME") or "").strip()
            raw_val = row.get("DATA_VALUE")
            try:
                v = float(raw_val)
                if v != v:  # NaN
                    continue
            except (TypeError, ValueError):
                continue

            records.append(
                {
                    "indicator_key": axis_key,
                    "country": "KR",
                    "category": meta["category"],
                    "date": _normalize_ecos_date(time_str, meta["freq"]),
                    "value": round(v, 6),
                    "unit_raw": (row.get("UNIT_NAME") or "").strip(),
                    "frequency": meta["freq"],
                    "source": "ECOS",
                    "source_stat_code": meta["stat_code"],
                    "source_item_code1": meta["item_code1"],
                    "source_item_code2": meta.get("item_code2", "?"),
                    "collected_at": now_iso,
                }
            )

        return records


# ──────────────────────────────────────────────
# 유틸 (모듈 private)
# ──────────────────────────────────────────────


def _normalize_ecos_date(time_str: str, freq: str) -> str:
    """ECOS TIME 필드 → 일관된 YYYYMMDD 형식 (Firestore Doc ID 일관성).

    - D: 그대로 8자리
    - M: YYYYMM → YYYYMM01 (월초로 정규화)
    - Q: YYYY+분기 → YYYY+분기말월+01 (Q1→0331, Q2→0630, Q3→0930, Q4→1231)
    - A: YYYY → YYYY1231
    """
    s = str(time_str).strip()
    if freq == "D":
        return s[:8] if len(s) >= 8 else s
    if freq == "M":
        return s[:6] + "01" if len(s) >= 6 else s
    if freq == "Q":
        if len(s) >= 5 and s[4].isdigit():
            year = s[:4]
            q = s[4]
            quarter_end_md = {"1": "0331", "2": "0630", "3": "0930", "4": "1231"}
            return year + quarter_end_md.get(q, "1231")
        return s
    if freq == "A":
        return s[:4] + "1231" if len(s) >= 4 else s
    return s
