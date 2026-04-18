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

# ── 간이 캐시 (무거운 API 결과 5분 캐싱) ──
_api_cache: dict = {}  # {key: {"data": ..., "expires": datetime}}
CACHE_TTL = timedelta(minutes=5)


def _cache_get(key: str):
    """캐시에서 값 가져오기 (만료 시 None)."""
    entry = _api_cache.get(key)
    if entry and datetime.now() < entry["expires"]:
        return entry["data"]
    return None


def _cache_set(key: str, data):
    """캐시에 값 저장."""
    _api_cache[key] = {"data": data, "expires": datetime.now() + CACHE_TTL}

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
        # v6 Phase 2: 수급
        foreign_consecutive=int(g("foreign_consecutive")),
        supply_intensity=round(float(g("supply_intensity")), 2),
        dual_buy=bool(g("dual_buy", False)),
        supply_grade=str(g("supply_grade", "")),
        # v6 Phase 3: 펀더멘탈 확장
        forward_pe=round(float(g("forward_pe")), 2),
        peg_ratio=round(float(g("peg_ratio")), 2),
        ev_ebitda=round(float(g("ev_ebitda")), 2),
        profit_margin=round(float(g("profit_margin")), 2),
        operating_margin=round(float(g("operating_margin")), 2),
        fcf_yield=round(float(g("fcf_yield")), 2),
        debt_equity=round(float(g("debt_equity")), 2),
        revenue_growth=round(float(g("revenue_growth")), 2),
        target_price=round(float(g("target_price")), 2),
        target_upside=round(float(g("target_upside")), 2),
        # v6 Phase 4: 리스크
        position_size=round(float(g("position_size")), 1),
    )


@router.get("/all-stocks")
async def get_all_stocks(q: str = "", limit: int = 30):
    """포트폴리오 자동완성용 전체 종목 경량 목록 (ticker/name/close/market만)."""
    df = _get_combined_df()
    if df is None or df.empty:
        return {"stocks": []}
    if q:
        ql = q.strip().lower()
        if ql:
            mask = df["ticker"].astype(str).str.lower().str.contains(ql, na=False) | \
                   df["name"].astype(str).str.lower().str.contains(ql, na=False)
            df = df[mask]
    df = df.head(max(1, min(limit, 200)))
    stocks = []
    for _, row in df.iterrows():
        stocks.append({
            "ticker": str(row.get("ticker", "")),
            "name": str(row.get("name", "") or row.get("ticker", "")),
            "close": float(row.get("close", 0) or 0),
            "market": str(row.get("market", "") or ""),
        })
    return {"stocks": stocks}


@router.get("/categories")
async def get_categories():
    """카테고리 목록 (그룹별). Free 카테고리 먼저 + tier 표시."""
    from screener.middleware import FREE_CATEGORIES
    current_phase = _data_store["loading_phase"]
    result = {}
    for group_key, group_info in GROUPS.items():
        cats = []
        for cat_key, cat_info in CATEGORIES.items():
            if cat_info["group"] == group_key:
                required_phase = CATEGORY_PHASE.get(cat_key, 1)
                tier = "free" if cat_key in FREE_CATEGORIES else "pro"
                cats.append(CategoryInfo(
                    key=cat_key,
                    name=cat_info["name"],
                    group=group_key,
                    desc=cat_info["desc"],
                    icon=cat_info["icon"],
                    columns=cat_info["columns"],
                    ready=current_phase >= required_phase,
                    tier=tier,
                ))
        # Free 먼저, Pro 나중 — 그룹 내 원래 순서 보존
        cats.sort(key=lambda c: 0 if c.tier == "free" else 1)
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
            "quality": "퀄리티주는 해외(US) 종목 전용입니다.\n국내 종목은 yfinance 펀더멘탈(순이익률·부채비율·매출성장률) 미제공.\n🇺🇸 해외 탭으로 전환하면 결과를 확인할 수 있습니다.",
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

    # 한글 파일명 브라우저 호환 (RFC 5987)
    from urllib.parse import quote
    ascii_fallback = f"screener_{today}"

    if format == "xlsx":
        buf = io.BytesIO()
        export_df.to_excel(buf, index=False, engine="openpyxl")
        buf.seek(0)
        fn_xlsx = quote(f"{filename}.xlsx")
        return StreamingResponse(
            buf,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename=\"{ascii_fallback}.xlsx\"; filename*=UTF-8''{fn_xlsx}",
            },
        )
    else:
        # UTF-8 BOM + CSV (Excel 한글 호환)
        csv_text = export_df.to_csv(index=False)
        csv_bytes = b"\xef\xbb\xbf" + csv_text.encode("utf-8")
        fn_csv = quote(f"{filename}.csv")
        return StreamingResponse(
            io.BytesIO(csv_bytes),
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f"attachment; filename=\"{ascii_fallback}.csv\"; filename*=UTF-8''{fn_csv}",
            },
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
    """시그널 백테스트 결과 (v6 다기간, 5분 캐싱)."""
    cached = _cache_get("backtest")
    if cached:
        return cached

    from screener.core.backtest import backtest_signals
    from screener.db.repository import load_history

    import asyncio
    loop = asyncio.get_event_loop()

    df = _get_combined_df()
    if df is None or df.empty:
        return {"signals": {}, "score_tracking": {}, "message": "데이터 없음"}

    history = await loop.run_in_executor(None, load_history)
    if history.empty:
        return {"signals": {}, "score_tracking": {}, "message": "히스토리 데이터 없음"}

    results = await loop.run_in_executor(None, backtest_signals, history, df)
    result = results if results else {"signals": {}, "score_tracking": {}}
    _cache_set("backtest", result)
    return result


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


# ──────────────────────────────────────────────
# v6 Phase 2-3: 시장 전체 수급 게이지
# ──────────────────────────────────────────────

@router.get("/market-sentiment")
async def get_market_sentiment():
    """시장 전체 수급 센티먼트."""
    df = _data_store.get("df")
    if df is None or df.empty:
        return {"kr": {}, "us": {}}

    result = {}
    for label, markets in [("kr", ["KOSPI", "KOSDAQ"]), ("us", ["NASDAQ", "S&P500"])]:
        mdf = df[df["market"].isin(markets)]
        if mdf.empty:
            result[label] = {}
            continue

        total = len(mdf)
        foreign_buy = (mdf.get("foreign_net", pd.Series(0, index=mdf.index)) > 0).sum()
        inst_buy = (mdf.get("inst_net", pd.Series(0, index=mdf.index)) > 0).sum()
        foreign_total = int(mdf.get("foreign_net", pd.Series(0, index=mdf.index)).sum())
        advancing = (mdf["change_pct"] > 0).sum()
        declining = (mdf["change_pct"] < 0).sum()
        adl_ratio = round(advancing / max(declining, 1), 2)

        above_ma20 = 0
        if "ma20" in mdf.columns:
            above_ma20 = ((mdf["close"] > 0) & (mdf["ma20"] > 0) & (mdf["close"] > mdf["ma20"])).sum()

        # 센티먼트 판별
        buy_ratio = foreign_buy / max(total, 1)
        if buy_ratio > 0.5 and adl_ratio > 1.2:
            sentiment = "매수 우위"
        elif buy_ratio < 0.3 and adl_ratio < 0.8:
            sentiment = "매도 우위"
        else:
            sentiment = "중립"

        result[label] = {
            "foreign_buy_ratio": round(foreign_buy / max(total, 1), 2),
            "foreign_total_net": foreign_total,
            "inst_buy_ratio": round(inst_buy / max(total, 1), 2),
            "advance_decline": adl_ratio,
            "above_ma20_ratio": round(above_ma20 / max(total, 1), 2),
            "sentiment": sentiment,
            "total_stocks": total,
        }

    return result


# ──────────────────────────────────────────────
# v6 Phase 4-2: 포트폴리오 리스크 (상관관계)
# ──────────────────────────────────────────────

def _clean_label(s: str, fallback: str = "기타") -> str:
    if not s:
        return fallback
    s = s.strip()
    if not s or "\ufffd" in s or any(ord(c) < 0x20 for c in s):
        return fallback
    if not any("\uac00" <= c <= "\ud7a3" or c.isascii() for c in s):
        return fallback
    return s


def _pf_sector_of(row_dict: dict) -> str:
    raw_sector = str(row_dict.get("sector", "") or "")
    themes_raw = str(row_dict.get("themes", "") or "")
    first_theme = themes_raw.split(",")[0].strip() if themes_raw else ""
    market = str(row_dict.get("market", "") or "")
    is_etf = "ETF" in market.upper()
    return _clean_label(raw_sector, "") or _clean_label(first_theme, "") or ("ETF" if is_etf else "기타")


def _pf_grade(score: float) -> str:
    if score >= 90: return "S"
    if score >= 80: return "A"
    if score >= 70: return "B"
    if score >= 60: return "C"
    if score >= 50: return "D"
    return "F"


def _pf_recommendations(
    *, n_stocks: int, max_sector_pct: int, max_sector_name: str,
    avg_corr: float, port_vol: float, mdd: float, market_split: dict,
    top_weight_pct: int, top_weight_name: str,
) -> list[dict]:
    recs: list[dict] = []
    if top_weight_pct >= 40:
        recs.append({"level": "danger", "msg": f"🚨 {top_weight_name}이(가) 포트폴리오의 {top_weight_pct}%를 차지합니다. 한 종목 리스크가 큽니다."})
    elif top_weight_pct >= 30:
        recs.append({"level": "warning", "msg": f"⚠️ {top_weight_name} 비중 {top_weight_pct}% — 20% 내로 조정 권장"})
    if max_sector_pct >= 60:
        recs.append({"level": "warning", "msg": f"⚠️ {max_sector_name} 섹터에 {max_sector_pct}% 집중. 2~3개 섹터로 분산 시 변동성 20% 감소"})
    elif max_sector_pct >= 40:
        recs.append({"level": "info", "msg": f"💡 {max_sector_name} 섹터 비중 {max_sector_pct}% — 타 섹터 추가 고려"})
    if n_stocks < 3:
        recs.append({"level": "warning", "msg": f"📌 종목 {n_stocks}개는 분산이 부족합니다. 5~10개가 이상적"})
    elif n_stocks < 5:
        recs.append({"level": "info", "msg": f"💡 현재 {n_stocks}개 보유. 5~10개로 확장 시 개별 리스크 크게 감소"})
    elif n_stocks > 15:
        recs.append({"level": "info", "msg": f"💡 {n_stocks}개 보유는 관리가 어려울 수 있습니다. 핵심 10개로 집중도 좋은 선택"})
    if avg_corr >= 0.7:
        recs.append({"level": "warning", "msg": f"⚠️ 종목 간 평균 상관관계 {avg_corr:.2f} — 유사하게 움직이는 종목들입니다. 역상관 자산 추가 권장"})
    elif avg_corr >= 0.5:
        recs.append({"level": "info", "msg": f"💡 상관관계 {avg_corr:.2f} — 섹터 간 분산 추가로 안정성↑"})
    if port_vol >= 35:
        recs.append({"level": "danger", "msg": f"🚨 연간 변동성 {port_vol:.0f}% — 고위험 구성입니다. 안정 자산 편입 필요"})
    elif port_vol >= 25:
        recs.append({"level": "warning", "msg": f"⚠️ 변동성 {port_vol:.0f}% — 시장 평균(KOSPI ~18%)보다 높음"})
    if mdd and mdd >= 25:
        recs.append({"level": "warning", "msg": f"📉 최대 낙폭 -{mdd:.1f}% — 손절선 설정 또는 현금 비중 확대 고려"})
    kr_pct = market_split.get("KR", 0)
    if kr_pct == 100:
        recs.append({"level": "info", "msg": "🌏 KR 100% — 글로벌 분산(US 20~30%)으로 통화·지역 리스크 감소"})
    elif kr_pct == 0:
        recs.append({"level": "info", "msg": "🇰🇷 국내 비중 0% — 국내 대형주로 환율 리스크 헤지 고려"})
    if not recs:
        recs.append({"level": "success", "msg": "🎯 균형 잡힌 포트폴리오입니다. 현재 구성이 훌륭해요."})
    return recs


@router.post("/portfolio/risk")
async def portfolio_risk(body: dict):
    """포트폴리오 전문가 리스크 분석 — 건강도/추천/MDD/비중/상관관계/섹터.

    body: {"tickers": [...]} 또는 {"holdings": [{ticker, buy_price, qty}, ...]}
    holdings가 있으면 실제 평가금 기반 비중. 없으면 동일 비중.
    """
    import asyncio
    import numpy as np
    from screener.db.repository import load_history_single

    holdings = body.get("holdings") or []
    if holdings:
        tickers = [str(h.get("ticker", "")) for h in holdings if h.get("ticker")]
    else:
        tickers = body.get("tickers", [])
    if not tickers or len(tickers) < 2:
        return {"error": "2개 이상 종목 필요"}

    df = _get_combined_df()

    # 실제 평가금 기반 비중 계산
    weights_map: dict[str, float] = {}
    market_split = {"KR": 0.0, "US": 0.0}
    current_values: dict[str, float] = {}
    name_of: dict[str, str] = {}
    sector_of: dict[str, str] = {}
    if holdings and df is not None:
        total_value = 0.0
        for h in holdings:
            t = str(h.get("ticker", ""))
            qty = float(h.get("qty", 0) or 0)
            row = df[df["ticker"] == t]
            if row.empty or qty <= 0:
                continue
            close = float(row.iloc[0].get("close", 0) or 0)
            val = close * qty
            if val <= 0:
                continue
            current_values[t] = val
            total_value += val
            name_of[t] = str(row.iloc[0].get("name", "") or t)
            sector_of[t] = _pf_sector_of(row.iloc[0].to_dict())
            mk = str(row.iloc[0].get("market", "") or "")
            if any(x in mk.upper() for x in ("US", "NASDAQ", "NYSE")):
                market_split["US"] += val
            else:
                market_split["KR"] += val
        if total_value > 0:
            for t, v in current_values.items():
                weights_map[t] = v / total_value
            market_split = {k: round(v / total_value * 100) for k, v in market_split.items() if v > 0}
    if not weights_map:
        # fallback 동일 비중
        for t in tickers:
            weights_map[t] = 1.0 / len(tickers)
            if df is not None:
                row = df[df["ticker"] == t]
                if not row.empty:
                    name_of[t] = str(row.iloc[0].get("name", "") or t)
                    sector_of[t] = _pf_sector_of(row.iloc[0].to_dict())
        market_split = {}

    loop = asyncio.get_event_loop()
    histories = {}
    for t in tickers[:15]:
        hdf = await loop.run_in_executor(None, load_history_single, t)
        if hdf is not None and not hdf.empty:
            hdf = hdf.sort_values("date").set_index("date")
            histories[t] = hdf["close"].pct_change().dropna()

    if len(histories) < 2:
        return {"error": "히스토리 데이터 부족", "tickers": tickers}

    returns_df = pd.DataFrame(histories).dropna()
    if len(returns_df) < 10:
        return {"error": "공통 기간 데이터 부족", "tickers": list(histories.keys())}

    hist_tickers = list(returns_df.columns)
    # 비중 벡터 정렬
    w = np.array([weights_map.get(t, 0) for t in hist_tickers])
    w_sum = w.sum()
    if w_sum <= 0:
        w = np.array([1.0 / len(hist_tickers)] * len(hist_tickers))
    else:
        w = w / w_sum

    # 포트폴리오 일일 수익률
    port_returns = returns_df.values @ w

    # 변동성 (연환산)
    port_vol = round(float(np.std(port_returns) * np.sqrt(250) * 100), 2)
    # 연환산 수익률 (단순 평균 기반)
    port_mean_daily = float(np.mean(port_returns))
    annualized_return = round(port_mean_daily * 250 * 100, 2)
    # 샤프 비율 (리스크프리 3%)
    rf = 0.03
    sharpe = round((port_mean_daily * 250 - rf) / (np.std(port_returns) * np.sqrt(250) + 1e-9), 2)
    # MDD
    cum = np.cumprod(1 + port_returns)
    running_max = np.maximum.accumulate(cum)
    drawdown = (cum - running_max) / running_max
    mdd = round(float(-drawdown.min()) * 100, 2)

    # 상관관계
    corr_df = returns_df.corr().round(3)
    corr_matrix = corr_df.values.tolist()
    # 평균 상관계수 (대각 제외)
    n = len(hist_tickers)
    if n > 1:
        triu = corr_df.values[np.triu_indices(n, k=1)]
        avg_corr = round(float(np.mean(triu)), 3)
    else:
        avg_corr = 0.0

    # 섹터 비중 (평가금 가중)
    sector_values: dict[str, float] = {}
    for t in tickers:
        s = sector_of.get(t, "기타")
        v = current_values.get(t, weights_map.get(t, 0))
        sector_values[s] = sector_values.get(s, 0) + v
    total_sv = sum(sector_values.values()) or 1
    sector_pct = {k: round(v / total_sv * 100) for k, v in sector_values.items()}
    max_sector = max(sector_pct.items(), key=lambda x: x[1], default=("", 0))

    # Top 비중 종목
    top_weight_t = max(weights_map, key=weights_map.get) if weights_map else ""
    top_weight_pct = int(round(weights_map.get(top_weight_t, 0) * 100))
    top_weight_name = name_of.get(top_weight_t, top_weight_t)

    # 건강도 점수 (0~100)
    score = 100.0
    if port_vol > 35: score -= 20
    elif port_vol > 25: score -= 10
    elif port_vol > 18: score -= 3
    if max_sector[1] >= 60: score -= 20
    elif max_sector[1] >= 40: score -= 10
    if len(tickers) < 3: score -= 15
    elif len(tickers) < 5: score -= 7
    if avg_corr >= 0.7: score -= 15
    elif avg_corr >= 0.5: score -= 7
    if mdd >= 30: score -= 15
    elif mdd >= 20: score -= 7
    if top_weight_pct >= 40: score -= 15
    elif top_weight_pct >= 30: score -= 7
    if sharpe >= 1.5: score += 5
    elif sharpe <= 0: score -= 10
    score = max(0.0, min(100.0, score))
    grade = _pf_grade(score)

    recommendations = _pf_recommendations(
        n_stocks=len(tickers),
        max_sector_pct=max_sector[1],
        max_sector_name=max_sector[0],
        avg_corr=avg_corr,
        port_vol=port_vol,
        mdd=mdd,
        market_split=market_split,
        top_weight_pct=top_weight_pct,
        top_weight_name=top_weight_name,
    )

    # 종목별 비중·섹터 정보 (프론트 차트용)
    positions = []
    for t in hist_tickers:
        positions.append({
            "ticker": t,
            "name": name_of.get(t, t),
            "sector": sector_of.get(t, "기타"),
            "weight_pct": round(weights_map.get(t, 0) * 100, 1),
        })
    positions.sort(key=lambda x: x["weight_pct"], reverse=True)

    # 리스크 경고 (기존 호환)
    risk_warning = ""
    if max_sector[1] >= 60:
        risk_warning = f"{max_sector[0]} 섹터 {max_sector[1]}% 집중 — 분산 권장"

    return {
        "tickers": hist_tickers,
        "positions": positions,
        "correlation_matrix": corr_matrix,
        "portfolio_volatility": port_vol,
        "annualized_return": annualized_return,
        "sharpe_ratio": sharpe,
        "max_drawdown": mdd,
        "health_score": round(score),
        "health_grade": grade,
        "avg_correlation": avg_corr,
        "top_weight_ticker": top_weight_t,
        "top_weight_name": top_weight_name,
        "top_weight_pct": top_weight_pct,
        "sector_concentration": sector_pct,
        "market_split": market_split,
        "recommendations": recommendations,
        "risk_warning": risk_warning,
    }


# ──────────────────────────────────────────────
# v6 Phase 4-3: 시장 레짐
# ──────────────────────────────────────────────

@router.get("/market-regime")
async def get_market_regime():
    """시장 레짐 감지 (강세/약세/횡보, 5분 캐싱)."""
    cached = _cache_get("market_regime")
    if cached:
        return cached

    import asyncio
    from screener.db.repository import load_history
    from screener.core.metrics import detect_market_regime

    loop = asyncio.get_event_loop()
    history = await loop.run_in_executor(None, load_history)

    if history.empty:
        return {"regime": "unknown", "confidence": 0}

    close_pivot = history.pivot_table(
        index="date", columns="ticker", values="close", aggfunc="last"
    ).sort_index()

    # 전종목 평균으로 인덱스 대체
    index_series = close_pivot.mean(axis=1)
    regime = detect_market_regime(index_series)

    # 레짐별 가중치
    REGIME_WEIGHTS = {
        "bull": {"surge": 1.0, "momentum": 1.2, "turnaround": 0.5, "value": 0.8},
        "bear": {"surge": 0.5, "momentum": 0.3, "turnaround": 1.5, "value": 1.2},
        "sideways": {"surge": 0.8, "momentum": 0.7, "turnaround": 1.0, "value": 1.0},
    }

    result = {
        **regime,
        "strategy_weights": REGIME_WEIGHTS.get(regime["regime"], {}),
    }
    _cache_set("market_regime", result)
    return result


# ──────────────────────────────────────────────
# v6 Phase 5-1: 종목 비교
# ──────────────────────────────────────────────

@router.get("/compare")
async def compare_stocks(tickers: str = ""):
    """2~5개 종목 나란히 비교."""
    if not tickers:
        return {"error": "tickers 파라미터 필요 (쉼표 구분)"}

    ticker_list = [t.strip() for t in tickers.split(",") if t.strip()][:5]
    df = _get_combined_df()
    if df is None or df.empty:
        return {"error": "데이터 없음"}

    results = []
    not_found = []
    for t in ticker_list:
        row = df[df["ticker"] == t]
        if row.empty:
            not_found.append(t)
            continue
        results.append(_row_to_item(row.iloc[0]).model_dump())

    resp = {"stocks": results, "count": len(results)}
    if not_found:
        resp["not_found"] = not_found
        resp["message"] = f"다음 종목을 찾을 수 없습니다: {', '.join(not_found)}"
    return resp


# ──────────────────────────────────────────────
# v6 Phase 5-3: 섹터 자금 흐름
# ──────────────────────────────────────────────

@router.get("/sector-flow")
async def get_sector_flow():
    """섹터별 외국인/기관 순매수 합계."""
    df = _data_store.get("df")
    if df is None or df.empty:
        return {"sectors": []}

    # 테마그룹 또는 섹터 기준
    kr = df[df["market"].isin(["KOSPI", "KOSDAQ"])]
    if kr.empty:
        return {"sectors": []}

    # 테마 그룹별 수급 집계
    from screener.db.repository import THEME_GROUP_MAP
    group_flow = {}
    import math
    for _, row in kr.iterrows():
        themes_str = str(row.get("themes", ""))
        fn = float(row.get("foreign_net", 0))
        inst = float(row.get("inst_net", 0))
        mcap = float(row.get("market_cap", 0))
        fn = 0.0 if (math.isnan(fn) or math.isinf(fn)) else fn
        inst = 0.0 if (math.isnan(inst) or math.isinf(inst)) else inst
        mcap = 0.0 if (math.isnan(mcap) or math.isinf(mcap)) else mcap

        # 종목의 테마에서 그룹 결정
        group = "기타"
        for g, keywords in THEME_GROUP_MAP.items():
            for kw in keywords:
                if kw.lower() in themes_str.lower():
                    group = g
                    break
            if group != "기타":
                break

        if group not in group_flow:
            group_flow[group] = {"foreign_net": 0, "inst_net": 0, "market_cap": 0, "count": 0}
        group_flow[group]["foreign_net"] += fn
        group_flow[group]["inst_net"] += inst
        group_flow[group]["market_cap"] += mcap
        group_flow[group]["count"] += 1

    sectors = []
    for name, data in sorted(group_flow.items(), key=lambda x: x[1]["foreign_net"], reverse=True):
        if data["count"] < 3:
            continue
        fn = data["foreign_net"]
        inst = data["inst_net"]
        sectors.append({
            "name": name,
            "foreign_net": int(fn) if not pd.isna(fn) else 0,
            "inst_net": int(inst) if not pd.isna(inst) else 0,
            "market_cap": round(data["market_cap"]) if not pd.isna(data["market_cap"]) else 0,
            "count": data["count"],
            "flow": "inflow" if fn > 0 else "outflow",
        })

    return {"sectors": sectors}
