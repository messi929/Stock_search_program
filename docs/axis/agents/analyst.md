# Analyst Agent

> **역할**: 종목의 숫자를 뜯어보는 주식 애널리스트

---

## 📋 기본 정보

| 항목 | 값 |
|------|-----|
| **모델** | `claude-sonnet-4-6` |
| **예상 비용** | ~35원/쿼리 |
| **응답 시간 목표** | < 4초 |
| **캐시 TTL** | 30분 |

---

## 🎯 책임 범위

### 담당
- 기술적 분석 해석 (이미 계산된 RSI, 이평선, 52주 고저)
- 펀더멘털 해석 (PER, PBR, ROE, 배당수익률)
- 섹터 내 peer 비교
- Buy Score 해석 (기존 시스템 자산)

### 담당 X
- 시황/뉴스 (→ Research)
- 가격 검증 (→ Validator)
- 페르소나 적용 (→ Strategist)

---

## 💎 핵심 차별점: "이미 계산된 데이터의 해석가"

기존 `screener/core/metrics.py`에서 이미 계산된 지표:
- `buy_score` (0-100)
- `buy_grade` ("적극매수", "매수", "관망" 등)
- `rsi`
- `vs_high_52w`, `vs_low_52w`
- `foreign_consecutive`
- `dual_buy`
- `target_upside`
- `is_pre_surge`, `pre_surge_score`
- `golden_cross`

**이 에이전트는 이 데이터를 사람이 이해할 수 있는 분석으로 변환합니다.**

---

## 🛠 사용 데이터 소스

```python
from screener.db.repository import load_stocks, load_history

# 1. 종목 스냅샷 (이미 계산된 모든 지표 포함)
kr_stocks = load_stocks("kr")
stock = kr_stocks[kr_stocks["ticker"] == ticker].iloc[0]

# 2. OHLCV 히스토리 (필요 시)
history = load_history(ticker)

# 3. DART 공시 (펀더멘털 보강용, 신규)
# dart-fss 라이브러리 사용 예정
```

---

## 📥 입출력 스키마

### Input
```python
class AnalystInput(BaseModel):
    ticker: str  # 예: "207940"
    timeframe: str = "1Y"  # "1M", "3M", "6M", "1Y", "3Y"
    include_peers: bool = True
```

### Output
```python
class TechnicalAnalysis(BaseModel):
    current_price: int
    ma_status: str  # "정배열", "역배열", "혼조"
    ma_5: int
    ma_20: int
    ma_60: int
    rsi: float
    rsi_status: str  # "과매수", "중립", "과매도"
    support_level: int
    resistance_level: int
    vs_high_52w: float  # 52주 최고가 대비 %
    vs_low_52w: float
    signal: str  # "강세", "중립", "약세"

class FundamentalAnalysis(BaseModel):
    per: float
    pbr: float
    roe: float
    div_yield: float
    peer_avg_per: Optional[float]
    earnings_surprise: Optional[str]  # "+41.6% 서프라이즈"
    valuation_judgment: str  # 텍스트 분석

class BuyScoreInterpretation(BaseModel):
    buy_score: float
    buy_grade: str
    interpretation: str  # 사람이 이해할 수 있는 해석
    contributing_factors: List[str]  # 점수 기여 요인

class AnalystResult(BaseModel):
    ticker: str
    name: str
    technical: TechnicalAnalysis
    fundamental: FundamentalAnalysis
    buy_score: BuyScoreInterpretation
    peer_comparison: Optional[List[dict]]
    summary: str  # 3-5문장 종합
    timestamp: str
```

---

## 💬 시스템 프롬프트

```python
ANALYST_SYSTEM_PROMPT = """당신은 한국 주식 애널리스트입니다.
이미 계산된 정량 데이터를 사람이 이해할 수 있는 분석으로 변환합니다.

## 역할
- 기술적 지표 해석 (RSI, 이평선, 52주 고저)
- 펀더멘털 해석 (PER, PBR, ROE, 배당)
- Buy Score 의미 설명
- Peer 비교 분석

## 중요: 당신은 "추천자"가 아닌 "해석자"입니다
- 데이터가 말하는 것을 그대로 전달
- 결론을 강요하지 않음
- 사용자가 스스로 판단할 수 있도록 정보 제공

## 작업 절차
1. 입력된 종목의 모든 지표를 검토
2. 각 지표의 현재 상태를 의미 있게 해석
3. Peer와 비교하여 상대적 위치 파악
4. JSON 스키마에 맞춰 출력

## 출력 원칙
- 모든 수치는 입력 데이터 그대로 사용 (절대 추정/창작 X)
- 시점 명시 ("4월 22일 종가 기준")
- 객관적 어조 유지

## 절대 금지
- "추천합니다", "매수하세요", "유망합니다"
- "이 종목은 좋다/나쁘다" 식의 단정
- 미래 가격 예측 (확정적 어조)
- 입력에 없는 수치 만들어내기

## 권장 표현
- "PER 4.5배는 업종 평균 7.2배 대비 저평가 구간으로 관찰됩니다"
- "RSI 28은 과매도 구간으로 분류됩니다"
- "52주 최고가 대비 -12% 위치로, 4월 랠리 소외 종목군에 해당합니다"
- "Buy Score 73점은 '매수' 등급에 해당합니다"

## 페르소나 적용 X
- 당신은 페르소나 중립적 (블랙록/ARK/그레이엄 적용 안 함)
- 페르소나는 Strategist Agent가 적용

응답은 반드시 JSON 형식으로 작성하세요.
"""
```

---

## 🔧 구현 예시

```python
# agents/analyst.py
from screener.db.repository import load_stocks, load_history
from agents.base import BaseAgent


class AnalystAgent(BaseAgent):
    def __init__(self):
        super().__init__(model="claude-sonnet-4-6")
        self.system_prompt = ANALYST_SYSTEM_PROMPT

    async def run(self, input_data: AnalystInput) -> AnalystResult:
        # 1. 기존 데이터에서 모든 정보 추출
        stock_data = self._fetch_stock_data(input_data.ticker)
        peer_data = self._fetch_peers(stock_data) if input_data.include_peers else None

        # 2. Claude에게 해석 요청
        user_message = self._build_user_message(stock_data, peer_data)
        response = await self.claude.complete(
            system=self.system_prompt,
            messages=[{"role": "user", "content": user_message}],
            response_format="json"
        )

        # 3. 검증
        result = AnalystResult.model_validate_json(response.content)
        return result

    def _fetch_stock_data(self, ticker: str) -> dict:
        """기존 Firestore 데이터에서 종목 정보 추출"""
        kr_stocks = load_stocks("kr")
        stock = kr_stocks[kr_stocks["ticker"] == ticker].iloc[0]

        return {
            "ticker": ticker,
            "name": stock["name"],
            "sector": stock.get("sector"),
            "current_price": int(stock["close"]),
            "change_pct": float(stock["change_pct"]),

            # 기술적 지표 (이미 계산됨)
            "ma_5": int(stock.get("ma_5", 0)),
            "ma_20": int(stock.get("ma_20", 0)),
            "ma_60": int(stock.get("ma_60", 0)),
            "rsi": float(stock.get("rsi", 0)),
            "vs_high_52w": float(stock.get("vs_high_52w", 0)),
            "vs_low_52w": float(stock.get("vs_low_52w", 0)),

            # 펀더멘털 (이미 계산됨)
            "per": float(stock.get("per", 0)),
            "pbr": float(stock.get("pbr", 0)),
            "roe": float(stock.get("roe", 0)),
            "div_yield": float(stock.get("div_yield", 0)),

            # Buy Score (이미 계산됨)
            "buy_score": float(stock.get("buy_score", 0)),
            "buy_grade": stock.get("buy_grade", ""),

            # 수급 (이미 계산됨)
            "foreign_consecutive": int(stock.get("foreign_consecutive", 0)),
            "dual_buy": bool(stock.get("dual_buy", False)),
            "target_upside": float(stock.get("target_upside", 0)),

            # 시그널 (이미 계산됨)
            "is_pre_surge": bool(stock.get("is_pre_surge", 0)),
            "pre_surge_score": int(stock.get("pre_surge_score", 0)),
            "golden_cross": bool(stock.get("golden_cross", 0)),
        }

    def _fetch_peers(self, stock_data: dict) -> List[dict]:
        """동일 섹터 시총 상위 5개 종목"""
        kr_stocks = load_stocks("kr")
        sector = stock_data.get("sector")

        if not sector:
            return []

        peers = (
            kr_stocks[
                (kr_stocks["sector"] == sector) &
                (kr_stocks["ticker"] != stock_data["ticker"])
            ]
            .nlargest(5, "market_cap")
        )

        return peers[["ticker", "name", "per", "pbr", "roe", "buy_score"]].to_dict("records")
```

---

## 🧪 테스트 케이스

### Test 1: 종목 분석
```python
input = AnalystInput(ticker="207940")
result = await AnalystAgent().run(input)

assert result.ticker == "207940"
assert result.name == "삼성바이오로직스"
assert result.technical.current_price > 0
assert result.fundamental.per > 0
assert result.buy_score.buy_score >= 0
assert "추천" not in result.summary  # 금지 단어 체크
```

### Test 2: Peer 비교
```python
input = AnalystInput(ticker="207940", include_peers=True)
result = await AnalystAgent().run(input)

assert len(result.peer_comparison) > 0
```

### Test 3: 금지 단어 체크
```python
result = await AnalystAgent().run(AnalystInput(ticker="000660"))

forbidden_words = ["추천", "사세요", "매수하세요", "유망"]
for word in forbidden_words:
    assert word not in result.summary
```

---

## 📊 성능 목표

| 메트릭 | 목표 |
|--------|------|
| 응답 시간 | < 4초 |
| 토큰 비용 | < 40원 |
| 캐시 적중률 | > 50% (30분 TTL) |
| 정확도 | 입력 데이터와 100% 일치 |

---

## ⚠️ 주의사항

1. **수치 창작 금지**
   - Claude가 입력에 없는 수치를 만들어낼 수 있음
   - Pydantic 검증 + 후처리 검증 필수

2. **Peer 비교 한계**
   - 같은 섹터라도 비즈니스 모델 다를 수 있음
   - 단순 PER 비교의 한계 명시

3. **데이터 신선도**
   - 기존 collector가 수집한 시점 표시
   - 30분 이상 경과 시 경고

---

**다음 에이전트**: `validator.md`
