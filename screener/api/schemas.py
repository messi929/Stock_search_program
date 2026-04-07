"""API 요청/응답 모델."""

from pydantic import BaseModel
from typing import Optional


class StockItem(BaseModel):
    """종목 정보."""
    ticker: str
    name: str = ""
    market: str = ""
    stock_type: str = "stock"
    close: int = 0
    change_pct: float = 0.0
    volume: int = 0
    volume_ratio: float = 0.0
    trading_value: float = 0.0
    market_cap: float = 0.0
    per: float = 0.0
    pbr: float = 0.0
    roe: float = 0.0
    div_yield: float = 0.0
    div_years: int = 0
    div_growth: float = 0.0
    ma5: float = 0.0
    ma20: float = 0.0
    ma60: float = 0.0
    golden_cross: int = 0
    ma_aligned: int = 0
    surge_score: int = 0
    is_surging: bool = False
    pre_surge_score: int = 0
    is_pre_surge: bool = False
    accumulation: int = 0
    breakout_score: int = 0
    volume_trend: int = 0
    ma_squeeze: float = 99.0
    consecutive_gains: int = 0
    rsi: float = 0.0
    vs_high_52w: float = 0.0
    vs_low_52w: float = 0.0
    foreign_net: int = 0
    inst_net: int = 0
    buy_score: float = 0.0
    buy_grade: str = ""
    golden_cross_long: int = 0
    volatility_20d: float = 0.0
    atr_14: float = 0.0
    risk_grade: str = ""
    sector: str = ""
    industry: str = ""
    themes: str = ""
    etf_category: str = ""
    nav: float = 0.0
    earning_rate: float = 0.0
    # v6 Phase 2: 수급 분석
    foreign_consecutive: int = 0
    supply_intensity: float = 0.0
    dual_buy: bool = False
    supply_grade: str = ""
    # v6 Phase 3: 펀더멘탈 확장
    forward_pe: float = 0.0
    peg_ratio: float = 0.0
    ev_ebitda: float = 0.0
    profit_margin: float = 0.0
    operating_margin: float = 0.0
    fcf_yield: float = 0.0
    debt_equity: float = 0.0
    revenue_growth: float = 0.0
    target_price: float = 0.0
    target_upside: float = 0.0
    # v6 Phase 4: 리스크
    position_size: float = 0.0


class ScanResponse(BaseModel):
    """탐색 결과."""
    total: int
    offset: int
    limit: int
    last_update: str
    category: str = ""
    message: str = ""
    stocks: list[StockItem]


class CategoryInfo(BaseModel):
    """카테고리 정보."""
    key: str
    name: str
    group: str
    desc: str
    icon: str
    columns: list[str]
    ready: bool = True


class StatusResponse(BaseModel):
    """서버 상태."""
    status: str
    total_stocks: int
    total_etf: int
    total_themes: int
    last_update: str
    loading_phase: int = 0
