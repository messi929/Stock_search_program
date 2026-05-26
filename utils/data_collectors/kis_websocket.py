"""한국투자증권 OpenAPI WebSocket 실시간 시세 클라이언트.

Phase 2 산출물 — 실시간 체결가 / 호가 push.
read-only 영역 (조회만, 주문 X).

⚠️ 정책
  - approval_key: REST access_token과 별개. 1일 1회 발급, 24h 유효.
  - 한 계정당 동시 WebSocket 연결 1개 (다중 접속 시 기존 끊김)
  - 실시간 동시 등록 종목 수: 실전 41 / 모의 16 (TR ID별 카운트)
  - PINGPONG: 서버가 주기적으로 보냄 → 그대로 echo (안 하면 끊김)
  - 데이터는 비암호화 ws:// (KIS 정책)

지원 TR (구독 가능):
  H0STCNT0: 실시간 체결가 (KOSPI/KOSDAQ)
  H0STASP0: 실시간 호가 (10단계)

사용 예:
  async def on_tick(tick: dict):
      print(tick)
  client = KisWebSocketClient()
  await client.connect()
  await client.subscribe("005930", "H0STCNT0", on_tick)
  await client.run_forever()
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Literal

import httpx
import websockets
from loguru import logger

from utils.data_collectors.kis_client import (
    KIS_PAPER_BASE,
    KIS_REAL_BASE,
    KisEnv,
    mask_kis_secrets_in_str,
)

# ──────────────────────────────────────────────
# 도메인 / 정책
# ──────────────────────────────────────────────

KIS_WS_REAL = "ws://ops.koreainvestment.com:21000"
KIS_WS_PAPER = "ws://ops.koreainvestment.com:31000"

# 재접속 backoff (초)
RECONNECT_BACKOFF_BASE = 1.0
RECONNECT_BACKOFF_MAX = 60.0

# 동시 등록 한도 (TR ID 통합)
MAX_SUBSCRIPTIONS_REAL = 41
MAX_SUBSCRIPTIONS_PAPER = 16


# ──────────────────────────────────────────────
# H0STCNT0 (실시간 체결가) 필드 파서
# ──────────────────────────────────────────────


# 공식 H0STCNT0 응답: ^로 구분된 ~46개 필드 (앞부분만 명명, 나머지는 raw로)
_H0STCNT0_FIELDS = [
    "ticker",              # 0  유가증권단축종목코드
    "exec_time",           # 1  주식체결시간 HHMMSS
    "price",               # 2  주식현재가
    "prdy_vrss_sign",      # 3  전일대비부호 (1상한 2상승 3보합 4하한 5하락)
    "prdy_vrss",           # 4  전일대비
    "prdy_ctrt",           # 5  전일대비율
    "wghn_avrg_prc",       # 6  가중평균주식가격
    "open",                # 7  시가
    "high",                # 8  고가
    "low",                 # 9  저가
    "ask1",                # 10 매도호가1
    "bid1",                # 11 매수호가1
    "cntg_vol",            # 12 체결거래량 (이번 체결분)
    "acml_vol",            # 13 누적거래량
    "acml_tr_pbmn",        # 14 누적거래대금
    "seln_cntg_csnu",      # 15 매도체결건수
    "shnu_cntg_csnu",      # 16 매수체결건수
    "ntby_cntg_csnu",      # 17 순매수체결건수
    "cttr",                # 18 체결강도
    "seln_cntg_smtn",      # 19 총매도수량
    "shnu_cntg_smtn",      # 20 총매수수량
    "ccld_dvsn",           # 21 체결구분 (1매도, 3장전, 5매수)
    "shnu_rate",           # 22 매수비율
    "prdy_vol_vrss_acml_vol_rate",  # 23 전일거래량대비등락율
    "oprc_hour",           # 24 시가시간
    "oprc_vrss_prpr_sign", # 25 시가대비현재가부호
    "oprc_vrss_prpr",      # 26 시가대비현재가
    "hgpr_hour",           # 27 최고가시간
    "hgpr_vrss_prpr_sign", # 28 고가대비현재가부호
    "hgpr_vrss_prpr",      # 29 고가대비현재가
    "lwpr_hour",           # 30 최저가시간
    "lwpr_vrss_prpr_sign", # 31 저가대비현재가부호
    "lwpr_vrss_prpr",      # 32 저가대비현재가
    "bsop_date",           # 33 영업일자 YYYYMMDD
    "new_mkop_cls_code",   # 34 신장운영구분코드
    "trht_yn",             # 35 거래정지여부
    "askp_rsqn1",          # 36 매도호가잔량1
    "bidp_rsqn1",          # 37 매수호가잔량1
    "total_askp_rsqn",     # 38 총매도호가잔량
    "total_bidp_rsqn",     # 39 총매수호가잔량
    "vol_tnrt",            # 40 거래량회전율
    "prdy_smns_hour_acml_vol",      # 41 전일동시간누적거래량
    "prdy_smns_hour_acml_vol_rate", # 42 전일동시간누적거래량비율
    "hour_cls_code",       # 43 시간구분코드 (0=장중, A=장후예상)
    "mrkt_trtm_cls_code",  # 44 임의종료구분코드
    "vi_stnd_prc",         # 45 정적VI발동기준가
]


def parse_h0stcnt0(payload: str) -> dict[str, Any]:
    """H0STCNT0 실시간 체결가 raw 메시지 파싱.

    Args:
        payload: "0|H0STCNT0|001|005930^160000^73000^..." 중 ^ 구분 본문.
                 (caller가 헤더 제거 후 본문만 전달)

    Returns:
        명명된 필드 dict. 알 수 없는 필드는 raw_<index>로.
    """
    parts = payload.split("^")
    out: dict[str, Any] = {}
    for i, val in enumerate(parts):
        key = _H0STCNT0_FIELDS[i] if i < len(_H0STCNT0_FIELDS) else f"raw_{i}"
        out[key] = val
    return out


# ──────────────────────────────────────────────
# 상태 / 통계
# ──────────────────────────────────────────────


@dataclass
class WsStats:
    """WebSocket 통계."""

    connections: int = 0
    reconnections: int = 0
    messages_received: int = 0
    ticks_dispatched: int = 0
    pingpongs: int = 0
    parse_errors: int = 0
    started_at: float = field(default_factory=time.time)

    def elapsed_sec(self) -> float:
        return time.time() - self.started_at

    def summary(self) -> str:
        return (
            f"conn={self.connections} reconn={self.reconnections} "
            f"msgs={self.messages_received} ticks={self.ticks_dispatched} "
            f"pings={self.pingpongs} parse_err={self.parse_errors} "
            f"elapsed={self.elapsed_sec():.1f}s"
        )


TickHandler = Callable[[dict[str, Any]], Awaitable[None]]


@dataclass
class _Subscription:
    """등록된 구독."""

    ticker: str
    tr_id: str  # H0STCNT0 | H0STASP0
    handler: TickHandler


# ──────────────────────────────────────────────
# 메인 클라이언트
# ──────────────────────────────────────────────


class KisWebSocketClient:
    """KIS 실시간 시세 WebSocket 클라이언트 (asyncio).

    Args:
        env: real | paper. None이면 환경변수 KIS_ENV.
        app_key, app_secret: None이면 환경변수 자동.
    """

    def __init__(
        self,
        env: KisEnv | None = None,
        app_key: str | None = None,
        app_secret: str | None = None,
    ) -> None:
        self.env: KisEnv = env or os.environ.get("KIS_ENV", "real").lower()  # type: ignore[assignment]
        if self.env not in ("real", "paper"):
            raise ValueError(f"KIS_ENV must be real|paper, got {self.env!r}")

        if self.env == "paper":
            self.app_key = app_key or os.environ.get("KIS_PAPER_APP_KEY", "")
            self.app_secret = app_secret or os.environ.get("KIS_PAPER_APP_SECRET", "")
            self.rest_base = KIS_PAPER_BASE
            self.ws_url = KIS_WS_PAPER
            self.max_subs = MAX_SUBSCRIPTIONS_PAPER
        else:
            self.app_key = app_key or os.environ.get("KIS_APP_KEY", "")
            self.app_secret = app_secret or os.environ.get("KIS_APP_SECRET", "")
            self.rest_base = KIS_REAL_BASE
            self.ws_url = KIS_WS_REAL
            self.max_subs = MAX_SUBSCRIPTIONS_REAL

        if not self.app_key or not self.app_secret:
            logger.warning(f"KIS_{self.env.upper()}_APP_KEY/SECRET 미설정")

        self._approval_key: str | None = None
        self._ws: Any = None  # websockets.WebSocketClientProtocol
        self._subscriptions: dict[tuple[str, str], _Subscription] = {}
        self._stop_event = asyncio.Event()
        self.stats = WsStats()

    # ──────────────────────────────────────────
    # approval_key 발급
    # ──────────────────────────────────────────

    def issue_approval_key(self) -> str:
        """WebSocket 접속용 approval_key 발급.

        REST의 access_token과는 별개 API. 1일 1회 발급, 24h 유효.
        간단한 메모리 캐시만 (재기동 시 재발급).
        """
        if self._approval_key:
            return self._approval_key

        url = f"{self.rest_base}/oauth2/Approval"
        body = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "secretkey": self.app_secret,
        }
        try:
            with httpx.Client(timeout=30) as http:
                r = http.post(url, json=body)
                r.raise_for_status()
                data = r.json()
        except Exception as e:
            raise RuntimeError(
                f"KIS approval_key 발급 실패: {type(e).__name__}: "
                f"{mask_kis_secrets_in_str(str(e))[:240]}"
            ) from None

        key = data.get("approval_key")
        if not key:
            raise RuntimeError(f"KIS approval_key 응답 비정상: {data}")

        self._approval_key = key
        logger.info(f"KIS approval_key 발급 (env={self.env}, key 앞12자: {key[:12]}***)")
        return key

    # ──────────────────────────────────────────
    # 연결 / 메시지 루프
    # ──────────────────────────────────────────

    async def connect(self) -> None:
        """WebSocket 접속."""
        if not self._approval_key:
            self.issue_approval_key()
        self._ws = await websockets.connect(self.ws_url, ping_interval=None)
        self.stats.connections += 1
        logger.info(f"KIS WebSocket 접속 (env={self.env}, url={self.ws_url})")

        # 재접속 시 기존 구독 복원
        for sub in self._subscriptions.values():
            await self._send_subscribe(sub.ticker, sub.tr_id, register=True)

    async def disconnect(self) -> None:
        """WebSocket 연결 종료."""
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None
        self._stop_event.set()
        logger.info(f"KIS WebSocket 종료 — {self.stats.summary()}")

    async def subscribe(
        self,
        ticker: str,
        tr_id: Literal["H0STCNT0", "H0STASP0"],
        handler: TickHandler,
    ) -> None:
        """종목 구독 등록.

        Args:
            ticker: 6자리 종목코드
            tr_id: H0STCNT0(체결) | H0STASP0(호가)
            handler: async 콜백 (tick dict 1개 받음)
        """
        ticker = str(ticker).zfill(6)
        if len(self._subscriptions) >= self.max_subs:
            raise RuntimeError(
                f"동시 구독 한도 초과: {len(self._subscriptions)}/{self.max_subs} "
                f"(env={self.env}). 일부 unsubscribe 필요."
            )
        key = (ticker, tr_id)
        self._subscriptions[key] = _Subscription(ticker, tr_id, handler)
        if self._ws is not None:
            await self._send_subscribe(ticker, tr_id, register=True)

    async def unsubscribe(
        self, ticker: str, tr_id: Literal["H0STCNT0", "H0STASP0"]
    ) -> None:
        """종목 구독 해제."""
        ticker = str(ticker).zfill(6)
        key = (ticker, tr_id)
        if key not in self._subscriptions:
            return
        if self._ws is not None:
            await self._send_subscribe(ticker, tr_id, register=False)
        del self._subscriptions[key]

    async def _send_subscribe(
        self, ticker: str, tr_id: str, *, register: bool
    ) -> None:
        msg = {
            "header": {
                "approval_key": self._approval_key,
                "custtype": "P",
                "tr_type": "1" if register else "2",
                "content-type": "utf-8",
            },
            "body": {"input": {"tr_id": tr_id, "tr_key": ticker}},
        }
        await self._ws.send(json.dumps(msg))
        logger.debug(
            f"KIS WS {'등록' if register else '해제'}: tr_id={tr_id} ticker={ticker}"
        )

    async def run_forever(self) -> None:
        """메시지 수신 루프. 끊김 시 자동 재접속 (exponential backoff)."""
        backoff = RECONNECT_BACKOFF_BASE
        while not self._stop_event.is_set():
            try:
                if self._ws is None:
                    await self.connect()
                await self._message_loop()
                # _message_loop가 정상 종료(close)되면 backoff 후 재접속
                backoff = RECONNECT_BACKOFF_BASE
            except (websockets.ConnectionClosed, ConnectionError) as e:
                logger.warning(f"KIS WS 끊김: {type(e).__name__}: {e}")
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(
                    f"KIS WS 예외: {type(e).__name__}: "
                    f"{mask_kis_secrets_in_str(str(e))[:240]}"
                )

            if self._stop_event.is_set():
                break

            self._ws = None
            self.stats.reconnections += 1
            logger.info(f"KIS WS 재접속 대기 {backoff:.1f}s...")
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=backoff)
                break
            except asyncio.TimeoutError:
                pass
            backoff = min(backoff * 2, RECONNECT_BACKOFF_MAX)

    async def _message_loop(self) -> None:
        """단일 연결 동안 메시지 수신."""
        async for raw in self._ws:
            self.stats.messages_received += 1
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8", errors="replace")

            # 1) JSON 메시지: PINGPONG, 등록/해제 응답
            if raw.startswith("{"):
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    self.stats.parse_errors += 1
                    continue
                await self._handle_json(data)
                continue

            # 2) 데이터: "0|H0STCNT0|001|005930^..." 또는 "1|..." (암호화)
            await self._handle_data_frame(raw)

    async def _handle_json(self, data: dict[str, Any]) -> None:
        header = data.get("header", {})
        tr_id = header.get("tr_id")
        if tr_id == "PINGPONG":
            self.stats.pingpongs += 1
            # 그대로 echo
            try:
                await self._ws.send(json.dumps(data))
            except Exception as e:
                logger.warning(f"PINGPONG echo 실패: {e}")
            return

        body = data.get("body", {})
        rt_cd = body.get("rt_cd")
        msg = body.get("msg1") or body.get("msg")
        if rt_cd == "0":
            logger.info(f"KIS WS 등록 응답 OK: tr_id={tr_id} msg={msg}")
        else:
            logger.warning(f"KIS WS 등록 응답 비정상: tr_id={tr_id} rt_cd={rt_cd} msg={msg}")

    async def _handle_data_frame(self, raw: str) -> None:
        """0|TR_ID|건수|본문^..^... 파싱."""
        parts = raw.split("|", 3)
        if len(parts) < 4:
            self.stats.parse_errors += 1
            return

        encrypted_flag, tr_id, count_str, body = parts
        if encrypted_flag == "1":
            # 암호화 데이터 (체결통보 등) — Phase 2 범위 외
            logger.debug(f"KIS WS 암호화 프레임 무시: tr_id={tr_id}")
            return

        try:
            count = int(count_str)
        except ValueError:
            count = 1

        if tr_id != "H0STCNT0":
            # 호가(H0STASP0)는 별도 파서 필요 — Phase 2에선 체결만 우선
            logger.debug(f"KIS WS 비지원 tr_id={tr_id} 무시")
            return

        # 한 프레임에 여러 건 — body는 ^로 구분된 단일 레코드 (대부분 1건)
        tick = parse_h0stcnt0(body)
        ticker = tick.get("ticker", "").zfill(6)
        key = (ticker, tr_id)
        sub = self._subscriptions.get(key)
        if not sub:
            logger.debug(f"KIS WS 미등록 ticker tick 수신: {ticker} tr_id={tr_id}")
            return

        try:
            await sub.handler(tick)
            self.stats.ticks_dispatched += 1
        except Exception as e:
            logger.warning(
                f"tick handler 예외 ({ticker} {tr_id}): {type(e).__name__}: {e}"
            )
