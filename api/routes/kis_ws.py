"""KIS 실시간 시세 WebSocket fan-out endpoint.

엔드포인트:
  WS /api/kis/ws/stream

프로토콜 (클라이언트 → 서버):
  {"action": "subscribe",   "tickers": ["005930", "000660"]}
  {"action": "unsubscribe", "tickers": ["005930"]}
  {"action": "ping"}

서버 → 클라이언트:
  {"type": "tick",       "ticker": "005930", "data": {...}}
  {"type": "subscribed", "ticker": "005930"}
  {"type": "error",      "message": "..."}
  {"type": "pong"}

⚠️ 운영 제약
  - KIS는 한 계정당 동시 WebSocket 1개 → 백엔드 1 인스턴스에 KIS WS 1개로 fan-out.
  - Cloud Run 다중 인스턴스에선 fan-out 분기 충돌. min/max instances=1로 강제 필요.
  - 동시 등록 종목 한도: 실전 41 / 모의 16 (전 클라이언트 합산).
"""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

from utils.data_collectors.kis_websocket import KisWebSocketClient


router = APIRouter(tags=["axis-kis-ws"])


# ──────────────────────────────────────────────
# Fan-out 매니저 (싱글톤)
# ──────────────────────────────────────────────


class KisFanout:
    """KIS 단일 WS → 여러 클라이언트 fan-out.

    같은 ticker를 여러 클라이언트가 구독하면 KIS에는 1개 등록.
    마지막 클라이언트가 떠나면 KIS에 unsubscribe.
    """

    def __init__(self) -> None:
        self._kis: KisWebSocketClient | None = None
        self._runner: asyncio.Task[Any] | None = None
        self._lock = asyncio.Lock()
        # ticker → set of WebSocket
        self._subs: dict[str, set[WebSocket]] = {}

    async def ensure_running(self) -> None:
        async with self._lock:
            if self._kis is None:
                self._kis = KisWebSocketClient()
            if self._runner is None or self._runner.done():
                await self._kis.connect()
                self._runner = asyncio.create_task(self._kis.run_forever())
                logger.info("KisFanout: KIS WS runner 시작")

    @property
    def kis(self) -> KisWebSocketClient:
        if self._kis is None:
            raise RuntimeError("KisFanout 미초기화 — ensure_running() 먼저 호출")
        return self._kis

    async def add(self, ticker: str, ws: WebSocket) -> None:
        ticker = ticker.zfill(6)
        async with self._lock:
            first_time = ticker not in self._subs or not self._subs[ticker]
            self._subs.setdefault(ticker, set()).add(ws)

        if first_time:
            await self.kis.subscribe(
                ticker, "H0STCNT0", self._make_dispatcher(ticker)
            )

    async def remove(self, ticker: str, ws: WebSocket) -> None:
        ticker = ticker.zfill(6)
        async with self._lock:
            if ticker not in self._subs:
                return
            self._subs[ticker].discard(ws)
            empty = not self._subs[ticker]
            if empty:
                del self._subs[ticker]

        if empty:
            try:
                await self.kis.unsubscribe(ticker, "H0STCNT0")
            except Exception as e:
                logger.debug(f"KIS unsubscribe {ticker} 실패: {e}")

    async def remove_all_for(self, ws: WebSocket) -> None:
        """클라이언트 disconnect 시 해당 ws의 모든 구독 정리."""
        async with self._lock:
            tickers = [t for t, ws_set in self._subs.items() if ws in ws_set]
        for t in tickers:
            await self.remove(t, ws)

    def _make_dispatcher(self, ticker: str):
        async def _dispatch(tick: dict[str, Any]) -> None:
            payload = {"type": "tick", "ticker": ticker, "data": tick}
            # 스냅샷 카피 (반복 중 변경 방지)
            async with self._lock:
                subs = list(self._subs.get(ticker, []))
            for ws in subs:
                try:
                    await ws.send_json(payload)
                except Exception as e:
                    logger.debug(f"WS send {ticker} 실패 (클라이언트 끊김?): {e}")

        return _dispatch


_fanout = KisFanout()


# ──────────────────────────────────────────────
# WebSocket endpoint
# ──────────────────────────────────────────────


@router.websocket("/api/kis/ws/stream")
async def stream(ws: WebSocket) -> None:
    """KIS 실시간 체결가 스트림.

    인증: 현재 미적용 (Phase 3D MVP). prod 전환 시 query token 검증 추가.
    """
    await ws.accept()
    try:
        await _fanout.ensure_running()
    except Exception as e:
        await ws.send_json({"type": "error", "message": f"KIS 초기화 실패: {e}"})
        await ws.close()
        return

    try:
        while True:
            msg = await ws.receive_json()
            action = msg.get("action")
            tickers = msg.get("tickers", []) or []

            if action == "subscribe":
                for t in tickers:
                    try:
                        await _fanout.add(str(t), ws)
                        await ws.send_json({"type": "subscribed", "ticker": str(t).zfill(6)})
                    except Exception as e:
                        await ws.send_json({
                            "type": "error",
                            "ticker": str(t),
                            "message": str(e),
                        })

            elif action == "unsubscribe":
                for t in tickers:
                    await _fanout.remove(str(t), ws)
                    await ws.send_json({"type": "unsubscribed", "ticker": str(t).zfill(6)})

            elif action == "ping":
                await ws.send_json({"type": "pong"})

            else:
                await ws.send_json({
                    "type": "error",
                    "message": f"unknown action: {action!r}",
                })
    except WebSocketDisconnect:
        logger.debug("WS client disconnected")
    except Exception as e:
        logger.warning(f"WS 예외: {type(e).__name__}: {e}")
    finally:
        await _fanout.remove_all_for(ws)
