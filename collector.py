"""독립 데이터 수집기 — 크롤링/서빙 분리 아키텍처.

사용법:
  # 전체 수집 (로컬 PC에서 주기적 실행)
  python collector.py --all

  # 개별 수집
  python collector.py --kr-snapshot
  python collector.py --us-snapshot
  python collector.py --fundamentals
  python collector.py --themes
  python collector.py --foreign-inst
  python collector.py --history
  python collector.py --us-history
  python collector.py --dividend

  # 스케줄 모드 (장중/장외 자동 판별, 무한 루프)
  python collector.py --schedule

아키텍처:
  [collector.py] → 크롤링 → Firestore 저장
  [Cloud Run]    ← Firestore 읽기 → API 서빙

이 스크립트는 Cloud Run과 독립적으로 실행됩니다.
로컬 PC, Cloud Functions, Cloud Scheduler + Cloud Run Job 등에서 실행 가능.
"""

import argparse
import os
import sys
import time
from datetime import datetime

from loguru import logger

# 로거 설정
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:HH:mm:ss}</green> | <level>{level:<7}</level> | {message}",
    level="INFO",
)

# Cloud Run Job 등 컨테이너 환경에서는 /tmp에 로그, 로컬에서는 현재 디렉토리
_log_dir = "/tmp" if os.environ.get("K_SERVICE") or os.environ.get("CLOUD_RUN_JOB") else "."
try:
    logger.add(
        os.path.join(_log_dir, "collector_{time:YYYY-MM-DD}.log"),
        rotation="1 day",
        retention="7 days",
        level="DEBUG",
    )
except Exception:
    pass  # 로그 파일 생성 실패 시 stderr만 사용


# ──────────────────────────────────────────────
# 텔레그램 알림
# ──────────────────────────────────────────────

def _send_alert(message: str):
    """텔레그램 봇으로 알림 전송.

    환경변수:
      TELEGRAM_BOT_TOKEN: 봇 토큰 (BotFather에서 발급)
      TELEGRAM_CHAT_ID: 수신할 채팅 ID (@userinfobot으로 확인)
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        logger.debug("텔레그램 미설정 — 알림 스킵")
        return

    try:
        import requests
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": f"📊 Stock Screener\n{message}",
            "parse_mode": "HTML",
        }
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            logger.info("텔레그램 알림 전송 완료")
        else:
            logger.warning(f"텔레그램 전송 실패: {resp.status_code}")
    except Exception as e:
        logger.warning(f"텔레그램 전송 오류: {e}")


def _send_signal_alerts():
    """시그널 충족 종목 텔레그램 알림.

    장중 갱신 후 호출. 조건:
    - buy_score >= 70 (적극매수)
    - is_pre_surge == 1 (급등 예보)
    - RSI <= 30 (과매도)
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        return

    from screener.db.repository import load_stocks

    try:
        kr = load_stocks("kr")
        if kr.empty:
            return

        alerts = []

        # 적극매수 종목 (buy_score >= 70)
        if "buy_score" in kr.columns:
            top_buy = kr[kr["buy_score"] >= 70].nlargest(5, "buy_score")
            if not top_buy.empty:
                lines = [f"  {r['name']}({r['ticker']}) {r['buy_score']:.0f}점" for _, r in top_buy.iterrows()]
                alerts.append("🔥 <b>적극매수 시그널</b>\n" + "\n".join(lines))

        # 급등 예보
        if "is_pre_surge" in kr.columns:
            pre_surge = kr[kr.get("is_pre_surge", 0) == 1]
            if len(pre_surge) > 0:
                top_ps = pre_surge.nlargest(min(5, len(pre_surge)), "pre_surge_score")
                lines = [f"  {r['name']}({r['ticker']}) 예보{r['pre_surge_score']}/5" for _, r in top_ps.iterrows()]
                alerts.append("🚀 <b>급등 예보</b>\n" + "\n".join(lines))

        # 과매도 반등 (RSI <= 30, 시총 1000억+)
        if "rsi" in kr.columns:
            oversold = kr[(kr["rsi"] > 0) & (kr["rsi"] <= 30) & (kr["market_cap"] >= 1000)]
            if not oversold.empty:
                top_os = oversold.nsmallest(min(5, len(oversold)), "rsi")
                lines = [f"  {r['name']}({r['ticker']}) RSI {r['rsi']:.0f}" for _, r in top_os.iterrows()]
                alerts.append("📉 <b>과매도 반등 기회</b>\n" + "\n".join(lines))

        # v6 Phase 5-2: 스마트 복합 알림
        # 외국인 연속매수 + 기술적 반등
        if "foreign_consecutive" in kr.columns and "rsi" in kr.columns:
            smart1 = kr[
                (kr["foreign_consecutive"] >= 5) &
                (kr["rsi"] > 0) & (kr["rsi"] <= 40) &
                (kr.get("golden_cross", pd.Series(0)) == 1)
            ]
            if not smart1.empty:
                lines = [f"  {r['name']}({r['ticker']}) 외국인{r['foreign_consecutive']}일연속+RSI{r['rsi']:.0f}" for _, r in smart1.head(5).iterrows()]
                alerts.append("🎯 <b>외국인 연속매수 + 기술반등</b>\n" + "\n".join(lines))

        # 수급 동반 + 목표가 괴리
        if "dual_buy" in kr.columns and "target_upside" in kr.columns:
            smart2 = kr[
                (kr["dual_buy"] == True) &
                (kr["target_upside"] > 20)
            ]
            if not smart2.empty:
                lines = [f"  {r['name']}({r['ticker']}) 동반매수+목표↑{r['target_upside']:.0f}%" for _, r in smart2.head(5).iterrows()]
                alerts.append("💎 <b>수급동반 + 실적기대</b>\n" + "\n".join(lines))

        if alerts:
            message = "\n\n".join(alerts)
            _send_alert(message)

    except Exception as e:
        logger.debug(f"시그널 알림 실패: {e}")


def _is_kr_market_hours() -> bool:
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    return (9 <= now.hour < 15) or (now.hour == 15 and now.minute <= 30)


def _is_us_market_hours() -> bool:
    now = datetime.now()
    if now.weekday() == 6:
        return False
    if now.weekday() == 5 and now.hour >= 6:
        return False
    return now.hour >= 23 or now.hour < 6


def collect_kr_snapshot():
    """KR 스냅샷 수집 → Firestore."""
    from screener.core.data_fetcher import fetch_daily_snapshot
    from screener.core.metrics import detect_surging_stocks
    from screener.db.repository import save_stocks, update_sync_metadata

    logger.info("=== KR 스냅샷 수집 시작 ===")
    snapshot = fetch_daily_snapshot()
    snapshot = detect_surging_stocks(snapshot)
    save_stocks(snapshot, "kr")
    update_sync_metadata(stocks_kr_updated_at=datetime.now().isoformat())
    logger.info(f"KR 스냅샷 완료: {len(snapshot)}종목")
    return snapshot


def collect_etf():
    """ETF 수집 → Firestore."""
    from screener.core.data_fetcher import fetch_etf_data
    from screener.db.repository import save_stocks, update_sync_metadata

    logger.info("=== ETF 수집 시작 ===")
    etf_df = fetch_etf_data()
    if not etf_df.empty:
        save_stocks(etf_df, "etf")
        update_sync_metadata(stocks_etf_updated_at=datetime.now().isoformat())
    logger.info(f"ETF 완료: {len(etf_df)}종목")
    return etf_df


def collect_us_snapshot():
    """US 스냅샷 수집 (시세 + 펀더멘탈) → Firestore."""
    from screener.core.data_fetcher import fetch_us_snapshot
    from screener.db.repository import save_stocks, update_sync_metadata

    logger.info("=== US 스냅샷 수집 시작 ===")
    us_df = fetch_us_snapshot()
    if not us_df.empty:
        save_stocks(us_df, "us")
        update_sync_metadata(stocks_us_updated_at=datetime.now().isoformat())
    logger.info(f"US 스냅샷 완료: {len(us_df)}종목")
    return us_df


def collect_fundamentals(snapshot=None):
    """KR 펀더멘탈 수집 → Firestore."""
    from screener.core.data_fetcher import fetch_naver_fundamentals, apply_fundamentals
    from screener.db.repository import save_stocks, load_stocks, update_sync_metadata

    logger.info("=== KR 펀더멘탈 수집 시작 ===")
    if snapshot is None:
        snapshot = load_stocks("kr")
    if snapshot.empty:
        logger.warning("KR 스냅샷 없음 — 펀더멘탈 스킵")
        return

    kr_stocks = snapshot[snapshot["market"].isin(["KOSPI", "KOSDAQ"])]
    top_tickers = kr_stocks.nlargest(500, "market_cap")["ticker"].tolist()
    fund_data = fetch_naver_fundamentals(top_tickers)
    if fund_data:
        snapshot = apply_fundamentals(snapshot, fund_data)
        fund_df = snapshot[snapshot["ticker"].isin(fund_data.keys())][
            ["ticker", "per", "pbr", "div_yield", "roe"]
        ]
        save_stocks(fund_df, "kr")
        update_sync_metadata(fundamentals_updated_at=datetime.now().isoformat())
        logger.info(f"KR 펀더멘탈 완료: {len(fund_data)}종목")


def collect_themes():
    """테마 수집 → Firestore."""
    from screener.core.data_fetcher import fetch_themes
    from screener.db.repository import save_themes, update_sync_metadata

    logger.info("=== 테마 수집 시작 ===")
    themes, stock_themes = fetch_themes()
    if themes:
        save_themes(themes, stock_themes)
        update_sync_metadata(themes_updated_at=datetime.now().isoformat())
    logger.info(f"테마 완료: {len(themes)}테마, {len(stock_themes)}종목")


def collect_foreign_inst(snapshot=None):
    """외국인/기관 순매수 수집 → Firestore."""
    from screener.core.data_fetcher import fetch_foreign_inst
    from screener.db.repository import save_stocks, load_stocks, update_sync_metadata
    import pandas as pd

    logger.info("=== 외국인/기관 수집 시작 ===")
    # 네이버 폴백용 ticker 목록 (pykrx 실패 시 사용)
    tickers = None
    if snapshot is not None and "ticker" in snapshot.columns:
        kr_mask = snapshot["market"].isin(["KOSPI", "KOSDAQ"])
        tickers = snapshot.loc[kr_mask, "ticker"].tolist()
    elif not tickers:
        try:
            kr_df = load_stocks("kr")
            if kr_df is not None and "ticker" in kr_df.columns:
                tickers = kr_df["ticker"].tolist()
        except Exception:
            pass
    fi_data = fetch_foreign_inst(tickers=tickers)
    if fi_data:
        rows = [{"ticker": t, **d} for t, d in fi_data.items()]
        fi_df = pd.DataFrame(rows)
        save_stocks(fi_df, "kr")
        update_sync_metadata(foreign_inst_updated_at=datetime.now().isoformat())

        # v6: 수급 이력 저장
        try:
            from screener.db.repository import save_supply_history
            save_supply_history(fi_data)
        except Exception as e:
            logger.warning(f"supply_history 저장 실패: {e}")

    logger.info(f"외국인/기관 완료: {len(fi_data)}종목")


def collect_dividend(snapshot=None):
    """배당 지속성 수집 → Firestore."""
    from screener.core.data_fetcher import fetch_dividend_history
    from screener.db.repository import save_stocks, load_stocks, update_sync_metadata
    import pandas as pd

    logger.info("=== 배당 지속성 수집 시작 ===")
    if snapshot is None:
        snapshot = load_stocks("kr")
    if snapshot.empty:
        logger.warning("KR 스냅샷 없음 — 배당 스킵")
        return

    div_tickers = snapshot[snapshot.get("div_yield", pd.Series(dtype=float)) > 0]["ticker"].tolist()
    if not div_tickers:
        # div_yield 컬럼이 없거나 0인 경우, 전체 상위 종목에서 시도
        logger.info("배당 종목 없음 — 스킵")
        return

    div_data = fetch_dividend_history(div_tickers)
    if div_data:
        rows = [{"ticker": t, **d} for t, d in div_data.items()]
        div_df = pd.DataFrame(rows)
        save_stocks(div_df, "kr")
        update_sync_metadata(dividend_updated_at=datetime.now().isoformat())
    logger.info(f"배당 완료: {len(div_data)}종목")


def collect_score_history():
    """v6: 일별 buy_score 스냅샷 저장 (장 마감 후 1회)."""
    from screener.db.repository import load_stocks, save_score_history

    logger.info("=== score_history 저장 시작 ===")
    kr = load_stocks("kr")
    if kr.empty or "buy_score" not in kr.columns:
        logger.warning("buy_score 데이터 없음 — score_history 스킵")
        return

    today = datetime.now().strftime("%Y-%m-%d")
    scores = {}
    for _, row in kr.iterrows():
        ticker = str(row.get("ticker", ""))
        bs = float(row.get("buy_score", 0))
        if ticker and bs > 0:
            scores[ticker] = {
                "buy_score": round(bs, 1),
                "buy_grade": str(row.get("buy_grade", "")),
                "close": int(row.get("close", 0)),
            }

    if scores:
        save_score_history(today, scores)
    logger.info(f"score_history 완료: {len(scores)}종목")


def collect_kr_history(snapshot=None):
    """KR 히스토리 + 기술지표 수집 → Firestore."""
    from screener.core.data_fetcher import fetch_historical_ohlcv
    from screener.core.metrics import (
        calculate_moving_averages, calculate_rsi,
        calculate_52week, detect_surging_stocks,
        calculate_buy_score,
    )
    from screener.db.repository import save_stocks, save_history, load_stocks, update_sync_metadata

    logger.info("=== KR 히스토리 수집 시작 ===")
    if snapshot is None:
        snapshot = load_stocks("kr")
    if snapshot.empty:
        logger.warning("KR 스냅샷 없음 — 히스토리 스킵")
        return

    kr = snapshot[snapshot["market"].isin(["KOSPI", "KOSDAQ"])]
    # v6.1: 커버리지 확대 (300+200 → 600+400, 중복 제거 시 ~700-800종목)
    top_cap = kr.nlargest(600, "market_cap")["ticker"].tolist()
    top_vol = kr.nlargest(400, "volume")["ticker"].tolist()
    target = list(set(top_cap + top_vol))

    history = fetch_historical_ohlcv(target)
    if history.empty:
        logger.warning("히스토리 수집 실패")
        return

    save_history(history)

    # 기술지표 계산 후 스냅샷에 반영
    snapshot = calculate_moving_averages(history, snapshot)
    rsi = calculate_rsi(history)
    if not rsi.empty:
        rsi_df = rsi.reset_index()
        rsi_df.columns = ["ticker", "rsi"]
        snapshot = snapshot.merge(rsi_df, on="ticker", how="left", suffixes=("_old", ""))
        if "rsi_old" in snapshot.columns:
            snapshot["rsi"] = snapshot["rsi"].fillna(snapshot["rsi_old"])
            snapshot.drop(columns=["rsi_old"], inplace=True)
        snapshot["rsi"] = snapshot["rsi"].fillna(0)

    vs_high, vs_low = calculate_52week(history)
    if not vs_high.empty:
        h_df = vs_high.reset_index(); h_df.columns = ["ticker", "vs_high_52w"]
        l_df = vs_low.reset_index(); l_df.columns = ["ticker", "vs_low_52w"]
        snapshot = snapshot.merge(h_df, on="ticker", how="left", suffixes=("_old", ""))
        if "vs_high_52w_old" in snapshot.columns:
            snapshot["vs_high_52w"] = snapshot["vs_high_52w"].fillna(snapshot["vs_high_52w_old"])
            snapshot.drop(columns=["vs_high_52w_old"], inplace=True)
        snapshot = snapshot.merge(l_df, on="ticker", how="left", suffixes=("_old", ""))
        if "vs_low_52w_old" in snapshot.columns:
            snapshot["vs_low_52w"] = snapshot["vs_low_52w"].fillna(snapshot["vs_low_52w_old"])
            snapshot.drop(columns=["vs_low_52w_old"], inplace=True)

    snapshot = detect_surging_stocks(snapshot)

    # v6: 수급 시그널 계산
    try:
        from screener.core.metrics import calculate_supply_signals
        from screener.db.repository import load_all_supply_history
        supply_hist = load_all_supply_history()
        if supply_hist:
            snapshot = calculate_supply_signals(snapshot, supply_hist)
    except Exception as e:
        logger.warning(f"수급 시그널 계산 실패: {e}")

    snapshot = calculate_buy_score(snapshot)
    kr_data = snapshot[snapshot["market"].isin(["KOSPI", "KOSDAQ"])]
    save_stocks(kr_data, "kr")
    update_sync_metadata(history_updated_at=datetime.now().isoformat())
    logger.info(f"KR 히스토리 완료: {len(target)}종목")


def collect_us_history():
    """US 히스토리 수집 + 기술지표 → Firestore."""
    import yfinance as yf
    import pandas as pd
    from screener.core.metrics import (
        calculate_moving_averages, calculate_rsi,
        calculate_52week, detect_surging_stocks,
        calculate_buy_score,
    )
    from screener.db.repository import save_stocks, save_history, load_stocks, update_sync_metadata
    from screener.config import HISTORY_DAYS

    logger.info("=== US 히스토리 수집 시작 ===")
    us_df = load_stocks("us")
    if us_df.empty:
        logger.warning("US 스냅샷 없음 — 히스토리 스킵")
        return

    # v6.1: 시가총액 상위 + 거래량 상위 (커버리지 확대)
    top_cap = us_df.nlargest(300, "market_cap")["ticker"].tolist()
    top_vol = us_df.nlargest(200, "volume")["ticker"].tolist()
    targets = list(set(top_cap + top_vol))
    logger.info(f"US 히스토리 대상: {len(targets)}종목")

    # yfinance 배치 다운로드
    all_history = []
    batch_size = 100
    period_days = HISTORY_DAYS * 2  # 여유롭게

    for i in range(0, len(targets), batch_size):
        batch = targets[i:i + batch_size]
        try:
            data = yf.download(
                batch, period=f"{period_days}d", group_by="ticker",
                auto_adjust=True, threads=True, progress=False,
            )
            if data.empty:
                continue

            for sym in batch:
                try:
                    if len(batch) == 1:
                        sym_data = data
                    else:
                        sym_data = data[sym] if sym in data.columns.get_level_values(0) else None

                    if sym_data is None or sym_data.empty:
                        continue

                    sym_data = sym_data.dropna(subset=["Close"])
                    if len(sym_data) < 5:
                        continue

                    df = sym_data.tail(HISTORY_DAYS).reset_index()
                    df = df.rename(columns={
                        "Date": "date", "Open": "open", "High": "high",
                        "Low": "low", "Close": "close", "Volume": "volume",
                    })
                    df["ticker"] = sym
                    all_history.append(df[["date", "ticker", "open", "high", "low", "close", "volume"]])
                except Exception:
                    continue

            logger.info(f"  US 히스토리 배치: {min(i + batch_size, len(targets))}/{len(targets)}")
        except Exception as e:
            logger.warning(f"US 히스토리 배치 실패 ({i}~{i+batch_size}): {e}")

    if not all_history:
        logger.warning("US 히스토리 수집 실패")
        return

    history = pd.concat(all_history, ignore_index=True)
    save_history(history)

    # 기술지표 계산
    us_df = calculate_moving_averages(history, us_df)
    rsi = calculate_rsi(history)
    if not rsi.empty:
        rsi_df = rsi.reset_index()
        rsi_df.columns = ["ticker", "rsi"]
        us_df = us_df.merge(rsi_df, on="ticker", how="left", suffixes=("_old", ""))
        if "rsi_old" in us_df.columns:
            us_df["rsi"] = us_df["rsi"].fillna(us_df["rsi_old"])
            us_df.drop(columns=["rsi_old"], inplace=True)
        us_df["rsi"] = us_df["rsi"].fillna(0)

    vs_high, vs_low = calculate_52week(history)
    if not vs_high.empty:
        h_df = vs_high.reset_index(); h_df.columns = ["ticker", "vs_high_52w"]
        l_df = vs_low.reset_index(); l_df.columns = ["ticker", "vs_low_52w"]
        us_df = us_df.merge(h_df, on="ticker", how="left", suffixes=("_old", ""))
        if "vs_high_52w_old" in us_df.columns:
            us_df["vs_high_52w"] = us_df["vs_high_52w"].fillna(us_df["vs_high_52w_old"])
            us_df.drop(columns=["vs_high_52w_old"], inplace=True)
        us_df = us_df.merge(l_df, on="ticker", how="left", suffixes=("_old", ""))
        if "vs_low_52w_old" in us_df.columns:
            us_df["vs_low_52w"] = us_df["vs_low_52w"].fillna(us_df["vs_low_52w_old"])
            us_df.drop(columns=["vs_low_52w_old"], inplace=True)

    us_df = detect_surging_stocks(us_df)
    us_df = calculate_buy_score(us_df)
    save_stocks(us_df, "us")
    update_sync_metadata(us_history_updated_at=datetime.now().isoformat())
    logger.info(f"US 히스토리 완료: {len(targets)}종목, {len(history)}행")


def validate_data() -> dict:
    """수집된 데이터 품질 검증. 이상 항목을 반환."""
    from screener.db.repository import load_stocks
    import pandas as pd

    logger.info("=" * 60)
    logger.info("데이터 품질 검증 시작")
    logger.info("=" * 60)

    issues = []
    stats = {}

    # KR 스냅샷 검증
    kr = load_stocks("kr")
    stats["kr_total"] = len(kr)
    if kr.empty:
        issues.append("CRITICAL: KR 스냅샷 0건")
    else:
        # 시가총액 0인 종목 비율
        zero_mcap = (kr["market_cap"] == 0).sum()
        if zero_mcap > len(kr) * 0.1:
            issues.append(f"WARNING: KR 시가총액 0 종목 {zero_mcap}건 ({zero_mcap/len(kr)*100:.1f}%)")

        # 등락률 이상치 (±30% 이상)
        extreme_change = kr[kr["change_pct"].abs() > 30]
        if len(extreme_change) > 50:
            issues.append(f"WARNING: 등락률 ±30% 초과 {len(extreme_change)}건 — 데이터 오류 가능성")

        # 펀더멘탈 커버리지
        has_per = (kr["per"] > 0).sum() if "per" in kr.columns else 0
        stats["kr_has_per"] = has_per
        if has_per < 100:
            issues.append(f"WARNING: KR PER 데이터 {has_per}건 — 펀더멘탈 수집 부족")

        # 기술지표 커버리지
        has_rsi = (kr["rsi"] > 0).sum() if "rsi" in kr.columns else 0
        stats["kr_has_rsi"] = has_rsi
        if has_rsi < 100:
            issues.append(f"WARNING: KR RSI 데이터 {has_rsi}건 — 히스토리 수집 부족")

        # 급등 예보 검증 — 비정상적으로 많으면 경고
        pre_surge = (kr.get("is_pre_surge", pd.Series(dtype=int)) == 1).sum()
        stats["kr_pre_surge"] = int(pre_surge)
        if pre_surge > 200:
            issues.append(f"WARNING: 급등예보 {pre_surge}건 — 기준 조정 필요 (200건 초과)")
        elif pre_surge == 0 and has_rsi > 0:
            issues.append(f"INFO: 급등예보 0건 — 시그널 조건이 엄격하거나 데이터 문제")

        # 카테고리별 결과 수 시뮬레이션
        from screener.core.screener import CATEGORIES, apply_filters
        for cat_id, cat_info in CATEGORIES.items():
            if cat_id == "watchlist":
                continue
            try:
                _, total = apply_filters(kr, cat_info["filter"])
                stats[f"cat_{cat_id}"] = total
                if total == 0 and cat_id in ("bluechip", "smallcap"):
                    issues.append(f"WARNING: {cat_info['name']} 0건 — 필터 문제")
                elif total > 500 and cat_id not in ("bluechip", "smallcap", "etf", "theme"):
                    issues.append(f"WARNING: {cat_info['name']} {total}건 — 필터가 너무 느슨")
            except Exception as e:
                issues.append(f"ERROR: {cat_info['name']} 검증 실패: {e}")

    # US 스냅샷 검증
    us = load_stocks("us")
    stats["us_total"] = len(us)
    if us.empty:
        issues.append("WARNING: US 스냅샷 0건")
    else:
        us_mcap_zero = (us["market_cap"] == 0).sum()
        if us_mcap_zero > len(us) * 0.3:
            issues.append(f"WARNING: US 시가총액 0 종목 {us_mcap_zero}건 ({us_mcap_zero/len(us)*100:.1f}%)")

    # 결과 요약
    logger.info("─" * 40)
    logger.info("검증 결과 요약")
    logger.info("─" * 40)
    for key, val in stats.items():
        logger.info(f"  {key}: {val}")

    if issues:
        logger.warning(f"발견된 이슈: {len(issues)}건")
        for issue in issues:
            if issue.startswith("CRITICAL"):
                logger.error(f"  {issue}")
            elif issue.startswith("WARNING"):
                logger.warning(f"  {issue}")
            else:
                logger.info(f"  {issue}")
    else:
        logger.info("  이슈 없음 — 데이터 정상")

    logger.info("=" * 60)
    return {"stats": stats, "issues": issues}


def collect_all():
    """전체 데이터 수집 (순차 실행)."""
    logger.info("=" * 60)
    logger.info("전체 데이터 수집 시작")
    logger.info("=" * 60)
    start = time.time()

    # Phase 1: 스냅샷
    snapshot = collect_kr_snapshot()
    collect_etf()

    # Phase 2: 펀더멘탈 + 테마 + 수급
    collect_fundamentals(snapshot)
    collect_us_snapshot()
    collect_themes()
    # 외국인/기관: pykrx 우선, 실패 시 네이버 폴백
    collect_foreign_inst(snapshot)
    collect_dividend(snapshot)

    # Phase 3: 히스토리 + 기술지표
    collect_kr_history(snapshot)
    collect_us_history()

    elapsed = time.time() - start
    logger.info("=" * 60)
    logger.info(f"전체 수집 완료: {elapsed:.0f}초 ({elapsed/60:.1f}분)")
    logger.info("=" * 60)

    # Phase 4: 데이터 품질 검증
    validation = validate_data()
    return validation


def _notify_cloud_run():
    """Cloud Run에 Firestore 리로드 요청.

    수집 완료 후 호출하여 고객이 즉시 최신 데이터를 볼 수 있게 함.
    """
    import requests as _req
    cloud_run_url = os.environ.get(
        "CLOUD_RUN_URL",
        "https://stock-screener-119320994983.asia-northeast3.run.app",
    )
    admin_key = os.environ.get("ADMIN_KEY", "")

    try:
        resp = _req.post(
            f"{cloud_run_url}/api/reload",
            params={"x_admin_key": admin_key} if admin_key else {},
            timeout=30,
        )
        if resp.status_code == 200:
            logger.info(f"Cloud Run 리로드 완료: {resp.json()}")
        else:
            logger.warning(f"Cloud Run 리로드 실패: {resp.status_code}")
    except Exception as e:
        logger.warning(f"Cloud Run 리로드 요청 실패: {e}")


# ──────────────────────────────────────────────
# 스케줄 정의 (heavy + light 2계층)
# ──────────────────────────────────────────────

# heavy: 기존 4회 — 히스토리, 펀더멘탈, 테마 등 포함 (무조건 실행)
# light_kr: 장중 KR 스냅샷 — 10:00~15:00 매 30분 (KR 장중에만 실행)
# light_us: 장중 US 스냅샷 — 00:00~05:00 매 60분 (US 장중에만 실행)

HEAVY_SCHEDULES = [
    {
        "time": "06:30",
        "name": "US 장 마감 후",
        "type": "heavy",
        "tasks": ["us_snapshot", "us_history", "kr_snapshot", "etf",
                  "fundamentals", "themes", "dividend"],
    },
    {
        "time": "09:30",
        "name": "KR 개장 30분 후",
        "type": "heavy",
        "tasks": ["kr_snapshot", "etf", "foreign_inst", "kr_history"],
    },
    {
        "time": "16:00",
        "name": "KR 장 마감 후",
        "type": "heavy",
        "tasks": ["kr_snapshot", "etf", "foreign_inst", "fundamentals",
                  "kr_history", "dividend", "score_history"],
    },
    {
        "time": "22:30",
        "name": "US 장 시작 전",
        "type": "heavy",
        "tasks": ["us_snapshot", "us_history"],
    },
]

LIGHT_KR_SCHEDULES = [
    {"time": t, "name": f"KR 장중 ({t})", "type": "light_kr", "tasks": ["kr_snapshot", "etf"]}
    for t in ["10:00", "10:30", "11:00", "11:30", "12:00", "13:00", "13:30", "14:00", "14:30", "15:00"]
]

LIGHT_US_SCHEDULES = [
    {"time": t, "name": f"US 장중 ({t})", "type": "light_us", "tasks": ["us_snapshot"]}
    for t in ["00:00", "01:00", "02:00", "03:00", "04:00", "05:00"]
]

ALL_SCHEDULES = HEAVY_SCHEDULES + LIGHT_KR_SCHEDULES + LIGHT_US_SCHEDULES


def _save_schedule_status(schedule_name: str, status: str, elapsed: float = 0,
                          tasks_done: list = None, error: str = ""):
    """스케줄 실행 상태를 JSON 파일에 기록 (72시간 안정성 테스트용).

    Cloud Run Job (one-shot) 환경에서는 Firestore에 기록하고,
    로컬/스케줄 모드에서는 JSON 파일에도 기록.
    """
    import json

    # Firestore에 실행 상태 기록 (클라우드에서도 영구 보존)
    try:
        from screener.db.repository import update_sync_metadata
        update_sync_metadata(
            last_collect_schedule=schedule_name,
            last_collect_status=status,
            last_collect_time=datetime.now().isoformat(),
            last_collect_elapsed=round(elapsed, 1),
            last_collect_error=error[:200] if error else "",
        )
    except Exception as e:
        logger.debug(f"Firestore 상태 기록 실패: {e}")

    status_file = os.path.join(os.path.dirname(__file__) or ".", "schedule_status.json")

    try:
        if os.path.exists(status_file):
            with open(status_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = {"runs": [], "summary": {"total": 0, "success": 0, "fail": 0}}
    except (json.JSONDecodeError, KeyError):
        data = {"runs": [], "summary": {"total": 0, "success": 0, "fail": 0}}

    run_entry = {
        "time": datetime.now().isoformat(),
        "schedule": schedule_name,
        "status": status,
        "elapsed_sec": round(elapsed, 1),
        "tasks": tasks_done or [],
        "error": error,
    }
    data["runs"].append(run_entry)
    # 최근 200건만 유지
    if len(data["runs"]) > 200:
        data["runs"] = data["runs"][-200:]

    data["summary"]["total"] += 1
    if status == "success":
        data["summary"]["success"] += 1
    else:
        data["summary"]["fail"] += 1
    data["summary"]["last_run"] = run_entry["time"]
    data["summary"]["uptime_hours"] = round(
        (datetime.now() - datetime.fromisoformat(data["runs"][0]["time"])).total_seconds() / 3600, 1
    ) if data["runs"] else 0
    data["summary"]["success_rate"] = round(
        data["summary"]["success"] / data["summary"]["total"] * 100, 1
    ) if data["summary"]["total"] > 0 else 0

    with open(status_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _run_scheduled_tasks(schedule: dict):
    """스케줄 정의에 따라 수집 태스크 실행."""
    name = schedule["name"]
    tasks = schedule["tasks"]
    sched_type = schedule.get("type", "heavy")
    is_light = sched_type.startswith("light")
    logger.info(f"[{name}] {'경량 ' if is_light else ''}수집 시작 — {', '.join(tasks)}")

    start = time.time()
    snapshot = None
    tasks_done = []

    try:
        for task in tasks:
            task_start = time.time()
            if task == "kr_snapshot":
                snapshot = collect_kr_snapshot()
            elif task == "etf":
                collect_etf()
            elif task == "us_snapshot":
                collect_us_snapshot()
            elif task == "fundamentals":
                collect_fundamentals(snapshot)
            elif task == "themes":
                collect_themes()
            elif task == "foreign_inst":
                collect_foreign_inst(snapshot)
            elif task == "dividend":
                collect_dividend(snapshot)
            elif task == "kr_history":
                collect_kr_history(snapshot)
            elif task == "us_history":
                collect_us_history()
            elif task == "score_history":
                collect_score_history()
            tasks_done.append({"task": task, "elapsed": round(time.time() - task_start, 1)})

        elapsed = time.time() - start
        logger.info(f"[{name}] 수집 완료: {elapsed:.0f}초")

        # 상태 기록
        _save_schedule_status(name, "success", elapsed, tasks_done)

        # Cloud Run에 리로드 알림
        _notify_cloud_run()

        # heavy 수집만: 시그널 알림 + 텔레그램 완료 알림
        if not is_light:
            if "kr_history" in tasks or "us_history" in tasks:
                _send_signal_alerts()
            _send_alert(f"[{name}] 수집 완료 ({elapsed:.0f}초)")

    except Exception as e:
        elapsed = time.time() - start
        logger.error(f"[{name}] 수집 실패: {e}")
        _save_schedule_status(name, "fail", elapsed, tasks_done, str(e))
        if not is_light:
            _send_alert(f"[{name}] 수집 실패: {e}")


def _write_heartbeat():
    """Firestore에 collector heartbeat 기록 (failover 감지용)."""
    try:
        from screener.db.repository import update_sync_metadata
        update_sync_metadata(collector_heartbeat=datetime.now().isoformat())
    except Exception as e:
        logger.debug(f"heartbeat 기록 실패: {e}")


def _should_run_schedule(schedule: dict, now: datetime) -> bool:
    """스케줄 실행 여부 판단. light 스케줄은 장중에만 실행."""
    sched_type = schedule.get("type", "heavy")

    if sched_type == "heavy":
        return True  # heavy는 무조건 실행

    if sched_type == "light_kr":
        # 평일 KR 장중 (09:00~15:30)에만 실행
        if now.weekday() >= 5:
            return False
        return (9 <= now.hour < 15) or (now.hour == 15 and now.minute <= 30)

    if sched_type == "light_us":
        # US 장중 (KST 23:30~06:00)에만 실행
        if now.weekday() == 6:
            return False
        if now.weekday() == 5 and now.hour >= 6:
            return False
        return now.hour >= 23 or now.hour < 6

    return True


def schedule_loop():
    """고정 스케줄 기반 수집 루프.

    heavy 스케줄: 06:30 / 09:30 / 16:00 / 22:30 (무조건 실행)
    light_kr: 10:00~15:00 매 30분 (KR 장중에만, 스냅샷만)
    light_us: 00:00~05:00 매 60분 (US 장중에만, 스냅샷만)
    상태 파일: schedule_status.json (안정성 검증용)
    """
    logger.info("=" * 60)
    logger.info("스케줄 수집 모드 시작")
    heavy_count = len(HEAVY_SCHEDULES)
    light_kr_count = len(LIGHT_KR_SCHEDULES)
    light_us_count = len(LIGHT_US_SCHEDULES)
    logger.info(f"  heavy: {heavy_count}개, light_kr: {light_kr_count}개, light_us: {light_us_count}개")
    for s in HEAVY_SCHEDULES:
        logger.info(f"  [heavy] {s['time']} — {s['name']}: {', '.join(s['tasks'])}")
    logger.info(f"  [light_kr] 10:00~15:00 매 30분 — kr_snapshot, etf")
    logger.info(f"  [light_us] 00:00~05:00 매 60분 — us_snapshot")
    logger.info("=" * 60)

    # 시작 기록
    _save_schedule_status("시스템", "started", 0, [], "")

    executed_today = set()
    heartbeat_count = 0

    while True:
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")

        for schedule in ALL_SCHEDULES:
            sched_time = schedule["time"]
            sched_key = f"{today}_{sched_time}"

            # 이미 실행된 스케줄은 스킵
            if sched_key in executed_today:
                continue

            # light 스케줄은 장중 여부 체크
            if not _should_run_schedule(schedule, now):
                continue

            # 스케줄 시간 ± 5분 이내면 실행
            sched_h, sched_m = map(int, sched_time.split(":"))
            diff_min = (now.hour * 60 + now.minute) - (sched_h * 60 + sched_m)

            if 0 <= diff_min <= 5:
                logger.info(f"스케줄 트리거: {sched_time} ({schedule['name']})")
                _run_scheduled_tasks(schedule)
                executed_today.add(sched_key)

        # 자정 넘으면 실행 기록 초기화
        if now.hour == 0 and now.minute < 2:
            executed_today.clear()

        # 5분마다 Firestore heartbeat (failover 감지용)
        # 30분마다 콘솔 heartbeat 로그
        heartbeat_count += 1
        if heartbeat_count % 10 == 0:  # 30초 * 10 = 5분
            _write_heartbeat()
        if heartbeat_count >= 60:  # 30초 * 60 = 30분
            next_schedules = []
            for s in ALL_SCHEDULES:
                if not _should_run_schedule(s, now):
                    continue
                sh, sm = map(int, s["time"].split(":"))
                s_min = sh * 60 + sm
                now_min = now.hour * 60 + now.minute
                if s_min > now_min:
                    next_schedules.append(f"{s['time']}({s['name']})")
            next_info = next_schedules[0] if next_schedules else "다음 스케줄 대기"
            executed_count = len(executed_today)
            total_possible = len([s for s in ALL_SCHEDULES if _should_run_schedule(s, now)])
            logger.info(f"[heartbeat] 대기 중 | 다음: {next_info} | 오늘 실행: {executed_count}/{total_possible}")
            heartbeat_count = 0

        # 30초마다 체크
        time.sleep(30)


def _check_local_collector_active() -> bool:
    """로컬 collector가 활성 상태인지 확인 (heartbeat 기반).

    Returns:
        True: 로컬 활성 (10분 이내 heartbeat 있음)
        False: 로컬 비활성 (10분 초과 또는 heartbeat 없음)
    """
    try:
        from screener.db.repository import get_sync_metadata
        meta = get_sync_metadata()
        hb = meta.get("collector_heartbeat")
        if not hb:
            return False
        last = datetime.fromisoformat(hb)
        age_min = (datetime.now() - last).total_seconds() / 60
        return age_min <= 10
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(description="Stock Screener Pro — 독립 데이터 수집기")
    parser.add_argument("--all", action="store_true", help="전체 수집")
    parser.add_argument("--schedule", action="store_true", help="스케줄 모드 (무한 루프)")
    parser.add_argument("--kr-snapshot", action="store_true", help="KR 스냅샷")
    parser.add_argument("--etf", action="store_true", help="ETF")
    parser.add_argument("--us-snapshot", action="store_true", help="US 스냅샷")
    parser.add_argument("--fundamentals", action="store_true", help="KR 펀더멘탈")
    parser.add_argument("--themes", action="store_true", help="테마")
    parser.add_argument("--foreign-inst", action="store_true", help="외국인/기관")
    parser.add_argument("--dividend", action="store_true", help="배당 지속성")
    parser.add_argument("--history", action="store_true", help="KR 히스토리 + 기술지표")
    parser.add_argument("--us-history", action="store_true", help="US 히스토리 + 기술지표")
    parser.add_argument("--validate", action="store_true", help="수집 데이터 품질 검증")
    parser.add_argument("--cloud-fallback", action="store_true",
                        help="클라우드 백업 모드 (로컬 collector 비활성 시에만 실행)")

    args = parser.parse_args()

    # 클라우드 백업 모드: 로컬 활성이면 스킵
    if args.cloud_fallback:
        if _check_local_collector_active():
            logger.info("로컬 collector 활성 — 클라우드 백업 스킵")
            return
        logger.warning("로컬 collector 비활성 감지 — 클라우드 백업 수집 실행")
        _send_alert("⚠️ 로컬 collector 비활성 — 클라우드 백업으로 수집 시작")

    if args.schedule:
        schedule_loop()
    elif args.validate:
        validate_data()
    elif args.all:
        collect_all()
        _notify_cloud_run()
    else:
        ran = False
        if args.kr_snapshot:
            collect_kr_snapshot(); ran = True
        if args.etf:
            collect_etf(); ran = True
        if args.us_snapshot:
            collect_us_snapshot(); ran = True
        if args.fundamentals:
            collect_fundamentals(); ran = True
        if args.themes:
            collect_themes(); ran = True
        if args.foreign_inst:
            collect_foreign_inst(); ran = True
        if args.dividend:
            collect_dividend(); ran = True
        if args.history:
            collect_kr_history(); ran = True
        if args.us_history:
            collect_us_history(); ran = True
        if ran:
            _notify_cloud_run()
        else:
            parser.print_help()


if __name__ == "__main__":
    main()
