# Stock Screener Pro v6.0 — 기관급 분석 개선 계획

> 골드만삭스/블랙록 애널리스트 관점 기반
> 작성: 2026-04-07 | 기준 버전: v5.5 (rev 00031)

---

## 현재 시스템 요약

- **스택**: FastAPI + Firestore + Cloud Run (readonly) + Cloud Scheduler (20 cron)
- **데이터**: FDR(KR OHLCV) + yfinance(US) + Naver(펀더멘탈/테마) + pykrx/Naver(수급)
- **지표**: MA5/20/60, RSI(Wilder), 52주고저, 골든크로스, 매집, 돌파, buy_score(0-100)
- **카테고리**: 16개 (전략 7 + 시장 5 + 시그널 4)
- **수집 주기**: heavy 4회/일 + light KR 6회 + light US 3회

---

## Phase 1: 시그널 신뢰도 확보

### 1-1. 다기간 수익률 검증

**파일**: `screener/core/backtest.py`

**현재**: 5일 수익률만 계산, 5개 시그널(golden_cross, accumulation, rsi_oversold, ma_squeeze, volume_trend)

**변경**:
```python
# 현재 구조
FORWARD_DAYS = 5  # 고정

# 변경 후
FORWARD_WINDOWS = [5, 10, 20, 60]  # 다기간

# 각 시그널마다:
# - hit_rate: 양수 수익률 비율 (%)
# - avg_return: 평균 수익률 (%)
# - median_return: 중앙값 수익률
# - profit_factor: 총이익 / 총손실
# - max_drawdown: 최대 낙폭
# - sample_count: 샘플 수
# - sharpe: (avg_return - risk_free) / std_return (연율화)
```

**추가할 시그널 검증**:
- `pre_surge_score >= 4` (급등예보)
- `buy_score >= 70` (적극매수 등급)
- `buy_score >= 50` (매수 등급)
- `breakout_score >= 3` (돌파 임박)
- `foreign_net > 0 AND inst_net > 0` (수급 동반 매수)

### 1-2. buy_score 이력 저장

**파일**: `screener/db/repository.py`, `collector.py`

**신규 Firestore 컬렉션**: `score_history/{date}`
```
{
  date: "2026-04-07",
  scores: {
    "005930": { buy_score: 72, buy_grade: "적극매수", close: 196500 },
    "000660": { buy_score: 45, buy_grade: "관심", close: 185000 },
    ...
  }
}
```

**구현**:
- `collector.py`의 heavy 스케줄(16:00 KST, 장 마감 후)에서 일 1회 저장
- `repository.py`에 `save_score_history(date, scores_dict)` 함수 추가
- 30일 보존 (이전 데이터 자동 삭제)

### 1-3. 벤치마크 대비 초과수익

**파일**: `screener/core/backtest.py`

**구현**:
```python
# KOSPI/S&P500 인덱스 수익률 수집
# FDR: StockDataReader("KS11") → KOSPI, StockDataReader("US500") → S&P500

# 각 시그널의 N일 수익률에서 같은 기간 인덱스 수익률을 빼면 = 알파
# alpha = signal_return - benchmark_return
```

### 1-4. UI: 시그널 성적표

**파일**: `screener/static/index.html`, `screener/api/routes.py`

**현재**: 백테스트 모달에 hit_rate%, avg_return%, sample_count만 표시

**변경**:
- 각 시그널 카드에 5/10/20/60일 수익률 탭 추가
- profit_factor, max_drawdown 표시
- 벤치마크 대비 알파 표시
- "이 시그널을 매번 따랐다면 연 X% 수익" 연율화 수치

**API 응답 확장**:
```json
GET /api/backtest
{
  "signals": {
    "golden_cross": {
      "windows": {
        "5d":  { "hit_rate": 62, "avg_return": 1.8, "alpha": 0.9, "sharpe": 1.2, "samples": 145 },
        "20d": { "hit_rate": 58, "avg_return": 3.5, "alpha": 1.5, "sharpe": 0.9, "samples": 145 }
      }
    }
  },
  "score_tracking": {
    "buy_70plus": { "20d_avg_return": 4.2, "hit_rate": 68, "alpha": 2.1 },
    "buy_50plus": { "20d_avg_return": 2.8, "hit_rate": 61, "alpha": 1.2 }
  }
}
```

---

## Phase 2: 수급 분석 고도화

### 2-1. 외국인 연속 매수 일수

**파일**: `screener/core/metrics.py`, `screener/db/repository.py`

**신규 Firestore 컬렉션**: `supply_history/{ticker}`
```
{
  data: [
    { date: "2026-04-07", foreign_net: 577919, inst_net: 0 },
    { date: "2026-04-06", foreign_net: 1672994, inst_net: 1198443 },
    ...
  ]
}
```

**계산 (metrics.py)**:
```python
def calculate_supply_signals(df, supply_history):
    # foreign_consecutive_days: 외국인 연속 순매수 일수 (음수면 연속 순매도)
    # supply_intensity: foreign_net / trading_value (수급 강도 %)
    # dual_buy: foreign_net > 0 AND inst_net > 0 (동반 매수 플래그)
```

**신규 필드 (schemas.py)**:
- `foreign_consecutive: int` — 외국인 연속 매수 일수 (음수=연속 매도)
- `supply_intensity: float` — 수급 강도 (거래대금 대비 %)
- `dual_buy: bool` — 외국인+기관 동반 매수

### 2-2. 수급 강도 등급

**파일**: `screener/core/metrics.py`

```python
# supply_grade 계산:
# - "강력매수": foreign_consecutive >= 5 AND dual_buy
# - "매수세": foreign_consecutive >= 3 OR supply_intensity > 10%
# - "중립": foreign_consecutive 0 근처
# - "매도세": foreign_consecutive <= -3
# - "강력매도": foreign_consecutive <= -5 AND inst 매도
```

### 2-3. 시장 전체 수급 게이지

**파일**: `screener/api/routes.py`, `screener/static/index.html`

**API**: `GET /api/market-sentiment`
```json
{
  "kr": {
    "foreign_buy_ratio": 0.42,      // 외국인 순매수 종목 비율
    "foreign_total_net": 3200000000, // 전체 외국인 순매수 합계 (원)
    "inst_buy_ratio": 0.38,
    "advance_decline": 1.35,         // 상승/하락 비율
    "above_ma20_ratio": 0.55,        // 20일선 위 종목 비율
    "sentiment": "매수 우위"
  }
}
```

**UI**: 헤더 영역 또는 결과 상단에 게이지 바 표시
```
외국인 매수세 ████████░░ 62%   기관 매수세 ██████░░░░ 42%
```

### 2-4. pykrx 기관 유형별 분리 (pykrx 정상화 시)

**파일**: `screener/core/data_fetcher.py`

```python
# pykrx detail=True 옵션:
# 금융투자, 보험, 투신, 사모, 은행, 기타금융, 연기금등
# 핵심: 연기금 vs 투신 방향이 다를 때가 중요 시그널

# 신규 필드:
# pension_net: 연기금 순매수 (장기 투자자)
# trust_net: 투신 순매수 (단기 매매)
```

---

## Phase 3: 펀더멘탈 깊이 확장

### 3-1. yfinance 추가 데이터 수집

**파일**: `screener/core/data_fetcher.py` — `fetch_us_snapshot()` 내 `_fetch_info()` 함수

**현재 수집하는 yfinance 필드**:
```python
# pe_ratio, pb_ratio, dividend_yield, roe (이미 수집)
# sector, industry (이미 수집)
```

**추가 수집할 필드**:
```python
info = ticker.info
new_fields = {
    "forward_pe": info.get("forwardPE", 0),
    "peg_ratio": info.get("pegRatio", 0),
    "ev_ebitda": info.get("enterpriseToEbitda", 0),
    "profit_margin": info.get("profitMargins", 0) * 100,      # %
    "operating_margin": info.get("operatingMargins", 0) * 100, # %
    "fcf_yield": 0,  # freeCashflow / marketCap * 100
    "debt_equity": info.get("debtToEquity", 0),
    "revenue_growth": info.get("revenueGrowth", 0) * 100,     # %
    "target_price": info.get("targetMeanPrice", 0),
    "target_upside": 0,  # (target_price - close) / close * 100
}
```

**한국 주식**: Naver Finance에서 추가 수집 가능한 것
- EPS (이미 수집하지만 미적용 → 적용 필요)
- 영업이익률: `finance.naver.com/item/main.naver?code={ticker}` 재무제표 테이블

### 3-2. schemas.py 필드 추가

```python
class StockItem(BaseModel):
    # 기존 필드...
    
    # Phase 3 신규
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
```

### 3-3. buy_score 가치 팩터 강화

**파일**: `screener/core/metrics.py` — `calculate_buy_score()`

**현재 가치 팩터 (15점)**:
- PER 범위 (6~8점)
- PBR 범위 (6~7점)

**변경 (15점, 더 정교한 배분)**:
```python
# PER 적정 범위: 4점
# PBR < 1.0: 3점
# EV/EBITDA < 10: 3점 (신규)
# FCF Yield > 5%: 3점 (신규)
# 목표주가 괴리율 > 20%: 2점 (신규)
```

### 3-4. 카테고리 확장

**파일**: `screener/core/screener.py`

**신규 카테고리 "quality" (퀄리티주)**:
```python
"quality": {
    "name": "퀄리티주", "group": "strategy",
    "desc": "높은 수익성 + 낮은 부채 + 안정 성장",
    "filter": ScreenerFilter(
        profit_margin_min=10, debt_equity_max=100,
        revenue_growth_min=5, market_cap_min=1000,
    ),
    "columns": ["profit_margin", "operating_margin", "debt_equity", 
                 "revenue_growth", "fcf_yield", "ev_ebitda"],
}
```

### 3-5. UI 종목 상세 모달 확장

**파일**: `screener/static/index.html` — `showStockDetail()`

모달 그리드에 탭 추가:
- **기본**: 현재 항목 (시총, PER, PBR, RSI 등)
- **펀더멘탈**: EV/EBITDA, 영업이익률, FCF, 부채비율, 성장률
- **수급**: 외국인/기관 연속일수, 강도, 동반매수

---

## Phase 4: 리스크 프레임워크

### 4-1. 포지션 사이징 제안

**파일**: `screener/core/metrics.py`

```python
def calculate_position_size(atr, account_size, risk_pct=0.02):
    """ATR 기반 적정 투자 비중 (간소화 켈리)"""
    # risk_per_share = atr * 2 (2ATR 손절 기준)
    # shares = (account_size * risk_pct) / risk_per_share
    # position_pct = (shares * close) / account_size * 100
    return position_pct  # "총 자산의 X% 투자 권장"
```

### 4-2. 관심종목 상관관계

**파일**: `screener/api/routes.py`, `screener/static/index.html`

**API**: `POST /api/portfolio/risk`
```json
{
  "tickers": ["005930", "000660", "035720"],
  "correlation_matrix": [[1.0, 0.72, 0.45], ...],
  "portfolio_volatility": 22.5,
  "sector_concentration": { "반도체": 67, "게임": 33 },
  "risk_warning": "반도체 섹터 67% 집중 — 분산 권장"
}
```

**계산**: history OHLCV에서 일간 수익률 → 피어슨 상관계수 행렬

### 4-3. 시장 레짐 감지

**파일**: `screener/core/metrics.py`

```python
def detect_market_regime(index_history):
    """시장 레짐 판별: 강세/약세/횡보"""
    # KOSPI/S&P500 인덱스 기준
    # 1. 20일 MA 위/아래
    # 2. 60일 MA 방향 (상승/하락)
    # 3. 등락비율 (ADR)
    # 4. 신고가-신저가 차이
    
    # regime: "bull" / "bear" / "sideways"
    # confidence: 0.0 ~ 1.0
```

### 4-4. 레짐별 전략 가중치 조정

**파일**: `screener/core/screener.py` 또는 `routes.py`

```python
REGIME_WEIGHTS = {
    "bull":     {"surge": 1.0, "momentum": 1.2, "turnaround": 0.5, "value": 0.8},
    "bear":     {"surge": 0.5, "momentum": 0.3, "turnaround": 1.5, "value": 1.2},
    "sideways": {"surge": 0.8, "momentum": 0.7, "turnaround": 1.0, "value": 1.0},
}
# buy_score 또는 카테고리 정렬에 레짐 가중치 적용
```

### 4-5. 섹터 편중 경고

**파일**: `screener/api/routes.py`

scan 결과에 섹터 분포 포함:
```json
{
  "stocks": [...],
  "sector_distribution": { "반도체": 35, "바이오": 22, "금융": 15, ... },
  "concentration_warning": "반도체 섹터 35% — 분산 투자 고려"
}
```

---

## Phase 5: 차별화 기능

### 5-1. 종목 비교

**API**: `GET /api/compare?tickers=005930,000660,035720`
**UI**: 2~3개 종목 나란히 비교 테이블 + 차트 오버레이

### 5-2. 스마트 알림

**파일**: `collector.py`

복합 조건 알림:
```python
SMART_ALERTS = [
    {
        "name": "외국인 연속매수 + 기술적 반등",
        "condition": "foreign_consecutive >= 5 AND rsi <= 40 AND golden_cross == 1",
    },
    {
        "name": "수급 동반 + 실적 서프라이즈",
        "condition": "dual_buy AND target_upside > 20",
    },
]
```

### 5-3. 섹터 로테이션 맵

**API**: `GET /api/sector-flow`
**데이터**: 섹터별 외국인/기관 순매수 합계 추이 (최근 5일)
**UI**: 버블 차트 또는 히트맵 (자금 유입 섹터 = 녹색, 유출 = 빨강)

### 5-4. 실적 캘린더

**데이터**: yfinance `earningsDate` 또는 DART API
**UI**: D-7 ~ D+1 실적 발표 종목 하이라이트 + 컨센서스 대비 괴리

---

## 파일별 수정 범위 요약

| 파일 | Phase 1 | Phase 2 | Phase 3 | Phase 4 | Phase 5 |
|------|---------|---------|---------|---------|---------|
| `screener/core/backtest.py` | **전면 개편** | - | - | - | - |
| `screener/core/metrics.py` | - | 수급 시그널 | buy_score 가치 | 포지션/레짐 | - |
| `screener/core/data_fetcher.py` | 인덱스 수집 | 수급 이력 | yfinance 확장 | - | 섹터 플로우 |
| `screener/core/screener.py` | - | - | quality 카테고리 | 레짐 가중치 | - |
| `screener/db/repository.py` | score_history | supply_history | 신규 필드 저장 | - | - |
| `screener/api/schemas.py` | backtest 모델 | 수급 필드 | 펀더멘탈 필드 | 리스크 모델 | 비교 모델 |
| `screener/api/routes.py` | /backtest 확장 | /market-sentiment | /scan 확장 | /portfolio/risk | /compare, /sector-flow |
| `screener/static/index.html` | 성적표 UI | 수급 게이지 | 모달 탭 | 리스크 대시보드 | 비교/알림 UI |
| `collector.py` | score 저장 | supply 저장 | 펀더멘탈 확장 | - | 스마트 알림 |
| `requirements.txt` | - | - | - | numpy (상관계수) | - |

---

## 구현 순서 (권장)

```
Phase 1-1: backtest.py 다기간 수익률 (backtest 전면 개편)
Phase 1-2: score_history Firestore 저장 (collector + repository)
Phase 1-3: 벤치마크 대비 알파 (backtest + data_fetcher)
Phase 1-4: UI 시그널 성적표 (index.html + routes)
  ↓
Phase 2-1: supply_history 저장 + 연속 매수 일수 (repository + metrics)
Phase 2-2: 수급 강도 등급 (metrics + schemas)
Phase 2-3: 시장 수급 게이지 API + UI (routes + index.html)
  ↓
Phase 3-1: yfinance 추가 필드 수집 (data_fetcher)
Phase 3-2: schemas + routes 필드 추가
Phase 3-3: buy_score 가치 팩터 강화 (metrics)
Phase 3-4: quality 카테고리 추가 (screener)
Phase 3-5: 모달 펀더멘탈 탭 (index.html)
  ↓
Phase 4-1: 포지션 사이징 (metrics)
Phase 4-2: 상관관계 + 섹터 편중 (routes)
Phase 4-3: 시장 레짐 감지 (metrics + data_fetcher)
Phase 4-4: 레짐별 전략 가중치 (screener)
  ↓
Phase 5: 종목비교, 스마트알림, 섹터맵, 실적캘린더
```

---

## 참고: 현재 데이터 소스 한계

- **pykrx**: 2025.12 KRX 회원제 전환으로 불안정. 네이버 frgn.naver 폴백 중 (외국인만, 기관 X)
- **yfinance**: US 종목은 풍부한 펀더멘탈 제공. KR 종목은 제한적
- **Naver Finance**: PER/PBR/배당 + 테마. 장 마감 후 sise_deal 빈 데이터
- **FDR**: KR OHLCV 안정적. US는 yfinance가 더 풍부
- **Firestore**: 무료 티어 일 20K 쓰기, 50K 읽기. score_history 30일 보관이면 충분
