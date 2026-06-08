"""데이터 수집기: FinanceDataReader + 네이버금융.

데이터 소스:
- FinanceDataReader: 주식 OHLCV, 시가총액, ETF
- 네이버금융: PER/PBR/배당률, 테마 분류, 외국인/기관 수급
"""

import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

import pandas as pd
import requests
from bs4 import BeautifulSoup
import FinanceDataReader as fdr
from loguru import logger

from screener.config import CACHE_DIR, HISTORY_DAYS

_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def _fdr_stock_listing(market: str, retries: int = 3, backoff: float = 3.0) -> pd.DataFrame:
    """fdr.StockListing 재시도 래퍼.

    KRX marcap CSV 다운로드가 일시적 네트워크 오류로 자주 실패한다.
    재시도 없이 예외가 전파되면 collect_all 전체가 첫 단계에서 죽으므로,
    지수 백오프로 N회 재시도한다.
    """
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            df = fdr.StockListing(market)
            if df is not None and len(df) > 0:
                return df
            last_err = ValueError(f"빈 결과 (market={market})")
        except Exception as e:
            last_err = e
            logger.warning(
                f"StockListing 실패 [{market}] ({attempt}/{retries}): "
                f"{type(e).__name__}: {str(e)[:120]}"
            )
        if attempt < retries:
            time.sleep(backoff * attempt)
    raise RuntimeError(f"StockListing 재시도 소진 [{market}]: {last_err}")


# ──────────────────────────────────────────────
# 주식 데이터
# ──────────────────────────────────────────────

def _pykrx_daily_snapshot() -> pd.DataFrame:
    """fdr.StockListing 실패 시 pykrx 폴백 — KOSPI/KOSDAQ 전종목 스냅샷.

    FDR의 KRX marcap 엔드포인트가 죽어도(과거 404 사례) pykrx로 같은 스키마를 구성.
    단, KRX 코어 자체가 점검 중이면 pykrx도 실패 — 그 경우는 불가피.
    반환 스키마는 fetch_daily_snapshot과 동일.
    """
    from pykrx import stock as krx

    # 최근 영업일 탐색 (오늘부터 최대 7일 역행)
    base = None
    for back in range(0, 8):
        d = (datetime.now() - timedelta(days=back)).strftime("%Y%m%d")
        try:
            test = krx.get_market_ohlcv_by_ticker(d, market="KOSPI")
            if test is not None and not test.empty and float(test["종가"].sum()) > 0:
                base = d
                break
        except Exception:
            continue
    if base is None:
        logger.warning("pykrx 폴백: 최근 영업일 데이터 없음")
        return pd.DataFrame()

    frames = []
    for market in ["KOSPI", "KOSDAQ"]:
        try:
            ohlcv = krx.get_market_ohlcv_by_ticker(base, market=market)
            cap = krx.get_market_cap_by_ticker(base, market=market)
        except Exception as e:
            logger.warning(f"pykrx {market} 조회 실패: {e}")
            continue
        if ohlcv is None or ohlcv.empty:
            continue
        merged = ohlcv.join(cap[["시가총액", "상장주식수"]], how="left")
        merged = merged.reset_index()
        tcol = merged.columns[0]  # '티커'
        tickers = merged[tcol].astype(str).tolist()
        names = []
        for t in tickers:
            try:
                names.append(krx.get_market_ticker_name(t))
            except Exception:
                names.append("")
        sub = pd.DataFrame({
            "ticker": tickers,
            "name": names,
            "market_type": market,
            "close": pd.to_numeric(merged.get("종가", 0), errors="coerce").fillna(0).astype(int),
            "open": pd.to_numeric(merged.get("시가", 0), errors="coerce").fillna(0).astype(int),
            "high": pd.to_numeric(merged.get("고가", 0), errors="coerce").fillna(0).astype(int),
            "low": pd.to_numeric(merged.get("저가", 0), errors="coerce").fillna(0).astype(int),
            "volume": pd.to_numeric(merged.get("거래량", 0), errors="coerce").fillna(0).astype(int),
            "trading_value": pd.to_numeric(merged.get("거래대금", 0), errors="coerce").fillna(0),
            "change_pct": pd.to_numeric(merged.get("등락률", 0), errors="coerce").fillna(0),
            "market_cap_raw": pd.to_numeric(merged.get("시가총액", 0), errors="coerce").fillna(0),
            "shares": pd.to_numeric(merged.get("상장주식수", 0), errors="coerce").fillna(0).astype(int),
        })
        frames.append(sub)

    if not frames:
        return pd.DataFrame()

    raw = pd.concat(frames, ignore_index=True)
    result = pd.DataFrame({
        "ticker": raw["ticker"], "name": raw["name"], "market": raw["market_type"],
        "close": raw["close"], "open": raw["open"], "high": raw["high"], "low": raw["low"],
        "volume": raw["volume"], "trading_value": raw["trading_value"],
        "change_pct": raw["change_pct"], "market_cap_raw": raw["market_cap_raw"],
        "shares": raw["shares"],
    })
    result["market_cap"] = (result["market_cap_raw"] / 1_0000_0000).round(0)
    result = result[result["close"] > 0].copy()
    for col in ["per", "pbr", "eps", "div_yield", "roe"]:
        result[col] = 0.0
    result["sector"] = ""
    result["industry"] = ""
    result["stock_type"] = "stock"
    logger.info(f"pykrx 폴백 스냅샷 완료: {len(result)}종목 (기준일 {base})")
    return result


def fetch_daily_snapshot() -> pd.DataFrame:
    """KOSPI + KOSDAQ 전종목 당일 스냅샷.

    1차: FinanceDataReader StockListing (재시도 포함).
    2차(폴백): pykrx — FDR 엔드포인트 회귀 시에도 수집 지속.
    """
    logger.info("전종목 일일 스냅샷 수집 시작...")

    all_data = []
    try:
        for market in ["KOSPI", "KOSDAQ"]:
            df = _fdr_stock_listing(market)
            df["market_type"] = market
            all_data.append(df)
    except Exception as e:
        logger.warning(f"FDR StockListing 실패 → pykrx 폴백 시도: {e}")
        fallback = _pykrx_daily_snapshot()
        if not fallback.empty:
            return fallback
        raise

    raw = pd.concat(all_data, ignore_index=True)

    result = pd.DataFrame({
        "ticker": raw["Code"].astype(str),
        "name": raw["Name"].astype(str),
        "market": raw["market_type"],
        "close": pd.to_numeric(raw.get("Close", 0), errors="coerce").fillna(0).astype(int),
        "open": pd.to_numeric(raw.get("Open", 0), errors="coerce").fillna(0).astype(int),
        "high": pd.to_numeric(raw.get("High", 0), errors="coerce").fillna(0).astype(int),
        "low": pd.to_numeric(raw.get("Low", 0), errors="coerce").fillna(0).astype(int),
        "volume": pd.to_numeric(raw.get("Volume", 0), errors="coerce").fillna(0).astype(int),
        "trading_value": pd.to_numeric(raw.get("Amount", 0), errors="coerce").fillna(0),
        "change_pct": pd.to_numeric(raw.get("ChagesRatio", 0), errors="coerce").fillna(0),
        "market_cap_raw": pd.to_numeric(raw.get("Marcap", 0), errors="coerce").fillna(0),
        "shares": pd.to_numeric(raw.get("Stocks", 0), errors="coerce").fillna(0).astype(int),
    })

    result["market_cap"] = (result["market_cap_raw"] / 1_0000_0000).round(0)
    result = result[result["close"] > 0].copy()

    # 초기값 — 펀더멘탈은 별도 수집이므로 DataFrame에만 추가 (Firestore에는 저장 안 함)
    for col in ["per", "pbr", "eps", "div_yield", "roe"]:
        result[col] = 0.0
    # 섹터/업종 초기값 (네이버 펀더멘탈 수집 시 채워짐)
    result["sector"] = ""
    result["industry"] = ""

    # 종목 타입 분류
    result["stock_type"] = "stock"

    logger.info(f"스냅샷 수집 완료: {len(result)}종목")
    return result


# ──────────────────────────────────────────────
# 해외 주식 (NASDAQ)
# ──────────────────────────────────────────────

def fetch_us_snapshot(top_n: int = 200) -> pd.DataFrame:
    """NASDAQ/S&P500 주요 종목 스냅샷 (yfinance 배치 수집).

    yfinance.download()로 배치 수집하여 개별 API 호출을 최소화.
    시가총액, PER 등 실제 데이터를 가져옴.
    """
    import yfinance as yf

    logger.info("미국 주식 스냅샷 수집 시작...")

    # S&P500 + NASDAQ 종목 목록 (FDR에서)
    symbols = {}
    for market in ["S&P500", "NASDAQ"]:
        try:
            listing = fdr.StockListing(market)
            if listing is not None and len(listing) > 0:
                for _, row in listing.iterrows():
                    sym = str(row.get("Symbol", ""))
                    name = str(row.get("Name", ""))
                    if sym and sym not in symbols:
                        symbols[sym] = {"name": name, "market": market}
        except Exception as e:
            logger.warning(f"{market} 목록 수집 실패: {e}")

    if not symbols:
        return pd.DataFrame()

    # S&P500 전종목 + NASDAQ top_n
    sp500 = {s: d for s, d in symbols.items() if d["market"] == "S&P500"}
    nasdaq_only = {s: d for s, d in symbols.items() if d["market"] == "NASDAQ" and s not in sp500}
    targets = list(sp500.keys()) + list(nasdaq_only.keys())[:top_n]
    logger.info(f"미국 종목 시세 수집: {len(targets)}종목 (yfinance 배치)")

    # ── yfinance 배치 다운로드 (1회 호출로 전체 수집) ──
    all_rows = []
    batch_size = 100  # yfinance 배치 크기

    for i in range(0, len(targets), batch_size):
        batch_symbols = targets[i:i + batch_size]
        try:
            data = yf.download(
                batch_symbols, period="5d", group_by="ticker",
                auto_adjust=True, threads=True, progress=False,
            )
            if data.empty:
                continue

            for sym in batch_symbols:
                try:
                    if len(batch_symbols) == 1:
                        sym_data = data
                    else:
                        sym_data = data[sym] if sym in data.columns.get_level_values(0) else None

                    if sym_data is None or sym_data.empty:
                        continue

                    sym_data = sym_data.dropna(subset=["Close"])
                    if len(sym_data) < 1:
                        continue

                    last = sym_data.iloc[-1]
                    prev = sym_data.iloc[-2] if len(sym_data) >= 2 else last
                    change_pct = ((last["Close"] / prev["Close"]) - 1) * 100 if prev["Close"] > 0 else 0

                    all_rows.append({
                        "ticker": sym,
                        "name": symbols.get(sym, {}).get("name", sym),
                        "market": symbols.get(sym, {}).get("market", "NASDAQ"),
                        "close": float(last["Close"]),
                        "open": float(last.get("Open", last["Close"])),
                        "high": float(last.get("High", last["Close"])),
                        "low": float(last.get("Low", last["Close"])),
                        "volume": int(last.get("Volume", 0)),
                        "change_pct": round(change_pct, 2),
                        "trading_value": float(last["Close"] * last.get("Volume", 0)),
                        "market_cap": 0.0,
                        "market_cap_raw": 0.0,
                    })
                except Exception:
                    continue

            logger.info(f"  US 배치: {min(i + batch_size, len(targets))}/{len(targets)} ({len(all_rows)}종목 수집)")

        except Exception as e:
            logger.warning(f"US 배치 수집 실패 ({i}~{i+batch_size}): {e}")
            continue

    if not all_rows:
        return pd.DataFrame()

    result = pd.DataFrame(all_rows)
    result = result[result["close"] > 0].copy()

    # ── 시가총액/펀더멘탈 수집 (yfinance ticker.info — 병렬) ──
    logger.info("미국 종목 시가총액/펀더멘탈 수집 중...")
    tickers_str = result["ticker"].tolist()

    def _fetch_single_info(sym):
        """yfinance ticker.info로 개별 종목 펀더멘탈 수집."""
        try:
            t = yf.Ticker(sym)
            info = t.info
            # dividendYield: yfinance returns as percentage already (0.41 = 0.41%)
            # returnOnEquity: yfinance returns as fraction (1.52 = 152%)
            raw_div = info.get("dividendYield", 0) or 0
            raw_roe = info.get("returnOnEquity", 0) or 0
            # v6 Phase 3: 추가 펀더멘탈 필드
            mcap = info.get("marketCap", 0) or 0
            fcf = info.get("freeCashflow", 0) or 0
            fcf_yield = round(fcf / mcap * 100, 2) if mcap > 0 else 0
            close_price = info.get("currentPrice", 0) or info.get("regularMarketPrice", 0) or 0
            target_mean = info.get("targetMeanPrice", 0) or 0
            target_upside = round((target_mean - close_price) / close_price * 100, 2) if close_price > 0 and target_mean > 0 else 0
            return sym, {
                "market_cap": mcap,
                "pe_ratio": round(info.get("trailingPE", 0) or 0, 2),
                "pbr": round(info.get("priceToBook", 0) or 0, 2),
                "div_yield": round(raw_div, 2),
                "roe": round(raw_roe * 100, 2),
                "sector": info.get("sector", "") or "",
                "industry": info.get("industry", "") or "",
                # v6 Phase 3 추가
                "forward_pe": round(info.get("forwardPE", 0) or 0, 2),
                "peg_ratio": round(info.get("pegRatio", 0) or 0, 2),
                "ev_ebitda": round(info.get("enterpriseToEbitda", 0) or 0, 2),
                "profit_margin": round((info.get("profitMargins", 0) or 0) * 100, 2),
                "operating_margin": round((info.get("operatingMargins", 0) or 0) * 100, 2),
                "fcf_yield": fcf_yield,
                "debt_equity": round(info.get("debtToEquity", 0) or 0, 2),
                "revenue_growth": round((info.get("revenueGrowth", 0) or 0) * 100, 2),
                "target_price": round(target_mean, 2),
                "target_upside": target_upside,
            }
        except Exception:
            return sym, {
                "market_cap": 0, "pe_ratio": 0, "pbr": 0, "div_yield": 0, "roe": 0,
                "sector": "", "industry": "",
                "forward_pe": 0, "peg_ratio": 0, "ev_ebitda": 0,
                "profit_margin": 0, "operating_margin": 0, "fcf_yield": 0,
                "debt_equity": 0, "revenue_growth": 0, "target_price": 0, "target_upside": 0,
            }

    info_results = {}
    done = 0
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(_fetch_single_info, sym): sym for sym in tickers_str}
        for future in as_completed(futures):
            done += 1
            sym, data = future.result()
            info_results[sym] = data
            if done % 100 == 0:
                logger.info(f"  US 펀더멘탈: {done}/{len(tickers_str)}")
    logger.info(f"  펀더멘탈 수집 완료: {sum(1 for v in info_results.values() if v['market_cap']>0)}종목")

    # 시가총액 적용 (억원 환산, 1USD ≈ 1400KRW)
    usd_to_krw = 1400
    result["market_cap"] = result["ticker"].map(
        lambda t: round(info_results.get(t, {}).get("market_cap", 0) * usd_to_krw / 1_0000_0000, 0)
    )
    result["per"] = result["ticker"].map(
        lambda t: round(info_results.get(t, {}).get("pe_ratio", 0), 2)
    )
    result["pbr"] = result["ticker"].map(
        lambda t: info_results.get(t, {}).get("pbr", 0)
    )
    result["div_yield"] = result["ticker"].map(
        lambda t: info_results.get(t, {}).get("div_yield", 0)
    )
    result["roe"] = result["ticker"].map(
        lambda t: info_results.get(t, {}).get("roe", 0)
    )
    result["sector"] = result["ticker"].map(
        lambda t: info_results.get(t, {}).get("sector", "")
    )
    result["industry"] = result["ticker"].map(
        lambda t: info_results.get(t, {}).get("industry", "")
    )

    # v6 Phase 3: 추가 펀더멘탈 필드 매핑
    for field in ["forward_pe", "peg_ratio", "ev_ebitda", "profit_margin",
                   "operating_margin", "fcf_yield", "debt_equity",
                   "revenue_growth", "target_price", "target_upside"]:
        result[field] = result["ticker"].map(
            lambda t, f=field: info_results.get(t, {}).get(f, 0)
        )

    for col in ["eps", "shares", "foreign_net", "inst_net", "div_years", "div_growth"]:
        if col not in result.columns:
            result[col] = 0.0

    result["stock_type"] = "stock"
    result = result.drop_duplicates(subset="ticker", keep="first")

    logger.info(f"미국 주식 수집 완료: {len(result)}종목 (시가총액 실제값 포함)")
    return result


# ──────────────────────────────────────────────
# ETF 데이터
# ──────────────────────────────────────────────

def fetch_etf_data() -> pd.DataFrame:
    """ETF 전종목 데이터."""
    logger.info("ETF 데이터 수집 시작...")

    try:
        raw = _fdr_stock_listing("ETF/KR")
    except Exception as e:
        logger.warning(f"ETF StockListing 실패 — 스킵: {e}")
        return pd.DataFrame()
    if raw is None or len(raw) == 0:
        logger.warning("ETF 데이터 없음")
        return pd.DataFrame()

    # ETF 카테고리 매핑
    cat_map = {
        "1": "국내시장", "2": "국내섹터", "3": "국내채권",
        "4": "해외주식", "5": "해외채권", "6": "원자재",
        "7": "레버리지", "8": "인버스", "9": "기타",
    }

    result = pd.DataFrame({
        "ticker": raw["Symbol"].astype(str),
        "name": raw["Name"].astype(str),
        "market": "ETF",
        "close": pd.to_numeric(raw.get("Price", 0), errors="coerce").fillna(0).astype(int),
        "change_pct": pd.to_numeric(raw.get("ChangeRate", 0), errors="coerce").fillna(0),
        "volume": pd.to_numeric(raw.get("Volume", 0), errors="coerce").fillna(0).astype(int),
        "trading_value": pd.to_numeric(raw.get("Amount", 0), errors="coerce").fillna(0) * 1_000_000,
        "nav": pd.to_numeric(raw.get("NAV", 0), errors="coerce").fillna(0),
        "earning_rate": pd.to_numeric(raw.get("EarningRate", 0), errors="coerce").fillna(0),
        "market_cap": (pd.to_numeric(raw.get("MarCap", 0), errors="coerce").fillna(0) / 1_0000_0000).round(0),
        "etf_category": raw.get("Category", "9").astype(str).map(cat_map).fillna("기타"),
    })

    result["stock_type"] = "etf"
    result["open"] = result["close"]
    result["high"] = result["close"]
    result["low"] = result["close"]

    for col in ["per", "pbr", "eps", "div_yield", "roe", "market_cap_raw", "shares"]:
        result[col] = 0.0

    result = result[result["close"] > 0].copy()
    logger.info(f"ETF 수집 완료: {len(result)}종목")
    return result


# ──────────────────────────────────────────────
# 펀더멘탈 (네이버금융 PER/PBR/배당률)
# ──────────────────────────────────────────────

def _fetch_single_fundamental(ticker: str) -> tuple:
    """단일 종목 PER/PBR/배당률 + 업종 수집 (병렬용)."""
    try:
        url = f"https://finance.naver.com/item/main.naver?code={ticker}"
        resp = requests.get(url, headers=_HEADERS, timeout=5)
        resp.encoding = "euc-kr"
        soup = BeautifulSoup(resp.text, "html.parser")

        data = {}
        for tag_id, key in [("_per", "per"), ("_pbr", "pbr"), ("_dvr", "div_yield")]:
            el = soup.select_one(f"#{tag_id}")
            if el:
                val = el.text.strip().replace(",", "")
                try:
                    data[key] = float(val)
                except ValueError:
                    data[key] = 0.0
            else:
                data[key] = 0.0

        # 업종 추출: "업종" 링크 텍스트 (div.sub_info > dl > dd 또는 a[href*="upjong"])
        sector = ""
        # 방법 1: 업종 링크 (가장 신뢰성 높음)
        upjong_link = soup.select_one('a[href*="/sise/sise_group_detail.naver"]')
        if upjong_link:
            sector = upjong_link.text.strip()
        else:
            # 방법 2: div.sub_info 내 업종 텍스트
            sub_info = soup.select_one("div.sub_info")
            if sub_info:
                for a_tag in sub_info.select("a"):
                    href = a_tag.get("href", "")
                    if "upjong" in href or "group" in href:
                        sector = a_tag.text.strip()
                        break
        if sector:
            data["sector"] = sector

        return ticker, data
    except Exception:
        return ticker, None


def fetch_naver_fundamentals(tickers: list[str], max_workers: int = 8) -> dict:
    """네이버금융에서 PER/PBR/배당률 병렬 수집.

    Returns:
        {ticker: {"per": float, "pbr": float, "div_yield": float}}
    """
    logger.info(f"네이버 펀더멘탈 수집: {len(tickers)}종목 (workers={max_workers})")
    result = {}
    done = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_fetch_single_fundamental, t): t
            for t in tickers
        }
        for future in as_completed(futures):
            done += 1
            ticker, data = future.result()
            if data:
                result[ticker] = data
            if done % 100 == 0:
                logger.info(f"  펀더멘탈: {done}/{len(tickers)}")

    logger.info(f"펀더멘탈 수집 완료: {len(result)}/{len(tickers)}")
    return result


def apply_fundamentals(snapshot: pd.DataFrame, fund_data: dict) -> pd.DataFrame:
    """펀더멘탈 데이터를 스냅샷에 적용."""
    for col in ["per", "pbr", "div_yield"]:
        mapping = {t: d.get(col, 0) for t, d in fund_data.items()}
        updates = snapshot["ticker"].map(mapping)
        valid = updates.notna() & (updates > 0)
        snapshot.loc[valid, col] = updates[valid]

    # ROE = PBR / PER * 100
    valid_per = snapshot["per"] > 0
    snapshot.loc[valid_per, "roe"] = (
        snapshot.loc[valid_per, "pbr"] / snapshot.loc[valid_per, "per"] * 100
    ).round(2)

    # 업종 (KR) — 네이버에서 가져온 sector 적용
    if "sector" not in snapshot.columns:
        snapshot["sector"] = ""
    if "industry" not in snapshot.columns:
        snapshot["industry"] = ""
    sector_map = {t: d.get("sector", "") for t, d in fund_data.items() if d.get("sector")}
    if sector_map:
        updates = snapshot["ticker"].map(sector_map)
        valid = updates.notna() & (updates != "")
        snapshot.loc[valid, "sector"] = updates[valid]
        # KR은 industry = sector와 동일하게 설정 (네이버는 업종만 제공)
        snapshot.loc[valid, "industry"] = updates[valid]

    return snapshot


# ──────────────────────────────────────────────
# 배당 지속성 데이터 (yfinance)
# ──────────────────────────────────────────────

def fetch_dividend_history(tickers: list[str], batch_size: int = 40) -> dict:
    """배당 이력 수집 (yfinance, 연도별 배당금).

    Returns:
        {ticker: {"div_years": int, "div_growth": float}}
    """
    import yfinance as yf

    logger.info(f"배당 지속성 수집: {len(tickers)}종목 (yfinance)")
    result = {}

    def _fetch_single_div(ticker):
        try:
            sym = f"{ticker}.KS"
            t = yf.Ticker(sym)
            divs = t.dividends
            if divs is None or divs.empty:
                return ticker, None

            # 연도별 합산
            annual = divs.groupby(divs.index.year).sum()
            # 최근 5년만
            recent = annual.tail(5)
            if len(recent) == 0:
                return ticker, None

            div_years = len(recent[recent > 0])
            if div_years == 0:
                return ticker, None

            # 배당 성장률: (최근연도 - 5년전) / 5년전 * 100
            vals = recent[recent > 0].values
            if len(vals) >= 2 and vals[0] > 0:
                div_growth = round((vals[-1] - vals[0]) / vals[0] * 100, 1)
            else:
                div_growth = 0.0

            return ticker, {"div_years": div_years, "div_growth": div_growth}
        except Exception:
            return ticker, None

    done = 0
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(_fetch_single_div, t): t for t in tickers}
        for future in as_completed(futures):
            done += 1
            ticker, data = future.result()
            if data:
                result[ticker] = data
            if done % batch_size == 0:
                logger.info(f"  배당 수집: {done}/{len(tickers)}")

    logger.info(f"배당 지속성 완료: {len(result)}/{len(tickers)}")
    return result


def apply_dividend_history(snapshot: pd.DataFrame, div_data: dict) -> pd.DataFrame:
    """배당 지속성 데이터를 스냅샷에 적용."""
    for col, default in [("div_years", 0), ("div_growth", 0.0)]:
        if col not in snapshot.columns:
            snapshot[col] = default
        mapping = {t: d.get(col, default) for t, d in div_data.items()}
        updates = snapshot["ticker"].map(mapping)
        valid = updates.notna()
        snapshot.loc[valid, col] = updates[valid]
    return snapshot


# ──────────────────────────────────────────────
# 테마 데이터 (네이버금융)
# ──────────────────────────────────────────────

def fetch_themes() -> tuple[dict, dict]:
    """네이버금융 테마 목록 및 종목-테마 매핑.

    Returns:
        themes: {theme_no: theme_name}
        stock_themes: {ticker: [theme1, theme2, ...]}
    """
    logger.info("테마 데이터 수집 시작...")
    themes = {}
    stock_themes = {}  # ticker → [theme_names]

    # 1) 전체 테마 목록 (페이지네이션)
    for page in range(1, 50):
        try:
            url = f"https://finance.naver.com/sise/theme.naver?&page={page}"
            resp = requests.get(url, headers=_HEADERS, timeout=5)
            resp.encoding = "euc-kr"
            soup = BeautifulSoup(resp.text, "html.parser")

            found = False
            for a in soup.select("td.col_type1 a"):
                name = a.text.strip()
                href = a.get("href", "")
                if name and "no=" in href:
                    no = href.split("no=")[-1].split("&")[0]
                    themes[no] = name
                    found = True

            if not found:
                break
            time.sleep(0.3)
        except Exception:
            break

    logger.info(f"테마 수집: {len(themes)}개")

    # 2) 각 테마별 종목 매핑
    for no, name in themes.items():
        try:
            url = f"https://finance.naver.com/sise/sise_group_detail.naver?type=theme&no={no}"
            resp = requests.get(url, headers=_HEADERS, timeout=5)
            resp.encoding = "euc-kr"
            soup = BeautifulSoup(resp.text, "html.parser")

            for a in soup.select("div.name_area a"):
                href = a.get("href", "")
                match = re.search(r"code=(\d{6})", href)
                if match:
                    ticker = match.group(1)
                    if ticker not in stock_themes:
                        stock_themes[ticker] = []
                    stock_themes[ticker].append(name)

            time.sleep(0.3)
        except Exception:
            continue

    logger.info(f"테마-종목 매핑: {len(stock_themes)}종목")
    return themes, stock_themes


# ──────────────────────────────────────────────
# 외국인/기관 순매수 (네이버 종목별 + pykrx 폴백)
# ──────────────────────────────────────────────

def _fetch_foreign_inst_naver(tickers: list[str]) -> dict:
    """네이버 종목별 외국인/기관 순매수 수집 (장 마감 후에도 동작).

    item/frgn.naver 페이지에서 당일 외국인 순매수(주) 수집.
    멀티스레드로 병렬 처리.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    result = {}

    def _fetch_one(ticker: str) -> tuple[str, int, int]:
        try:
            # 외국인 순매수
            url = f"https://finance.naver.com/item/frgn.naver?code={ticker}"
            resp = requests.get(url, headers=_HEADERS, timeout=5)
            resp.encoding = "euc-kr"
            soup = BeautifulSoup(resp.text, "html.parser")

            foreign_net = 0
            inst_net = 0
            rows = soup.select("table.type2 tr")
            for row in rows:
                tds = row.select("td")
                if len(tds) >= 7:
                    date_text = tds[0].text.strip()
                    if not date_text or "." not in date_text:
                        continue
                    # 최근 1행만 (당일 데이터)
                    raw = tds[5].text.strip().replace(",", "").replace("+", "")
                    try:
                        foreign_net = int(raw)
                    except ValueError:
                        pass
                    break

            return ticker, foreign_net, inst_net
        except Exception:
            return ticker, 0, 0

    # 8스레드 병렬 처리
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(_fetch_one, t): t for t in tickers}
        done = 0
        for fut in as_completed(futures):
            ticker, fn, inst = fut.result()
            if fn != 0 or inst != 0:
                result[ticker] = {"foreign_net": fn, "inst_net": inst}
            done += 1
            if done % 200 == 0:
                logger.info(f"  외국인/기관 수집 중... {done}/{len(tickers)}")

    return result


def _fetch_foreign_inst_pykrx() -> dict:
    """KRX에서 외국인/기관 순매수 수집 (pykrx, 원 단위)."""
    try:
        from pykrx import stock as pykrx_stock
    except ImportError:
        logger.warning("pykrx 미설치 — 스킵")
        return {}

    from datetime import timedelta

    result = {}
    today = datetime.now()
    date_str = today.strftime("%Y%m%d")

    for market in ["KOSPI", "KOSDAQ"]:
        try:
            df_foreign = pykrx_stock.get_market_net_purchases_of_equities(
                date_str, date_str, market, "외국인"
            )
            df_inst = pykrx_stock.get_market_net_purchases_of_equities(
                date_str, date_str, market, "기관합계"
            )

            if df_foreign.empty:
                prev = (today - timedelta(days=3)).strftime("%Y%m%d")
                df_foreign = pykrx_stock.get_market_net_purchases_of_equities(
                    prev, date_str, market, "외국인"
                )
                df_inst = pykrx_stock.get_market_net_purchases_of_equities(
                    prev, date_str, market, "기관합계"
                )

            if df_foreign.empty:
                continue

            col = "순매수거래대금"
            if col not in df_foreign.columns:
                col = df_foreign.columns[-1]

            for ticker in df_foreign.index:
                foreign_val = int(df_foreign.loc[ticker, col])
                inst_val = int(df_inst.loc[ticker, col]) if ticker in df_inst.index else 0
                result[ticker] = {
                    "foreign_net": foreign_val,
                    "inst_net": inst_val,
                }

            logger.info(f"  {market} (pykrx): {len(df_foreign)}종목")
            time.sleep(1)
        except Exception as e:
            logger.warning(f"  {market} pykrx 실패: {e}")
            continue

    return result


def _fetch_foreign_inst_kis(tickers: list[str]) -> dict:
    """KIS OpenAPI 투자자별 매매동향 수집 (외국인 + 기관 합계, 주 단위).

    pykrx 실패 시 폴백. 네이버보다 우선 — 공식 API, 회색지대 X.
    종목당 1회 호출, 초당 5회 한도 (kis_client sleep 자동 적용).
    KIS_APP_KEY/SECRET 미설정 시 빈 결과 → 다음 폴백(네이버)로.
    """
    if not os.environ.get("KIS_APP_KEY") and not os.environ.get("KIS_PAPER_APP_KEY"):
        logger.info("KIS 키 미설정 — KIS 폴백 스킵")
        return {}

    try:
        from utils.data_collectors.kis_client import KisClient
    except ImportError as e:
        logger.warning(f"KIS 클라이언트 import 실패: {e}")
        return {}

    try:
        kis = KisClient()
    except Exception as e:
        logger.warning(f"KIS 클라이언트 초기화 실패: {type(e).__name__}: {e}")
        return {}

    result = {}
    failed = 0
    for i, ticker in enumerate(tickers, 1):
        try:
            rows = kis.get_investor_trend(ticker)
            if not rows:
                failed += 1
                continue
            # 가장 최근(첫 행) 데이터 사용
            latest = rows[0]
            foreign_net = int(latest.get("frgn_ntby_qty", 0) or 0)
            inst_net = int(latest.get("orgn_ntby_qty", 0) or 0)
            if foreign_net != 0 or inst_net != 0:
                result[ticker] = {"foreign_net": foreign_net, "inst_net": inst_net}
        except Exception as e:
            failed += 1
            logger.debug(f"KIS investor {ticker} 실패: {type(e).__name__}: {e}")

        if i % 200 == 0:
            logger.info(
                f"  KIS 투자자 수집 중... {i}/{len(tickers)} "
                f"(ok={len(result)} fail={failed})"
            )

    logger.info(f"  KIS 투자자 수집: {len(result)} 종목 (fail={failed}) — {kis.stats.summary()}")
    return result


def fetch_foreign_inst(tickers: list[str] | None = None) -> dict:
    """외국인/기관 순매수 수집 — pykrx → KIS → 네이버 3단 폴백.

    Returns:
        {ticker: {"foreign_net": int, "inst_net": int}}
    """
    logger.info("외국인/기관 순매수 수집 시작...")

    # 1차: pykrx (KRX 공식, 원 단위 거래대금, 전종목 일괄)
    result = _fetch_foreign_inst_pykrx()
    if result:
        logger.info(f"외국인/기관 수집 완료 (pykrx): {len(result)}종목")
        return result

    # 2차: KIS OpenAPI (공식 API, 주 단위, 종목별)
    if tickers:
        logger.info("pykrx 데이터 없음 → KIS 폴백 시도")
        result = _fetch_foreign_inst_kis(tickers)
        if result:
            logger.info(f"외국인/기관 수집 완료 (KIS): {len(result)}종목")
            return result

    # 3차: 네이버 종목별 페이지 (최후 안전망, 회색지대)
    if not tickers:
        logger.warning("외국인/기관 폴백: ticker 목록 없음 → 빈 결과")
        return {}

    logger.info("KIS 데이터 없음 → 네이버 폴백 시작")
    result = _fetch_foreign_inst_naver(tickers)
    logger.info(f"외국인/기관 수집 완료 (네이버): {len(result)}종목")
    return result


def apply_foreign_inst(snapshot: pd.DataFrame, fi_data: dict) -> pd.DataFrame:
    """외국인/기관 순매수 데이터를 스냅샷에 적용."""
    for col in ["foreign_net", "inst_net"]:
        if col not in snapshot.columns:
            snapshot[col] = 0
        mapping = {t: d.get(col, 0) for t, d in fi_data.items()}
        updates = snapshot["ticker"].map(mapping)
        valid = updates.notna()
        snapshot.loc[valid, col] = updates[valid].astype(int)
    return snapshot


# ──────────────────────────────────────────────
# 히스토리 데이터 (이동평균/RSI 계산용)
# ──────────────────────────────────────────────

def _fetch_single_history(ticker: str, start_date: str, days: int):
    """단일 종목 히스토리 수집 (병렬용). 10초 타임아웃."""
    import signal
    import threading

    result_holder = [None]
    def _fetch():
        try:
            df = fdr.DataReader(ticker, start_date)
            if df is not None and len(df) > 0:
                df = df.reset_index()
                df["ticker"] = ticker
                df = df.rename(columns={
                    "Date": "date", "Open": "open", "High": "high",
                    "Low": "low", "Close": "close", "Volume": "volume",
                })
                df = df.tail(days)
                result_holder[0] = df[["date", "ticker", "open", "high", "low", "close", "volume"]]
        except Exception as e:
            logger.debug(f"히스토리 수집 실패 [{ticker}]: {e}")

    t = threading.Thread(target=_fetch, daemon=True)
    t.start()
    t.join(timeout=20)  # v6.1: 20초 타임아웃 (10초에서 확대, 커버리지 개선)
    if result_holder[0] is None:
        logger.debug(f"히스토리 타임아웃/실패 [{ticker}]")
    return result_holder[0]


def fetch_historical_ohlcv(
    tickers: list[str],
    days: int = HISTORY_DAYS,
    max_workers: int = 5,
) -> pd.DataFrame:
    """최근 N일 히스토리 수집 (병렬화)."""
    start_date = (datetime.now() - timedelta(days=days * 2)).strftime("%Y-%m-%d")
    logger.info(f"히스토리 수집: {len(tickers)}종목, {start_date}~오늘 (workers={max_workers})")

    all_data = []
    done = 0
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_fetch_single_history, t, start_date, days): t
            for t in tickers
        }
        for future in as_completed(futures):
            done += 1
            result = future.result()
            if result is not None:
                all_data.append(result)
            if done % 100 == 0:
                logger.info(f"  히스토리: {done}/{len(tickers)}")

    if not all_data:
        return pd.DataFrame()

    result = pd.concat(all_data, ignore_index=True)
    logger.info(f"히스토리 완료: {len(result)}행 ({len(tickers)}종목)")
    return result


# ──────────────────────────────────────────────
# US 히스토리 데이터 (yfinance 배치)
# ──────────────────────────────────────────────

def fetch_us_historical_ohlcv(
    tickers: list[str],
    days: int = HISTORY_DAYS,
) -> pd.DataFrame:
    """US 종목 히스토리 수집 (yfinance 배치 다운로드)."""
    import yfinance as yf

    logger.info(f"US 히스토리 수집: {len(tickers)}종목")
    all_history = []
    batch_size = 100
    period_days = days * 2

    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i + batch_size]
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

                    df = sym_data.tail(days).reset_index()
                    df = df.rename(columns={
                        "Date": "date", "Open": "open", "High": "high",
                        "Low": "low", "Close": "close", "Volume": "volume",
                    })
                    df["ticker"] = sym
                    all_history.append(df[["date", "ticker", "open", "high", "low", "close", "volume"]])
                except Exception:
                    continue

            logger.info(f"  US 히스토리: {min(i + batch_size, len(tickers))}/{len(tickers)}")
        except Exception as e:
            logger.warning(f"US 히스토리 배치 실패 ({i}~{i+batch_size}): {e}")

    if not all_history:
        return pd.DataFrame()

    result = pd.concat(all_history, ignore_index=True)
    logger.info(f"US 히스토리 완료: {len(result)}행 ({len(tickers)}종목)")
    return result


# ──────────────────────────────────────────────
# 캐시
# ──────────────────────────────────────────────

def save_cache(df: pd.DataFrame, name: str):
    """DataFrame 캐시 저장."""
    path = CACHE_DIR / f"{name}.parquet"
    df.to_parquet(path, index=False)


def load_cache(name: str) -> pd.DataFrame | None:
    """오늘 생성된 캐시만 로드."""
    path = CACHE_DIR / f"{name}.parquet"
    if path.exists():
        mtime = datetime.fromtimestamp(os.path.getmtime(path))
        if mtime.date() == datetime.now().date():
            return pd.read_parquet(path)
    return None


def save_dict_cache(data: dict, name: str):
    """딕셔너리 캐시 저장 (JSON)."""
    import json
    path = CACHE_DIR / f"{name}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def load_dict_cache(name: str) -> dict | None:
    """오늘 생성된 딕셔너리 캐시 로드."""
    import json
    path = CACHE_DIR / f"{name}.json"
    if path.exists():
        mtime = datetime.fromtimestamp(os.path.getmtime(path))
        if mtime.date() == datetime.now().date():
            with open(path, encoding="utf-8") as f:
                return json.load(f)
    return None
