"""KIS WebSocket 클라이언트 단위 테스트.

⚠️ 라이브 WS는 scripts/check_kis_ws_smoke.py.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from utils.data_collectors.kis_websocket import (
    KIS_WS_PAPER,
    KIS_WS_REAL,
    KisWebSocketClient,
    parse_h0stcnt0,
)


# ──────────────────────────────────────────────
# 1. parse_h0stcnt0
# ──────────────────────────────────────────────


def test_parse_h0stcnt0_basic():
    # 005930 체결 raw (46개 필드 — 일부)
    raw = (
        "005930^160000^73000^2^500^0.69^72800^72500^73200^72400"
        "^73000^72900^100^10000000^730000000000^50^60^110^120.5"
        "^200^300^5^55.5^1.2^090000^2^200^150000^1^200^155500^1^500"
        "^20260526^A^N^200^300^1745247^1273640^0.5^9000000^1.1^0^^72500"
    )
    tick = parse_h0stcnt0(raw)
    assert tick["ticker"] == "005930"
    assert tick["exec_time"] == "160000"
    assert tick["price"] == "73000"
    assert tick["prdy_ctrt"] == "0.69"
    assert tick["acml_vol"] == "10000000"
    assert tick["bsop_date"] == "20260526"


def test_parse_h0stcnt0_with_extras():
    # 더 긴 필드 (KIS 확장)
    raw = "005930^160000^73000" + "^X" * 50
    tick = parse_h0stcnt0(raw)
    assert tick["ticker"] == "005930"
    # 정의되지 않은 필드는 raw_<index>로
    assert "raw_46" in tick


# ──────────────────────────────────────────────
# 2. 초기화 / env 분기
# ──────────────────────────────────────────────


def test_env_real(monkeypatch):
    monkeypatch.setenv("KIS_ENV", "real")
    monkeypatch.setenv("KIS_APP_KEY", "PS" + "X" * 34)
    monkeypatch.setenv("KIS_APP_SECRET", "S" * 180)
    c = KisWebSocketClient()
    assert c.env == "real"
    assert c.ws_url == KIS_WS_REAL
    assert c.max_subs == 41


def test_env_paper(monkeypatch):
    monkeypatch.setenv("KIS_ENV", "paper")
    monkeypatch.setenv("KIS_PAPER_APP_KEY", "PS" + "X" * 34)
    monkeypatch.setenv("KIS_PAPER_APP_SECRET", "S" * 180)
    c = KisWebSocketClient()
    assert c.env == "paper"
    assert c.ws_url == KIS_WS_PAPER
    assert c.max_subs == 16


# ──────────────────────────────────────────────
# 3. PINGPONG echo
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_pingpong_echo(monkeypatch):
    monkeypatch.setenv("KIS_ENV", "real")
    monkeypatch.setenv("KIS_APP_KEY", "PS" + "X" * 34)
    monkeypatch.setenv("KIS_APP_SECRET", "S" * 180)
    c = KisWebSocketClient()

    mock_ws = MagicMock()
    mock_ws.send = AsyncMock()
    c._ws = mock_ws

    ping_msg = {"header": {"tr_id": "PINGPONG"}, "body": {}}
    await c._handle_json(ping_msg)
    assert c.stats.pingpongs == 1
    mock_ws.send.assert_awaited_once()
    sent = mock_ws.send.await_args.args[0]
    assert json.loads(sent) == ping_msg


# ──────────────────────────────────────────────
# 4. subscribe + tick dispatch
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_subscribe_and_dispatch(monkeypatch):
    monkeypatch.setenv("KIS_ENV", "real")
    monkeypatch.setenv("KIS_APP_KEY", "PS" + "X" * 34)
    monkeypatch.setenv("KIS_APP_SECRET", "S" * 180)
    c = KisWebSocketClient()
    c._approval_key = "FAKE_APPROVAL"

    mock_ws = MagicMock()
    mock_ws.send = AsyncMock()
    c._ws = mock_ws

    received: list[dict[str, Any]] = []

    async def handler(tick: dict[str, Any]) -> None:
        received.append(tick)

    await c.subscribe("005930", "H0STCNT0", handler)
    # subscribe 메시지가 전송됐는지
    mock_ws.send.assert_awaited()
    sent = json.loads(mock_ws.send.await_args.args[0])
    assert sent["header"]["tr_type"] == "1"
    assert sent["body"]["input"]["tr_id"] == "H0STCNT0"
    assert sent["body"]["input"]["tr_key"] == "005930"

    # 데이터 프레임 처리
    raw = "0|H0STCNT0|001|005930^160000^73000^2^500^0.69" + "^0" * 40
    await c._handle_data_frame(raw)
    assert len(received) == 1
    assert received[0]["price"] == "73000"
    assert c.stats.ticks_dispatched == 1


@pytest.mark.asyncio
async def test_unknown_ticker_ignored(monkeypatch):
    monkeypatch.setenv("KIS_ENV", "real")
    monkeypatch.setenv("KIS_APP_KEY", "PS" + "X" * 34)
    monkeypatch.setenv("KIS_APP_SECRET", "S" * 180)
    c = KisWebSocketClient()
    raw = "0|H0STCNT0|001|999999^160000^73000" + "^0" * 43
    await c._handle_data_frame(raw)
    # 미등록 ticker → dispatch 안 됨
    assert c.stats.ticks_dispatched == 0


@pytest.mark.asyncio
async def test_subscription_limit(monkeypatch):
    monkeypatch.setenv("KIS_ENV", "paper")
    monkeypatch.setenv("KIS_PAPER_APP_KEY", "PS" + "X" * 34)
    monkeypatch.setenv("KIS_PAPER_APP_SECRET", "S" * 180)
    c = KisWebSocketClient()
    c.max_subs = 2  # 강제 작게

    async def handler(tick):
        pass

    await c.subscribe("000001", "H0STCNT0", handler)
    await c.subscribe("000002", "H0STCNT0", handler)
    with pytest.raises(RuntimeError, match="동시 구독 한도"):
        await c.subscribe("000003", "H0STCNT0", handler)
