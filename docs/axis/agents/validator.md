# Validator Agent ⭐

> **역할**: AI가 거짓말하지 않는지 감시하는 파수꾼  
> **이 프로덕트의 진짜 차별점**

---

## 📋 기본 정보

| 항목 | 값 |
|------|-----|
| **모델** | `claude-sonnet-4-6` |
| **예상 비용** | ~25원/쿼리 |
| **응답 시간 목표** | < 3초 |
| **캐시** | 사용 안 함 (항상 실시간 검증) |

---

## 💎 왜 이 에이전트가 핵심인가

JEON님과 Claude 대화에서 가장 자주 나온 요구:
> "검증해줘", "4월 22일 종가 기준으로 다시"

이 에이전트는 그 경험을 프로덕트화한 것입니다:
- **AI 답변을 무조건 신뢰하지 않는다**는 철학
- 사용자가 "검증" 버튼만 누르면 모든 수치가 재검증됨
- 데이터가 오래되었다면 자동으로 재분석 트리거

이게 다른 AI 투자 도구와의 결정적 차이입니다.

---

## 🎯 책임 범위

### 담당
- Research/Analyst Agent의 모든 수치 실시간 재검증
- 데이터 신선도(freshness) 판정
- Contrarian 시나리오 생성 ("이 분석이 틀릴 수 있는 이유")
- Stale data 감지 및 재분석 트리거

### 담당 X
- 새로운 분석 수행 (검증만)
- 사용자 응답 작성 (→ Strategist)

---

## 🔬 3가지 핵심 기능

### 1. 수치 자동 추출 (Extraction)

다른 에이전트의 출력에서 검증해야 할 모든 수치를 자동 추출:

```python
EXTRACTION_PATTERNS = {
    "price": r"(\d{1,3}(?:,\d{3})*)\s*원",  # "1,561,000원"
    "percentage": r"([+-]?\d+\.?\d*)\s*%",   # "+41.6%"
    "ticker": r"\((\d{6})\)",                # "(207940)"
    "ratio": r"(?:PER|PBR|ROE)\s*[:=]?\s*(\d+\.?\d*)",  # "PER 4.5"
    "score": r"(?:buy_score|점수)\s*[:=]?\s*(\d+)",      # "Buy Score 73점"
}
```

### 2. 실시간 재조회 (Verification)

```python
async def verify_price(ticker: str, claimed_price: float) -> dict:
    """현재가를 FinanceDataReader로 재조회 후 비교"""
    import FinanceDataReader as fdr
    from datetime import datetime

    # 최신 가격 조회 (5분 캐시)
    df = fdr.DataReader(ticker)
    current_price = float(df["Close"].iloc[-1])
    last_update = df.index[-1]

    diff_pct = abs((claimed_price - current_price) / current_price * 100)

    return {
        "ticker": ticker,
        "claimed": claimed_price,
        "verified": current_price,
        "diff_pct": diff_pct,
        "last_update": last_update.isoformat(),
        "status": (
            "OK" if diff_pct < 5
            else "WARN" if diff_pct < 10
            else "FAIL"
        )
    }
```

### 3. Contrarian 시나리오 (Devil's Advocate)

분석에 동의하지 않고, **반대 시나리오 3가지**를 강제로 생성:

```
예시:
1. "미-중 바이오 정책 역풍 시 -20% 가능"
2. "CDMO 경쟁 심화로 마진 압박"
3. "환율 1,500원 돌파 시 수익성 타격"
```

이건 사용자의 **확증 편향(Confirmation Bias)을 막는** 핵심 장치입니다.

---

## 📥 입출력 스키마

### Input
```python
class ValidatorInput(BaseModel):
    research_output: Optional[ResearchResult]
    analyst_output: Optional[AnalystResult]
    ticker: str  # 검증할 메인 종목
    strict_mode: bool = False  # True면 5%, False면 10% 임계값
```

### Output
```python
class ValidationCheck(BaseModel):
    item: str  # "삼성바이오 현재가"
    claimed: float
    verified: float
    diff_pct: float
    status: str  # "OK", "WARN", "FAIL"
    last_data_update: str

class ContrarianScenario(BaseModel):
    title: str  # "미-중 바이오 관세 강화"
    description: str
    impact_estimate: str  # "-15% ~ -25%"
    probability: str  # "LOW", "MEDIUM", "HIGH"
    indicators_to_watch: List[str]

class ValidatorResult(BaseModel):
    overall_status: str  # "PASS", "WARN", "FAIL"
    checks: List[ValidationCheck]
    stale_data_count: int
    fresh_data_count: int
    
    contrarian_scenarios: List[ContrarianScenario]
    blind_spots: List[str]  # 분석에서 빠진 관점
    
    confidence_score: float  # 0-1, 분석 신뢰도
    requires_reanalysis: bool  # 재분석 필요 여부
    
    timestamp: str
```

---

## 💬 시스템 프롬프트

```python
VALIDATOR_SYSTEM_PROMPT = """당신은 AI 분석의 검증관(Auditor)입니다.
다른 에이전트의 분석을 무조건 신뢰하지 않고, 의심스러운 눈으로 검토합니다.

## 역할
1. 모든 수치의 실시간 검증
2. Stale data 감지
3. Contrarian 시나리오 강제 생성 (분석에 반대되는 관점)
4. Blind spot 식별

## 핵심 원칙: "의심하라"
- "분석가가 이렇게 말한다"는 것을 그대로 믿지 마세요
- 데이터가 며칠 지났을 가능성을 항상 고려
- 반대 시나리오를 반드시 3가지 이상 제시
- 분석에서 다루지 않은 리스크 발굴

## 작업 절차

### Step 1: 수치 검증
- 입력된 모든 가격/지표를 verification 결과와 비교
- 5% 미만 차이: OK
- 5-10% 차이: WARN
- 10%+ 차이: FAIL → requires_reanalysis = True

### Step 2: Contrarian 시나리오 생성
다음 카테고리에서 최소 3가지 반대 시나리오:
- 거시 경제 리스크 (금리, 환율, 무역분쟁)
- 산업/섹터 리스크 (경쟁, 규제, 기술 변화)
- 종목 고유 리스크 (실적, 경영진, 회계)

### Step 3: Blind Spot 식별
분석에서 다루지 않았지만 중요한 관점:
- 환경/사회/거버넌스 (ESG)
- 노동/노사 이슈
- 지정학적 리스크
- 기술 disruptive 가능성

### Step 4: 종합 신뢰도 점수
- 모든 수치 OK + 합리적 분석: 0.8-1.0
- 일부 stale data: 0.6-0.8
- 다수 stale data 또는 논리 오류: 0.0-0.6

## 출력 원칙
- 객관적, 비판적 어조 유지
- 비판은 데이터 기반으로
- 상위 분석가의 결론에 휘둘리지 않기

## 절대 금지
- 분석가의 결론에 무조건 동의
- "괜찮아 보입니다" 식의 안이한 검증
- 추측성 비판

## 권장 표현
- "데이터 검증 결과..."
- "다음 시나리오에서 분석이 틀릴 수 있습니다"
- "이 관점이 누락되었습니다"

응답은 반드시 JSON 형식으로 작성하세요.
"""
```

---

## 🔧 구현 예시

```python
# agents/validator.py
import re
from datetime import datetime, timedelta
from typing import List, Optional
import FinanceDataReader as fdr

from agents.base import BaseAgent
from agents.research import ResearchResult
from agents.analyst import AnalystResult


class ValidatorAgent(BaseAgent):
    def __init__(self):
        super().__init__(model="claude-sonnet-4-6")
        self.system_prompt = VALIDATOR_SYSTEM_PROMPT

    async def run(self, input_data: ValidatorInput) -> ValidatorResult:
        # Step 1: 수치 추출
        extracted_values = self._extract_values(input_data)

        # Step 2: 실시간 재조회 (병렬 처리)
        verification_results = await self._verify_all(extracted_values)

        # Step 3: Stale data 카운트
        stale_count = sum(1 for v in verification_results if v["status"] == "FAIL")
        fresh_count = sum(1 for v in verification_results if v["status"] == "OK")

        # Step 4: Claude에게 Contrarian + Blind Spot 요청
        contrarian_response = await self._request_contrarian(
            input_data,
            verification_results
        )

        # Step 5: 종합 결과
        overall_status = self._determine_overall_status(verification_results)
        requires_reanalysis = stale_count >= 2  # 2개 이상 stale → 재분석

        return ValidatorResult(
            overall_status=overall_status,
            checks=verification_results,
            stale_data_count=stale_count,
            fresh_data_count=fresh_count,
            contrarian_scenarios=contrarian_response["scenarios"],
            blind_spots=contrarian_response["blind_spots"],
            confidence_score=self._calculate_confidence(verification_results),
            requires_reanalysis=requires_reanalysis,
            timestamp=datetime.now().isoformat()
        )

    def _extract_values(self, input_data: ValidatorInput) -> List[dict]:
        """입력에서 검증할 수치 추출"""
        values = []

        if input_data.analyst_output:
            tech = input_data.analyst_output.technical
            values.extend([
                {
                    "type": "price",
                    "ticker": input_data.ticker,
                    "label": f"{input_data.ticker} 현재가",
                    "value": tech.current_price
                },
                {
                    "type": "indicator",
                    "ticker": input_data.ticker,
                    "label": "RSI",
                    "value": tech.rsi
                },
                # ... PER, PBR 등
            ])

        return values

    async def _verify_all(self, values: List[dict]) -> List[dict]:
        """모든 수치 병렬 검증"""
        import asyncio
        tasks = [self._verify_one(v) for v in values]
        return await asyncio.gather(*tasks)

    async def _verify_one(self, value: dict) -> dict:
        """단일 수치 검증"""
        if value["type"] == "price":
            return await self._verify_price(value)
        elif value["type"] == "indicator":
            return await self._verify_indicator(value)
        # ...

    async def _verify_price(self, value: dict) -> dict:
        """가격 재조회"""
        try:
            df = fdr.DataReader(value["ticker"])
            current = float(df["Close"].iloc[-1])
            last_update = df.index[-1].isoformat()

            claimed = value["value"]
            diff_pct = abs((claimed - current) / current * 100) if current > 0 else 0

            return {
                "item": value["label"],
                "claimed": claimed,
                "verified": current,
                "diff_pct": round(diff_pct, 2),
                "last_data_update": last_update,
                "status": (
                    "OK" if diff_pct < 5
                    else "WARN" if diff_pct < 10
                    else "FAIL"
                )
            }
        except Exception as e:
            return {
                "item": value["label"],
                "claimed": value["value"],
                "verified": None,
                "diff_pct": None,
                "last_data_update": None,
                "status": "ERROR",
                "error": str(e)
            }

    async def _request_contrarian(
        self,
        input_data: ValidatorInput,
        verification: List[dict]
    ) -> dict:
        """Claude에게 반대 시나리오 요청"""
        prompt = self._build_contrarian_prompt(input_data, verification)
        response = await self.claude.complete(
            system=self.system_prompt,
            messages=[{"role": "user", "content": prompt}],
            response_format="json"
        )
        return json.loads(response.content)

    def _determine_overall_status(self, checks: List[dict]) -> str:
        """전체 상태 판정"""
        if any(c["status"] == "FAIL" for c in checks):
            return "FAIL"
        if any(c["status"] == "WARN" for c in checks):
            return "WARN"
        return "PASS"

    def _calculate_confidence(self, checks: List[dict]) -> float:
        """신뢰도 점수 계산"""
        if not checks:
            return 0.5

        ok_count = sum(1 for c in checks if c["status"] == "OK")
        warn_count = sum(1 for c in checks if c["status"] == "WARN")
        total = len(checks)

        return round((ok_count * 1.0 + warn_count * 0.5) / total, 2)
```

---

## 🧪 테스트 케이스

### Test 1: 모든 데이터 신선
```python
# 1분 전에 분석된 결과 검증
input = ValidatorInput(
    research_output=fresh_research,
    analyst_output=fresh_analyst,
    ticker="207940"
)
result = await ValidatorAgent().run(input)

assert result.overall_status == "PASS"
assert result.stale_data_count == 0
assert result.confidence_score >= 0.8
assert len(result.contrarian_scenarios) >= 3
```

### Test 2: Stale Data 감지
```python
# 일부러 오래된 가격 입력
stale_analyst = AnalystResult(...)
stale_analyst.technical.current_price = 1000000  # 실제는 1561000

input = ValidatorInput(
    analyst_output=stale_analyst,
    ticker="207940"
)
result = await ValidatorAgent().run(input)

assert result.overall_status == "FAIL"
assert result.requires_reanalysis is True
assert any(c["status"] == "FAIL" for c in result.checks)
```

### Test 3: Contrarian 시나리오 품질
```python
result = await ValidatorAgent().run(input)

# 최소 3개의 반대 시나리오
assert len(result.contrarian_scenarios) >= 3

# 각 시나리오에 필수 필드
for scenario in result.contrarian_scenarios:
    assert scenario.title
    assert scenario.description
    assert scenario.probability in ["LOW", "MEDIUM", "HIGH"]
    assert len(scenario.indicators_to_watch) > 0
```

---

## 📊 성능 목표

| 메트릭 | 목표 |
|--------|------|
| 응답 시간 | < 3초 |
| 토큰 비용 | < 30원 |
| 가격 검증 정확도 | 99%+ |
| Stale data 검출률 | 95%+ |
| Contrarian 다양성 | 매번 다른 관점 |

---

## ⚠️ 주의사항

1. **FinanceDataReader 안정성**
   - 가끔 실패하므로 폴백 데이터 소스 필요
   - 1차: pykrx, 2차: yfinance

2. **수치 추출 정확도**
   - 정규식만으로 100% 추출 어려움
   - 중요 수치는 명시적 마커 사용 (`{{price:1561000}}`)

3. **Contrarian의 함정**
   - 무조건 부정적이면 신뢰 잃음
   - 합리적 비판만 (말도 안 되는 시나리오 X)

4. **재분석 무한 루프 방지**
   - 재분석 카운터 (최대 2회)
   - 2회 후에도 FAIL → 사용자에게 명시

---

## 🎯 사용자 UX 연결

이 에이전트의 결과는 프론트엔드의 **"검증 버튼"**과 직결됩니다:

```typescript
// components/analyze/ValidateButton.tsx
function ValidateButton({ analysisId }) {
  const { data, mutate } = useMutation({
    mutationFn: () => api.post(`/api/ai/validate/${analysisId}`)
  });

  return (
    <Button onClick={mutate}>
      🔍 검증하기
      {data?.overall_status === "PASS" && "✅"}
      {data?.overall_status === "WARN" && "⚠️"}
      {data?.overall_status === "FAIL" && "❌ 재분석 필요"}
    </Button>
  );
}
```

**프론트엔드 설계는 `docs/frontend/components.md` 참고**

---

**다음 에이전트**: `strategist.md`
