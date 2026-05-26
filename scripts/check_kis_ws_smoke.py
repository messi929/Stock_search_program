"""KIS WebSocket Phase 2 라이브 smoke test.

사용법:
    py scripts/check_kis_ws_smoke.py [duration_sec]

기본 30초 수신 후 종료. 005930(삼성전자) 실시간 체결가 구독.

⚠️ 장 마감 후엔 데이터가 안 오거나 매우 적음 (정상 — 동작 자체는 검증됨).
⚠️ 한 계정당 동시 WebSocket 1개. 다른 곳에서 접속 중이면 끊김 가능.
"""

from __future__ import annotations

import asyncio
import io
import os
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # type: ignore

load_dotenv(ROOT / ".env")

from utils.data_collectors.kis_websocket import KisWebSocketClient  # noqa: E402


async def run(duration: float = 30.0) -> int:
    env = os.environ.get("KIS_ENV", "real")
    app_key = os.environ.get(
        "KIS_PAPER_APP_KEY" if env == "paper" else "KIS_APP_KEY", ""
    )
    if not app_key:
        print(f"❌ KIS_{'PAPER_' if env == 'paper' else ''}APP_KEY 미설정")
        return 1

    print(f"━━━ KIS WebSocket Smoke (env={env}, duration={duration}s) ━━━")
    print(f"app_key prefix: {app_key[:6]}***")

    client = KisWebSocketClient()

    # 1) approval_key
    print("\n[1] approval_key 발급")
    try:
        key = client.issue_approval_key()
        print(f"  ✅ approval_key 앞 12자: {key[:12]}***")
    except Exception as e:
        print(f"  ❌ approval_key 실패: {type(e).__name__}: {e}")
        return 2

    # 2) tick handler — 5개까지만 상세 출력, 이후 카운트만
    counter = {"n": 0}

    async def on_tick(tick: dict) -> None:
        counter["n"] += 1
        if counter["n"] <= 5:
            print(
                f"  [{counter['n']:>3}] {tick.get('ticker')} "
                f"{tick.get('exec_time')} "
                f"price={tick.get('price')} "
                f"chg={tick.get('prdy_vrss')} ({tick.get('prdy_ctrt')}%) "
                f"vol={tick.get('cntg_vol')} cum={tick.get('acml_vol')}"
            )
        elif counter["n"] % 50 == 0:
            print(f"  ... {counter['n']} ticks 누적")

    # 3) connect + subscribe
    print(f"\n[2] connect → subscribe 005930 (H0STCNT0)")
    await client.connect()
    await client.subscribe("005930", "H0STCNT0", on_tick)

    # 4) run for duration
    print(f"\n[3] {duration}초 동안 수신 (장 마감 후엔 0건 정상)")
    runner = asyncio.create_task(client.run_forever())
    try:
        await asyncio.sleep(duration)
    finally:
        await client.disconnect()
        try:
            await asyncio.wait_for(runner, timeout=3.0)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            runner.cancel()

    print(f"\n━━━ 최종 stats ━━━")
    print(f"  {client.stats.summary()}")
    print(f"  ticks 수신: {counter['n']}")
    print("\n✅ Smoke test 완료 (장중이면 ticks > 0, 마감 후면 0~소수 정상)")
    return 0


def main() -> int:
    duration = float(sys.argv[1]) if len(sys.argv) > 1 else 30.0
    try:
        return asyncio.run(run(duration))
    except KeyboardInterrupt:
        print("\n중단됨")
        return 130


if __name__ == "__main__":
    sys.exit(main())
