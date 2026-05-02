# 이벤트 데이터 인프라 상세 스펙

> **목적**: Event Analyst 페르소나에 필요한 이벤트 캘린더, 옵션/신용/공매도, 유사 이벤트 추론 시스템 설계
> **위치**: `docs/data_infra/event.md`
> **연관**: `docs/personas/event.md`, `docs/v2_roadmap/WEEK_C.md`

---

## 📋 수집 데이터 5종

| # | 데이터 | 소스 | 빈도 | 우선순위 |
|---|--------|------|------|---------|
| 1 | 매크로 이벤트 캘린더 (FOMC, CPI, GDP) | 정적 + Fed 사이트 | 분기 갱신 | 🔴 최우선 |
| 2 | 기업 이벤트 캘린더 (실적/배당/IPO) | DART + EDGAR | 실시간 | 🔴 최우선 |
| 3 | 옵션 시장 데이터 (IV, Put/Call) | yfinance + KRX | 일별 | 🟠 높음 |
| 4 | 신용잔고 + 공매도 | pykrx (한국) + FINRA (미국) | 일별/격주 | 🟠 높음 |
| 5 | 유사 이벤트 LLM 추론 시스템 | Claude API + 캐싱 | on-demand | 🟡 중간 |

---

## 1. 매크로 이벤트 캘린더

⚠️ **중복 회피**: `docs/data_infra/macro.md`의 `data/macro_calendar.json` 그대로 활용.

추가로 이벤트 페르소나 전용으로 필요한 것:

### 1.1 이벤트 메타데이터 확장

```python
# data/macro_event_metadata.json (Event Analyst 전용)

{
  "FOMC": {
    "event_type": "central_bank_meeting",
    "country": "US",
    "typical_volatility_window": {
      "before": "D-3",
      "after": "D+1"
    },
    "historical_avg_abs_return_d_minus_3_to_d_plus_1": 1.8,  # %
    "historical_std_dev": 1.2,
    "key_assets_affected": ["SPY", "TLT", "DXY", "GLD", "VIX"],
    "kr_assets_affected": ["KOSPI", "KOSDAQ", "USD/KRW"]
  },
  "US_CPI": {
    "event_type": "macro_release",
    "country": "US",
    "typical_volatility_window": {
      "before": "D-1",
      "after": "D"
    },
    "historical_avg_abs_return_d": 0.9,
    "historical_std_dev": 1.5,
    "surprise_threshold_for_reaction": 0.2  # %p (예상치 vs 발표치 차이)
  },
  ...
}
```

### 1.2 활용 logic

```python
def get_event_meta(event_type: str) -> dict:
    """이벤트 타입별 통계 메타 조회"""
    with open("data/macro_event_metadata.json") as f:
        meta = json.load(f)
    return meta.get(event_type, {})
```

---

## 2. 기업 이벤트 캘린더

### 2.1 한국 기업 이벤트 (DART)

**소스**: DART API (`docs/data_infra/korea_market.md`의 자사주 파싱과 같은 API 활용)

**관심 공시 유형**:
- 실적 발표 (분기/반기/사업보고서)
- 자사주 매입/소각 결정
- M&A 공시 (합병, 분할, 인수)
- 신주 발행 / 전환사채 / BW
- 공시 의무 위반 (사후 분석)

```python
# utils/data_collectors/dart_event_collector.py

DART_EVENT_TYPES = {
    "performance": "분기보고서|반기보고서|사업보고서",
    "buyback_decision": "자기주식취득결정",
    "buyback_burn": "주식소각결정",
    "ma_decision": "회사합병결정|회사분할결정|영업양수도결정",
    "new_shares": "유상증자결정|무상증자결정",
    "convertible_bond": "전환사채발행결정|신주인수권부사채발행결정",
}

async def fetch_dart_events_for_ticker(
    ticker: str,
    start_date: str,
    end_date: str,
    event_types: Optional[list] = None,
) -> list:
    """종목별 기업 이벤트 조회"""
    pass
```

### 2.2 미국 기업 이벤트 (EDGAR + yfinance)

**소스 1: yfinance — 실적/배당 일정 (실제 1.3.0 검증)**
```python
import yfinance as yf

ticker = yf.Ticker("RKLB")

# 다음 실적 발표일 + 배당락
calendar = ticker.calendar  # dict 형태 (이전 DataFrame에서 변경됨)
# 또는
calendar = ticker.get_calendar()

# 실적 발표 이력 + 예정 (권장)
earnings_dates = ticker.earnings_dates  # DataFrame: Reported EPS, Estimate, Surprise
# 또는
earnings_dates = ticker.get_earnings_dates(limit=12)

# 배당 이력
dividends = ticker.dividends  # Series

# ⚠️ quarterly_earnings는 deprecated 가능, 권장 대안:
quarterly_income = ticker.quarterly_income_stmt  # 분기 손익 전체
```

**소스 2: SEC EDGAR — 8-K 등 주요 공시**
```python
import httpx

EDGAR_BASE = "https://data.sec.gov/submissions/CIK"

async def fetch_recent_8k(cik: str) -> list:
    """최근 8-K 공시 (M&A, 경영진 변경, 실적 수정 등)"""
    url = f"{EDGAR_BASE}{cik:0>10}.json"
    async with httpx.AsyncClient(headers={"User-Agent": "Axis Research..."}) as c:
        resp = await c.get(url)
        # 8-K 필터링
        pass
```

⚠️ **EDGAR 헤더 요구사항**: User-Agent에 이메일 필수. 위반 시 차단.

### 2.3 IPO 캘린더

**한국 IPO**: 한국거래소 상장공시 (DART와 별도)
**미국 IPO**: 
- SEC S-1 공시 (`https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&type=S-1`)
- 또는 ipohub, NASDAQ IPO 캘린더 사이트 크롤링 (회색지대)

⚠️ **현실적 권장**:
- IPO는 자동 수집보다 **수동 큐레이션 + LLM 보조**
- "예정된 주요 IPO" 케이스만 사용자/관리자가 추가
- `data/upcoming_ipo.json` 정적 파일

```python
# data/upcoming_ipo.json
[
  {
    "company": "SpaceX",
    "ticker": "(unlisted)",
    "expected_market": "NYSE",
    "expected_date_range": "2026 Q4",
    "certainty_score": 7,
    "secondary_beneficiaries": ["RKLB", "ASTS", "IRDM"],
    "added_at": "2026-04-01"
  }
]
```

---

## 3. 옵션 시장 데이터

### 3.1 미국 옵션 (yfinance — 종목별 풍부, 1.3.0 검증)

```python
import yfinance as yf

ticker = yf.Ticker("RKLB")

# 만기일 목록 (튜플 반환)
expirations = ticker.options  # ('2026-01-19', '2026-02-16', ...)

# 특정 만기 옵션 체인
# ⚠️ option_chain(date=None, tz=None) — date가 첫 인자
opt_chain = ticker.option_chain("2026-01-19")
calls = opt_chain.calls    # DataFrame
puts = opt_chain.puts

# 주요 컬럼: contractSymbol, strike, lastPrice, bid, ask, change,
#           percentChange, volume, openInterest, impliedVolatility,
#           inTheMoney, contractSize, currency
```

**계산 가능한 신호**:

```python
async def calculate_options_signals(ticker: str) -> dict:
    """옵션 시장 신호 계산"""
    yf_ticker = yf.Ticker(ticker)
    
    if not yf_ticker.options:
        return {"available": False, "reason": "옵션 거래 없음"}
    
    # 가장 가까운 만기 (1-2개월)
    nearest_expiration = yf_ticker.options[0]
    chain = yf_ticker.option_chain(nearest_expiration)
    
    # Put/Call ratio (거래량 기준)
    call_volume = chain.calls["volume"].sum()
    put_volume = chain.puts["volume"].sum()
    pcr_volume = put_volume / call_volume if call_volume > 0 else None
    
    # Put/Call ratio (미결제 기준)
    call_oi = chain.calls["openInterest"].sum()
    put_oi = chain.puts["openInterest"].sum()
    pcr_oi = put_oi / call_oi if call_oi > 0 else None
    
    # ATM IV (현재가 ± 5% 근처)
    current_price = yf_ticker.info.get("currentPrice", 0)
    atm_calls = chain.calls[
        (chain.calls["strike"] >= current_price * 0.95) &
        (chain.calls["strike"] <= current_price * 1.05)
    ]
    atm_iv = atm_calls["impliedVolatility"].mean() if len(atm_calls) > 0 else None
    
    return {
        "available": True,
        "expiration": nearest_expiration,
        "put_call_ratio_volume": round(pcr_volume, 2) if pcr_volume else None,
        "put_call_ratio_oi": round(pcr_oi, 2) if pcr_oi else None,
        "atm_iv_pct": round(atm_iv * 100, 2) if atm_iv else None,
        "interpretation": interpret_options(pcr_volume, atm_iv)
    }


def interpret_options(pcr: Optional[float], iv: Optional[float]) -> str:
    """옵션 신호 해석"""
    if pcr is None or iv is None:
        return "데이터 부족"
    
    if pcr > 1.2:
        return "Put 우세 — 헷징/하락 베팅 우세 (역발상 가능 신호)"
    elif pcr < 0.7:
        return "Call 우세 — 강세 베팅 우세 (정점 가능 경계)"
    else:
        return "균형 — 명확한 방향성 신호 부재"
```

### 3.2 한국 옵션 (KRX — 코스피200만)

⚠️ **한국 개별 종목 옵션은 거래량이 매우 적어 의미 X**
- KRX에서 코스피200 옵션만 IV/PCR 활용
- pykrx에 옵션 함수 있으나 시장 전체 지표만

```python
from pykrx import stock

# 사용 가능한 옵션 함수 검증 필요
# stock.get_index_ohlcv_by_date 등으로 코스피200 + VKOSPI 활용
```

**대안**: VKOSPI (코스피200 변동성 지수) 활용
- yfinance ticker: `^VKOSPI` (시도 필요)
- 또는 KRX 웹페이지 크롤링

⚠️ **검증 필요 항목**: VKOSPI를 무료로 자동 수집할 수 있는지

### 3.3 Firestore 스키마

```python
# Collection: options_signals
# Document ID: {ticker}_{date}

{
    "ticker": "RKLB",
    "date": "20251231",
    "available": true,
    "nearest_expiration": "2026-01-19",
    "put_call_ratio_volume": 0.62,
    "put_call_ratio_oi": 0.78,
    "atm_iv_pct": 85.2,
    "iv_30d_avg": 65.0,
    "iv_change_pct": 31.1,  # vs 30일 평균
    "interpretation": "Call 우세 + IV 상승 = 옵션 시장에서 변동성 확대 베팅 관찰됨, 선행 신호 가능성",
    "data_source": "yfinance",
    "collected_at": "..."
}
```

---

## 4. 신용잔고 + 공매도

⚠️ **중복 회피**: `docs/data_infra/korea_market.md`의 공매도 부분과 같음.

### 4.1 한국 — 이미 Week A에서 처리

`utils/data_collectors/short_selling.py` 모듈 그대로 재사용.

### 4.2 미국 — FINRA 데이터

**소스**: FINRA (Financial Industry Regulatory Authority)
- 격주 발표 (월 2회)
- 무료 데이터: https://www.finra.org/finra-data/short-sale-volume-data

**대안 — yfinance**:
```python
import yfinance as yf

ticker = yf.Ticker("RKLB")
info = ticker.info

# 공매도 관련 필드
short_data = {
    "shortRatio": info.get("shortRatio"),  # Days to Cover
    "shortPercentOfFloat": info.get("shortPercentOfFloat"),
    "sharesShort": info.get("sharesShort"),
    "sharesShortPriorMonth": info.get("sharesShortPriorMonth"),
}
```

⚠️ **yfinance 필드 신뢰도**: 무료 데이터는 격주 발표 → 약간의 지연 있음

### 4.3 신용잔고 — 미국은 어려움

미국 시장은 **종목별 신용잔고 데이터 무료 부재**
- Margin Debt 시장 전체는 FINRA 발표
- 종목별은 유료 (FactSet, Refinitiv)

**대응**: 미국 종목 분석 시 "신용잔고 데이터 부재" 명시

---

## 5. 유사 이벤트 LLM 추론 시스템 (옵션 C Phase 1)

### 5.1 핵심 아이디어

자체 이벤트 통계 DB 구축은 5주 내 불가능 → **Claude API로 유사 이벤트 추론**.

⚠️ **주의**: LLM이 fabricate(거짓 통계 만들어냄) 위험 → 명시적 한계 표시 필수.

### 5.2 추론 프롬프트 패턴

```python
SIMILAR_EVENT_PROMPT = """
당신은 이벤트 트레이딩 전문가입니다.
다음 이벤트와 유사한 과거 사례를 찾아 통계를 추정하세요.

**현재 이벤트**:
- 종류: {event_type}
- 대상: {event_target}
- 1차 수혜: {primary}
- 2차 수혜 분석 대상: {secondary_ticker}

**작업**:
1. 비슷한 카테고리의 과거 5-15개 사례를 학습 데이터에서 식별
2. 각 사례의 D-30 ~ D-day 평균 수익률 추정
3. 표준편차 추정
4. **표본 수가 5개 미만이면 반드시 "표본 부족"으로 표시**

**출력 형식 (JSON)**:
{{
  "comparable_events": [
    {{
      "event": "Uber IPO 2019.05",
      "primary": "UBER",
      "secondary": "LYFT",
      "secondary_d_minus_60_to_d_day_return_pct": "+22%",
      "data_confidence": "high"  // high | medium | low (LLM 학습 데이터 신뢰도)
    }},
    ...
  ],
  "sample_size": 11,
  "sample_reliability": "✅ 통계 신뢰 가능" | "⚠️ 표본 부족",
  "fabrication_warning": "위 수치는 LLM 학습 데이터 기반 추정이며 실제 수치와 차이 있을 수 있습니다",
  "verification_needed": [
    "각 사례의 실제 D-60~D-day 수익률 외부 검증 권장",
    "표본 수가 적을수록 통계 신뢰도 낮음"
  ]
}}
"""
```

### 5.3 캐싱 전략

```python
# utils/event_inference_cache.py

import hashlib
from utils.cache import default_cache

async def get_similar_events_cached(
    event_type: str,
    event_target: str,
    primary: str,
    secondary_ticker: str,
) -> dict:
    """캐시된 유사 이벤트 추론"""
    cache_key = hashlib.md5(
        f"{event_type}|{event_target}|{primary}|{secondary_ticker}".encode()
    ).hexdigest()
    
    cached = await default_cache.get(cache_key)
    if cached:
        return cached
    
    # Claude 호출
    result = await claude_client.complete(
        system="...",
        messages=[{"role": "user", "content": SIMILAR_EVENT_PROMPT.format(...)}],
        response_format="json"
    )
    
    parsed = json.loads(result.content)
    
    # 24시간 캐시 (같은 이벤트는 자주 분석되지 않음)
    await default_cache.set(cache_key, parsed, ttl=86400)
    return parsed
```

### 5.4 검증 — LLM 추론의 한계

⚠️ **반드시 응답에 표시**:
1. "LLM 학습 데이터 기반 추정" 명시
2. "각 사례 외부 검증 권장"
3. 표본 수 < 5: "통계 미제시, 정성 분석만"
4. 표본 수 5-9: "표본 부족 — 참고용"
5. 표본 수 ≥ 10: "통계 신뢰 가능" (단, fabrication 경고 유지)

### 5.5 Phase 2 계획 (베타 후)

자체 DB 구축은 베타 후 사용자 피드백 보고 결정.
- 자주 분석되는 TOP 10 이벤트 카테고리 우선
- 학계 Event Study 논문 데이터 활용
- 1년 자체 backtest로 검증 후 LLM 추론 대체

---

## 📂 파일 구조 요약

```
axis/
├── data/
│   ├── macro_calendar.json          # Week B와 공유
│   ├── macro_event_metadata.json    # Event Analyst 전용
│   └── upcoming_ipo.json            # 수동 큐레이션
│
├── utils/data_collectors/
│   ├── dart_event_collector.py      # 한국 기업 이벤트
│   ├── edgar_collector.py           # 미국 기업 이벤트 (8-K)
│   ├── yfinance_event_collector.py  # 미국 실적/배당
│   ├── options_signals.py           # 옵션 IV/PCR 계산
│   └── event_inference_cache.py     # 유사 이벤트 LLM 추론 + 캐싱
│
├── jobs/
│   ├── daily_options_collect.py     # 일일 옵션 데이터
│   └── weekly_event_calendar_sync.py # 주간 이벤트 캘린더 갱신
│
└── tests/data_collectors/
    ├── test_options_signals.py
    └── test_event_inference.py
```

---

## 🧪 검증 체크리스트

각 모듈 작성 후 reviewer subagent에 검증 요청:

- [ ] yfinance 옵션 체인 구조 정확
- [ ] EDGAR User-Agent 헤더 포함
- [ ] DART 이벤트 분류 정확
- [ ] 옵션 IV 계산 단위 (소수 vs 퍼센트)
- [ ] LLM 추론 결과에 fabrication 경고 자동 첨부
- [ ] 캐시 키 충돌 없는지
- [ ] 표본 수 임계값 (10/5) 일관 적용
- [ ] Korean Specialist의 공매도 모듈 중복 없는지

---

## ⚠️ 알려진 위험 + 대응

### 1. yfinance 데이터 안정성
- yfinance는 비공식 (Yahoo Finance 스크래핑)
- **간헐적 차단/지연 발생**
- 대응: try-except + 캐시 폴백 + 사용자에게 "데이터 일시 부재" 표시

### 2. EDGAR User-Agent 차단
- 헤더 누락 시 즉시 차단
- 대응: User-Agent 강제 (`"Axis Research <email>"`)
- rate limit: 10 requests/sec

### 3. LLM Fabrication
- Claude가 그럴듯한 가짜 사례 만들어낼 위험
- **대응 1**: 표본 수 명시 + 외부 검증 권장
- **대응 2**: data_confidence 필드로 사례별 신뢰도 표시
- **대응 3**: 베타 사용자에게 "통계 추정값" 명시

### 4. 한국 옵션 데이터 한정
- KRX 개별 종목 옵션 거래량 적음
- 대응: 코스피200/VKOSPI만 시장 신호로 활용
- 개별 한국 종목엔 옵션 신호 없음 명시

### 5. IPO 캘린더 자동화 어려움
- 신뢰할 수 있는 무료 IPO 캘린더 부재
- 대응: 수동 큐레이션 + LLM 보조

### 6. 미국 신용잔고 데이터 부재
- yfinance는 일부만, 정확도 ↓
- 대응: 미국 종목엔 "신용잔고 분석 제외" 명시

---

## 📊 예상 작업량

```
Day 1: yfinance 옵션 시그널 모듈 + 캐싱
       - calculate_options_signals 구현
       - 한국 코스피200/VKOSPI 보조

Day 2: DART 이벤트 수집 (Week A 자사주 모듈 확장)
       - dart_event_collector.py
       - EDGAR 8-K 수집

Day 3: 매크로 이벤트 메타 + IPO 큐레이션
       - macro_event_metadata.json
       - upcoming_ipo.json 초기 데이터

Day 4: LLM 유사 이벤트 추론 시스템
       - event_inference_cache.py
       - 프롬프트 + 캐싱

Day 5: 일일 수집 Job + Reviewer 검증
       - Cloud Run Job 스케줄
       - 회귀 테스트
```

**총 5일 (Week C)**.

**비용**:
- yfinance: 무료
- DART: 무료 (10K 호출/일 한도)
- EDGAR: 무료
- Claude LLM 유사 이벤트 추론: ~50원/호출 × 100 캐시 미스/일 = **월 ~150,000원**
  - 캐시 적중률 80% 가정 시 **월 ~30,000원**
- Firestore: 추가 무시 가능 수준
