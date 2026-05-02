"""FRED (Federal Reserve Economic Data) API 클라이언트.

WEEK_B.md Day 1 산출물 — Macro PM 페르소나용 미국 매크로 인프라.

데이터 소스:
  - FRED OpenAPI (https://fred.stlouisfed.org/)
  - 일일 호출 한도 120K (실질 무제한)
  - Python 라이브러리: fredapi 0.5.x (sync)

핵심 12 시리즈 (FRED_SERIES):
  - 금리 4: DFF / DGS2 / DGS10 / T10Y2Y
  - 경기 3: INDPRO / UNRATE / PAYEMS
  - 인플레 3: CPIAUCSL / CPILFESL / PCEPILFE
  - 통화 1: DTWEXBGS (광범위 달러 인덱스)
  - 보조 1: DCOILWTICO (WTI 원유)

⚠️ ISM PMI는 FRED 무료에서 미제공 → INDPRO + UNRATE 조합으로 경기 사이클 판정.
   응답에 'PMI 대신 산업생산 사용' 명시 (Macro PM 페르소나 시스템 프롬프트).

⚠️ 보안: API 키는 .env에서만 읽기. 로그/예외 시 mask_api_key_in_str로 마스킹.
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd
from loguru import logger


# ──────────────────────────────────────────────
# 핵심 시리즈 매핑
# ──────────────────────────────────────────────
# 키 = Axis 내부 식별자, 값 = (FRED series_id, category, unit, frequency)
# units는 FRED가 'percent'/'index'/'thousands'/'billions' 등 다양하므로 후처리에서 통일.

FRED_SERIES: dict[str, dict[str, str]] = {
    # 금리 (interest_rate)
    "fed_funds_rate": {
        "series_id": "DFF",
        "category": "interest_rate",
        "frequency": "D",
        "description": "연방기금 일별 실효금리 (%)",
    },
    "treasury_2y": {
        "series_id": "DGS2",
        "category": "interest_rate",
        "frequency": "D",
        "description": "미국 2년 국채 수익률 (%)",
    },
    "treasury_10y": {
        "series_id": "DGS10",
        "category": "interest_rate",
        "frequency": "D",
        "description": "미국 10년 국채 수익률 (%)",
    },
    "yield_spread_10y_2y": {
        "series_id": "T10Y2Y",
        "category": "interest_rate",
        "frequency": "D",
        "description": "10Y-2Y 장단기 스프레드 (%) — 음수면 역전",
    },
    # 경기 (business_cycle)
    "industrial_production": {
        "series_id": "INDPRO",
        "category": "business_cycle",
        "frequency": "M",
        "description": "산업생산 지수 (2017=100, ISM PMI 무료 미제공 대안)",
    },
    "unemployment_rate": {
        "series_id": "UNRATE",
        "category": "business_cycle",
        "frequency": "M",
        "description": "실업률 (%)",
    },
    "nonfarm_payrolls": {
        "series_id": "PAYEMS",
        "category": "business_cycle",
        "frequency": "M",
        "description": "비농업 고용 (천명)",
    },
    # 인플레 (inflation)
    "cpi_all": {
        "series_id": "CPIAUCSL",
        "category": "inflation",
        "frequency": "M",
        "description": "CPI All Items (NSA 1982-84=100)",
    },
    "cpi_core": {
        "series_id": "CPILFESL",
        "category": "inflation",
        "frequency": "M",
        "description": "Core CPI (식품/에너지 제외)",
    },
    "pce_core": {
        "series_id": "PCEPILFE",
        "category": "inflation",
        "frequency": "M",
        "description": "Core PCE (Fed 선호 인플레 지표)",
    },
    # 통화 (currency)
    "dxy_broad": {
        "series_id": "DTWEXBGS",
        "category": "currency",
        "frequency": "D",
        "description": "광범위 달러 인덱스 (Trade-Weighted USD Broad)",
    },
    # 원자재 (commodity, 보조 지표)
    "oil_wti": {
        "series_id": "DCOILWTICO",
        "category": "commodity",
        "frequency": "D",
        "description": "WTI 원유 가격 ($/배럴)",
    },
}


# ──────────────────────────────────────────────
# 보안 — API 키 마스킹 (DART와 동일 패턴)
# ──────────────────────────────────────────────


_FRED_KEY_RE = re.compile(r"api_key=[a-f0-9]{32}", re.IGNORECASE)


def mask_api_key_in_str(s: str) -> str:
    """문자열에서 FRED API 키 노출을 마스킹 (로그/예외용)."""
    return _FRED_KEY_RE.sub("api_key=***", s)


# ──────────────────────────────────────────────
# 통계
# ──────────────────────────────────────────────


@dataclass
class FREDStats:
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    empty_responses: int = 0
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
# 클라이언트
# ──────────────────────────────────────────────


class FREDClient:
    """FRED API 호출 래퍼 (fredapi 0.5.x 기반).

    Args:
        api_key: FRED API 키 (None 시 환경변수 FRED_API_KEY 사용).
        sleep_sec: 호출 간 sleep (관행 0.1초; 무제한이지만 매너).
        fred_instance: fredapi.Fred 인스턴스 (테스트 mock 주입용).
    """

    def __init__(
        self,
        api_key: str | None = None,
        sleep_sec: float = 0.1,
        fred_instance: Any | None = None,
    ) -> None:
        self.api_key = api_key or os.environ.get("FRED_API_KEY", "")
        if not self.api_key and fred_instance is None:
            logger.warning("FRED_API_KEY 미설정 — 호출 시 인증 오류 발생")
        self.sleep_sec = sleep_sec
        self._fred = fred_instance
        self.stats = FREDStats()

    @property
    def fred(self) -> Any:
        if self._fred is None:
            from fredapi import Fred

            self._fred = Fred(api_key=self.api_key)
        return self._fred

    def _sleep(self) -> None:
        time.sleep(self.sleep_sec)

    # ──────────────────────────────────────────────
    # 단일 시리즈 시계열
    # ──────────────────────────────────────────────

    def get_series(
        self,
        series_id: str,
        observation_start: str | None = None,
        observation_end: str | None = None,
    ) -> pd.Series:
        """단일 시리즈 시계열 조회.

        Args:
            series_id: FRED series ID (예: "DFF")
            observation_start: ISO date "YYYY-MM-DD" (fredapi 인자명 정확)
            observation_end: ISO date "YYYY-MM-DD"

        Returns:
            pd.Series (index = pd.DatetimeIndex). 실패/빈 결과 시 빈 Series.
        """
        self.stats.total_calls += 1
        try:
            kwargs: dict[str, Any] = {}
            if observation_start:
                kwargs["observation_start"] = observation_start
            if observation_end:
                kwargs["observation_end"] = observation_end
            series = self.fred.get_series(series_id, **kwargs)
        except Exception as e:
            self.stats.failed_calls += 1
            logger.warning(
                f"FRED get_series 실패 (series={series_id}): "
                f"{type(e).__name__}: {mask_api_key_in_str(str(e))[:160]}"
            )
            self._sleep()
            return pd.Series(dtype=float)

        self._sleep()

        if series is None or len(series) == 0:
            self.stats.empty_responses += 1
            return pd.Series(dtype=float)

        self.stats.successful_calls += 1
        # NaN 제거 (FRED는 휴장일에 NaN 반환)
        return series.dropna()

    # ──────────────────────────────────────────────
    # 최신값 + 메타 정보
    # ──────────────────────────────────────────────

    def get_latest_value(self, series_id: str) -> dict[str, Any] | None:
        """최신값 + 시리즈 메타.

        Returns:
            {
                "series_id": "DFF",
                "title": "Federal Funds Effective Rate",
                "latest_value": 5.33,
                "latest_date": "2025-12-31",
                "frequency": "Daily, 7-Day",
                "units": "Percent",
            }
            실패 시 None.
        """
        self.stats.total_calls += 1
        try:
            series = self.fred.get_series_latest_release(series_id)
            info = self.fred.get_series_info(series_id)
        except Exception as e:
            self.stats.failed_calls += 1
            logger.warning(
                f"FRED get_latest_value 실패 (series={series_id}): "
                f"{type(e).__name__}: {mask_api_key_in_str(str(e))[:160]}"
            )
            self._sleep()
            return None

        self._sleep()

        if series is None or len(series) == 0:
            self.stats.empty_responses += 1
            return None

        clean = series.dropna()
        if len(clean) == 0:
            self.stats.empty_responses += 1
            return None

        self.stats.successful_calls += 1
        return {
            "series_id": series_id,
            "title": info.get("title", "") if hasattr(info, "get") else str(info.get("title", "")),
            "latest_value": float(clean.iloc[-1]),
            "latest_date": str(clean.index[-1].date()),
            "frequency": str(info.get("frequency", "")) if hasattr(info, "get") else "",
            "units": str(info.get("units", "")) if hasattr(info, "get") else "",
        }

    # ──────────────────────────────────────────────
    # 일괄 조회 (Axis 식별자 기준)
    # ──────────────────────────────────────────────

    def get_multiple_series(
        self,
        keys: list[str] | None = None,
        observation_start: str | None = None,
        observation_end: str | None = None,
    ) -> dict[str, pd.Series]:
        """FRED_SERIES 키 list로 여러 시리즈 일괄 조회.

        Args:
            keys: FRED_SERIES 키 리스트. None이면 전체 12개.

        Returns:
            {axis_key: pd.Series} (실패 시 해당 키는 빈 Series).
        """
        if keys is None:
            keys = list(FRED_SERIES.keys())

        result: dict[str, pd.Series] = {}
        for key in keys:
            meta = FRED_SERIES.get(key)
            if meta is None:
                logger.warning(f"FRED_SERIES에 없는 키: {key} → skip")
                result[key] = pd.Series(dtype=float)
                continue

            series = self.get_series(
                meta["series_id"],
                observation_start=observation_start,
                observation_end=observation_end,
            )
            result[key] = series

        return result

    # ──────────────────────────────────────────────
    # Firestore 스키마 정규화
    # ──────────────────────────────────────────────

    def normalize_to_records(
        self, axis_key: str, series: pd.Series
    ) -> list[dict[str, Any]]:
        """단일 시리즈 → Firestore macro_indicators 컬렉션용 record 리스트.

        Doc ID 권장: {indicator_key}_{date} (예: "fed_funds_rate_20251231").
        실제 Doc ID 부여는 저장 단계에서 (Day 5 Job).

        Args:
            axis_key: FRED_SERIES 키 (예: "fed_funds_rate")
            series: pd.Series (index = DatetimeIndex)

        Returns:
            [{indicator_key, country, category, date, value, unit, frequency,
              source, source_series_id, collected_at}, ...]
        """
        meta = FRED_SERIES.get(axis_key)
        if meta is None:
            logger.warning(f"normalize_to_records: 미등록 키 {axis_key}")
            return []
        if series is None or len(series) == 0:
            return []

        now_iso = datetime.now().isoformat()
        records: list[dict[str, Any]] = []
        for idx, val in series.items():
            try:
                v = float(val)
                if v != v:  # NaN
                    continue
            except (TypeError, ValueError):
                continue
            records.append(
                {
                    "indicator_key": axis_key,
                    "country": "US",
                    "category": meta["category"],
                    "date": idx.strftime("%Y%m%d") if hasattr(idx, "strftime") else str(idx)[:10].replace("-", ""),
                    "value": round(v, 6),
                    "unit": _unit_label(meta["category"]),
                    "frequency": meta["frequency"],
                    "source": "FRED",
                    "source_series_id": meta["series_id"],
                    "collected_at": now_iso,
                }
            )
        return records


# ──────────────────────────────────────────────
# 유틸 (모듈 private)
# ──────────────────────────────────────────────


_CATEGORY_UNIT = {
    "interest_rate": "percent",
    "business_cycle": "index_or_count",
    "inflation": "index_yoy",
    "currency": "index",
    "commodity": "usd_per_barrel",
}


def _unit_label(category: str) -> str:
    """카테고리 → 표준 단위 라벨 (FRED 원본 단위는 다양함)."""
    return _CATEGORY_UNIT.get(category, "raw")
