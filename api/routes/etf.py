"""ETF 상세 — 정보 + 구성종목(holdings) + 섹터/국가/자산 비중.

KR 상장 ETF(국내 + 국내상장 국외) 대상. 데이터 소스는 네이버 모바일 etfAnalysis API
(`m.stock.naver.com/api/stock/{code}/etfAnalysis`) — 운용사·추적지수·NAV·보수·추적오차 +
상위 10 구성종목 + 자산/국가/섹터 비중을 단일 JSON으로 제공.

비용/안정성: 종목당 1일 1회만 외부 호출하도록 Firestore(`etf_details/{ticker}`)에 캐시.
LEGAL: ETF는 사실 데이터지만 응답 문자열은 filter_forbidden을 거친다(이중 안전).

⚠️ 상위 10 구성종목만 제공(네이버 소스 한계). 전체 구성종목(PDF)은 KRX 직접 연동이 필요 —
추후 확장. 해외(US 상장) ETF는 별도 파이프라인(미구현).
"""

from __future__ import annotations

import asyncio
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests
from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel, Field

# 라우팅: 순수 알파벳(SPY/QQQ)=해외(US, yfinance), 그 외(숫자 포함: 069500, 0193T0 등
# KRX 코드)=국내 상장(naver). KR ETF는 신상품에서 문자 포함 6자 코드(0193T0)도 쓰므로
# \d{6}로는 부족 — 숫자 포함 여부로 판별.
_US_TICKER = re.compile(r"^[A-Za-z]{1,6}$")

router = APIRouter(prefix="/api/etf", tags=["etf"])

_NAVER_ETF_URL = "https://m.stock.naver.com/api/stock/{code}/etfAnalysis"
_HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": "https://m.stock.naver.com/"}


# ──────────────────────────────────────────────
# 응답 스키마
# ──────────────────────────────────────────────

class Holding(BaseModel):
    seq: int
    ticker: str = ""          # 국내 구성종목은 6자리 코드, 국외는 "" (해외 종목)
    name: str
    shares: Optional[str] = None  # CU당 수량(문자열, 네이버 원형)
    weight: Optional[float] = None  # 비중(%) — 국외 ETF는 미제공("-")일 수 있음


class Breakdown(BaseModel):
    code: str  # IT / FINANCIALS / KR / US / EQUITY / CASH ...
    weight: float


class EtfDetail(BaseModel):
    ticker: str
    name: str = ""
    issuer: str = ""              # 운용사
    base_index: str = ""          # 추적지수
    nav: Optional[float] = None
    total_nav: str = ""           # 순자산총액(네이버 포맷 문자열, 예 "32조 5,500억")
    total_fee: Optional[float] = None       # 총보수(%)
    chase_error_rate: Optional[float] = None  # 추적오차(%)
    deviation_rate: Optional[float] = None    # 괴리율(%)
    listed_date: str = ""
    underlying_region: str = "unknown"  # domestic | foreign | mixed
    top_holdings: list[Holding] = Field(default_factory=list)
    sector_breakdown: list[Breakdown] = Field(default_factory=list)
    country_breakdown: list[Breakdown] = Field(default_factory=list)
    asset_breakdown: list[Breakdown] = Field(default_factory=list)
    as_of: str = ""
    source: str = "naver"
    disclaimer: str = ""


# ──────────────────────────────────────────────
# 정규화
# ──────────────────────────────────────────────

def _to_float(v) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(str(v).replace(",", "").replace("%", "").strip())
    except (TypeError, ValueError):
        return None


def _parse_weight(v) -> Optional[float]:
    """'33.19%' → 33.19, '-'/'' → None."""
    if v is None:
        return None
    s = str(v).strip()
    if not s or s == "-":
        return None
    return _to_float(s)


def _breakdowns(raw: Optional[list]) -> list[Breakdown]:
    out: list[Breakdown] = []
    for it in raw or []:
        code = str(it.get("detailTypeCode") or "").strip()
        w = _to_float(it.get("weight"))
        if code and w is not None:
            out.append(Breakdown(code=code, weight=w))
    return out


def _classify_region(countries: list[Breakdown]) -> str:
    """국가 비중으로 국내/국외/혼합 분류 — 국내상장 국외ETF 식별용."""
    if not countries:
        return "unknown"
    kr = next((c.weight for c in countries if c.code.upper() == "KR"), 0.0)
    if kr >= 90:
        return "domestic"
    if kr <= 10:
        return "foreign"
    return "mixed"


def _normalize(ticker: str, j: dict) -> EtfDetail:
    holdings: list[Holding] = []
    for it in j.get("etfTop10MajorConstituentAssets") or []:
        holdings.append(
            Holding(
                seq=int(it.get("seq") or 0),
                ticker=str(it.get("itemCode") or "").strip(),
                name=str(it.get("itemName") or "").strip(),
                shares=str(it.get("stockCount")) if it.get("stockCount") is not None else None,
                weight=_parse_weight(it.get("etfWeight")),
            )
        )
    countries = _breakdowns(j.get("countryPortfolioList"))
    return EtfDetail(
        ticker=ticker,
        name=str(j.get("itemName") or "").strip(),
        issuer=str(j.get("issuerName") or "").strip(),
        base_index=str(j.get("etfBaseIndex") or "").strip(),
        nav=_to_float(j.get("nav")),
        total_nav=str(j.get("totalNav") or "").strip(),
        total_fee=_to_float(j.get("totalFee")),
        chase_error_rate=_to_float(j.get("chaseErrorRate")),
        deviation_rate=_to_float(j.get("deviationRate")),
        listed_date=str(j.get("listedDate") or "").strip(),
        underlying_region=_classify_region(countries),
        top_holdings=holdings,
        sector_breakdown=_breakdowns(j.get("sectorPortfolioList")),
        country_breakdown=countries,
        asset_breakdown=_breakdowns(j.get("assetPortfolioList")),
    )


# ──────────────────────────────────────────────
# Firestore 일일 캐시
# ──────────────────────────────────────────────

def _kst_today() -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=9)).strftime("%Y-%m-%d")


def _cache_get(ticker: str) -> Optional[dict]:
    try:
        from screener.db.firebase_client import get_db

        doc = get_db().collection("etf_details").document(ticker).get()
        if doc.exists:
            data = doc.to_dict() or {}
            if data.get("as_of_date") == _kst_today():
                return data.get("payload")
    except Exception as e:
        logger.debug(f"[etf] 캐시 조회 실패 {ticker}: {e}")
    return None


def _cache_set(ticker: str, payload: dict) -> None:
    try:
        from firebase_admin import firestore

        from screener.db.firebase_client import get_db

        get_db().collection("etf_details").document(ticker).set(
            {
                "as_of_date": _kst_today(),
                "payload": payload,
                "updated_at": firestore.SERVER_TIMESTAMP,
            }
        )
    except Exception as e:
        logger.debug(f"[etf] 캐시 저장 실패 {ticker}: {e}")


def _fetch_naver_etf(ticker: str) -> Optional[dict]:
    """네이버 모바일 etfAnalysis 호출. 실패/비ETF면 None."""
    try:
        resp = requests.get(
            _NAVER_ETF_URL.format(code=ticker), headers=_HEADERS, timeout=8
        )
        resp.encoding = "utf-8"
        if resp.status_code != 200:
            return None
        j = resp.json()
        # ETF가 아니면 itemName 없음/구조 다름 → 가벼운 검증
        if not isinstance(j, dict) or not j.get("itemName"):
            return None
        return j
    except Exception as e:
        logger.warning(f"[etf] 네이버 조회 실패 {ticker}: {e}")
        return None


# ──────────────────────────────────────────────
# 해외(US 상장) ETF — yfinance funds_data
# ──────────────────────────────────────────────

# yfinance 섹터 키 → 한글 라벨.
_YF_SECTOR_KO = {
    "technology": "기술",
    "financial_services": "금융",
    "healthcare": "헬스케어",
    "consumer_cyclical": "임의소비재",
    "consumer_defensive": "필수소비재",
    "communication_services": "커뮤니케이션",
    "industrials": "산업재",
    "energy": "에너지",
    "basic_materials": "소재",
    "real_estate": "부동산",
    "realestate": "부동산",
    "utilities": "유틸리티",
}


def _fmt_usd_aum(v) -> str:
    """총자산(USD) → '$650.2B' 류 포맷."""
    try:
        n = float(v)
    except (TypeError, ValueError):
        return ""
    if n <= 0:
        return ""
    if n >= 1e12:
        return f"${n/1e12:.1f}T"
    if n >= 1e9:
        return f"${n/1e9:.1f}B"
    if n >= 1e6:
        return f"${n/1e6:.1f}M"
    return f"${n:,.0f}"


def _normalize_us(ticker: str, info: dict, top_df, sectors: dict, overview: dict) -> EtfDetail:
    holdings: list[Holding] = []
    seq = 1
    try:
        for sym, row in (top_df.iterrows() if top_df is not None else []):
            w = row.get("Holding Percent")
            holdings.append(
                Holding(
                    seq=seq,
                    ticker=str(sym or "").strip(),
                    name=str(row.get("Name") or "").strip(),
                    shares=None,
                    weight=round(float(w) * 100, 2) if w is not None else None,
                )
            )
            seq += 1
    except Exception as e:
        logger.debug(f"[etf:us] holdings 파싱 실패 {ticker}: {e}")

    sector_bd: list[Breakdown] = []
    for k, v in (sectors or {}).items():
        try:
            w = float(v) * 100
        except (TypeError, ValueError):
            continue
        if w > 0:
            sector_bd.append(Breakdown(code=_YF_SECTOR_KO.get(str(k), str(k)), weight=round(w, 2)))
    sector_bd.sort(key=lambda b: b.weight, reverse=True)

    fee = info.get("netExpenseRatio") or info.get("annualReportExpenseRatio")
    fee_pct = None
    if fee is not None:
        f = _to_float(fee)
        # yfinance는 0.0945(=0.0945%) 또는 비율(0.000945) 혼재 — 1 미만이면 ×100 보정 안전치
        fee_pct = round(f, 3) if (f is not None and f >= 0.01) else (round(f * 100, 3) if f is not None else None)

    return EtfDetail(
        ticker=ticker,
        name=str(info.get("longName") or info.get("shortName") or ticker).strip(),
        issuer=str(overview.get("family") or "").strip(),
        base_index=str(overview.get("categoryName") or "").strip(),  # 카테고리(지수 아님)
        nav=_to_float(info.get("navPrice") or info.get("regularMarketPrice")),
        total_nav=_fmt_usd_aum(info.get("totalAssets")),
        total_fee=fee_pct,
        chase_error_rate=None,
        deviation_rate=None,
        listed_date="",
        underlying_region="us",
        top_holdings=holdings,
        sector_breakdown=sector_bd,
        country_breakdown=[],  # yfinance US ETF는 국가 비중 미제공
        asset_breakdown=[],
    )


def _fetch_us_etf(ticker: str) -> Optional[EtfDetail]:
    """yfinance로 US 상장 ETF 정보+상위 holdings 수집. ETF 아니면 None."""
    try:
        import yfinance as yf

        t = yf.Ticker(ticker)
        info = t.info or {}
        if str(info.get("quoteType") or "").upper() != "ETF":
            return None
        fd = t.funds_data
        top_df = getattr(fd, "top_holdings", None)
        sectors = getattr(fd, "sector_weightings", None) or {}
        overview = getattr(fd, "fund_overview", None) or {}
        return _normalize_us(ticker, info, top_df, sectors, overview)
    except Exception as e:
        logger.warning(f"[etf:us] yfinance 조회 실패 {ticker}: {e}")
        return None


@router.get("/{ticker}")
async def get_etf_detail(ticker: str) -> dict:
    """ETF 상세(정보 + 상위 구성종목 + 섹터/국가/자산 비중). 1일 1회 외부 호출, 그 외 캐시.

    KR 상장 ETF 대상(국내 + 국내상장 국외). 비ETF/미상 티커는 404.
    """
    from agents.base import DISCLAIMER

    ticker = (ticker or "").strip().upper()
    if not ticker or len(ticker) > 12:
        raise HTTPException(400, {"code": "INVALID_TICKER", "message": "유효한 종목 코드 필요"})

    cached = _cache_get(ticker)
    if cached is not None:
        return cached

    # 순수 알파벳(SPY 등) → 해외(US) yfinance, 그 외(숫자 포함 KRX 코드) → 국내 상장 naver.
    if _US_TICKER.match(ticker):
        detail = await asyncio.to_thread(_fetch_us_etf, ticker)
    else:
        j = await asyncio.to_thread(_fetch_naver_etf, ticker)
        detail = _normalize(ticker, j) if j is not None else None

    if detail is None:
        raise HTTPException(
            404,
            {"code": "ETF_NOT_FOUND", "message": "ETF 정보를 찾을 수 없습니다."},
        )

    detail.as_of = datetime.now(timezone.utc).isoformat()
    detail.disclaimer = DISCLAIMER

    payload = _wrap_legal(detail.model_dump())
    _cache_set(ticker, payload)
    return payload


def _wrap_legal(payload: dict) -> dict:
    """응답 문자열 LEGAL 필터(이중 안전). ETF는 사실 데이터지만 일관 적용."""
    from api.routes.ai import _sanitize_response

    return _sanitize_response(payload)
