# 한국 시장 데이터 인프라 상세 스펙

> **목적**: Korean Market Specialist 페르소나에 필요한 모든 데이터 수집/처리 모듈 설계
> **위치**: `docs/data_infra/korea_market.md`
> **연관**: `docs/personas/korean.md`, `docs/v2_roadmap/WEEK_A.md`

---

## 📋 수집 데이터 8종

| # | 데이터 | 소스 | 빈도 | 우선순위 |
|---|--------|------|------|---------|
| 1 | 외국인 5년 보유 비중 + 순매수 히스토리 | pykrx | 일별 | 🔴 최우선 |
| 2 | 기관 8대 분류별 매매 | pykrx | 일별 | 🔴 최우선 |
| 3 | 재벌 그룹 + 자회사 매핑 | 정적 테이블 | 분기 갱신 | 🟠 높음 |
| 4 | 지주사 NAV 디스카운트 | 자체 계산 | 일별 | 🟠 높음 |
| 5 | 자사주 정책 (소각/보유 공시) | DART API | 실시간 + 월 1회 백필 | 🟠 높음 |
| 6 | 밸류업 인덱스 종목 + 편입/제외 | KRX 공식 | 분기별 | 🟡 중간 |
| 7 | 거버넌스 점수 (자체 평가) | 자체 모듈 | 분기별 | 🟡 중간 |
| 8 | 공매도 잔고 + 대차잔고 | pykrx | 일별 | 🟡 중간 |

---

## 1. 외국인/기관 수급 5년 히스토리

### 1.1 데이터 소스 검증 (실제 pykrx 1.2.7 검증 완료)

**라이브러리**: pykrx (이미 기존 시스템에서 사용 중)

**API 함수 — 종목별 투자자 매매 시계열**:
```python
from pykrx import stock

# 종목별 일별 투자자 매매 (특정 투자자만 시계열)
df = stock.get_market_trading_value_and_volume_by_ticker(
    fromdate="20210101",
    todate="20251231",
    market="KOSPI",        # KOSPI | KOSDAQ
    investor="외국인합계"  # 외국인합계 | 기관합계 | 개인 등
)
# 반환: 거래일별로 모든 종목의 해당 투자자 매수/매도 거래대금
```

**API 함수 — 일자 단위 투자자 카테고리별 매매**:
```python
# 특정 종목의 기간 내 투자자 카테고리별 누적 매매
df = stock.get_market_trading_value_by_investor(
    fromdate="20210101",
    todate="20251231",
    ticker="005930",
    etf=False, etn=False, elw=False  # 실제 시그니처
)
# 반환: 투자자 카테고리(외국인/기관/개인 등) × 매수/매도/순매수
```

**⚠️ 검증 결과**: 종목별 일별 투자자별 시계열을 한번에 받는 단일 함수는 없음.
- **전략**: `get_market_trading_value_and_volume_by_ticker`를 투자자별로 여러 번 호출 후 종목별로 재조립

**보유 비중 데이터**:
```python
# 일별 - 특정 종목의 외국인 보유 시계열
df_holding_series = stock.get_exhaustion_rates_of_foreign_investment_by_date(
    fromdate="20210101",
    todate="20251231",
    ticker="005930"
)

# 종목별 - 특정 일자의 모든 종목 외국인 보유 현황
df_holding_snapshot = stock.get_exhaustion_rates_of_foreign_investment_by_ticker(
    date="20251231",
    market="KOSPI",
    balance_limit=False
)
# 반환: 보유수량, 한도수량, 한도소진률
```

### 1.2 수집 전략 (실제 pykrx 호출 패턴)

**Phase 1 — 백필 (Backfill)**

⚠️ **수정**: 종목별 일별 투자자 시계열을 받는 단일 함수가 없으므로, 다음 두 가지 방식 중 선택:

**방식 A — 일자별 전체 종목 (권장)**
```python
# 거래일마다 1번씩 호출 → 그날의 모든 종목 데이터
for trade_date in trading_dates:  # 5년 = 약 1,250 영업일
    df = stock.get_market_trading_value_and_volume_by_ticker(
        fromdate=trade_date,
        todate=trade_date,
        market="KOSPI",
        investor="외국인합계"
    )
    # 한 번 호출 = 약 950개 종목 데이터
    time.sleep(1.0)  # rate limit
```
- 호출 수: 1,250일 × 2개 시장(KOSPI, KOSDAQ) × 9개 투자자 카테고리 = **22,500회**
- 소요 시간 (1초/호출): **약 6.3시간**
- 데이터 양: 1,250일 × 950종목 × 9 카테고리 ≈ 10.7M row
- **현실적 권장**: 9개 카테고리 → 핵심 4개(외국인합계/기관합계/연기금/개인)로 축소
- 축소 후: 1,250 × 2 × 4 = **10,000회 / 약 2.8시간**

**방식 B — 종목별 시계열**
```python
# 외국인 보유 비중만 종목별 시계열로 받음
for ticker in tickers:  # 350 종목
    df = stock.get_exhaustion_rates_of_foreign_investment_by_date(
        fromdate="20210101",
        todate="20251231",
        ticker=ticker
    )
    time.sleep(1.0)
```
- 호출 수: **350회 / 약 6분** (보유 비중만)
- 단점: 일별 매매 데이터(순매수)는 안 들어옴

**최종 전략 (하이브리드)**:
1. **방식 B**로 외국인 보유 비중 5년 시계열 수집 (350회, ~6분)
2. **방식 A로 핵심 4개 투자자 카테고리만 5년 일별 수집** (10,000회, ~2.8시간)
3. 1회 백필은 야간 Cloud Run Job으로 1회 실행 후 완료

**Phase 2 — 일별 증분 (Incremental)**
- 매일 16:30 (장마감 후) 자동 수집
- 전 거래일 데이터만 수집
- 호출 수: 2 시장 × 4 카테고리 = **8회 / 약 10초**
- + 보유 비중 스냅샷: 2 시장 × 1회 = 2회
- 총: **10회 / 약 12초**

### 1.3 Firestore 스키마

⚠️ **수정**: 실제 수집 가능한 데이터에 맞춰 스키마 단순화

```python
# Collection: historical_supply
# Document ID: {ticker}_{date}  (예: "005930_20251231")

{
    "ticker": "005930",
    "date": "20251231",
    "year": 2025,
    "month": 12,
    
    # 외국인 (방식 B에서 수집)
    "foreign_holding_qty": 3289450000,       # 외국인 보유수량
    "foreign_limit_qty": 5969782550,         # 한도수량
    "foreign_exhaustion_pct": 55.12,         # 한도 소진율 %
    
    # 외국인/기관 매매 (방식 A에서 수집, 거래대금 기준)
    "foreign_buy_value": 150000000000,       # 외국인 매수 거래대금
    "foreign_sell_value": 270000000000,      # 외국인 매도 거래대금
    "foreign_net_buy_value": -120000000000,  # 외국인 순매수
    
    "institution_buy_value": 200000000000,
    "institution_sell_value": 150000000000,
    "institution_net_buy_value": 50000000000,
    
    "pension_net_buy_value": 20000000000,    # 연기금
    "individual_net_buy_value": 70000000000, # 개인
    
    # 메타
    "collected_at": "2026-01-01T16:30:00+09:00",
    "data_source": "pykrx_1.2.7",
    "collection_phase": "backfill" | "incremental"
}
```

**⚠️ 중요 — 데이터 단위**:
- pykrx 반환: **거래대금(원) 또는 거래량(주)**
- 위 스키마는 **거래대금 기준**
- 5년 시계열 + 백만 row 저장 시 Firestore 비용 증가 → 핵심 4개 카테고리만 저장

**Index 설정**:
- `ticker` + `date DESC` (종목별 시계열)
- `date DESC` (특정 일자 전체 종목)

### 1.4 5년 추이 분석 함수

```python
# utils/data_collectors/korea_supply.py

async def get_foreign_5y_trend(ticker: str) -> dict:
    """
    종목별 5년 외국인 수급 추이 + 통계
    Returns:
        {
            "current_holding_pct": 55.12,
            "5y_avg_holding_pct": 53.4,
            "1y_change_pct_points": +1.4,
            "5y_max": 56.8,
            "5y_min": 49.2,
            "consecutive_buy_days": 4,  # 최근 연속 순매수일
            "30d_net_buy": 8500000000,  # 30일 누적
            "interpretation_signal": "increasing_above_avg"
        }
    """
    pass
```

---

## 2. 재벌 그룹 + 지주사 매핑

### 2.1 재벌 그룹 정적 테이블

**소스**: 공정거래위원회 대규모기업집단 지정 (매년 5월 발표)
- 2025년 기준 88개 그룹
- 자산 5조원 이상

**파일**: `data/chaebol_groups.json`

```json
{
  "삼성": {
    "rank": 1,
    "total_assets_trillion": 632.6,
    "chairman": "이재용",
    "holding_company": "삼성물산",
    "core_companies": ["005930", "005380", "207940", "028260", "032830"],
    "all_listed_companies": [...],
    "circular_ownership_resolved": true,
    "governance_issues_2024": [],
    "kcgs_avg_grade": "B+"
  },
  "SK": {
    "rank": 2,
    "total_assets_trillion": 334.3,
    "holding_company": "SK",
    "core_companies": ["000660", "017670", "096770", "034730"],
    ...
  },
  ...
}
```

**구축 방법**:
- 공정위 공시 자료 + DART 그룹 정보 통합
- 분기 1회 수동 갱신 (자동화 어려움)
- LLM 보조: 그룹 정보 누락 시 보충

### 2.2 지주사 NAV 디스카운트 자동 계산

**개념**:
```
NAV = Σ(보유 자회사 시총 × 지분율) + 순현금자산
NAV Discount % = (NAV - 지주사 시총) / NAV × 100
```

**데이터 필요**:
- 지주사가 보유한 자회사 지분율 (DART 공시)
- 자회사 시가총액 (실시간)
- 지주사 자체 시가총액 (실시간)
- 순현금자산 (재무제표)

**구현**:
```python
# utils/data_collectors/holding_company.py

HOLDING_COMPANIES = {
    "003550": {  # LG
        "name": "LG",
        "subsidiaries": [
            {"ticker": "066570", "name": "LG전자", "stake_pct": 33.7},
            {"ticker": "051910", "name": "LG화학", "stake_pct": 33.3},
            {"ticker": "032640", "name": "LG유플러스", "stake_pct": 37.7},
            ...
        ],
        "net_cash_billion": 1500,  # 분기마다 갱신
    },
    "034730": {  # SK
        ...
    },
    ...
}

async def calculate_nav_discount(holding_ticker: str) -> dict:
    """지주사 NAV 디스카운트 계산"""
    holding_data = HOLDING_COMPANIES.get(holding_ticker)
    if not holding_data:
        return None
    
    nav = holding_data["net_cash_billion"] * 1e9
    for sub in holding_data["subsidiaries"]:
        sub_market_cap = await get_market_cap(sub["ticker"])
        nav += sub_market_cap * (sub["stake_pct"] / 100)
    
    holding_market_cap = await get_market_cap(holding_ticker)
    discount_pct = (nav - holding_market_cap) / nav * 100
    
    return {
        "nav": nav,
        "market_cap": holding_market_cap,
        "discount_pct": round(discount_pct, 2),
        "interpretation": classify_discount(discount_pct)
    }

def classify_discount(pct: float) -> str:
    if pct < 20: return "낮음 (적정 평가)"
    elif pct < 40: return "중간 (구조적 디스카운트)"
    elif pct < 60: return "높음 (가치 vs 거버넌스 갈등)"
    else: return "매우 높음 (기회 또는 함정)"
```

**대상 종목 (예상 30~40개)**:
- 주요 그룹: 삼성물산, SK, LG, 두산, 한화, 롯데, GS, 효성 등
- 사업회사 + 지주사 분리 종목

### 2.3 검증 포인트

⚠️ **자회사 지분율은 분기마다 변동 가능** → 자동 동기화 필요
- DART 분기보고서 파싱 (어려움)
- 또는 분기 1회 수동 갱신 (현실적)

---

## 3. 자사주 정책 (소각 vs 보유)

### 3.1 데이터 소스: DART API

**API**: 전자공시시스템 OpenAPI
- 인증키 무료 발급 (https://opendart.fss.or.kr)
- 일일 10,000건 제한

**관련 공시 유형**:
1. **자기주식 취득 결정** — 매입 결정
2. **자기주식 처분 결정** — 매각/소각
3. **자기주식 취득 결과보고서** — 매입 완료
4. **주식소각 결정** — ⭐ 가장 중요

### 3.2 파싱 전략

```python
# utils/data_collectors/dart_buyback.py

DART_API_KEY = os.getenv("DART_API_KEY")

async def fetch_buyback_disclosures(start_date: str, end_date: str):
    """기간 내 자사주 관련 공시 일괄 수집"""
    url = "https://opendart.fss.or.kr/api/list.json"
    
    # 공시 유형 코드
    # B001: 정기공시
    # 자사주 취득은 주요사항보고서 안에 있음
    
    params = {
        "crtfc_key": DART_API_KEY,
        "bgn_de": start_date,
        "end_de": end_date,
        "pblntf_detail_ty": "B001",
    }
    
    response = await httpx.get(url, params=params)
    # 키워드 필터링: "자기주식", "자사주", "주식소각"
    pass
```

### 3.3 공시 분류 logic

```python
def classify_buyback_action(title: str, content: str) -> dict:
    """공시 제목/내용에서 자사주 액션 분류"""
    if "소각" in title or "소각" in content[:500]:
        return {
            "action": "burn",  # 소각
            "weight": 3,  # 주주환원 강함
            "rating": "★★★"
        }
    elif "취득" in title and "처분" not in title:
        return {
            "action": "buy_and_hold",  # 매입 후 보유
            "weight": 1,  # 의미 약함
            "rating": "★"
        }
    elif "처분" in title and "임직원" in content:
        return {
            "action": "esop",  # 임직원 보상용
            "weight": 0,
            "rating": "☆"
        }
```

### 3.4 Firestore 스키마

```python
# Collection: buyback_history
# Document ID: {ticker}_{date}_{disclosure_id}

{
    "ticker": "005930",
    "company_name": "삼성전자",
    "disclosure_date": "20251115",
    "disclosure_id": "20251115000123",
    "action": "burn",  # burn | buy_and_hold | esop | dispose
    "amount_krw": 71400000000000,  # 7.14조
    "shares": 50140000,
    "price_per_share": 70000,
    "schedule_start": "20251201",
    "schedule_end": "20260301",
    "rating": "★★★",
    "weight": 3,
    "raw_title": "주식소각 결정",
    "raw_content_preview": "..."
}
```

---

## 4. 밸류업 인덱스 종목

### 4.1 데이터 소스

**KRX 공식**: "코리아 밸류업 지수" (2024년 9월 출시)
- 100개 구성 종목
- 분기별 리밸런싱 (3, 6, 9, 12월)
- 발표: KRX 인덱스 페이지 또는 ETF 운용사 공시

**대안**: ETF 보유 종목 활용
- KODEX 코리아밸류업 ETF (379800)
- TIGER 코리아밸류업 ETF (379810)
- NAVER 금융이나 ETF 운용사 사이트에서 보유 종목 데이터

### 4.2 수집 방법

**Option A — KRX 직접 (선호)**
```python
import requests
from bs4 import BeautifulSoup

async def fetch_valueup_index_constituents():
    """KRX 코리아 밸류업 지수 구성 종목"""
    # KRX 인덱스 페이지 또는 정보데이터시스템 활용
    url = "https://data.krx.co.kr/contents/MDC/MDI/mdiLoader/index.cmd?menuId=MDC0201"
    # 실제 구현 시 API 엔드포인트 확인 필요
    pass
```

**Option B — ETF 보유 종목 활용 (Fallback)**
```python
async def fetch_valueup_via_etf():
    """KODEX/TIGER 밸류업 ETF 보유 종목으로 추정"""
    # 운용사 사이트의 일별 PDF/CSV 다운로드
    pass
```

### 4.3 Firestore 스키마

```python
# Collection: valueup_index
# Document ID: {date}  (분기별, 예: "20260331")

{
    "rebalancing_date": "20260331",
    "total_constituents": 100,
    "constituents": [
        {
            "ticker": "005930",
            "name": "삼성전자",
            "weight_pct": 14.32,
            "added_at_this_rebalancing": false
        },
        ...
    ],
    "added_companies": [...],   # 이번 리밸런싱에서 신규 편입
    "removed_companies": [...]  # 제외
}
```

### 4.4 활용 logic

```python
async def is_in_valueup_index(ticker: str) -> dict:
    """종목의 밸류업 인덱스 편입 여부 + 편입 시점"""
    latest = await get_latest_valueup_index()
    
    for c in latest["constituents"]:
        if c["ticker"] == ticker:
            return {
                "included": True,
                "weight_pct": c["weight_pct"],
                "newly_added": c["added_at_this_rebalancing"],
                "since": find_first_inclusion_date(ticker)
            }
    return {"included": False}
```

---

## 5. 거버넌스 점수 (자체 평가 — Option C)

### 5.1 외부 평가 vs 자체 평가

**외부 평가 (KCGS 등)**:
- ⚠️ 유료 데이터 ($50~/월)
- ⚠️ 종목 커버리지 제한
- ✅ 검증된 평가
- ❌ 자체 변경 불가

**자체 평가 (Option C 채택)**:
- ✅ 무료
- ✅ 모든 종목 커버
- ✅ 변수 변경 가능
- ❌ 신뢰도 검증 필요

### 5.2 자체 평가 logic (5개 변수)

```python
def calculate_governance_score(ticker: str) -> dict:
    """
    자체 거버넌스 점수 (0~10점)
    각 변수 0~2점 × 5개 변수
    """
    score_components = {
        "buyback_policy": evaluate_buyback_policy(ticker),         # 0~2
        "dividend_consistency": evaluate_dividend(ticker),          # 0~2
        "circular_ownership": evaluate_circular(ticker),           # 0~2
        "controlling_shareholder_ratio": evaluate_chairman(ticker), # 0~2
        "audit_opinion_history": evaluate_audit(ticker),           # 0~2
    }
    
    total = sum(score_components.values())
    return {
        "total_score": total,  # 0~10
        "grade": score_to_grade(total),  # S, A+, A, B+, B, C, D
        "components": score_components,
        "rationale": generate_rationale(score_components)
    }
```

**각 변수 평가 기준**:

```python
def evaluate_buyback_policy(ticker: str) -> int:
    """자사주 정책 (0~2)"""
    history_3y = get_buyback_history(ticker, years=3)
    if any(h["action"] == "burn" for h in history_3y):
        return 2  # 소각 이력 있음
    elif any(h["action"] == "buy_and_hold" for h in history_3y):
        return 1  # 매입만
    return 0  # 자사주 정책 없음

def evaluate_dividend(ticker: str) -> int:
    """배당 일관성 (0~2)"""
    last_5y_dividends = get_dividend_history(ticker, years=5)
    if all(d > 0 for d in last_5y_dividends) and is_increasing(last_5y_dividends):
        return 2  # 5년 연속 증가
    elif all(d > 0 for d in last_5y_dividends):
        return 1  # 5년 연속 지급
    return 0

def evaluate_circular(ticker: str) -> int:
    """순환출자 (0~2)"""
    group = find_chaebol_group(ticker)
    if not group:
        return 2  # 비재벌 = 순환출자 X
    if group["circular_ownership_resolved"]:
        return 2
    return 0

def evaluate_chairman(ticker: str) -> int:
    """지배주주 지분율 (0~2)"""
    # 너무 낮음(<10%) 또는 너무 높음(>50%) 둘 다 위험
    chairman_pct = get_chairman_holding_pct(ticker)
    if 15 <= chairman_pct <= 40:
        return 2  # 적정 범위
    elif 10 <= chairman_pct <= 50:
        return 1
    return 0

def evaluate_audit(ticker: str) -> int:
    """감사 의견 이력 (0~2)"""
    last_5y_audits = get_audit_history(ticker, years=5)
    if all(a == "적정" for a in last_5y_audits):
        return 2
    elif any(a == "한정" for a in last_5y_audits):
        return 1
    return 0  # 의견거절/부적정 있음
```

### 5.3 검증 + 신뢰도 표시

⚠️ **자체 평가의 한계 명시**

응답에 항상 표시:
```
"governance_score": 7,
"governance_method": "자체 평가 (5변수 정량 모델)",
"governance_disclaimer": "외부 평가기관 의견과 다를 수 있습니다",
"external_reference": "KCGS 등급 미참조"
```

---

## 6. 공매도 / 대차잔고 데이터

### 6.1 데이터 소스 (실제 pykrx 1.2.7 검증)

```python
from pykrx import stock

# ⭐ 종목별 공매도 잔고 시계열 (정확한 함수)
df_short_balance = stock.get_shorting_balance_by_date(
    fromdate="20251101",
    todate="20251231",
    ticker="005930"
)
# 컬럼: 공매도잔고, 상장주식수, 공매도금액, 시가총액, 비중

# 종목별 공매도 거래량 시계열
df_short_volume = stock.get_shorting_volume_by_date(
    fromdate="20251101",
    todate="20251231",
    ticker="005930"
)

# 종목별 공매도 종합 (공매도/잔고/대차 통합)
df_short_status = stock.get_shorting_status_by_date(
    fromdate="20251101",
    todate="20251231",
    ticker="005930"
)

# 일자별 전체 종목 공매도 잔고 (스냅샷)
df_snapshot = stock.get_shorting_balance_by_ticker(
    date="20251231",
    market="KOSPI"
)
```

⚠️ **주의 — 이름은 비슷한데 기능이 다름**:
- `*_by_date(fromdate, todate, ticker)`: **종목별 시계열**
- `*_by_ticker(date, market)`: **일자별 모든 종목 스냅샷**

### 6.2 정책 변동 대응

⚠️ 한국 공매도 정책 자주 변동 (2023.11~2024.06 전면 금지 등)

```python
SHORT_SELLING_POLICY_HISTORY = {
    "2008-10": "리먼사태 후 금지",
    "2009-06": "재개",
    "2011-08": "유럽 위기 후 금지",
    "2011-11": "재개",
    "2020-03": "코로나 후 금지",
    "2021-05": "코스피200/코스닥150만 재개",
    "2023-11": "전면 금지 (불법공매도 점검)",
    "2025-03": "전면 재개",
    # 2026년 현재 시점 정책 명시 필요
}
```

### 6.3 분석 logic

```python
async def analyze_short_signals(ticker: str) -> dict:
    """공매도/대차 종합 분석"""
    # 30일 추이
    history_30d = await get_short_history(ticker, days=30)
    
    return {
        "current_short_balance_pct": 1.2,  # 시총 대비
        "30d_change": "-0.3%p",  # 감소 = 숏 커버링
        "short_to_market_cap": "낮음 (5% 미만)",
        "loan_balance_change": "+15%",
        "interpretation": "공매도 잔고 감소 + 대차 증가 = 숏 커버링 진행 중",
        "policy_status": "전면 재개 (2025.03~)"
    }
```

---

## 📂 파일 구조 요약

```
axis/
├── data/
│   ├── chaebol_groups.json          # 재벌 그룹 매핑
│   └── short_selling_policy.json    # 공매도 정책 이력
│
├── utils/data_collectors/
│   ├── __init__.py
│   ├── korea_supply.py              # 외국인/기관 수급
│   ├── holding_company.py           # 지주사 NAV
│   ├── dart_buyback.py              # 자사주 정책
│   ├── valueup_index.py             # 밸류업 인덱스
│   ├── governance_score.py          # 자체 거버넌스 점수
│   └── short_selling.py             # 공매도/대차
│
├── jobs/
│   ├── backfill_korea_supply.py     # 5년 백필 (1회 실행)
│   └── daily_korea_collect.py       # 일일 증분 수집
│
└── tests/data_collectors/
    ├── test_korea_supply.py
    ├── test_holding_company.py
    └── ...
```

---

## 🧪 검증 체크리스트

각 모듈 작성 후 reviewer subagent에 다음 검증 요청:

- [ ] pykrx API 시그니처 정확히 사용했나
- [ ] rate limit 준수 (sleep 0.5초+)
- [ ] 에러 발생 시 재시도 + 로깅
- [ ] Firestore 스키마 일관성
- [ ] 데이터 시점 (T+1) 명시
- [ ] 정책 변동 대응 (공매도)
- [ ] 자체 평가 신뢰도 한계 명시
- [ ] 비용: pykrx 무료, DART 무료 한도 내

---

## ⚠️ 알려진 위험 + 대응

### 1. pykrx 데이터 시점
- 한국거래소 발표 후 다음 날 09:00 이후 가능
- **실시간 데이터 아님** → 응답에 명시

### 2. DART API 일일 한도
- 10,000건/일 무료
- 350 종목 × 30일 = 10,500건/월 → 무료 한도 안전

### 3. 재벌 그룹 매핑 갱신
- 분기 1회 수동 갱신 필요
- 누락 시: LLM 보조로 임시 보충

### 4. 지주사 자회사 지분율 변경
- 분기 1회 DART 보고서 확인 필요
- 자동화 어려움 → 수동 갱신

### 5. 밸류업 인덱스 KRX 공식 API 부재
- ETF 보유 종목으로 fallback
- 분기별 리밸런싱 시점 모니터링

### 6. 공매도 정책 변동
- 정책 발표 즉시 모듈 동작 검증
- `SHORT_SELLING_POLICY_HISTORY` 수동 업데이트

---

## 📊 예상 작업량 (재검증 완료)

```
Day 1: 외국인/기관 백필 + 증분 (구조 + 1차 실행)
       - Backfill: 1회 야간 실행, ~3시간 소요
       - 증분: 매일 16:30 Cloud Run Job
       - 검증: 100종목 sample 데이터 확인

Day 2: 외국인 보유 비중 5년 시계열 + 분석 함수
       - get_foreign_5y_trend() 등 분석 헬퍼
       - 단위 테스트

Day 3: 재벌 그룹 매핑 (정적) + 지주사 NAV 자동 계산

Day 4: 자사주 DART 파싱 (소각 vs 보유)

Day 5: 밸류업 인덱스 + 거버넌스 자체 평가 + 공매도/대차
```

**총 5일 (Week A)**, 각 모듈에 reviewer 검증 1회씩 포함.

⚠️ **백필 1회 실행 비용/시간**:
- pykrx 무료 (rate limit 1초/호출)
- 백필 1회: 약 3시간 (야간 실행)
- Firestore 쓰기: 1.25M doc × $0.18/100K = **약 $2.3 (1회 비용)**
- 일별 증분: 1,000 doc/일 × 30일 = 30K doc/월 × $0.18/100K = **월 $0.05**
