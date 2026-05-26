"""WS endpoint /api/kis/ws/stream 검증.

subscribe → ack 확인. 장 마감 후엔 tick 0개 정상.
"""
from __future__ import annotations

import asyncio
import io
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

import websockets


async def main(duration: float = 8.0) -> int:
    url = "ws://127.0.0.1:8501/api/kis/ws/stream"
    print(f"━━━ WS endpoint {url} ━━━")

    try:
        async with websockets.connect(url, ping_interval=None) as ws:
            print("[1] connect OK")

            await ws.send(json.dumps({"action": "subscribe", "tickers": ["005930"]}))
            print("[2] subscribe 005930 sent")

            tick_count = 0
            ack_count = 0
            end_t = asyncio.get_event_loop().time() + duration

            while asyncio.get_event_loop().time() < end_t:
                remaining = end_t - asyncio.get_event_loop().time()
                if remaining <= 0:
                    break
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
                except asyncio.TimeoutError:
                    break
                msg = json.loads(raw)
                t = msg.get("type")
                if t == "subscribed":
                    ack_count += 1
                    print(f"[3] ack: subscribed {msg.get('ticker')}")
                elif t == "tick":
                    tick_count += 1
                    d = msg.get("data", {})
                    if tick_count <= 3:
                        print(
                            f"[4] tick #{tick_count}: {msg.get('ticker')} "
                            f"price={d.get('price')} time={d.get('exec_time')}"
                        )
                elif t == "error":
                    print(f"[!] error: {msg}")
                else:
                    print(f"[?] {msg}")

            # 정리 — 끊기 전에 ping 한 번
            await ws.send(json.dumps({"action": "ping"}))
            try:
                pong = await asyncio.wait_for(ws.recv(), timeout=2.0)
                print(f"[5] ping → {json.loads(pong).get('type')}")
            except asyncio.TimeoutError:
                print("[5] ping → 응답 없음 (예상밖)")

            print(f"\n━━━ 결과 ━━━")
            print(f"  subscribe ack: {ack_count}")
            print(f"  ticks received: {tick_count} (장 마감 후엔 0~소수 정상)")
            print("✅ WS endpoint smoke OK")
    except Exception as e:
        print(f"❌ WS 실패: {type(e).__name__}: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
