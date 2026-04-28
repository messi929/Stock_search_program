"""종목 추천 엔진 — 15개 카테고리 (매매 시그널 기반)."""

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd
from loguru import logger

from screener.config import MIN_TRADING_VALUE


@dataclass
class ScreenerFilter:
    """필터 조건."""
    market: str = "ALL"
    per_min: Optional[float] = None
    per_max: Optional[float] = None
    pbr_min: Optional[float] = None
    pbr_max: Optional[float] = None
    div_yield_min: Optional[float] = None
    roe_min: Optional[float] = None
    roe_max: Optional[float] = None
    market_cap_min: Optional[float] = None
    market_cap_max: Optional[float] = None
    volume_min: Optional[int] = None
    volume_ratio_min: Optional[float] = None
    volume_ratio_max: Optional[float] = None
    change_pct_min: Optional[float] = None
    change_pct_max: Optional[float] = None
    above_ma: Optional[int] = None
    golden_cross: Optional[bool] = None
    ma_aligned: Optional[bool] = None
    surge_only: bool = False
    pre_surge_only: bool = False
    accumulation_only: bool = False
    stock_type: Optional[str] = None
    etf_category: Optional[str] = None
    theme: Optional[str] = None
    theme_group: Optional[str] = None
    trading_value_min: Optional[float] = None
    rsi_min: Optional[float] = None
    rsi_max: Optional[float] = None
    vs_high_52w_min: Optional[float] = None
    vs_high_52w_max: Optional[float] = None
    breakout_score_min: Optional[int] = None
    buy_score_min: Optional[float] = None
    foreign_net_min: Optional[int] = None
    sector: Optional[str] = None
    tickers: Optional[list] = None
    # v6 Phase 3: 퀄리티 필터
    profit_margin_min: Optional[float] = None
    debt_equity_max: Optional[float] = None
    revenue_growth_min: Optional[float] = None
    # v6 Phase 2: 수급 필터
    dual_buy_only: bool = False
    supply_grade: Optional[str] = None
    sort_by: str = "change_pct"
    sort_asc: bool = False
    sort_by2: Optional[str] = None
    sort_asc2: bool = False
    limit: int = 100
    offset: int = 0


# ──────────────────────────────────────────────
# 15개 카테고리 — "지금 매수할 종목" 중심
# ──────────────────────────────────────────────

CATEGORIES = {
    # ══════════════════════════════════════════
    # 전략별 — 매수 타이밍 추천
    # ══════════════════════════════════════════
    "surge": {
        "name": "급등 예보", "group": "strategy",
        "desc": "곧 급등할 가능성이 높은 종목을 포착합니다",
        "icon": "rocket",
        "filter": ScreenerFilter(
            market_cap_min=500, trading_value_min=MIN_TRADING_VALUE,
            stock_type="stock", pre_surge_only=True,
            sort_by="pre_surge_score", sort_asc=False,
        ),
        "columns": ["pre_surge_score", "volume_ratio", "volume_trend", "ma_squeeze", "risk_grade", "change_pct", "market_cap"],
        "requires_phase": 3,
    },
    "growth": {
        "name": "성장주 매수", "group": "strategy",
        "desc": "수익성이 높으면서 적정 가격인 장기 성장 후보",
        "icon": "trending-up",
        "filter": ScreenerFilter(
            roe_min=15, per_min=0.1, per_max=30, market_cap_min=1000,
            trading_value_min=MIN_TRADING_VALUE, stock_type="stock",
            sort_by="roe", sort_asc=False,
        ),
        "columns": ["roe", "per", "pbr", "change_pct", "market_cap", "volume_ratio"],
    },
    "value": {
        "name": "저평가 매수", "group": "strategy",
        "desc": "실적 대비 저평가된 종목, 가격 회복 시 수익 기대",
        "icon": "gem",
        "filter": ScreenerFilter(
            per_min=0.1, per_max=10, pbr_min=0.1, pbr_max=1.0,
            market_cap_min=1000, trading_value_min=MIN_TRADING_VALUE,
            stock_type="stock", sort_by="per", sort_asc=True,
        ),
        "columns": ["per", "pbr", "roe", "div_yield", "market_cap", "change_pct"],
    },
    "dividend": {
        "name": "배당주 매수", "group": "strategy",
        "desc": "높은 배당을 꾸준히 지급하는 안정 수익형 종목",
        "icon": "coins",
        "filter": ScreenerFilter(
            div_yield_min=3.0, market_cap_min=1000,
            trading_value_min=MIN_TRADING_VALUE,
            stock_type="stock", sort_by="div_yield", sort_asc=False,
        ),
        "columns": ["div_yield", "div_years", "div_growth", "per", "market_cap", "change_pct"],
    },
    "momentum": {
        "name": "추세 진입", "group": "strategy",
        "desc": "골든크로스 + 거래량 동반, 상승 추세 초입 종목",
        "icon": "zap",
        "filter": ScreenerFilter(
            golden_cross=True, volume_ratio_min=1.2, market_cap_min=500,
            trading_value_min=MIN_TRADING_VALUE,
            stock_type="stock", sort_by="breakout_score", sort_asc=False,
        ),
        "columns": ["breakout_score", "golden_cross", "golden_cross_long", "ma_aligned", "volume_ratio", "change_pct", "market_cap"],
        "requires_phase": 3,
    },
    "turnaround": {
        "name": "반등 매수", "group": "strategy",
        "desc": "바닥권에서 거래가 살아나며 반등이 시작되는 종목",
        "icon": "refresh-cw",
        "filter": ScreenerFilter(
            rsi_min=1, rsi_max=35, volume_ratio_min=1.5, pbr_max=1.5,
            market_cap_min=500, trading_value_min=MIN_TRADING_VALUE,
            stock_type="stock", sort_by="rsi", sort_asc=True,
        ),
        "columns": ["rsi", "volume_ratio", "vs_high_52w", "pbr", "change_pct", "market_cap"],
        "requires_phase": 3,
    },

    "quality": {
        "name": "퀄리티주", "group": "strategy",
        "desc": "높은 수익성 + 낮은 부채 + 안정 성장 (해외 종목 전용 — yfinance 펀더멘탈 기반)",
        "icon": "award",
        "filter": ScreenerFilter(
            profit_margin_min=10, debt_equity_max=100,
            revenue_growth_min=5, market_cap_min=1000,
            stock_type="stock", sort_by="profit_margin", sort_asc=False,
        ),
        "columns": ["profit_margin", "operating_margin", "debt_equity",
                     "revenue_growth", "fcf_yield", "ev_ebitda", "per"],
    },
    "recommend": {
        "name": "종합 추천", "group": "strategy",
        "desc": "기술적·모멘텀·수급·가치 종합 30점 이상 종목 (참고용, 투자 판단은 본인 책임)",
        "icon": "brain",
        "filter": ScreenerFilter(
            market_cap_min=1000, trading_value_min=MIN_TRADING_VALUE,
            stock_type="stock", buy_score_min=30,
            sort_by="buy_score", sort_asc=False,
        ),
        "columns": ["buy_score", "buy_grade", "risk_grade", "pre_surge_score", "rsi", "volume_ratio", "per"],
        "requires_phase": 3,
    },

    # ══════════════════════════════════════════
    # 시장별 — 시장 세그먼트
    # ══════════════════════════════════════════
    "etf": {
        "name": "ETF", "group": "market",
        "desc": "상장지수펀드",
        "icon": "layers",
        "filter": ScreenerFilter(
            stock_type="etf", sort_by="volume", sort_asc=False,
        ),
        "columns": ["etf_category", "change_pct", "volume", "earning_rate", "nav", "market_cap"],
    },
    "bluechip": {
        "name": "대형주", "group": "market",
        "desc": "국내 대표 우량 대형주",
        "icon": "shield",
        "filter": ScreenerFilter(
            market_cap_min=50000, stock_type="stock",
            sort_by="market_cap", sort_asc=False,
        ),
        "columns": ["market_cap", "per", "roe", "div_yield", "change_pct", "volume_ratio"],
    },
    "smallcap": {
        "name": "중소형주", "group": "market",
        "desc": "중소형 종목 중 성장 잠재력이 큰 종목",
        "icon": "target",
        "filter": ScreenerFilter(
            market_cap_min=500, market_cap_max=5000, stock_type="stock",
            sort_by="volume_ratio", sort_asc=False,
        ),
        "columns": ["volume_ratio", "change_pct", "market_cap", "per", "roe", "volume"],
    },
    "theme": {
        "name": "테마주", "group": "market",
        "desc": "분야별 테마에 속한 종목 탐색",
        "icon": "hash",
        "filter": ScreenerFilter(
            stock_type="stock", market_cap_min=300,
            sort_by="volume_ratio", sort_asc=False,
        ),
        "columns": ["themes", "volume_ratio", "change_pct", "volume", "market_cap", "per"],
    },
    "watchlist": {
        "name": "관심종목", "group": "market",
        "desc": "내가 저장한 종목",
        "icon": "star",
        "filter": ScreenerFilter(
            sort_by="change_pct", sort_asc=False,
        ),
        "columns": ["change_pct", "volume_ratio", "market_cap", "per", "roe", "volume"],
    },

    # ══════════════════════════════════════════
    # 시그널 — 실시간 매매 시그널
    # ══════════════════════════════════════════
    "accumulation": {
        "name": "매집 의심", "group": "signal",
        "desc": "조용히 물량을 모으고 있는 것으로 의심되는 종목",
        "icon": "bar-chart-2",
        "filter": ScreenerFilter(
            market_cap_min=500, trading_value_min=MIN_TRADING_VALUE,
            stock_type="stock", accumulation_only=True,
            sort_by="volume_ratio", sort_asc=False,
        ),
        "columns": ["volume_ratio", "volume_trend", "change_pct", "ma_squeeze", "market_cap", "per"],
        "requires_phase": 3,
    },
    "foreign_inst": {
        "name": "스마트머니", "group": "signal",
        "desc": "외국인·기관이 당일 순매수 중인 종목 (KRX 공식 데이터)",
        "icon": "globe",
        "filter": ScreenerFilter(
            market_cap_min=1000, trading_value_min=MIN_TRADING_VALUE,
            stock_type="stock", foreign_net_min=1,
            sort_by="foreign_net", sort_asc=False,
        ),
        "columns": ["foreign_net", "inst_net", "change_pct", "volume_ratio", "market_cap", "per"],
    },
    "breakout": {
        "name": "돌파 임박", "group": "signal",
        "desc": "신고가를 돌파할 가능성이 높은 종목",
        "icon": "arrow-up-down",
        "filter": ScreenerFilter(
            vs_high_52w_min=-5.0, breakout_score_min=2, market_cap_min=500,
            trading_value_min=MIN_TRADING_VALUE,
            stock_type="stock", sort_by="breakout_score", sort_asc=False,
        ),
        "columns": ["breakout_score", "vs_high_52w", "volume_ratio", "volume_trend", "risk_grade", "change_pct", "market_cap"],
        "requires_phase": 3,
    },
    "oversold": {
        "name": "과매도 반등", "group": "signal",
        "desc": "RSI 30 이하 과매도 종목, 반등 매수 기회",
        "icon": "activity",
        "filter": ScreenerFilter(
            rsi_min=1, rsi_max=30, market_cap_min=1000,
            trading_value_min=MIN_TRADING_VALUE,
            volume_ratio_min=1.0,
            stock_type="stock", sort_by="rsi", sort_asc=True,
        ),
        "columns": ["rsi", "vs_high_52w", "volume_ratio", "change_pct", "pbr", "market_cap"],
        "requires_phase": 3,
    },
    # Axis 전용: 사용자 지정 필터 (커스텀 스크리너) — 빈 preset
    # /api/scan?category=custom&per_min=...&pbr_max=... 형태로 사용자 필터만 적용됨.
    # CATEGORY_PHASE에 등록 안 함 = phase 1 (모든 phase에서 사용 가능)
    "custom": {
        "name": "커스텀 스크리너", "group": "strategy",
        "desc": "사용자가 직접 조건을 조합하는 스크리너 (Pro)",
        "icon": "sliders",
        "filter": ScreenerFilter(),  # 빈 preset — 모든 필터는 query param에서
        "columns": ["per", "pbr", "roe", "rsi", "change_pct", "volume_ratio", "market_cap"],
    },
}

# 그룹 정보
GROUPS = {
    "strategy": {"name": "매수 전략", "icon": "briefcase"},
    "market": {"name": "시장별", "icon": "building"},
    "signal": {"name": "매매 시그널", "icon": "radio"},
}

# 카테고리별 최소 필요 Phase (1=기본, 2=펀더멘탈/테마, 3=히스토리/기술지표)
# Phase 3 필요 카테고리: 기술지표(RSI/MA/52주) 기반 시그널
CATEGORY_PHASE = {
    "surge": 3, "growth": 2, "value": 2, "dividend": 2,
    "quality": 2, "momentum": 3, "turnaround": 3, "recommend": 3,
    "etf": 1, "bluechip": 1, "smallcap": 1, "theme": 2, "watchlist": 1,
    "accumulation": 3, "foreign_inst": 1, "breakout": 3, "oversold": 3,
}


def apply_filters(df: pd.DataFrame, f: ScreenerFilter) -> tuple[pd.DataFrame, int]:
    """필터 조건에 따라 종목 필터링."""
    result = df.copy()
    initial = len(result)

    # 종목 타입
    if f.stock_type:
        result = result[result["stock_type"] == f.stock_type]

    # 특정 종목 필터 (관심종목)
    if f.tickers:
        result = result[result["ticker"].isin(f.tickers)]

    # ETF 카테고리
    if f.etf_category and "etf_category" in result.columns:
        result = result[result["etf_category"] == f.etf_category]

    # 시장 (KR=국내, US=해외 묶음 지원)
    if f.market == "KR":
        result = result[result["market"].isin(["KOSPI", "KOSDAQ"])]
    elif f.market == "US":
        result = result[result["market"].isin(["NASDAQ", "S&P500"])]
    elif f.market not in ("ALL", ""):
        result = result[result["market"] == f.market]

    # 섹터 (US 종목)
    if f.sector and "sector" in result.columns:
        result = result[result["sector"] == f.sector]

    # 테마 (그룹 또는 개별)
    if f.theme_group and "themes" in result.columns:
        from screener.api.routes import _data_store
        tg = _data_store.get("theme_groups", {})
        group_themes = tg.get(f.theme_group, [])
        if group_themes:
            theme_names = [t["name"] if isinstance(t, dict) else t for t in group_themes]
            pattern = "|".join([t.replace("(", "\\(").replace(")", "\\)") for t in theme_names])
            result = result[result["themes"].str.contains(pattern, na=False)]
    elif f.theme and "themes" in result.columns:
        result = result[result["themes"].str.contains(f.theme, na=False)]

    # PER — 카테고리가 PER 필터를 요구하면 데이터 없는 종목 제외
    if "per" in result.columns:
        if f.per_min is not None:
            result = result[result["per"] >= f.per_min]
        if f.per_max is not None:
            result = result[result["per"] <= f.per_max]

    # PBR
    if "pbr" in result.columns:
        if f.pbr_min is not None:
            result = result[result["pbr"] >= f.pbr_min]
        if f.pbr_max is not None:
            result = result[result["pbr"] <= f.pbr_max]

    # 배당수익률
    if "div_yield" in result.columns:
        if f.div_yield_min is not None:
            result = result[result["div_yield"] >= f.div_yield_min]

    # ROE
    if "roe" in result.columns:
        if f.roe_min is not None:
            result = result[result["roe"] >= f.roe_min]
        if f.roe_max is not None:
            result = result[result["roe"] <= f.roe_max]

    # 시가총액
    if f.market_cap_min is not None:
        result = result[result["market_cap"] >= f.market_cap_min]
    if f.market_cap_max is not None:
        result = result[result["market_cap"] <= f.market_cap_max]

    # 거래량
    if f.volume_min is not None:
        result = result[result["volume"] >= f.volume_min]
    if f.volume_ratio_min is not None and "volume_ratio" in result.columns:
        result = result[result["volume_ratio"] >= f.volume_ratio_min]
    if f.volume_ratio_max is not None and "volume_ratio" in result.columns:
        result = result[result["volume_ratio"] <= f.volume_ratio_max]

    # 거래대금 (US 주식은 단위가 다르므로 필터 제외)
    if f.trading_value_min is not None and "trading_value" in result.columns:
        us_markets = {"NASDAQ", "S&P500"}
        is_us = result["market"].isin(us_markets)
        result = result[is_us | (result["trading_value"] >= f.trading_value_min)]

    # 등락률
    if f.change_pct_min is not None:
        result = result[result["change_pct"] >= f.change_pct_min]
    if f.change_pct_max is not None:
        result = result[result["change_pct"] <= f.change_pct_max]

    # 이동평균선 위
    if f.above_ma is not None:
        ma_col = f"ma{f.above_ma}"
        if ma_col in result.columns:
            result = result[result["close"] > result[ma_col]]

    # 골든크로스 — 데이터 없으면 빈 결과 (bypass 금지)
    if f.golden_cross:
        if "golden_cross" not in result.columns or not (result["golden_cross"] > 0).any():
            logger.debug("골든크로스 데이터 없음 → 빈 결과")
            result = result.iloc[0:0]
        else:
            result = result[result["golden_cross"] == 1]

    # 정배열
    if f.ma_aligned:
        if "ma_aligned" not in result.columns or not (result["ma_aligned"] > 0).any():
            result = result.iloc[0:0]
        else:
            result = result[result["ma_aligned"] == 1]

    # 급등주 (기발생)
    if f.surge_only:
        if "is_surging" not in result.columns or not (result["is_surging"] > 0).any():
            result = result.iloc[0:0]
        else:
            result = result[result["is_surging"] == 1]

    # 급등 예보 (예측) — 데이터 없으면 빈 결과
    if f.pre_surge_only:
        if "is_pre_surge" not in result.columns or not (result["is_pre_surge"] > 0).any():
            logger.debug("급등예보 데이터 없음 → 빈 결과")
            result = result.iloc[0:0]
        else:
            result = result[result["is_pre_surge"] == 1]

    # 매집 의심 — 데이터 없으면 빈 결과
    if f.accumulation_only:
        if "accumulation" not in result.columns or not (result["accumulation"] > 0).any():
            logger.debug("매집 데이터 없음 → 빈 결과")
            result = result.iloc[0:0]
        else:
            result = result[result["accumulation"] == 1]

    # RSI — 데이터 없으면 RSI 필터 요구 시 빈 결과
    if f.rsi_min is not None or f.rsi_max is not None:
        has_rsi = "rsi" in result.columns and (result["rsi"] > 0).any()
        if not has_rsi:
            logger.debug("RSI 데이터 없음 → 빈 결과")
            result = result.iloc[0:0]
        else:
            if f.rsi_min is not None:
                result = result[result["rsi"] >= f.rsi_min]
            if f.rsi_max is not None:
                result = result[result["rsi"] <= f.rsi_max]

    # 52주 고가 대비 — 데이터 없으면 빈 결과
    if f.vs_high_52w_min is not None or f.vs_high_52w_max is not None:
        has_52w = "vs_high_52w" in result.columns and (result["vs_high_52w"] != 0).any()
        if not has_52w:
            logger.debug("52주 데이터 없음 → 빈 결과")
            result = result.iloc[0:0]
        else:
            if f.vs_high_52w_min is not None:
                result = result[result["vs_high_52w"] >= f.vs_high_52w_min]
            if f.vs_high_52w_max is not None:
                result = result[result["vs_high_52w"] <= f.vs_high_52w_max]

    # 돌파 점수
    if f.breakout_score_min is not None and "breakout_score" in result.columns:
        result = result[result["breakout_score"] >= f.breakout_score_min]

    # 매수 추천 점수 — 데이터 없으면 빈 결과
    if f.buy_score_min is not None:
        if "buy_score" not in result.columns or not (result["buy_score"] > 0).any():
            logger.debug("buy_score 데이터 없음 → 빈 결과")
            result = result.iloc[0:0]
        else:
            result = result[result["buy_score"] >= f.buy_score_min]

    # v6 Phase 3: 퀄리티 필터
    if f.profit_margin_min is not None and "profit_margin" in result.columns:
        result = result[result["profit_margin"] >= f.profit_margin_min]
    if f.debt_equity_max is not None and "debt_equity" in result.columns:
        result = result[(result["debt_equity"] > 0) & (result["debt_equity"] <= f.debt_equity_max)]
    if f.revenue_growth_min is not None and "revenue_growth" in result.columns:
        result = result[result["revenue_growth"] >= f.revenue_growth_min]

    # v6 Phase 2: 수급 필터
    if f.dual_buy_only and "dual_buy" in result.columns:
        result = result[result["dual_buy"] == True]
    if f.supply_grade and "supply_grade" in result.columns:
        result = result[result["supply_grade"] == f.supply_grade]

    # 외국인 순매수 최소 — 데이터 없으면 빈 결과
    if f.foreign_net_min is not None:
        if "foreign_net" not in result.columns or not (result["foreign_net"] != 0).any():
            logger.debug("외국인 순매수 데이터 없음 → 빈 결과")
            result = result.iloc[0:0]
        else:
            result = result[result["foreign_net"] >= f.foreign_net_min]

    # 정렬 (1차 + 2차)
    sort_cols = []
    sort_ascs = []
    if f.sort_by in result.columns:
        sort_cols.append(f.sort_by)
        sort_ascs.append(f.sort_asc)
    if f.sort_by2 and f.sort_by2 in result.columns and f.sort_by2 != f.sort_by:
        sort_cols.append(f.sort_by2)
        sort_ascs.append(f.sort_asc2)
    if sort_cols:
        result = result.sort_values(sort_cols, ascending=sort_ascs, na_position="last")

    total = len(result)
    result = result.iloc[f.offset:f.offset + f.limit]

    logger.debug(f"필터: {initial} → {total}종목 (표시: {len(result)})")
    return result, total
