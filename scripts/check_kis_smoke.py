"""KIS Phase 0 라이브 smoke test.

사용법:
    cd C:\\src\\Stock_search_program
    py scripts/check_kis_smoke.py

검증 항목:
    1. .env 로드 + KIS_APP_KEY/SECRET 존재 확인
    2. access_token 발급 또는 파일 캐시 hit 확인
    3. 삼성전자(005930) 현재가 조회
    4. 삼성전자 일봉 5개 조회
    5. 두 번째 클라이언트로 token 캐시 hit 검증
    6. stats 출력

⚠️ access_token은 1분 1회 발급 정책. 이 스크립트를 반복 실행해도
   파일 캐시(/tmp/kis_token_real.json)가 작동하므로 EGW00133 락은 안 걸림.
"""

from __future__ import annotations

import io
import os
import sys
from pathlib import Path

# Windows PowerShell cp949 콘솔 대비 — UTF-8 강제
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

# 프로젝트 루트 sys.path 등록
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # type: ignore

load_dotenv(ROOT / ".env")

from utils.data_collectors.kis_client import KisClient  # noqa: E402


def main() -> int:
    env = os.environ.get("KIS_ENV", "real")
    app_key = os.environ.get(
        "KIS_PAPER_APP_KEY" if env == "paper" else "KIS_APP_KEY", ""
    )
    if not app_key:
        print(f"❌ KIS_{'PAPER_' if env == 'paper' else ''}APP_KEY 미설정")
        return 1

    print(f"━━━ KIS Phase 0 Smoke Test (env={env}) ━━━")
    print(f"app_key prefix: {app_key[:6]}***")

    # 1. 첫 클라이언트 — token 발급 또는 캐시 hit
    print("\n[1] 첫 클라이언트: get_access_token()")
    client = KisClient()
    try:
        token = client.get_access_token()
    except Exception as e:
        print(f"❌ token 발급 실패: {type(e).__name__}: {e}")
        return 2
    print(f"  ✅ token (앞 12자): {token[:12]}***")
    print(f"  expires_at: {client._token_expires_at:.0f}")
    print(f"  stats: {client.stats.summary()}")

    # 2. 현재가
    print("\n[2] 005930 (삼성전자) 현재가")
    price = client.get_current_price("005930")
    if not price:
        print("  ❌ 현재가 응답 비어있음")
        return 3
    fields_of_interest = [
        ("stck_prpr", "현재가"),
        ("prdy_vrss", "전일대비"),
        ("prdy_ctrt", "등락률(%)"),
        ("acml_vol", "거래량"),
        ("stck_oprc", "시가"),
        ("stck_hgpr", "고가"),
        ("stck_lwpr", "저가"),
        ("stck_mxpr", "상한가"),
        ("stck_llam", "하한가"),
    ]
    for k, label in fields_of_interest:
        print(f"  {label:8s} ({k:12s}): {price.get(k, '—')}")

    # 3. 일봉 5개
    print("\n[3] 005930 일봉 5개 (최근 → 과거)")
    bars = client.get_daily_chart("005930", period="D")
    if not bars:
        print("  ❌ 일봉 응답 비어있음")
        return 4
    print(f"  총 {len(bars)}개 응답 → 앞 5개 표시")
    for bar in bars[:5]:
        print(
            f"  {bar.get('stck_bsop_date')} "
            f"O={bar.get('stck_oprc')} H={bar.get('stck_hgpr')} "
            f"L={bar.get('stck_lwpr')} C={bar.get('stck_clpr')} "
            f"V={bar.get('acml_vol')}"
        )

    # 4. 10호가
    print("\n[4] 005930 10호가")
    ob = client.get_orderbook("005930")
    if not ob:
        print("  ❌ 호가 응답 비어있음")
    else:
        orderbook = ob["orderbook"]
        expected = ob["expected"]
        print(f"  접수시각: {orderbook.get('aspr_acpt_hour')}")
        # 매도 1~5호가, 매수 1~5호가 (10호가는 너무 길어 5호가만 표시)
        for i in range(5, 0, -1):
            ap = orderbook.get(f"askp{i}", "—")
            aq = orderbook.get(f"askp_rsqn{i}", "—")
            print(f"  매도{i:>2}호가: {ap:>10} (잔량 {aq})")
        print("  ─" * 20)
        for i in range(1, 6):
            bp = orderbook.get(f"bidp{i}", "—")
            bq = orderbook.get(f"bidp_rsqn{i}", "—")
            print(f"  매수{i:>2}호가: {bp:>10} (잔량 {bq})")
        print(f"  매도총잔량: {orderbook.get('total_askp_rsqn')}")
        print(f"  매수총잔량: {orderbook.get('total_bidp_rsqn')}")
        if expected and expected.get("antc_cnpr"):
            print(f"  예상체결가: {expected.get('antc_cnpr')} (전일대비 {expected.get('antc_cntg_vrss')})")

    # 5. 분봉 30개
    print("\n[5] 005930 분봉 (최근 30분)")
    mbars = client.get_minute_chart("005930")
    if not mbars:
        print("  ❌ 분봉 응답 비어있음")
    else:
        print(f"  총 {len(mbars)}개 응답 → 앞 5개 표시")
        for bar in mbars[:5]:
            print(
                f"  {bar.get('stck_bsop_date')} {bar.get('stck_cntg_hour')} "
                f"O={bar.get('stck_oprc')} H={bar.get('stck_hgpr')} "
                f"L={bar.get('stck_lwpr')} C={bar.get('stck_prpr')} "
                f"V={bar.get('cntg_vol')}"
            )

    # 6. 투자자별 매매동향
    print("\n[6] 005930 투자자별 매매동향 (최근 5일)")
    inv = client.get_investor_trend("005930")
    if not inv:
        print("  ❌ 투자자 응답 비어있음")
    else:
        print(f"  총 {len(inv)}일 응답 → 앞 5일 표시")
        for row in inv[:5]:
            print(
                f"  {row.get('stck_bsop_date')} "
                f"개인 {row.get('prsn_ntby_qty'):>14} "
                f"외인 {row.get('frgn_ntby_qty'):>14} "
                f"기관 {row.get('orgn_ntby_qty'):>14}"
            )

    # 7. 두 번째 클라이언트 — 파일 캐시 hit 검증
    print("\n[7] 두 번째 클라이언트 (캐시 hit 기대)")
    client2 = KisClient()
    token2 = client2.get_access_token()
    if token2 == token:
        print(f"  ✅ 동일 토큰 — 파일 캐시 hit (hits={client2.stats.token_cache_hits})")
    else:
        print(f"  ⚠️ 토큰 달라짐 — 캐시 미동작? token_issues={client2.stats.token_issues}")

    print("\n━━━ 최종 stats ━━━")
    print(f"client #1: {client.stats.summary()}")
    print(f"client #2: {client2.stats.summary()}")
    print(f"\ntoken cache file: {client._token_cache_path}")
    print("\n✅ Smoke test PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
