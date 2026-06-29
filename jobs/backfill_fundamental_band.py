"""밸류에이션 밴드 백필 잡 (jobs.backfill_fundamental_band) — 1b/1c.

KR 대형주의 PER/PBR 역사 밴드 + EPS 사이클 요약을 pykrx에서 당겨 Firestore
`fundamental_band/{ticker}`에 적재한다. 마케팅 글(marketer)이 '현황 단일 PER 함정'을
자기 역사 밴드로 방어하는 데 쓴다(경기민감주 PER 함정 — 호황 이익피크 저PER 착시).

⚠️ KRX 펀더멘탈 엔드포인트는 야간점검 시 빈 응답 → **낮 시간(KRX 운영 중)에 실행**할 것.
   초반 연속 빈 응답이면 조기 중단(야간 churn 방지).

실행:
  python -m jobs.backfill_fundamental_band               # KR 시총 상위 300, 5년
  python -m jobs.backfill_fundamental_band --limit 100   # 상위 100
  python -m jobs.backfill_fundamental_band --years 3
  python -m jobs.backfill_fundamental_band --dry-run     # 수집·계산만, 저장 X
"""

from __future__ import annotations

import argparse
import time
from datetime import datetime, timedelta
from typing import Optional

from loguru import logger


def _kr_universe(limit: int) -> list[str]:
    """KR 시총 상위 종목코드 리스트(밴드 백필 대상)."""
    try:
        from screener.db.repository import load_stocks

        df = load_stocks("kr")
        if df is None or df.empty:
            return []
        d = df.copy()
        if "market_cap" in d.columns:
            d = d.nlargest(limit, "market_cap")
        return d["ticker"].astype(str).tolist()[:limit]
    except Exception as e:
        logger.warning(f"[band] 유니버스 로드 실패: {e}")
        return []


def run_backfill(
    limit: int = 300,
    years: int = 5,
    sleep_sec: float = 1.0,
    dry_run: bool = False,
    flush_every: int = 50,
) -> dict:
    """밴드 백필 메인. pykrx 1s/호출 레이트리밋.

    인증 KRX 펀더멘탈 fetch가 종목당 ~10~12초로 무거워 전체 실행이 ~1시간 → 끝에서
    일괄 저장하면 중도 타임아웃 시 전손. 따라서 `flush_every`종목마다 증분 저장한다
    (save_fundamental_band은 종목당 덮어쓰기라 재호출 안전).
    """
    from screener.core.fundamental_band import compute_band, fetch_fundamental_history
    from screener.db.repository import save_fundamental_band

    tickers = _kr_universe(limit)
    if not tickers:
        logger.error("[band] 유니버스 비어있음 — 중단(load_stocks 결손?)")
        return {"computed": 0, "saved": 0}

    todate = datetime.now().strftime("%Y%m%d")
    fromdate = (datetime.now() - timedelta(days=int(years * 365.25))).strftime("%Y%m%d")
    logger.info(f"[band] 백필 시작: {len(tickers)}종목, {fromdate}~{todate}")

    bands: dict = {}          # 전체 누적(dry-run 샘플·집계용)
    pending: dict = {}        # 아직 저장 안 한 버퍼(증분 flush 대상)
    saved = 0
    empty_streak = 0

    def _flush() -> None:
        """버퍼를 저장하고 비운다(비-dry-run)."""
        nonlocal saved, pending
        if pending and not dry_run:
            saved += save_fundamental_band(pending)
            pending = {}

    for i, t in enumerate(tickers):
        df = fetch_fundamental_history(t, fromdate, todate)
        if df is None:
            empty_streak += 1
            # 초반 연속 빈 응답 = KRX 펀더멘탈 점검/인증 결손 추정 → 조기 중단(낮에 재실행).
            if i < 10 and empty_streak >= 6:
                logger.error(
                    "[band] 초반 연속 빈 응답 — KRX 펀더멘탈 점검/인증 결손 추정, 중단"
                )
                return {"computed": len(bands), "saved": saved, "aborted": True}
            time.sleep(sleep_sec)
            continue
        empty_streak = 0
        band = compute_band(df, t)
        if band:
            bands[t] = band
            pending[t] = band
        # flush_every '수집'마다 증분 저장 → 중도 타임아웃에도 직전까지 보존.
        if len(pending) >= flush_every:
            _flush()
        if (i + 1) % 50 == 0:
            logger.info(f"[band] 진행 {i + 1}/{len(tickers)} (수집 {len(bands)} 저장 {saved})")
        time.sleep(sleep_sec)

    logger.info(f"[band] 계산 완료: {len(bands)}/{len(tickers)}종목")

    if dry_run:
        from screener.core.fundamental_band import band_facts, cycle_assessment

        for t, b in list(bands.items())[:3]:
            print("\n" + "=" * 56)
            print(f"[{t}] samples={b.get('samples')} per={b.get('per')} eps={b.get('eps')}")
            cur_per = (b.get("per") or {}).get("median")
            print(band_facts(b, cur_per, (b.get("pbr") or {}).get("median")))
            print("사이클판정:", cycle_assessment(b, cur_per) or "(없음)")
    else:
        _flush()  # 잔여 버퍼 저장

    return {"computed": len(bands), "saved": saved}


def main(argv: Optional[list[str]] = None) -> int:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:
        pass

    p = argparse.ArgumentParser(description="밸류에이션 밴드 백필 (PER/PBR 역사 + EPS 사이클)")
    p.add_argument("--limit", type=int, default=300, help="KR 시총 상위 N종목 (기본 300)")
    p.add_argument("--years", type=int, default=5, help="히스토리 기간(년, 기본 5)")
    p.add_argument("--sleep", type=float, default=1.0, help="pykrx 호출 간격(초, 기본 1.0)")
    p.add_argument("--flush-every", type=int, default=50, help="N종목마다 증분 저장(기본 50)")
    p.add_argument("--dry-run", action="store_true", help="수집·계산만, 저장 X")
    a = p.parse_args(argv)

    res = run_backfill(
        limit=a.limit,
        years=a.years,
        sleep_sec=a.sleep,
        dry_run=a.dry_run,
        flush_every=a.flush_every,
    )
    logger.info(f"[band] 결과: {res}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
