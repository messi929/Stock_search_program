# 매크로 데이터 인프라 상세 스펙

> **목적**: Macro PM 페르소나에 필요한 매크로 지표 + 사이클 판정 모듈 설계
> **위치**: `docs/data_infra/macro.md`
> **연관**: `docs/personas/macro.md`, `docs/v2_roadmap/WEEK_B.md`

---

## 📋 수집 데이터 구조

| # | 카테고리 | 핵심 지표 | 소스 | 빈도 |
|---|---------|----------|------|------|
| 1 | 미국 금리 | Fed Funds Rate, 10Y/2Y Treasury | FRED | 일별 |
| 2 | 미국 경기 | GDP, PMI, Unemployment | FRED | 월별 |
| 3 | 미국 인플레 | CPI, Core CPI, PCE | FRED | 월별 |
| 4 | 미국 통화 | DXY (달러 인덱스) | FRED + yfinance | 일별 |
| 5 | 한국 금리 | 기준금리, 국고채 3Y/10Y | ECOS | 일별 |
| 6 | 한국 경기 | GDP, 산업생산, PMI | ECOS | 월별 |
| 7 | 한국 인플레 | CPI, Core CPI | ECOS | 월별 |
| 8 | 한국 통화 | USD/KRW | yfinance/ECOS | 일별 |
| 9 | 매크로 캘린더 | FOMC/한은 일정 | 정적 데이터 | 분기 갱신 |

---

## 1. FRED API 연동 (미국 매크로)

### 1.1 API 정보

**FRED (Federal Reserve Economic Data)**
- URL: https://fred.stlouisfed.org/
- API 무료 (인증키 필요)
- 일일 호출 제한: 120,000회/일 (실질 무제한)
- Python 라이브러리: `fredapi`

### 1.2 핵심 시리즈 ID

```python
FRED_SERIES = {
    # 금리
    "fed_funds_rate": "DFF",           # 연방 기금 일별 (Daily)
    "fed_funds_target_upper": "DFEDTARU",  # 정책금리 상단
    "fed_funds_target_lower": "DFEDTARL",  # 정책금리 하단
    "treasury_2y": "DGS2",             # 2년 국채
    "treasury_10y": "DGS10",           # 10년 국채
    "yield_spread_10y_2y": "T10Y2Y",   # 장단기 스프레드
    "high_yield_spread": "BAMLH0A0HYM2",  # HY OAS 스프레드
    
    # 경기
    "gdp_yoy": "A191RL1Q225SBEA",      # 실질 GDP 전년 동기 대비
    "ism_manufacturing": "MANEMP",      # ⚠️ 공식 ISM은 FRED에서 못 받음 (유료)
    "industrial_production": "INDPRO",  # 산업 생산 지수
    "unemployment_rate": "UNRATE",      # 실업률
    "nonfarm_payrolls": "PAYEMS",       # 비농업 고용
    "consumer_sentiment": "UMCSENT",    # 소비자 신뢰
    
    # 인플레
    "cpi_all": "CPIAUCSL",              # CPI (NSA)
    "cpi_core": "CPILFESL",             # Core CPI (식품/에너지 제외)
    "cpi_yoy": "CPIAUCSL_PC1",          # CPI YoY (계산 시리즈)
    "pce_core": "PCEPILFE",             # Core PCE (Fed 선호 지표)
    "ppi_all": "PPIACO",                # PPI
    
    # 통화
    "dxy": "DTWEXBGS",                  # 광범위 달러 인덱스
    
    # 원자재
    "oil_wti": "DCOILWTICO",            # WTI 원유
    "gold": "GOLDPMGBD228NLBM",         # 금
}
```

⚠️ **검증 필요**: ISM PMI는 FRED 무료에서 직접 제공 안 함
- 대안 1: `MANEMP` (제조업 고용) 활용
- 대안 2: `NAPM` 시리즈 (구버전, 일부만)
- 대안 3: ISM 사이트 직접 크롤링 (회색지대)
- **현실적 권장**: Industrial Production (`INDPRO`) + Unemployment 조합으로 경기 사이클 판정

### 1.3 라이브러리 사용법 (실제 fredapi 0.5.2 검증)

```python
# utils/data_collectors/fred_client.py
from fredapi import Fred
import os
from typing import Optional
import pandas as pd

class FREDClient:
    def __init__(self):
        api_key = os.getenv("FRED_API_KEY")
        if not api_key:
            raise ValueError("FRED_API_KEY env var required")
        self.fred = Fred(api_key=api_key)
    
    async def get_series(
        self, 
        series_id: str, 
        observation_start: str = "2020-01-01",   # ⚠️ start가 아닌 observation_start
        observation_end: Optional[str] = None,    # ⚠️ end가 아닌 observation_end
    ) -> pd.Series:
        """단일 시리즈 시계열 조회"""
        return self.fred.get_series(
            series_id, 
            observation_start=observation_start, 
            observation_end=observation_end
        )
    
    async def get_latest_value(self, series_id: str) -> dict:
        """최신값 + 메타"""
        series = self.fred.get_series_latest_release(series_id)
        info = self.fred.get_series_info(series_id)
        return {
            "series_id": series_id,
            "title": info["title"],
            "latest_value": float(series.iloc[-1]),
            "latest_date": str(series.index[-1].date()),
            "frequency": info["frequency"],
            "units": info["units"]
        }
```

### 1.4 실제 검증 (시그니처 — fredapi 0.5.2)

`fredapi` 라이브러리 함수 (실제 검증 완료):
- `Fred(api_key=None, api_key_file=None, proxies=None)`
- `fred.get_series(series_id, observation_start=None, observation_end=None, **kwargs)` ← **kwargs로 frequency, aggregation_method 등 추가 가능
- `fred.get_series_info(series_id)` → 메타 dict
- `fred.get_series_latest_release(series_id)`
- `fred.search(text, limit=1000, order_by=None, sort_order=None, filter=None)` → 시리즈 검색
- `fred.search_by_category(...)` / `fred.search_by_release(...)`
- `fred.get_series_first_release(series_id)` / `fred.get_series_as_of_date(...)` (revision 추적용)

---

## 2. ECOS API 연동 (한국 매크로)

### 2.1 API 정보

**ECOS (한국은행 경제통계시스템)**
- URL: https://ecos.bok.or.kr/api/
- 인증키 무료 발급
- 일일 호출 제한: 100,000건/일
- HTTP REST (Python 전용 라이브러리 없음 — 직접 호출)

### 2.2 핵심 통계 코드

**ECOS는 시리즈가 아니라 "통계표"와 "통계항목" 구조**:
- 통계표코드 (4자리): 예 "722Y001" = 한국은행 기준금리
- 통계항목코드 (가변): 표 안의 세부 항목

```python
ECOS_CODES = {
    # 금리
    "base_rate": {
        "stat_code": "722Y001",
        "item_code1": "0101000",  # 한국은행 기준금리
        "freq": "M",  # Monthly
    },
    "treasury_3y": {
        "stat_code": "721Y001",
        "item_code1": "5020000",  # 국고채 3년
        "freq": "D",
    },
    "treasury_10y": {
        "stat_code": "721Y001",
        "item_code1": "5050000",  # 국고채 10년
        "freq": "D",
    },
    
    # 경기
    "gdp_yoy": {
        "stat_code": "200Y002",
        "item_code1": "10101",  # GDP 성장률
        "freq": "Q",
    },
    "industrial_production": {
        "stat_code": "901Y033",
        "item_code1": "I31AA",  # 광공업 생산지수
        "freq": "M",
    },
    
    # 인플레
    "cpi_total": {
        "stat_code": "901Y009",
        "item_code1": "0",  # 총지수
        "freq": "M",
    },
    "cpi_core": {
        "stat_code": "901Y009",
        "item_code1": "QA",  # 식품 및 에너지 제외 (근원물가)
        "freq": "M",
    },
    
    # 통화
    "usd_krw": {
        "stat_code": "731Y001",
        "item_code1": "0000001",  # 원/달러 평균환율
        "freq": "D",
    },
}
```

### 2.3 직접 호출 (HTTP)

```python
# utils/data_collectors/ecos_client.py
import httpx
import os
from typing import Optional

class ECOSClient:
    BASE_URL = "https://ecos.bok.or.kr/api"
    
    def __init__(self):
        self.api_key = os.getenv("ECOS_API_KEY")
        if not self.api_key:
            raise ValueError("ECOS_API_KEY env var required")
    
    async def get_statistic_search(
        self,
        stat_code: str,
        freq: str,            # D | M | Q | A
        start: str,           # YYYYMMDD or YYYYMM or YYYY
        end: str,
        item_code1: str = "?",
        item_code2: str = "?",
        item_code3: str = "?",
    ) -> dict:
        """통계 시계열 조회"""
        url = (
            f"{self.BASE_URL}/StatisticSearch/{self.api_key}/json/kr/1/100/"
            f"{stat_code}/{freq}/{start}/{end}/"
            f"{item_code1}/{item_code2}/{item_code3}"
        )
        async with httpx.AsyncClient() as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            
            # 정상 응답 구조
            if "StatisticSearch" in data:
                return data["StatisticSearch"]["row"]
            # 에러 응답
            elif "RESULT" in data:
                raise Exception(f"ECOS API error: {data['RESULT']}")
            return []
```

### 2.4 검증 포인트

⚠️ **ECOS 통계 코드는 자주 변경됨**
- 한국은행이 통계 분류 개편 시 코드 변경
- 예: 2020년대 초 GDP 통계 분류 개편 있었음
- **대응**: 분기 1회 코드 유효성 검증 + 변경 시 매핑 테이블 업데이트

⚠️ **freq별 날짜 형식 다름**
- D: YYYYMMDD
- M: YYYYMM
- Q: YYYY+분기 (Q1=YYYY1, Q2=YYYY2, ...) — 검증 필요
- A: YYYY

---

## 3. Firestore 스키마

```python
# Collection: macro_indicators
# Document ID: {indicator_key}_{date}  (예: "fed_funds_rate_20251231")

{
    "indicator_key": "fed_funds_rate",  # FRED_SERIES 또는 ECOS_CODES의 키
    "country": "US",  # US | KR | GLOBAL
    "category": "interest_rate",  # interest_rate | business_cycle | inflation | currency
    "date": "20251231",
    "value": 5.25,
    "unit": "percent",
    "frequency": "D",  # D | M | Q | A
    "source": "FRED",  # FRED | ECOS | yfinance
    "source_series_id": "DFF",
    
    # 변동 (자동 계산)
    "yoy_change": -0.5,        # 전년 대비
    "mom_change": 0.0,         # 전월 대비
    "wow_change": 0.0,         # 전주 대비
    
    "collected_at": "2026-01-01T12:00:00Z"
}
```

**별도 컬렉션 — 사이클 판정 결과**:
```python
# Collection: macro_regime_history
# Document ID: {country}_{date}  (예: "US_20251231")

{
    "country": "US",
    "date": "20251231",
    "interest_rate_stage": "인상 후반",
    "business_cycle_stage": "확장 후기",
    "currency_stage": "강달러 (다소 약화)",
    "inflation_stage": "고인플레이션 (둔화 중)",
    "regime": "Late Cycle",
    "regime_confidence": 0.7,
    "transition_to": "Stagflation",
    "transition_signals_count": 2,
    
    "key_indicators_snapshot": {
        "fed_funds": 5.25,
        "treasury_spread_10y_2y": 0.15,
        "cpi_yoy": 3.2,
        "dxy": 104.5,
        "unemployment": 4.1
    },
    
    "calculated_at": "2026-01-01T12:00:00Z"
}
```

---

## 4. 사이클 자동 판정 모듈

### 4.1 금리 사이클 판정

```python
# utils/data_collectors/cycle_detector.py

def detect_interest_rate_stage(
    fed_rate_current: float,
    fed_rate_3m_ago: float,
    fed_rate_12m_ago: float,
    spread_10y_2y: float,
) -> dict:
    """
    금리 사이클 단계 판정
    
    Returns:
        stage: 인하시작 | 인하후반 | 인상시작 | 인상후반
        confidence: 0~1
        rationale: str
    """
    rate_change_3m = fed_rate_current - fed_rate_3m_ago
    rate_change_12m = fed_rate_current - fed_rate_12m_ago
    
    # 인상 사이클
    if rate_change_12m > 0.5:  # 1년 동안 +50bp 이상
        if rate_change_3m > 0.0:
            stage = "인상 후반"
            rationale = "12개월 누적 인상 + 최근 3개월에도 인상 지속"
        else:
            stage = "인상 후반 (둔화)"
            rationale = "장기 인상 사이클이지만 최근 3개월 인상 멈춤"
    
    # 인하 사이클
    elif rate_change_12m < -0.5:
        if rate_change_3m < 0.0:
            stage = "인하 시작"
            rationale = "최근 인하 진행 중"
        else:
            stage = "인하 후반"
            rationale = "1년 동안 인하 진행했지만 최근 3개월 안정"
    
    # 횡보
    else:
        stage = "횡보"
        rationale = "12개월 변동 -50~+50bp 이내"
    
    confidence = min(abs(rate_change_12m) / 1.0, 1.0)  # 변동 크면 신뢰도 ↑
    
    return {
        "stage": stage,
        "confidence": round(confidence, 2),
        "rationale": rationale,
        "rate_change_3m": rate_change_3m,
        "rate_change_12m": rate_change_12m,
        "yield_curve_signal": "정상" if spread_10y_2y > 0 else "역전"
    }
```

### 4.2 경기 사이클 판정

```python
def detect_business_cycle_stage(
    gdp_yoy: float,
    industrial_production_yoy: float,
    unemployment_current: float,
    unemployment_12m_ago: float,
    pmi: Optional[float] = None,  # 가능하면 ISM PMI
) -> dict:
    """
    경기 사이클 단계 판정 (4단계)
    """
    unemployment_change = unemployment_current - unemployment_12m_ago
    
    # 확장 단계
    if gdp_yoy > 1.5 and industrial_production_yoy > 0:
        if unemployment_change < -0.5:  # 실업률 빠르게 하락
            stage = "확장 초기"
        else:
            stage = "확장 후기"
    
    # 수축 단계
    elif gdp_yoy < 1.5 or industrial_production_yoy < 0:
        if unemployment_change > 0.5:  # 실업률 상승
            stage = "수축 후기"
        else:
            stage = "수축 초기"
    
    else:
        stage = "전환기 (불확실)"
    
    return {
        "stage": stage,
        "gdp_yoy": gdp_yoy,
        "industrial_production_yoy": industrial_production_yoy,
        "unemployment_change_12m": unemployment_change,
        "pmi": pmi,
        "confidence": 0.7  # 기본값
    }
```

### 4.3 인플레이션 사이클 판정

```python
def detect_inflation_stage(
    cpi_yoy: float,
    core_cpi_yoy: float,
    cpi_3m_avg_change: float,  # 3개월 이동평균 변화
) -> dict:
    """
    인플레이션 사이클 (4단계)
    """
    if cpi_yoy < 1.0:
        stage = "디플레이션 우려"
    elif 1.0 <= cpi_yoy < 3.0:
        stage = "저인플레이션"
    elif 3.0 <= cpi_yoy < 6.0:
        if cpi_3m_avg_change < 0:
            stage = "고인플레이션 (둔화 중)"
        else:
            stage = "고인플레이션 (가속)"
    else:
        stage = "하이퍼인플레이션"
    
    return {
        "stage": stage,
        "cpi_yoy": cpi_yoy,
        "core_cpi_yoy": core_cpi_yoy,
        "trend": "accelerating" if cpi_3m_avg_change > 0 else "decelerating"
    }
```

### 4.4 통화 사이클 판정

```python
def detect_currency_stage(
    dxy_current: float,
    dxy_3m_ago: float,
    dxy_12m_ago: float,
) -> dict:
    """달러 강세/약세 판정"""
    change_3m = (dxy_current - dxy_3m_ago) / dxy_3m_ago * 100
    change_12m = (dxy_current - dxy_12m_ago) / dxy_12m_ago * 100
    
    if change_12m > 5 and change_3m > 0:
        stage = "달러 강세"
    elif change_12m < -5 and change_3m < 0:
        stage = "달러 약세"
    else:
        stage = "달러 횡보"
    
    return {
        "stage": stage,
        "dxy_current": dxy_current,
        "change_12m_pct": round(change_12m, 2),
        "change_3m_pct": round(change_3m, 2)
    }
```

---

## 5. 6대 매크로 국면 매핑

### 5.1 국면 판정 logic

```python
def detect_macro_regime(
    interest_rate_stage: str,
    business_cycle_stage: str,
    currency_stage: str,
    inflation_stage: str,
) -> dict:
    """
    4개 사이클 → 6대 국면 매핑
    """
    # 시그니처 패턴 매칭
    patterns = {
        "Goldilocks": {
            "interest_rate": ["인하 후반", "횡보"],
            "business_cycle": ["확장 후기"],
            "currency": ["달러 약세", "달러 횡보"],
            "inflation": ["저인플레이션"],
        },
        "Reflation": {
            "interest_rate": ["인하 시작"],
            "business_cycle": ["확장 초기"],
            "currency": ["달러 약세"],
            "inflation": ["저인플레이션", "고인플레이션 (둔화 중)"],
        },
        "Stagflation": {
            "interest_rate": ["인상 후반"],
            "business_cycle": ["수축 초기", "수축 후기"],
            "currency": ["달러 강세"],
            "inflation": ["고인플레이션 (가속)", "고인플레이션 (둔화 중)"],
        },
        "Risk-Off": {
            "interest_rate": ["인상 후반"],
            "business_cycle": ["수축 후기"],
            "currency": ["달러 강세"],
            "inflation": ["저인플레이션"],
        },
        "Recovery": {
            "interest_rate": ["인하 시작"],
            "business_cycle": ["수축 후기", "확장 초기"],
            "currency": ["달러 약세"],
            "inflation": ["저인플레이션"],
        },
        "Late Cycle": {
            "interest_rate": ["인상 시작", "인상 후반"],
            "business_cycle": ["확장 후기"],
            "currency": ["달러 강세"],
            "inflation": ["고인플레이션 (가속)", "고인플레이션 (둔화 중)"],
        },
    }
    
    # 매칭 점수 계산
    matches = {}
    for regime, criteria in patterns.items():
        score = 0
        if interest_rate_stage in criteria["interest_rate"]: score += 1
        if business_cycle_stage in criteria["business_cycle"]: score += 1
        if currency_stage in criteria["currency"]: score += 1
        if inflation_stage in criteria["inflation"]: score += 1
        matches[regime] = score
    
    # 최고 점수 + 차순위
    sorted_matches = sorted(matches.items(), key=lambda x: x[1], reverse=True)
    primary = sorted_matches[0]
    secondary = sorted_matches[1] if len(sorted_matches) > 1 else None
    
    return {
        "regime": primary[0],
        "regime_score": primary[1],  # 4점 만점
        "regime_confidence": round(primary[1] / 4.0, 2),
        "transition_to": secondary[0] if secondary and secondary[1] >= 2 else None,
        "all_scores": matches
    }
```

### 5.2 검증 — 매칭이 모호한 경우

⚠️ **주의**: 4개 사이클이 모두 명확한 패턴에 안 맞을 수 있음
- 점수 < 2: "전환기 (Transition)"로 표시
- 점수가 동률인 국면 2개: "혼합 국면" 표시
- 사용자에게 confidence 점수 명시

---

## 6. 매크로 캘린더

### 6.1 정적 데이터 구조

```python
# data/macro_calendar.json

{
  "fomc_2026": [
    {"date": "2026-01-29", "type": "FOMC", "country": "US"},
    {"date": "2026-03-19", "type": "FOMC", "country": "US"},
    {"date": "2026-05-07", "type": "FOMC", "country": "US"},
    {"date": "2026-06-18", "type": "FOMC", "country": "US"},
    {"date": "2026-07-30", "type": "FOMC", "country": "US"},
    {"date": "2026-09-17", "type": "FOMC", "country": "US"},
    {"date": "2026-11-05", "type": "FOMC", "country": "US"},
    {"date": "2026-12-17", "type": "FOMC", "country": "US"}
  ],
  "bok_2026": [
    {"date": "2026-01-15", "type": "BOK_RATE", "country": "KR"},
    {"date": "2026-02-26", "type": "BOK_RATE", "country": "KR"},
    ...
  ],
  "us_cpi_2026": [
    {"date": "2026-01-14", "type": "US_CPI", "country": "US"},
    ...
  ],
  "us_employment_2026": [...],
  "kr_cpi_2026": [...]
}
```

⚠️ **주의**: 정적 데이터이므로 분기마다 갱신 필요
- 1월: 그 해 + 다음 해 일정 업데이트
- 자동화 가능: FOMC 일정은 Fed 사이트에서 발표 (XML/JSON)

### 6.2 활용 예시

```python
def get_upcoming_macro_events(days_ahead: int = 30) -> list:
    """앞으로 N일 안의 매크로 이벤트"""
    today = datetime.now().date()
    end_date = today + timedelta(days=days_ahead)
    
    with open("data/macro_calendar.json") as f:
        calendar = json.load(f)
    
    events = []
    for category, items in calendar.items():
        for event in items:
            event_date = datetime.fromisoformat(event["date"]).date()
            if today <= event_date <= end_date:
                events.append({
                    **event,
                    "days_until": (event_date - today).days
                })
    
    return sorted(events, key=lambda x: x["days_until"])
```

---

## 📂 파일 구조 요약

```
axis/
├── data/
│   └── macro_calendar.json          # FOMC, 한은, CPI 일정
│
├── utils/data_collectors/
│   ├── fred_client.py               # FRED API
│   ├── ecos_client.py               # ECOS API
│   ├── cycle_detector.py            # 4대 사이클 자동 판정
│   └── regime_detector.py           # 6대 국면 매핑
│
├── jobs/
│   ├── daily_macro_collect.py       # 일일 FRED + ECOS 수집
│   └── monthly_regime_calc.py       # 월별 사이클 + 국면 계산
│
└── tests/data_collectors/
    ├── test_fred_client.py
    ├── test_ecos_client.py
    └── test_cycle_detector.py
```

---

## 🧪 검증 체크리스트

각 모듈 작성 후 reviewer subagent에 검증 요청:

- [ ] FRED 시리즈 ID 정확 (특히 ISM PMI 대안)
- [ ] ECOS 통계 코드 유효 (분기 변경 가능성)
- [ ] freq 별 날짜 형식 정확 (D/M/Q/A)
- [ ] 사이클 판정 logic 경계값 테스트
- [ ] 국면 매핑 점수 동률 처리
- [ ] confidence 점수 의미 있게 계산
- [ ] 비용: FRED/ECOS 무료 한도 내

---

## ⚠️ 알려진 위험 + 대응

### 1. ISM PMI 무료 데이터 부재
- **문제**: ISM 공식 PMI는 유료
- **대응 1**: Industrial Production (`INDPRO`) + Unemployment 조합
- **대응 2**: NY Fed 또는 Chicago Fed PMI 활용 (`NAPMNOI` 등)
- **대응 3**: 사용자에게 "PMI 대신 산업생산 사용" 명시

### 2. ECOS 통계 코드 변경
- **문제**: 한국은행이 통계 분류 개편 시 코드 변경
- **대응**: 매월 1회 코드 유효성 검증 스크립트
- **대응**: 변경 감지 시 알림 + 매핑 업데이트

### 3. 사이클 판정의 후행성
- **문제**: 매크로 지표는 **발표가 후행함** (한 달~분기 지연)
- **예**: 12월 GDP는 다음 분기 1~2월에 발표
- **대응**: 응답에 "최근 발표 데이터 기준" 명시
- **대응**: 시장 가격 (Treasury yields, DXY)는 실시간이므로 보조 활용

### 4. 매크로 국면 명확하지 않은 시기
- **문제**: 전환기에는 4개 사이클이 충돌
- **대응**: confidence < 0.5 시 "전환기" 표시
- **대응**: 매크로 PM 페르소나에서 "혼재 국면" 설명

### 5. 한국 vs 미국 국면 차이
- **문제**: 미국이 Stagflation, 한국이 Recovery일 수 있음
- **대응**: 두 국가 별도 판정 + Korean Specialist에서 한국 우선
- **대응**: 글로벌 매크로 PM은 미국 우선 + 한국 보조

---

## 📊 예상 작업량

```
Day 1: FRED API 연동 + 핵심 시리즈 수집 모듈
       - FREDClient 클래스
       - 1년 백필 테스트
       
Day 2: ECOS API 연동 + 핵심 통계 수집
       - ECOSClient 클래스
       - 통계 코드 매핑 검증
       
Day 3: 4대 사이클 판정 모듈
       - 금리/경기/통화/인플레 detector
       - 단위 테스트 (경계값)
       
Day 4: 6대 국면 매핑 + 캘린더
       - regime_detector 구현
       - macro_calendar.json 생성
       
Day 5: 일일 수집 Job + Firestore 쓰기
       - Cloud Run Job 스케줄
       - reviewer 검증
```

**총 5일 (Week B)**.

**비용**:
- FRED/ECOS: 무료
- yfinance: 무료
- Firestore 쓰기: 매일 ~30 doc (지표 수) → 월 $0.005 미만
- **사실상 무료**
