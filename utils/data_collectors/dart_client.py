"""DART OpenAPI 클라이언트.

WEEK_A.md Day 4 산출물 (자사주 공시 모듈의 의존성).

DART (전자공시시스템) 활용:
  - 공시 목록 조회 (list.json) — 페이지네이션 자동 처리
  - 종목코드 ↔ 회사고유코드 매핑 (corpCode.xml — ZIP 압축)

API 인증: 환경변수 DART_API_KEY (.env)
일일 호출 한도: 10,000건
Rate limit: 권장 0.5~1초/호출 (자체 정책)

⚠️ 보안: API 키는 절대 commit/log에 노출 X. 응답 url에서도 자동 마스킹 권장.
"""

from __future__ import annotations

import io
import os
import re
import time
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from typing import Any

import httpx
from loguru import logger


DART_BASE_URL = "https://opendart.fss.or.kr/api"
DEFAULT_PAGE_COUNT = 100  # DART API 최대 100/페이지
RATE_LIMIT_SEC = 0.5  # 일일 한도 10K, 5초/회 = 충분


@dataclass
class DartStats:
    """호출 통계."""

    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    started_at: float = field(default_factory=time.time)

    def elapsed_sec(self) -> float:
        return time.time() - self.started_at

    def summary(self) -> str:
        return (
            f"calls={self.total_calls} "
            f"(ok={self.successful_calls}, fail={self.failed_calls}) "
            f"elapsed={self.elapsed_sec():.1f}s"
        )


class DartClient:
    """DART OpenAPI 호출 래퍼.

    Args:
        api_key: DART API 키 (None 시 환경변수 DART_API_KEY 사용).
        base_url: DART API base URL.
        sleep_sec: 호출 간 sleep.
        http_client: httpx.Client (테스트 mock 주입용).
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = DART_BASE_URL,
        sleep_sec: float = RATE_LIMIT_SEC,
        http_client: Any | None = None,
    ) -> None:
        self.api_key = api_key or os.environ.get("DART_API_KEY", "")
        if not self.api_key:
            logger.warning("DART_API_KEY 미설정 — 호출 시 401/103 응답 가능")
        self.base_url = base_url.rstrip("/")
        self.sleep_sec = sleep_sec
        self._http = http_client or httpx.Client(timeout=30)
        self._corp_code_cache: dict[str, dict[str, str]] | None = None
        self.stats = DartStats()

    def _sleep(self) -> None:
        time.sleep(self.sleep_sec)

    # ──────────────────────────────────────────────
    # 공시 목록 조회 (페이지네이션 자동)
    # ──────────────────────────────────────────────

    def fetch_disclosures(
        self,
        corp_code: str | None = None,
        bgn_de: str | None = None,
        end_de: str | None = None,
        max_pages: int = 50,
        extra_params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """공시 목록을 페이지네이션 자동으로 모두 가져옴.

        Args:
            corp_code: 8자리 회사고유코드 (None이면 전체 종목)
            bgn_de: 시작일 YYYYMMDD
            end_de: 종료일 YYYYMMDD
            max_pages: 안전 상한 (기본 50 = 5,000건)
            extra_params: 추가 query parameters (예: pblntf_ty)

        Returns:
            공시 dict 리스트. 빈 결과면 [].
        """
        if not self.api_key:
            logger.error("DART_API_KEY 없음 — fetch_disclosures 호출 불가")
            return []

        all_items: list[dict[str, Any]] = []
        page_no = 1

        while page_no <= max_pages:
            params: dict[str, Any] = {
                "crtfc_key": self.api_key,
                "page_no": str(page_no),
                "page_count": str(DEFAULT_PAGE_COUNT),
            }
            if corp_code:
                params["corp_code"] = corp_code
            if bgn_de:
                params["bgn_de"] = bgn_de
            if end_de:
                params["end_de"] = end_de
            if extra_params:
                params.update(extra_params)

            self.stats.total_calls += 1
            try:
                r = self._http.get(f"{self.base_url}/list.json", params=params)
                r.raise_for_status()
                data = r.json()
            except Exception as e:
                self.stats.failed_calls += 1
                logger.warning(
                    f"DART list.json 호출 실패 (page={page_no}): "
                    f"{type(e).__name__}: {str(e)[:120]}"
                )
                self._sleep()
                break

            status = data.get("status")
            if status != "000":
                # "013" = 조회된 데이터 없음 (정상)
                if status == "013":
                    logger.debug(f"DART: 조회 결과 없음 (corp_code={corp_code}, {bgn_de}~{end_de})")
                else:
                    logger.warning(
                        f"DART API 비정상 응답: status={status!r}, message={data.get('message')!r}"
                    )
                self._sleep()
                break

            self.stats.successful_calls += 1
            items = data.get("list", []) or []
            all_items.extend(items)

            # 페이지 끝 도달
            total_page = int(data.get("total_page", 1))
            if page_no >= total_page or not items:
                self._sleep()
                break

            page_no += 1
            self._sleep()

        return all_items

    # ──────────────────────────────────────────────
    # 회사고유코드 매핑 (1회 다운로드 + 캐시)
    # ──────────────────────────────────────────────

    def get_corp_code_map(self, force_refresh: bool = False) -> dict[str, dict[str, str]]:
        """corpCode.xml ZIP 다운로드 → {stock_code: {corp_code, corp_name}} 매핑.

        Args:
            force_refresh: True면 캐시 무시하고 재다운로드.

        Returns:
            {stock_code: {"corp_code": "00126380", "corp_name": "삼성전자"}}
            stock_code 미부여 회사 (비상장 등)는 제외.
        """
        if self._corp_code_cache is not None and not force_refresh:
            return self._corp_code_cache

        if not self.api_key:
            logger.error("DART_API_KEY 없음 — get_corp_code_map 호출 불가")
            return {}

        self.stats.total_calls += 1
        try:
            r = self._http.get(
                f"{self.base_url}/corpCode.xml",
                params={"crtfc_key": self.api_key},
                timeout=60,
            )
            r.raise_for_status()
        except Exception as e:
            self.stats.failed_calls += 1
            logger.error(f"corpCode.xml 다운로드 실패: {type(e).__name__}: {str(e)[:120]}")
            return {}

        if r.content[:2] != b"PK":
            self.stats.failed_calls += 1
            logger.error(f"corpCode 응답이 ZIP 아님 (content-type={r.headers.get('content-type')})")
            return {}

        # ZIP 압축 해제
        try:
            with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                xml_data = z.read(z.namelist()[0]).decode("utf-8")
        except Exception as e:
            self.stats.failed_calls += 1
            logger.error(f"corpCode ZIP 압축 해제 실패: {type(e).__name__}: {e}")
            return {}

        # XML 파싱 → stock_code 매핑
        mapping: dict[str, dict[str, str]] = {}
        try:
            root = ET.fromstring(xml_data)
        except ET.ParseError as e:
            self.stats.failed_calls += 1
            logger.error(f"corpCode XML 파싱 실패: {e}")
            return {}

        for entry in root.findall("list"):
            stock_code = (entry.findtext("stock_code") or "").strip()
            corp_code = (entry.findtext("corp_code") or "").strip()
            corp_name = (entry.findtext("corp_name") or "").strip()
            if stock_code and corp_code:
                # stock_code는 6자리 zero-padded
                stock_code = stock_code.zfill(6)
                # 동일 stock_code에 여러 corp_code 매핑되는 경우, 마지막 것 유지
                # (실무: 존속회사가 마지막에 등록되는 패턴)
                mapping[stock_code] = {"corp_code": corp_code, "corp_name": corp_name}

        self.stats.successful_calls += 1
        self._corp_code_cache = mapping
        logger.info(f"corpCode 매핑 캐시 구축: {len(mapping)} 종목 (xml {len(xml_data)} chars)")
        self._sleep()
        return mapping

    def corp_code_for_stock(self, stock_code: str) -> str | None:
        """6자리 종목코드 → 8자리 DART 회사고유코드.

        Returns:
            corp_code 또는 None (매핑 없음 = 비상장/상장폐지).
        """
        mapping = self.get_corp_code_map()
        entry = mapping.get(str(stock_code).zfill(6))
        return entry["corp_code"] if entry else None


# ──────────────────────────────────────────────
# 보조 유틸
# ──────────────────────────────────────────────


_API_KEY_RE = re.compile(r"crtfc_key=[a-f0-9]{40}", re.IGNORECASE)


def mask_api_key_in_str(s: str) -> str:
    """문자열에서 DART API 키 노출을 마스킹 (로그/예외 메시지용)."""
    return _API_KEY_RE.sub("crtfc_key=***", s)
