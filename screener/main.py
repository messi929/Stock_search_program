"""종목탐색기 FastAPI 메인 애플리케이션.

데이터 로딩 전략:
  1) Firestore에서 캐시 데이터 즉시 로드 (3~5초)
  2) 화면 표시 가능 상태로 전환
  3) 백그라운드에서 stale 데이터만 갱신 → Firestore 저장
"""

import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

import pandas as pd
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from loguru import logger

from screener.api.routes import router, set_data
from screener.core.data_fetcher import (
    fetch_daily_snapshot, fetch_us_snapshot, fetch_etf_data,
    fetch_naver_fundamentals, apply_fundamentals,
    fetch_themes, fetch_foreign_inst, apply_foreign_inst,
    fetch_dividend_history, apply_dividend_history,
    fetch_historical_ohlcv, fetch_us_historical_ohlcv,
    save_cache, load_cache, save_dict_cache, load_dict_cache,
)
from screener.core.metrics import (
    calculate_moving_averages, calculate_rsi,
    calculate_52week, detect_surging_stocks,
    calculate_buy_score,
)
from screener.db.repository import (
    save_stocks, load_stocks,
    save_themes, load_themes,
    save_history, load_history,
    get_sync_metadata, update_sync_metadata, is_stale,
)


# ──────────────────────────────────────────────
# Phase 0: Firestore에서 즉시 로드
# ──────────────────────────────────────────────

async def load_from_firestore() -> bool:
    """Firestore 캐시에서 데이터 로드. 데이터 있으면 True."""
    loop = asyncio.get_event_loop()

    logger.info("=" * 60)
    logger.info("Firestore 캐시 로드 시도...")
    logger.info("=" * 60)

    try:
        # 종목 데이터 로드
        kr_df = await loop.run_in_executor(None, load_stocks, "kr")
        us_df = await loop.run_in_executor(None, load_stocks, "us")
        etf_df = await loop.run_in_executor(None, load_stocks, "etf")

        if kr_df.empty:
            logger.info("Firestore에 데이터 없음 — 크롤링 모드로 전환")
            return False

        # 종목 합치기
        snapshot = kr_df.copy()
        if not us_df.empty:
            snapshot = pd.concat([snapshot, us_df], ignore_index=True)

        # 종목명 딕셔너리
        names = dict(zip(snapshot["ticker"], snapshot["name"]))
        if not etf_df.empty:
            names.update(dict(zip(etf_df["ticker"], etf_df["name"])))

        # 급등주 탐지 (메모리 내 계산)
        snapshot = detect_surging_stocks(snapshot)
        snapshot = calculate_buy_score(snapshot)
    

        # 테마 로드
        themes, stock_themes, theme_groups = await loop.run_in_executor(None, load_themes)

        # 테마 매핑 적용
        if stock_themes:
            snapshot["themes"] = snapshot["ticker"].map(
                lambda t: ", ".join(stock_themes.get(t, []))
            )

        # Phase 1 즉시 활성화
        set_data(snapshot, etf_df=etf_df, names=names,
                 themes=themes or {}, stock_themes=stock_themes or {},
                 theme_groups=theme_groups or {},
                 phase=2)

        logger.info(f"Firestore 로드 완료: KR {len(kr_df)} + US {len(us_df)} + ETF {len(etf_df)}")

        # 히스토리 로드 → 기술지표 재계산
        history = await loop.run_in_executor(None, load_history)
        if not history.empty:
            snapshot = _apply_technicals(snapshot, history)
            snapshot = detect_surging_stocks(snapshot)
            snapshot = calculate_buy_score(snapshot)
        
            set_data(snapshot, etf_df=etf_df, names=names,
                     themes=themes or {}, stock_themes=stock_themes or {},
                     theme_groups=theme_groups or {},
                     phase=3)
            logger.info("Firestore 기술지표 적용 완료 — Phase 3")

        return True

    except Exception as e:
        logger.warning(f"Firestore 로드 실패: {e}")
        return False


def _apply_technicals(snapshot: pd.DataFrame, history: pd.DataFrame) -> pd.DataFrame:
    """히스토리 데이터로 기술지표 계산 후 스냅샷에 적용."""
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
        h_df = vs_high.reset_index()
        h_df.columns = ["ticker", "vs_high_52w"]
        l_df = vs_low.reset_index()
        l_df.columns = ["ticker", "vs_low_52w"]
        snapshot = snapshot.merge(h_df, on="ticker", how="left", suffixes=("_old", ""))
        if "vs_high_52w_old" in snapshot.columns:
            snapshot["vs_high_52w"] = snapshot["vs_high_52w"].fillna(snapshot["vs_high_52w_old"])
            snapshot.drop(columns=["vs_high_52w_old"], inplace=True)
        snapshot = snapshot.merge(l_df, on="ticker", how="left", suffixes=("_old", ""))
        if "vs_low_52w_old" in snapshot.columns:
            snapshot["vs_low_52w"] = snapshot["vs_low_52w"].fillna(snapshot["vs_low_52w_old"])
            snapshot.drop(columns=["vs_low_52w_old"], inplace=True)

    return snapshot


# ──────────────────────────────────────────────
# 시장 시간 판별
# ──────────────────────────────────────────────

def _is_kr_market_hours() -> bool:
    """KR 장중 여부 (평일 09:00~15:30)."""
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    return (9 <= now.hour < 15) or (now.hour == 15 and now.minute <= 30)


def _is_us_market_hours() -> bool:
    """US 장중 여부 (KST 기준 평일 23:30~06:00).
    월~금: 전날 23:30 ~ 당일 06:00 (서머타임 시 22:30~05:00).
    """
    now = datetime.now()
    # 토요일 새벽(금요 미장), 일요일은 미장 없음
    if now.weekday() == 6:  # 일요일
        return False
    if now.weekday() == 5 and now.hour >= 6:  # 토요일 오전 6시 이후
        return False
    return now.hour >= 23 or now.hour < 6


def _get_refresh_intervals() -> dict:
    """현재 시간대에 따른 갱신 주기(시간) 반환.

    장중/장외에 따라 갱신 주기를 차등 적용:
      - KR 장중: 기술지표 매 갱신, 외국인/기관 1시간
      - US 장중: US 시세 1시간
      - 장외: 기존 주기 유지
    """
    kr_open = _is_kr_market_hours()
    us_open = _is_us_market_hours()

    return {
        # 스냅샷: 항상 매번
        "stocks_kr": 0,
        "stocks_etf": 0,
        # US: 장중 1시간, 장외 6시간
        "stocks_us": 1 if us_open else 6,
        # 펀더멘탈: 항상 24시간 (장중 급변 안함)
        "fundamentals": 24,
        # 테마: 항상 7일
        "themes": 168,
        # 외국인/기관: 장중 1시간, 장외 12시간
        "foreign_inst": 1 if kr_open else 12,
        # 배당: 항상 7일
        "dividend": 168,
        # 히스토리+기술지표: 장중 매 갱신(0), 장외 24시간
        "history": 0 if kr_open else 24,
    }


# ──────────────────────────────────────────────
# 백그라운드 갱신: 장중/장외 차등 갱신
# ──────────────────────────────────────────────

_refresh_lock = asyncio.Lock() if hasattr(asyncio, 'Lock') else None

async def refresh_stale_data(force: bool = False):
    """장중/장외 차등 갱신 — stale 데이터만 선별적으로 갱신 후 Firestore 저장."""
    global _refresh_lock
    if _refresh_lock is None:
        _refresh_lock = asyncio.Lock()
    if _refresh_lock.locked():
        logger.info("갱신 이미 진행 중 — 스킵")
        return
    async with _refresh_lock:
        await _refresh_stale_data_impl(force)

async def _refresh_stale_data_impl(force: bool = False):
    loop = asyncio.get_event_loop()
    intervals = _get_refresh_intervals()
    # force=True이면 is_stale 항상 True
    _is_stale = (lambda *a, **kw: True) if force else is_stale

    kr_open = _is_kr_market_hours()
    us_open = _is_us_market_hours()
    mode = "KR장중" if kr_open else ("US장중" if us_open else "장외")

    logger.info("=" * 60)
    logger.info(f"백그라운드 갱신 시작 [{mode}]")
    logger.info(f"  갱신 주기: US={intervals['stocks_us']}h, "
                f"수급={intervals['foreign_inst']}h, "
                f"기술지표={'매번' if intervals['history'] == 0 else '24h'}")
    logger.info("=" * 60)

    # ── Phase 1: KR 스냅샷 (매번 갱신, 빠름) ──
    snapshot = await loop.run_in_executor(None, fetch_daily_snapshot)
    try:
        await loop.run_in_executor(None, save_stocks, snapshot, "kr")
        update_sync_metadata(stocks_kr_updated_at=datetime.now().isoformat())
    except Exception as e:
        logger.warning(f"Firestore 저장 실패 (KR) — 인메모리 모드 계속: {e}")
    logger.info(f"KR 스냅샷 갱신: {len(snapshot)}종목")

    # ETF
    etf_df = await loop.run_in_executor(None, fetch_etf_data)
    if not etf_df.empty:
        try:
            await loop.run_in_executor(None, save_stocks, etf_df, "etf")
        except Exception as e:
            logger.warning(f"Firestore 저장 실패 (ETF): {e}")
    try:
        update_sync_metadata(stocks_etf_updated_at=datetime.now().isoformat())
    except Exception:
        pass

    names = dict(zip(snapshot["ticker"], snapshot["name"]))
    if not etf_df.empty:
        names.update(dict(zip(etf_df["ticker"], etf_df["name"])))

    snapshot = detect_surging_stocks(snapshot)
    snapshot = calculate_buy_score(snapshot)

    set_data(snapshot, etf_df=etf_df, names=names, phase=1)
    logger.info("Phase 1 갱신 완료")

    # ── KR 펀더멘탈 (US 전에 먼저 — 핵심 데이터) ──
    if _is_stale("fundamentals_updated_at", max_age_hours=intervals["fundamentals"]):
        logger.info("KR 펀더멘탈 갱신 중...")
        kr_stocks = snapshot[snapshot["market"].isin(["KOSPI", "KOSDAQ"])]
        top_tickers = kr_stocks.nlargest(500, "market_cap")["ticker"].tolist()
        fund_data = await loop.run_in_executor(None, fetch_naver_fundamentals, top_tickers)
        if fund_data:
            snapshot = apply_fundamentals(snapshot, fund_data)
            try:
                fund_df = snapshot[snapshot["ticker"].isin(fund_data.keys())][
                    ["ticker", "per", "pbr", "div_yield", "roe"]
                ]
                await loop.run_in_executor(None, save_stocks, fund_df, "kr")
                update_sync_metadata(fundamentals_updated_at=datetime.now().isoformat())
            except Exception as e:
                logger.warning(f"Firestore 저장 실패 (펀더멘탈): {e}")
            logger.info(f"KR 펀더멘탈 갱신: {len(fund_data)}종목")
            set_data(snapshot, etf_df=etf_df, names=names, phase=2)

    # ── US 주식 (장중 1시간 / 장외 6시간) ──
    us_df = pd.DataFrame()
    if _is_stale("stocks_us_updated_at", max_age_hours=intervals["stocks_us"]):
        logger.info(f"US 주식 갱신 중... (주기: {intervals['stocks_us']}h)")
        us_df = await loop.run_in_executor(None, fetch_us_snapshot)
        if not us_df.empty:
            try:
                await loop.run_in_executor(None, save_stocks, us_df, "us")
                update_sync_metadata(stocks_us_updated_at=datetime.now().isoformat())
            except Exception as e:
                logger.warning(f"Firestore 저장 실패 (US): {e}")
            snapshot = pd.concat([snapshot, us_df], ignore_index=True)
            names.update(dict(zip(us_df["ticker"], us_df["name"])))
            logger.info(f"US 주식 갱신: {len(us_df)}종목")
    else:
        try:
            us_df = await loop.run_in_executor(None, load_stocks, "us")
        except Exception as e:
            logger.warning(f"Firestore 로드 실패 (US): {e}")
            us_df = pd.DataFrame()
        if not us_df.empty:
            snapshot = pd.concat([snapshot, us_df], ignore_index=True)
            names.update(dict(zip(us_df["ticker"], us_df["name"])))
            logger.info(f"US 주식 DB 캐시: {len(us_df)}종목")

    snapshot = detect_surging_stocks(snapshot)
    snapshot = calculate_buy_score(snapshot)

    set_data(snapshot, etf_df=etf_df, names=names, phase=1)

    # ── 테마 (7일) ──
    if _is_stale("themes_updated_at", max_age_hours=intervals["themes"]):
        logger.info("테마 갱신 중...")
        themes, stock_themes_raw = await loop.run_in_executor(None, fetch_themes)
        if themes:
            try:
                await loop.run_in_executor(None, save_themes, themes, stock_themes_raw)
                update_sync_metadata(themes_updated_at=datetime.now().isoformat())
            except Exception as e:
                logger.warning(f"Firestore 저장 실패 (테마): {e}")
            logger.info(f"테마 갱신: {len(themes)}테마")

    # 테마 로드 (갱신 여부 무관)
    themes, stock_themes, theme_groups = {}, {}, {}
    try:
        themes, stock_themes, theme_groups = await loop.run_in_executor(None, load_themes)
    except Exception as e:
        logger.warning(f"Firestore 테마 로드 실패: {e}")
    if stock_themes:
        snapshot["themes"] = snapshot["ticker"].map(
            lambda t: ", ".join(stock_themes.get(t, []))
        )

    # ── 외국인/기관 (장중 1시간 / 장외 12시간) ──
    try:
        if _is_stale("foreign_inst_updated_at", max_age_hours=intervals["foreign_inst"]):
            logger.info(f"외국인/기관 갱신 중... (주기: {intervals['foreign_inst']}h)")
            kr_tickers = snapshot.loc[
                snapshot["market"].isin(["KOSPI", "KOSDAQ"]), "ticker"
            ].tolist() if snapshot is not None else None
            fi_data = await loop.run_in_executor(
                None, lambda: fetch_foreign_inst(tickers=kr_tickers)
            )
            if fi_data:
                snapshot = apply_foreign_inst(snapshot, fi_data)
                try:
                    update_sync_metadata(foreign_inst_updated_at=datetime.now().isoformat())
                except Exception:
                    pass
                logger.info("외국인/기관 갱신 완료")
    except Exception as e:
        logger.warning(f"외국인/기관 갱신 실패: {e}")

    # ── 배당 지속성 (7일) ──
    try:
        if _is_stale("dividend_updated_at", max_age_hours=intervals["dividend"]):
            div_tickers = snapshot[snapshot["div_yield"] > 0]["ticker"].tolist()
            if div_tickers:
                div_data = await loop.run_in_executor(None, fetch_dividend_history, div_tickers)
                if div_data:
                    snapshot = apply_dividend_history(snapshot, div_data)
                    try:
                        update_sync_metadata(dividend_updated_at=datetime.now().isoformat())
                    except Exception:
                        pass
    except Exception as e:
        logger.warning(f"배당 갱신 실패: {e}")

    snapshot = detect_surging_stocks(snapshot)
    snapshot = calculate_buy_score(snapshot)

    set_data(snapshot, etf_df=etf_df, names=names,
             themes=themes or {}, stock_themes=stock_themes or {},
             theme_groups=theme_groups or {},
             phase=2)
    logger.info("Phase 2 갱신 완료")

    # ── Phase 3: 히스토리 + 기술지표 (장중 매번 / 장외 24시간) ──
    history = None
    if intervals["history"] == 0 or _is_stale("history_updated_at", max_age_hours=intervals["history"]):
        if intervals["history"] == 0:
            logger.info("기술지표 갱신 중... (장중 모드: 매 갱신)")
        else:
            logger.info("히스토리 갱신 중...")
        kr = snapshot[snapshot["market"].isin(["KOSPI", "KOSDAQ"])]
        top_cap = kr.nlargest(300, "market_cap")["ticker"].tolist()
        top_vol = kr.nlargest(200, "volume")["ticker"].tolist()
        target = list(set(top_cap + top_vol))
        history = await loop.run_in_executor(None, fetch_historical_ohlcv, target)
        if not history.empty:
            try:
                await loop.run_in_executor(None, save_history, history)
                update_sync_metadata(history_updated_at=datetime.now().isoformat())
            except Exception as e:
                logger.warning(f"Firestore 저장 실패 (히스토리): {e}")
    else:
        try:
            history = await loop.run_in_executor(None, load_history)
        except Exception as e:
            logger.warning(f"Firestore 히스토리 로드 실패: {e}")

    if history is not None and not history.empty:
        snapshot = _apply_technicals(snapshot, history)

    # ── US 히스토리 + 기술지표 ──
    us_in_snap = snapshot[snapshot["market"].isin(["NASDAQ", "S&P500"])]
    if not us_in_snap.empty and _is_stale("us_history_updated_at", max_age_hours=24):
        logger.info("US 히스토리 갱신 중...")
        us_top_cap = us_in_snap.nlargest(150, "market_cap")["ticker"].tolist()
        us_top_vol = us_in_snap.nlargest(100, "volume")["ticker"].tolist()
        us_targets = list(set(us_top_cap + us_top_vol))
        us_history = await loop.run_in_executor(None, fetch_us_historical_ohlcv, us_targets)
        if not us_history.empty:
            try:
                await loop.run_in_executor(None, save_history, us_history)
                update_sync_metadata(us_history_updated_at=datetime.now().isoformat())
            except Exception as e:
                logger.warning(f"Firestore 저장 실패 (US 히스토리): {e}")
            snapshot = _apply_technicals(snapshot, us_history)
            logger.info(f"US 히스토리 갱신: {len(us_targets)}종목")

    snapshot = detect_surging_stocks(snapshot)
    snapshot = calculate_buy_score(snapshot)


    # 최종 스냅샷을 Firestore에 저장 (기술지표 포함)
    try:
        await loop.run_in_executor(None, save_stocks, snapshot[snapshot["market"].isin(["KOSPI", "KOSDAQ"])], "kr")
        if not us_df.empty:
            await loop.run_in_executor(None, save_stocks, snapshot[snapshot["market"].isin(["NASDAQ", "S&P500"])], "us")
    except Exception as e:
        logger.warning(f"Firestore 최종 저장 실패: {e}")

    set_data(snapshot, etf_df=etf_df, names=names,
             themes=themes or {}, stock_themes=stock_themes or {},
             theme_groups=theme_groups or {},
             phase=3)

    logger.info("=" * 60)
    logger.info(f"전체 갱신 완료 [{mode}]: {len(snapshot)}종목 + ETF {len(etf_df)}")
    logger.info("=" * 60)


async def auto_refresh():
    """장중/미장 자동 갱신.

    갱신 주기:
      - KR 장중 (09:00~15:30): 30분마다
      - US 장중 (23:30~06:00): 60분마다
      - 장외: 갱신 안함 (다음 장 시작까지 대기)
    """
    from screener.config import REFRESH_INTERVAL_MIN
    while True:
        kr_open = _is_kr_market_hours()
        us_open = _is_us_market_hours()

        if kr_open:
            interval = REFRESH_INTERVAL_MIN * 60  # 30분
        elif us_open:
            interval = 60 * 60  # 60분
        else:
            # 장외: 5분마다 체크만 하고 장 열릴 때까지 대기
            await asyncio.sleep(5 * 60)
            continue

        await asyncio.sleep(interval)

        now = datetime.now()
        mode = "KR장중" if kr_open else "US장중"
        logger.info(f"자동 갱신 시작 [{mode}] ({now.strftime('%H:%M')})")
        try:
            await refresh_stale_data()
        except Exception as e:
            logger.error(f"자동 갱신 실패: {e}")
        logger.info(f"자동 갱신 완료 [{mode}]")


async def readonly_reload():
    """읽기전용 모드: Firestore에서 주기적으로 데이터 리로드.

    collector.py가 별도로 크롤링 → Firestore 저장하므로,
    Cloud Run은 Firestore에서 읽기만 하면 됨.
    장중 5분, 장외 30분마다 리로드.
    """
    while True:
        kr_open = _is_kr_market_hours()
        us_open = _is_us_market_hours()

        if kr_open or us_open:
            interval = 5 * 60  # 장중: 5분마다 리로드
            mode = "KR장중" if kr_open else "US장중"
        else:
            interval = 30 * 60  # 장외: 30분마다
            mode = "장외"

        await asyncio.sleep(interval)

        logger.info(f"Firestore 리로드 [{mode}]")
        try:
            await load_from_firestore()
        except Exception as e:
            logger.error(f"Firestore 리로드 실패: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    from screener.config import COLLECT_MODE

    # Firestore 캐시를 먼저 로드 (서버 시작 전에 완료)
    has_cache = await load_from_firestore()

    tasks = []

    if COLLECT_MODE == "readonly":
        # 읽기전용 모드: 크롤링 없이 Firestore 주기적 리로드만
        logger.info("=" * 60)
        logger.info("서빙 전용 모드 (COLLECT_MODE=readonly)")
        logger.info("크롤링 없음 — Firestore 주기적 리로드")
        logger.info("=" * 60)
        tasks.append(asyncio.create_task(readonly_reload()))
    else:
        # 전체 모드: 크롤링 + Firestore 저장
        async def _background_refresh():
            if has_cache:
                logger.info("Firestore 캐시 있음 → 백그라운드 갱신 시작")
            else:
                logger.info("캐시 없음 → 전체 크롤링 + Firestore 저장")
            await refresh_stale_data()

        tasks.append(asyncio.create_task(_background_refresh()))
        tasks.append(asyncio.create_task(auto_refresh()))

    yield

    for t in tasks:
        t.cancel()


app = FastAPI(title="Stock Screener Pro", version="5.0.0", lifespan=lifespan)

# CORS — 데스크톱 클라이언트가 원격 서버에 접속 허용
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 인증 + 티어 미들웨어 (AUTH_ENABLED=true 시 활성화)
from screener.middleware import AuthMiddleware
app.add_middleware(AuthMiddleware)

from screener.api.lemon_routes import router as payment_router
from screener.api.user_routes import router as user_router
from screener.api.admin_routes import router as admin_router
from screener.api.rank_page import router as rank_router
app.include_router(router)
app.include_router(payment_router)
app.include_router(user_router)
app.include_router(admin_router)
app.include_router(rank_router)

static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def index():
    return FileResponse(
        str(static_dir / "index.html"),
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


def _legal_page(filename: str):
    return FileResponse(
        str(static_dir / filename),
        headers={"Cache-Control": "public, max-age=3600"},
    )


@app.get("/pricing")
async def pricing():
    return _legal_page("pricing.html")


@app.get("/terms")
async def terms():
    return _legal_page("terms.html")


@app.get("/privacy")
async def privacy():
    return _legal_page("privacy.html")


@app.get("/refund")
async def refund():
    return _legal_page("refund.html")


@app.get("/admin")
async def admin_page():
    return FileResponse(
        str(static_dir / "admin.html"),
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


@app.post("/api/refresh")
async def refresh_data(x_admin_key: str | None = None):
    """수동 갱신 — 관리자 키 필요 (상용 배포 시)."""
    from screener.config import ADMIN_KEY
    if ADMIN_KEY and x_admin_key != ADMIN_KEY:
        from fastapi import HTTPException
        raise HTTPException(403, "관리자 인증 필요")
    asyncio.create_task(refresh_stale_data(force=True))
    return {"message": "데이터 강제 갱신 시작됨"}


@app.post("/api/reload")
async def reload_data(x_admin_key: str | None = None):
    """Firestore에서 즉시 리로드 — collector 수집 완료 후 호출.

    readonly 모드에서 사용. 크롤링 없이 Firestore 데이터만 재로드.
    """
    from screener.config import ADMIN_KEY
    if ADMIN_KEY and x_admin_key != ADMIN_KEY:
        from fastapi import HTTPException
        raise HTTPException(403, "관리자 인증 필요")
    success = await load_from_firestore()
    return {"message": "리로드 완료" if success else "리로드 실패", "success": success}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8501))
    uvicorn.run("screener.main:app", host="0.0.0.0", port=port, reload=True)
