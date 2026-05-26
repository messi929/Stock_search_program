"""한국투자증권 OpenAPI (KIS Developers) REST 클라이언트.

Phase 0 산출물 — 시세 조회 전용 (현재가 + 일봉).
주문/잔고/체결은 보류 (read-only 영역만 도입).

⚠️ 발급 정책 (반드시 준수)
  - access_token: 1분에 1회 발급 한도 + 24h 유효
  - 잘못된 반복 발급 시 EGW00133 락 (수 분 ~ 수십 분)
  - 일일 호출 한도: 종목당 분당 20회 (시세), 초당 5회 일반
  - 이 클라이언트는 자동 캐시(메모리 + /tmp 파일)로 재발급을 강하게 억제

환경변수 (KIS_ENV로 실전/모의 분기):
  KIS_ENV=real | paper
  실전: KIS_APP_KEY, KIS_APP_SECRET, KIS_ACCOUNT_NO(선택)
  모의: KIS_PAPER_APP_KEY, KIS_PAPER_APP_SECRET, KIS_PAPER_ACCOUNT_NO(선택)

dart_client.py 패턴 follow: stats, key masking, sleep, http injectable.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import httpx
from loguru import logger


# ──────────────────────────────────────────────
# 도메인 / 정책 상수
# ──────────────────────────────────────────────

KIS_REAL_BASE = "https://openapi.koreainvestment.com:9443"
KIS_PAPER_BASE = "https://openapivts.koreainvestment.com:29443"

# REST 호출 사이 권장 sleep. 초당 5회 한도 대비 안전 마진.
RATE_LIMIT_SEC = 0.25

# token 발급 1분 1회 정책. 캐시 만료 전 재발급 시도하면 EGW00133 락.
# 24h 유효이지만 보수적으로 23h만 사용 후 갱신.
TOKEN_TTL_SEC = 23 * 3600

KisEnv = Literal["real", "paper"]


# ──────────────────────────────────────────────
# stats / token cache
# ──────────────────────────────────────────────


@dataclass
class KisStats:
    """호출 통계."""

    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    token_issues: int = 0
    token_cache_hits: int = 0
    started_at: float = field(default_factory=time.time)

    def elapsed_sec(self) -> float:
        return time.time() - self.started_at

    def summary(self) -> str:
        return (
            f"calls={self.total_calls} (ok={self.successful_calls}, fail={self.failed_calls}) "
            f"token_issues={self.token_issues} cache_hits={self.token_cache_hits} "
            f"elapsed={self.elapsed_sec():.1f}s"
        )


@dataclass
class _CachedToken:
    """파일 캐시 schema."""

    access_token: str
    issued_at: float  # epoch
    expires_at: float  # epoch
    env: KisEnv
    app_key_fingerprint: str  # app_key 앞 6자 — 키 회전 감지용

    def is_valid(self, env: KisEnv, app_key: str, now: float | None = None) -> bool:
        now = now if now is not None else time.time()
        return (
            self.env == env
            and self.app_key_fingerprint == app_key[:6]
            and now < self.expires_at
        )


# ──────────────────────────────────────────────
# 메인 클라이언트
# ──────────────────────────────────────────────


class KisClient:
    """KIS REST 시세 조회 클라이언트.

    Args:
        env: "real" | "paper". None이면 환경변수 KIS_ENV (기본 real).
        app_key, app_secret: None이면 환경변수에서 자동 로드.
        token_cache_path: token 파일 캐시 경로 (None이면 OS temp 디렉토리).
        sleep_sec: 호출 간 sleep.
        http_client: httpx.Client (테스트 mock 주입용).
    """

    def __init__(
        self,
        env: KisEnv | None = None,
        app_key: str | None = None,
        app_secret: str | None = None,
        token_cache_path: str | Path | None = None,
        sleep_sec: float = RATE_LIMIT_SEC,
        http_client: Any | None = None,
    ) -> None:
        self.env: KisEnv = env or os.environ.get("KIS_ENV", "real").lower()  # type: ignore[assignment]
        if self.env not in ("real", "paper"):
            raise ValueError(f"KIS_ENV must be real|paper, got {self.env!r}")

        # 환경변수 분기 — paper는 KIS_PAPER_* 우선
        if self.env == "paper":
            self.app_key = app_key or os.environ.get("KIS_PAPER_APP_KEY", "")
            self.app_secret = app_secret or os.environ.get("KIS_PAPER_APP_SECRET", "")
        else:
            self.app_key = app_key or os.environ.get("KIS_APP_KEY", "")
            self.app_secret = app_secret or os.environ.get("KIS_APP_SECRET", "")

        if not self.app_key or not self.app_secret:
            logger.warning(
                f"KIS_{self.env.upper()}_APP_KEY/SECRET 미설정 — 호출 시 401 응답 가능"
            )

        self.base_url = KIS_REAL_BASE if self.env == "real" else KIS_PAPER_BASE
        self.sleep_sec = sleep_sec
        self._http = http_client or httpx.Client(timeout=30)
        self._access_token: str | None = None
        self._token_expires_at: float = 0.0

        # token 파일 캐시 경로 (env별 분리 — 실전/모의 토큰 섞이지 않게)
        if token_cache_path:
            self._token_cache_path = Path(token_cache_path)
        else:
            self._token_cache_path = (
                Path(tempfile.gettempdir()) / f"kis_token_{self.env}.json"
            )

        self.stats = KisStats()

    # ──────────────────────────────────────────
    # access_token (캐시 매우 신중)
    # ──────────────────────────────────────────

    def _load_token_from_file(self) -> _CachedToken | None:
        """파일 캐시에서 토큰 로드. 만료/환경 불일치면 None."""
        if not self._token_cache_path.exists():
            return None
        try:
            data = json.loads(self._token_cache_path.read_text(encoding="utf-8"))
            cached = _CachedToken(**data)
        except Exception as e:
            logger.warning(f"KIS token cache 파싱 실패 → 무시: {type(e).__name__}: {e}")
            return None
        if not cached.is_valid(self.env, self.app_key):
            return None
        return cached

    def _save_token_to_file(self, token: str, expires_at: float) -> None:
        """토큰을 파일에 저장 (재기동 시 재발급 방지)."""
        try:
            payload = {
                "access_token": token,
                "issued_at": time.time(),
                "expires_at": expires_at,
                "env": self.env,
                "app_key_fingerprint": self.app_key[:6],
            }
            self._token_cache_path.write_text(
                json.dumps(payload, ensure_ascii=False), encoding="utf-8"
            )
            try:
                # 가능하면 0600 권한 (Unix only)
                os.chmod(self._token_cache_path, 0o600)
            except OSError:
                pass
        except Exception as e:
            logger.warning(f"KIS token 파일 저장 실패: {type(e).__name__}: {e}")

    def get_access_token(self, force_refresh: bool = False) -> str:
        """access_token을 반환. 메모리 → 파일 → 신규 발급 순.

        Args:
            force_refresh: True면 캐시 무시 (운영 중 사용 비권장 — EGW00133 락 위험).
        """
        now = time.time()

        # 1) 메모리 캐시
        if (
            not force_refresh
            and self._access_token
            and now < self._token_expires_at
        ):
            self.stats.token_cache_hits += 1
            return self._access_token

        # 2) 파일 캐시
        if not force_refresh:
            cached = self._load_token_from_file()
            if cached is not None:
                self._access_token = cached.access_token
                self._token_expires_at = cached.expires_at
                self.stats.token_cache_hits += 1
                logger.debug(
                    f"KIS token cache hit (file, env={self.env}, "
                    f"expires_in={int(cached.expires_at - now)}s)"
                )
                return cached.access_token

        # 3) 신규 발급
        if not self.app_key or not self.app_secret:
            raise RuntimeError("KIS_APP_KEY/SECRET 미설정 — token 발급 불가")

        self.stats.total_calls += 1
        self.stats.token_issues += 1
        url = f"{self.base_url}/oauth2/tokenP"
        body = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
        }
        try:
            r = self._http.post(url, json=body)
            r.raise_for_status()
            data = r.json()
        except httpx.HTTPStatusError as e:
            self.stats.failed_calls += 1
            # EGW00133 (1분 내 재발급)는 body에 명시됨
            body_text = mask_kis_secrets_in_str(e.response.text)[:240]
            raise RuntimeError(
                f"KIS token 발급 실패 (HTTP {e.response.status_code}): {body_text}"
            ) from None
        except Exception as e:
            self.stats.failed_calls += 1
            raise RuntimeError(
                f"KIS token 발급 실패: {type(e).__name__}: "
                f"{mask_kis_secrets_in_str(str(e))[:240]}"
            ) from None

        token = data.get("access_token")
        if not token:
            self.stats.failed_calls += 1
            raise RuntimeError(f"KIS token 응답 비정상: {data}")

        # expires_in (초) 또는 access_token_token_expired (YYYY-MM-DD HH:MM:SS) 둘 다 처리
        expires_in = data.get("expires_in")
        if isinstance(expires_in, (int, float)):
            ttl = float(expires_in)
        else:
            ttl = TOKEN_TTL_SEC
        # 보수적으로 -60s 마진
        expires_at = now + max(60.0, ttl - 60.0)

        self._access_token = token
        self._token_expires_at = expires_at
        self._save_token_to_file(token, expires_at)
        self.stats.successful_calls += 1
        logger.info(
            f"KIS token 신규 발급 (env={self.env}, ttl≈{int(ttl)}s, "
            f"cache={self._token_cache_path})"
        )
        self._sleep()
        return token

    # ──────────────────────────────────────────
    # 시세 호출
    # ──────────────────────────────────────────

    def get_current_price(self, ticker: str) -> dict[str, Any]:
        """현재가 + 등락률 + 거래량 + 시고저종 등 종합 시세.

        Args:
            ticker: 6자리 종목코드 (예: "005930")

        Returns:
            KIS 응답 dict (output 필드 평탄화). 실패 시 {}.

        주요 output 필드:
            stck_prpr   : 현재가
            prdy_vrss   : 전일 대비
            prdy_ctrt   : 전일 대비율 (%)
            acml_vol    : 누적 거래량
            stck_oprc / hgpr / lwpr : 시가/고가/저가
            stck_mxpr / llam : 상한가/하한가
        """
        ticker = str(ticker).zfill(6)
        path = "/uapi/domestic-stock/v1/quotations/inquire-price"
        # tr_id: 실전 FHKST01010100, 모의도 동일 (시세는 보통 공통)
        tr_id = "FHKST01010100"
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",  # J: 주식
            "FID_INPUT_ISCD": ticker,
        }
        result = self._call_get(path, tr_id, params)
        return result.get("output", {}) if result else {}

    def get_orderbook(self, ticker: str) -> dict[str, Any]:
        """10호가 + 예상체결 조회.

        Args:
            ticker: 6자리 종목코드

        Returns:
            {"orderbook": output1, "expected": output2}
            output1 주요 필드:
                aspr_acpt_hour     : 호가접수시간 (HHMMSS)
                askp1..askp10      : 매도 1~10호가
                bidp1..bidp10      : 매수 1~10호가
                askp_rsqn1..10     : 매도 잔량
                bidp_rsqn1..10     : 매수 잔량
                total_askp_rsqn    : 매도 총잔량
                total_bidp_rsqn    : 매수 총잔량
            output2 주요 필드:
                antc_cnpr          : 예상체결가
                antc_cntg_vrss     : 예상체결 전일대비
                antc_vol           : 예상체결 거래량
        """
        ticker = str(ticker).zfill(6)
        path = "/uapi/domestic-stock/v1/quotations/inquire-asking-price-exp-ccn"
        tr_id = "FHKST01010200"
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": ticker,
        }
        result = self._call_get(path, tr_id, params)
        if not result:
            return {}
        return {
            "orderbook": result.get("output1", {}) or {},
            "expected": result.get("output2", {}) or {},
        }

    def get_minute_chart(
        self,
        ticker: str,
        time_hhmmss: str | None = None,
        include_past: bool = True,
    ) -> list[dict[str, Any]]:
        """당일 분봉 (1분 간격, 최근 30개).

        KIS는 분봉을 한 번에 최대 30개 반환. 더 긴 구간은 시간 윈도우를 옮겨서 다회 호출 필요.

        Args:
            ticker: 6자리 종목코드
            time_hhmmss: 기준 시각 (HHMMSS). None이면 현재 시각 (KST). 장 마감 후엔 마감 시각 기준.
            include_past: True면 기준 시각 이전 30분치, False면 미래 방향.

        Returns:
            output2 리스트. 비어있으면 [].

        주요 output2 필드:
            stck_bsop_date     : 영업일자 YYYYMMDD
            stck_cntg_hour     : 체결시각 HHMMSS
            stck_prpr          : 현재가 (해당 분봉 종가)
            stck_oprc / hgpr / lwpr : 시고저
            cntg_vol           : 체결량
            acml_tr_pbmn       : 누적 거래대금
        """
        ticker = str(ticker).zfill(6)
        path = "/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice"
        tr_id = "FHKST03010200"

        if time_hhmmss is None:
            from datetime import datetime
            time_hhmmss = datetime.now().strftime("%H%M%S")
        # KIS는 6자리 HHMMSS 요구
        time_hhmmss = str(time_hhmmss).zfill(6)

        params = {
            "FID_ETC_CLS_CODE": "",
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": ticker,
            "FID_INPUT_HOUR_1": time_hhmmss,
            "FID_PW_DATA_INCU_YN": "Y" if include_past else "N",
        }
        result = self._call_get(path, tr_id, params)
        if not result:
            return []
        return result.get("output2", []) or []

    def get_investor_trend(
        self,
        ticker: str,
    ) -> list[dict[str, Any]]:
        """투자자별 매매동향 (외국인/기관 등) — 일별.

        네이버 frgn.naver 페이지의 KIS 공식 대체.

        Args:
            ticker: 6자리 종목코드

        Returns:
            output 리스트. 최근 일자 → 과거 순.

        주요 output 필드:
            stck_bsop_date       : 영업일자
            stck_clpr            : 종가
            prsn_ntby_qty        : 개인 순매수량
            frgn_ntby_qty        : 외국인 순매수량
            orgn_ntby_qty        : 기관계 순매수량
            (각각 _tr_pbmn 필드는 거래대금)
        """
        ticker = str(ticker).zfill(6)
        path = "/uapi/domestic-stock/v1/quotations/inquire-investor"
        tr_id = "FHKST01010900"
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": ticker,
        }
        result = self._call_get(path, tr_id, params)
        if not result:
            return []
        return result.get("output", []) or []

    def get_daily_chart(
        self,
        ticker: str,
        period: Literal["D", "W", "M", "Y"] = "D",
        adjusted: bool = True,
        bgn_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict[str, Any]]:
        """일/주/월/년봉 차트.

        Args:
            ticker: 6자리 종목코드
            period: D|W|M|Y
            adjusted: 수정주가 여부 (True=수정)
            bgn_date: 시작 YYYYMMDD (None이면 KIS 기본값 — 100개 영업일 전)
            end_date: 종료 YYYYMMDD (None이면 오늘)

        Returns:
            output2 리스트 (날짜 내림차순). 비어있으면 [].

        주요 output2 필드:
            stck_bsop_date : 영업일자 YYYYMMDD
            stck_clpr      : 종가
            stck_oprc / hgpr / lwpr : 시가/고가/저가
            acml_vol       : 거래량
            acml_tr_pbmn   : 거래대금
        """
        ticker = str(ticker).zfill(6)
        path = "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"
        tr_id = "FHKST03010100"
        from datetime import datetime, timedelta

        today = datetime.now()
        if end_date is None:
            end_date = today.strftime("%Y%m%d")
        if bgn_date is None:
            bgn_date = (today - timedelta(days=140)).strftime("%Y%m%d")

        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": ticker,
            "FID_INPUT_DATE_1": bgn_date,
            "FID_INPUT_DATE_2": end_date,
            "FID_PERIOD_DIV_CODE": period,
            "FID_ORG_ADJ_PRC": "0" if adjusted else "1",  # 0=수정주가, 1=원주가
        }
        result = self._call_get(path, tr_id, params)
        if not result:
            return []
        return result.get("output2", []) or []

    # ──────────────────────────────────────────
    # 공통 GET
    # ──────────────────────────────────────────

    def _call_get(
        self, path: str, tr_id: str, params: dict[str, Any]
    ) -> dict[str, Any] | None:
        """공통 GET 호출 — token 자동 첨부 + 에러 통계."""
        token = self.get_access_token()
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "authorization": f"Bearer {token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": tr_id,
            "custtype": "P",  # P=개인, B=법인
        }
        url = f"{self.base_url}{path}"

        self.stats.total_calls += 1
        try:
            r = self._http.get(url, headers=headers, params=params)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            self.stats.failed_calls += 1
            logger.warning(
                f"KIS {path} 호출 실패: {type(e).__name__}: "
                f"{mask_kis_secrets_in_str(str(e))[:240]}"
            )
            self._sleep()
            return None

        rt_cd = data.get("rt_cd")
        if rt_cd != "0":
            self.stats.failed_calls += 1
            logger.warning(
                f"KIS {path} 비정상 응답: rt_cd={rt_cd!r} "
                f"msg_cd={data.get('msg_cd')!r} msg={data.get('msg1')!r}"
            )
            self._sleep()
            return None

        self.stats.successful_calls += 1
        self._sleep()
        return data

    def _sleep(self) -> None:
        if self.sleep_sec > 0:
            time.sleep(self.sleep_sec)


# ──────────────────────────────────────────────
# 보조 유틸 — 키 마스킹
# ──────────────────────────────────────────────


# KIS app_key: 36자 영숫자
_KIS_APP_KEY_RE = re.compile(r"\bPS[0-9A-Za-z]{34}\b")
# KIS app_secret: 보통 ~180자 base64-ish
_KIS_APP_SECRET_RE = re.compile(r"\b[A-Za-z0-9+/=]{120,}\b")
# Bearer 토큰
_KIS_BEARER_RE = re.compile(r"Bearer\s+[A-Za-z0-9._\-]{20,}", re.IGNORECASE)


def mask_kis_secrets_in_str(s: str) -> str:
    """KIS 앱키/시크릿/토큰 노출을 마스킹 (로그/예외 메시지용)."""
    s = _KIS_APP_KEY_RE.sub("PS***", s)
    s = _KIS_APP_SECRET_RE.sub("***", s)
    s = _KIS_BEARER_RE.sub("Bearer ***", s)
    return s
