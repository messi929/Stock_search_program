"""FastAPI 라우터."""

import io
from copy import deepcopy
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from loguru import logger
import pandas as pd

from screener.api.schemas import ScanResponse, StockItem, CategoryInfo, StatusResponse
from screener.core.screener import ScreenerFilter, apply_filters, CATEGORIES, GROUPS, CATEGORY_PHASE

router = APIRouter(prefix="/api")

_data_store = {
    "df": None,
    "etf_df": None,
    "last_update": "",
    "names": {},
    "themes": {},
    "stock_themes": {},
    "theme_groups": {},
    "loading_phase": 0,
}

_ws_clients: list[WebSocket] = []


async def _broadcast_ws(msg: dict):
    """WebSocket 클라이언트에 메시지 브로드캐스트."""
    import json
    dead = []
    for ws in _ws_clients:
        try:
            await ws.send_text(json.dumps(msg))
        except Exception:
            dead.append(ws)
    for ws in dead:
        _ws_clients.remove(ws)


def set_data(df, etf_df=None, names=None, themes=None, stock_themes=None, theme_groups=None, phase=None):
    """데이터 주입."""
    _data_store["df"] = df
    if etf_df is not None:
        _data_store["etf_df"] = etf_df
    if names is not None:
        _data_store["names"] = names
    if themes is not None:
        _data_store["themes"] = themes
    if stock_themes is not None:
        _data_store["stock_themes"] = stock_themes
    if theme_groups is not None:
        _data_store["theme_groups"] = theme_groups
    if phase is not None:
        # Phase는 낮아지지 않도록 (Firestore 캐시 → 백그라운드 갱신 시 리셋 방지)
        _data_store["loading_phase"] = max(_data_store["loading_phase"], phase)
    _kst = timezone(timedelta(hours=9))
    _data_store["last_update"] = datetime.now(_kst).strftime("%Y-%m-%d %H:%M:%S")
    # WebSocket 알림 (비동기 스케줄)
    if _ws_clients:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(_broadcast_ws({
                    "type": "data_updated",
                    "phase": _data_store["loading_phase"],
                    "last_update": _data_store["last_update"],
                }))
        except RuntimeError:
            pass


def _get_combined_df():
    """주식 + ETF 합친 DataFrame."""
    dfs = []
    if _data_store["df"] is not None:
        dfs.append(_data_store["df"])
    if _data_store["etf_df"] is not None:
        dfs.append(_data_store["etf_df"])
    if not dfs:
        return None
    import pandas as pd
    return pd.concat(dfs, ignore_index=True)


def _safe(val, default=0):
    """NaN-safe 값 변환."""
    import math
    if val is None:
        return default
    try:
        if isinstance(val, float) and math.isnan(val):
            return default
    except (TypeError, ValueError):
        pass
    return val


def _row_to_item(row) -> StockItem:
    """DataFrame row → StockItem."""
    g = lambda k, d=0: _safe(row.get(k, d), d)
    return StockItem(
        ticker=str(g("ticker", "")),
        name=str(g("name", "")),
        market=str(g("market", "")),
        stock_type=str(g("stock_type", "stock")),
        close=int(g("close")),
        change_pct=round(float(g("change_pct")), 2),
        volume=int(g("volume")),
        volume_ratio=round(float(g("volume_ratio")), 2),
        trading_value=round(float(g("trading_value")), 0),
        market_cap=round(float(g("market_cap")), 0),
        per=round(float(g("per")), 2),
        pbr=round(float(g("pbr")), 2),
        roe=round(float(g("roe")), 2),
        div_yield=round(float(g("div_yield")), 2),
        div_years=int(g("div_years")),
        div_growth=round(float(g("div_growth")), 1),
        ma5=round(float(g("ma5")), 0),
        ma20=round(float(g("ma20")), 0),
        ma60=round(float(g("ma60")), 0),
        golden_cross=int(g("golden_cross")),
        ma_aligned=int(g("ma_aligned")),
        surge_score=int(g("surge_score")),
        is_surging=bool(g("is_surging", False)),
        pre_surge_score=int(g("pre_surge_score")),
        is_pre_surge=bool(g("is_pre_surge", False)),
        accumulation=int(g("accumulation")),
        breakout_score=int(g("breakout_score")),
        volume_trend=int(g("volume_trend")),
        ma_squeeze=round(float(g("ma_squeeze", 99.0)), 2),
        consecutive_gains=int(g("consecutive_gains")),
        rsi=round(float(g("rsi")), 1),
        vs_high_52w=round(float(g("vs_high_52w")), 2),
        vs_low_52w=round(float(g("vs_low_52w")), 2),
        foreign_net=int(g("foreign_net")),
        inst_net=int(g("inst_net")),
        themes=str(g("themes", "")),
        buy_score=round(float(g("buy_score")), 1),
        buy_grade=str(g("buy_grade", "")),
        sector=str(g("sector", "")),
        industry=str(g("industry", "")),
        etf_category=str(g("etf_category", "")),
        golden_cross_long=int(g("golden_cross_long")),
        volatility_20d=round(float(g("volatility_20d")), 2),
        atr_14=round(float(g("atr_14")), 2),
        risk_grade=str(g("risk_grade", "")),
        nav=round(float(g("nav")), 2),
        earning_rate=round(float(g("earning_rate")), 2),
    )


@router.get("/categories")
async def get_categories():
    """카테고리 목록 (그룹별)."""
    current_phase = _data_store["loading_phase"]
    result = {}
    for group_key, group_info in GROUPS.items():
        cats = []
        for cat_key, cat_info in CATEGORIES.items():
            if cat_info["group"] == group_key:
                required_phase = CATEGORY_PHASE.get(cat_key, 1)
                cats.append(CategoryInfo(
                    key=cat_key,
                    name=cat_info["name"],
                    group=group_key,
                    desc=cat_info["desc"],
                    icon=cat_info["icon"],
                    columns=cat_info["columns"],
                    ready=current_phase >= required_phase,
                ))
        result[group_key] = {
            "name": group_info["name"],
            "icon": group_info["icon"],
            "categories": cats,
        }
    return result


def _build_filter(
    category="surge", market="",
    per_min=None, per_max=None, pbr_min=None, pbr_max=None,
    div_yield_min=None, roe_min=None, roe_max=None,
    market_cap_min=None, market_cap_max=None,
    volume_min=None, volume_ratio_min=None, trading_value_min=None,
    change_pct_min=None, change_pct_max=None,
    above_ma=None, golden_cross=None, ma_aligned=None, surge_only=None,
    rsi_min=None, rsi_max=None, theme=None, theme_group=None, etf_category=None,
    sector=None, tickers=None,
    sort_by=None, sort_asc=None, sort_by2=None, sort_asc2=None,
    limit=100, offset=0,
) -> ScreenerFilter:
    """카테고리 프리셋 + 사용자 오버라이드 → ScreenerFilter."""
    cat_info = CATEGORIES.get(category, CATEGORIES["surge"])
    f = deepcopy(cat_info["filter"])
    if market:
        f.market = market
    if per_min is not None:
        f.per_min = per_min
    if per_max is not None:
        f.per_max = per_max
    if pbr_min is not None:
        f.pbr_min = pbr_min
    if pbr_max is not None:
        f.pbr_max = pbr_max
    if div_yield_min is not None:
        f.div_yield_min = div_yield_min
    if roe_min is not None:
        f.roe_min = roe_min
    if roe_max is not None:
        f.roe_max = roe_max
    if market_cap_min is not None:
        f.market_cap_min = market_cap_min
    if market_cap_max is not None:
        f.market_cap_max = market_cap_max
    if volume_min is not None:
        f.volume_min = volume_min
    if volume_ratio_min is not None:
        f.volume_ratio_min = volume_ratio_min
    if trading_value_min is not None:
        f.trading_value_min = trading_value_min
    if change_pct_min is not None:
        f.change_pct_min = change_pct_min
    if change_pct_max is not None:
        f.change_pct_max = change_pct_max
    if above_ma is not None:
        f.above_ma = above_ma
    if golden_cross is not None:
        f.golden_cross = golden_cross
    if ma_aligned is not None:
        f.ma_aligned = ma_aligned
    if surge_only is not None:
        f.surge_only = surge_only
    if rsi_min is not None:
        f.rsi_min = rsi_min
    if rsi_max is not None:
        f.rsi_max = rsi_max
    if theme:
        f.theme = theme
    if theme_group:
        f.theme_group = theme_group
    if etf_category:
        f.etf_category = etf_category
    if sector:
        f.sector = sector
    if tickers:
        f.tickers = tickers
    if sort_by:
        f.sort_by = sort_by
    if sort_asc is not None:
        f.sort_asc = sort_asc
    if sort_by2:
        f.sort_by2 = sort_by2
    if sort_asc2 is not None:
        f.sort_asc2 = sort_asc2
    f.limit = limit
    f.offset = offset
    return f


@router.get("/scan", response_model=ScanResponse)
async def scan_stocks(
    category: str = "surge",
    market: str = "",
    per_min: float | None = None,
    per_max: float | None = None,
    pbr_min: float | None = None,
    pbr_max: float | None = None,
    div_yield_min: float | None = None,
    roe_min: float | None = None,
    roe_max: float | None = None,
    market_cap_min: float | None = None,
    market_cap_max: float | None = None,
    volume_min: int | None = None,
    volume_ratio_min: float | None = None,
    trading_value_min: float | None = None,
    change_pct_min: float | None = None,
    change_pct_max: float | None = None,
    above_ma: int | None = None,
    golden_cross: bool | None = None,
    ma_aligned: bool | None = None,
    surge_only: bool | None = None,
    rsi_min: float | None = None,
    rsi_max: float | None = None,
    theme: str | None = None,
    theme_group: str | None = None,
    etf_category: str | None = None,
    sector: str | None = None,
    tickers: str | None = None,
    sort_by: str | None = None,
    sort_asc: bool | None = None,
    sort_by2: str | None = None,
    sort_asc2: bool | None = None,
    limit: int = 100,
    offset: int = 0,
):
    """카테고리 기반 종목 탐색."""
    df = _get_combined_df()
    if df is None or df.empty:
        return ScanResponse(total=0, offset=0, limit=limit, last_update="", stocks=[])

    # 카테고리 준비 상태 확인
    required_phase = CATEGORY_PHASE.get(category, 1)
    current_phase = _data_store["loading_phase"]
    if current_phase < required_phase:
        phase_names = {2: "펀더멘탈/테마", 3: "기술지표(이동평균/RSI/52주)"}
        msg = f"{phase_names.get(required_phase, '')} 데이터 로딩 중입니다. 잠시 후 다시 시도해주세요."
        return ScanResponse(
            total=0, offset=0, limit=limit,
            last_update=_data_store["last_update"],
            category=category, message=msg, stocks=[],
        )

    # tickers 문자열을 리스트로 변환
    _filter_keys = {
        "category", "market", "per_min", "per_max", "pbr_min", "pbr_max",
        "div_yield_min", "roe_min", "roe_max", "market_cap_min", "market_cap_max",
        "volume_min", "volume_ratio_min", "trading_value_min",
        "change_pct_min", "change_pct_max", "above_ma", "golden_cross",
        "ma_aligned", "surge_only", "rsi_min", "rsi_max", "theme", "theme_group",
        "etf_category", "sector", "tickers", "sort_by", "sort_asc",
        "sort_by2", "sort_asc2", "limit", "offset",
    }
    params = {k: v for k, v in locals().items() if k in _filter_keys}
    if params.get("tickers") and isinstance(params["tickers"], str):
        params["tickers"] = [t.strip() for t in params["tickers"].split(",") if t.strip()]
    f = _build_filter(**params)
    filtered, total = apply_filters(df, f)
    stocks = [_row_to_item(row) for _, row in filtered.iterrows()]

    # 빈 결과일 때 카테고리 기준 안내 메시지
    msg = ""
    if not stocks:
        cat_info = CATEGORIES.get(category, {})
        cat_name = cat_info.get("name", category)
        cat_desc = cat_info.get("desc", "")
        _empty_hints = {
            "surge": "급등예보 5개 조건 중 4개 이상 충족 종목이 현재 없습니다.\n(거래량 매집 + 추세 수렴 + 연속 상승 + 골든크로스 동시 충족 필요)",
            "momentum": "골든크로스 발생 + 거래량 1.2배 이상 동반 종목이 현재 없습니다.",
            "turnaround": "RSI 35 이하 + 거래량 1.5배 이상 + PBR 1.5 이하 동시 충족 종목이 현재 없습니다.",
            "accumulation": "거래량 급증 + 가격 안정(매집 의심) 패턴이 현재 감지되지 않습니다.",
            "breakout": "52주 고가 대비 -5% 이내 + 돌파 점수 2 이상인 종목이 현재 없습니다.",
            "oversold": "RSI 30 이하 과매도 구간 종목이 현재 없습니다.",
            "foreign_inst": "외국인·기관 순매수 종목이 현재 없습니다.\n휴일·장 시작 전에는 직전 거래일 데이터가 표시됩니다.",
        }
        hint = _empty_hints.get(category, "")
        if hint:
            msg = hint
        else:
            msg = f"[{cat_name}] 조건에 맞는 종목이 현재 없습니다."
        if cat_desc and category not in _empty_hints:
            msg += f"\n기준: {cat_desc}"

    return ScanResponse(
        total=total, offset=offset, limit=limit,
        last_update=_data_store["last_update"],
        category=category, message=msg, stocks=stocks,
    )


# 내보내기용 컬럼 한글 매핑
_EXPORT_COLUMNS = {
    "ticker": "종목코드", "name": "종목명", "market": "시장",
    "close": "현재가", "change_pct": "등락률(%)", "volume": "거래량",
    "volume_ratio": "거래량비", "trading_value": "거래대금",
    "market_cap": "시총(억)", "per": "PER", "pbr": "PBR",
    "roe": "ROE(%)", "div_yield": "배당률(%)", "div_years": "연속배당(년)", "div_growth": "배당성장률(%)",
    "ma5": "MA5", "ma20": "MA20", "ma60": "MA60",
    "rsi": "RSI", "vs_high_52w": "52주고가比(%)", "vs_low_52w": "52주저가比(%)",
    "surge_score": "급등점수", "pre_surge_score": "급등예보점수",
    "accumulation": "매집신호", "breakout_score": "돌파점수",
    "volume_trend": "거래량추세(일)", "ma_squeeze": "이평수렴(%)",
    "foreign_net": "외국인순매수(원)", "inst_net": "기관순매수(원)",
    "themes": "테마",
    "etf_category": "ETF분류", "nav": "NAV", "earning_rate": "수익률(%)",
}


@router.get("/export")
async def export_stocks(
    category: str = "surge",
    format: str = "csv",
    market: str = "",
    per_min: float | None = None,
    per_max: float | None = None,
    pbr_min: float | None = None,
    pbr_max: float | None = None,
    div_yield_min: float | None = None,
    roe_min: float | None = None,
    roe_max: float | None = None,
    market_cap_min: float | None = None,
    market_cap_max: float | None = None,
    volume_min: int | None = None,
    volume_ratio_min: float | None = None,
    trading_value_min: float | None = None,
    change_pct_min: float | None = None,
    change_pct_max: float | None = None,
    above_ma: int | None = None,
    golden_cross: bool | None = None,
    ma_aligned: bool | None = None,
    surge_only: bool | None = None,
    rsi_min: float | None = None,
    rsi_max: float | None = None,
    theme: str | None = None,
    etf_category: str | None = None,
    sort_by: str | None = None,
    sort_asc: bool | None = None,
):
    """현재 필터 결과를 CSV/Excel로 내보내기."""
    df = _get_combined_df()
    if df is None or df.empty:
        return {"error": "데이터 없음"}

    params = {k: v for k, v in locals().items() if k not in ("df", "format")}
    params["limit"] = 10000
    params["offset"] = 0
    f = _build_filter(**params)
    filtered, total = apply_filters(df, f)

    # 카테고리별 표시 컬럼 결정
    cat_info = CATEGORIES.get(category, CATEGORIES["surge"])
    display_cols = ["ticker", "name", "market", "close"] + cat_info["columns"]
    # 실제 존재하는 컬럼만
    export_cols = [c for c in display_cols if c in filtered.columns]
    export_df = filtered[export_cols].copy()
    export_df.rename(columns={c: _EXPORT_COLUMNS.get(c, c) for c in export_cols}, inplace=True)

    cat_name = cat_info["name"]
    today = datetime.now().strftime("%Y%m%d")
    filename = f"screener_{cat_name}_{today}"

    if format == "xlsx":
        buf = io.BytesIO()
        export_df.to_excel(buf, index=False, engine="openpyxl")
        buf.seek(0)
        return StreamingResponse(
            buf,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}.xlsx"},
        )
    else:
        buf = io.StringIO()
        export_df.to_csv(buf, index=False, encoding="utf-8-sig")
        buf.seek(0)
        return StreamingResponse(
            io.BytesIO(buf.getvalue().encode("utf-8-sig")),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}.csv"},
        )


@router.get("/chart")
async def get_chart_data(ticker: str):
    """종목 차트 데이터 (OHLCV) — Firestore에서 로드."""
    import asyncio

    empty = {"candles": [], "ma5": [], "ma20": [], "ma60": []}
    df = _data_store.get("df")
    if df is None:
        return empty

    # Firestore history에서 해당 종목 데이터 로드
    try:
        from screener.db.repository import load_history_single
        loop = asyncio.get_event_loop()
        hdf = await loop.run_in_executor(None, load_history_single, ticker)
    except Exception:
        # fallback: 로컬 캐시
        from screener.core.data_fetcher import load_cache
        history = load_cache("history")
        if history is None or history.empty:
            return empty
        hdf = history[history["ticker"] == ticker].copy()

    if hdf is None or hdf.empty:
        return empty

    hdf = hdf.sort_values("date")
    hdf["date_str"] = hdf["date"].dt.strftime("%Y-%m-%d") if hasattr(hdf["date"].iloc[0], "strftime") else hdf["date"].astype(str)

    candles = [
        {"time": r["date_str"], "open": float(r["open"]), "high": float(r["high"]),
         "low": float(r["low"]), "close": float(r["close"])}
        for _, r in hdf.iterrows()
    ]

    # 이동평균
    ma_data = {}
    for period in [5, 20, 60]:
        hdf[f"ma{period}"] = hdf["close"].rolling(period).mean()
        ma_data[f"ma{period}"] = [
            {"time": r["date_str"], "value": round(float(r[f"ma{period}"]), 0)}
            for _, r in hdf.iterrows() if pd.notna(r[f"ma{period}"])
        ]

    return {"candles": candles, **ma_data}


@router.get("/themes")
async def get_themes():
    """테마 목록 (그룹별 분류 포함)."""
    return {
        "themes": _data_store.get("themes", {}),
        "groups": _data_store.get("theme_groups", {}),
    }


@router.get("/auth-config")
async def get_auth_config():
    """Firebase 웹 앱 설정 (프론트엔드 초기화용).

    환경변수 FIREBASE_WEB_API_KEY 미설정 시 빈 객체 반환 (인증 비활성).
    """
    import os
    api_key = os.environ.get("FIREBASE_WEB_API_KEY", "")
    project_id = os.environ.get("FIREBASE_PROJECT_ID", "")
    if not api_key:
        return {}
    return {
        "apiKey": api_key,
        "authDomain": f"{project_id}.firebaseapp.com",
        "projectId": project_id,
    }


@router.get("/sectors")
async def get_sectors():
    """US 섹터 목록 (종목 수 포함)."""
    df = _get_combined_df()
    if df is None or df.empty or "sector" not in df.columns:
        return {"sectors": []}

    us_df = df[df["market"].isin(["NASDAQ", "S&P500"])]
    sector_counts = us_df[us_df["sector"] != ""].groupby("sector").size().sort_values(ascending=False)
    sectors = [{"name": name, "count": int(count)} for name, count in sector_counts.items()]
    return {"sectors": sectors}


@router.get("/backtest")
async def get_backtest():
    """시그널 백테스트 결과."""
    from screener.core.backtest import backtest_signals
    from screener.db.repository import load_history

    import asyncio
    loop = asyncio.get_event_loop()

    df = _get_combined_df()
    if df is None or df.empty:
        return {"signals": {}, "message": "데이터 없음"}

    history = await loop.run_in_executor(None, load_history)
    if history.empty:
        return {"signals": {}, "message": "히스토리 데이터 없음"}

    results = await loop.run_in_executor(None, backtest_signals, history, df)
    return {"signals": results}


@router.post("/portfolio")
async def update_portfolio(body: dict):
    """포트폴리오 저장/수정.

    body: {"holdings": [{"ticker": "005930", "buy_price": 70000, "qty": 10}, ...]}
    """
    holdings = body.get("holdings", [])
    if not holdings:
        return {"error": "holdings 필드 필요"}

    df = _get_combined_df()
    if df is None or df.empty:
        return {"error": "데이터 로딩 중"}

    results = []
    total_invested = 0
    total_current = 0

    for h in holdings:
        ticker = h.get("ticker", "")
        buy_price = float(h.get("buy_price", 0))
        qty = int(h.get("qty", 0))

        if not ticker or buy_price <= 0 or qty <= 0:
            continue

        row = df[df["ticker"] == ticker]
        if row.empty:
            results.append({
                "ticker": ticker, "name": "미확인",
                "buy_price": buy_price, "qty": qty,
                "current_price": 0, "return_pct": 0, "return_amount": 0,
            })
            continue

        stock = row.iloc[0]
        current_price = float(stock.get("close", 0))
        invested = buy_price * qty
        current_val = current_price * qty
        return_pct = ((current_price / buy_price) - 1) * 100 if buy_price > 0 else 0
        return_amount = current_val - invested

        total_invested += invested
        total_current += current_val

        results.append({
            "ticker": ticker,
            "name": str(stock.get("name", "")),
            "market": str(stock.get("market", "")),
            "buy_price": buy_price,
            "qty": qty,
            "current_price": current_price,
            "change_pct": float(stock.get("change_pct", 0)),
            "return_pct": round(return_pct, 2),
            "return_amount": round(return_amount),
            "buy_score": float(stock.get("buy_score", 0)),
            "buy_grade": str(stock.get("buy_grade", "")),
        })

    total_return_pct = ((total_current / total_invested) - 1) * 100 if total_invested > 0 else 0

    return {
        "holdings": results,
        "summary": {
            "total_invested": round(total_invested),
            "total_current": round(total_current),
            "total_return_pct": round(total_return_pct, 2),
            "total_return_amount": round(total_current - total_invested),
            "count": len(results),
        },
    }


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 실시간 업데이트."""
    await websocket.accept()
    _ws_clients.append(websocket)
    try:
        while True:
            await websocket.receive_text()  # keepalive
    except WebSocketDisconnect:
        if websocket in _ws_clients:
            _ws_clients.remove(websocket)


@router.get("/schedule-status")
async def get_schedule_status():
    """스케줄 수집 상태 (안정성 모니터링).

    Firestore sync_metadata에서 최근 수집 상태를 반환.
    로컬 JSON 파일이 있으면 병합.
    """
    import json
    import os
    from screener.db.repository import get_sync_metadata

    # Firestore에서 수집 상태 가져오기
    result = {"runs": [], "summary": {}, "cloud_status": {}}
    try:
        meta = get_sync_metadata()
        result["cloud_status"] = {
            "last_schedule": meta.get("last_collect_schedule", ""),
            "last_status": meta.get("last_collect_status", ""),
            "last_time": meta.get("last_collect_time", ""),
            "last_elapsed": meta.get("last_collect_elapsed", 0),
            "last_error": meta.get("last_collect_error", ""),
            "collector_heartbeat": meta.get("collector_heartbeat", ""),
            "kr_updated": meta.get("stocks_kr_updated_at", ""),
            "us_updated": meta.get("stocks_us_updated_at", ""),
            "etf_updated": meta.get("stocks_etf_updated_at", ""),
            "history_updated": meta.get("history_updated_at", ""),
            "themes_updated": meta.get("themes_updated_at", ""),
        }
    except Exception as e:
        result["cloud_status"] = {"error": str(e)}

    # 로컬 JSON 파일 (있으면 병합)
    status_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "schedule_status.json")
    if os.path.exists(status_file):
        try:
            with open(status_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            result["runs"] = data.get("runs", [])[-20:]
            result["summary"] = data.get("summary", {})
        except Exception:
            pass

    return result


@router.get("/status", response_model=StatusResponse)
async def get_status():
    """서버 상태."""
    df = _data_store["df"]
    etf = _data_store["etf_df"]
    return StatusResponse(
        status="ready" if df is not None and not df.empty else "loading",
        total_stocks=len(df) if df is not None else 0,
        total_etf=len(etf) if etf is not None else 0,
        total_themes=len(_data_store.get("themes", {})),
        last_update=_data_store["last_update"],
        loading_phase=_data_store["loading_phase"],
    )
