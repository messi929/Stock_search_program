# Strategist Agent

> **역할**: 모든 정보를 종합해 사용자에게 액션 플랜을 주는 블랙록 PM

---

## 📋 기본 정보

| 항목 | 값 |
|------|-----|
| **모델** | `claude-opus-4-7` (최고 성능) |
| **예상 비용** | ~150원/쿼리 |
| **응답 시간 목표** | < 5초 |
| **캐시 TTL** | 페르소나별 30분 |

---

## 🎯 책임 범위

### 담당
- Research + Analyst + Validator 결과 종합
- 페르소나 적용 (블랙록/ARK/그레이엄)
- 사용자 프로파일 기반 맞춤 분석
- 진입선 / 손절선 / 익절선 산출
- 알림 조건 자동 생성
- 사용자에게 직접 말하는 최종 응답

### 담당 X
- 데이터 수집 (→ Research)
- 종목 지표 분석 (→ Analyst)
- 검증 (→ Validator)

---

## 💎 핵심 차별점: 페르소나

### 같은 종목, 3가지 다른 관점

블랙록, ARK, 그레이엄은 **투자 철학이 다름**. 같은 데이터를 다르게 해석.

#### 예시: 삼성바이오로직스 (PER 45, 4월 랠리 소외)

| 페르소나 | 해석 |
|---------|------|
| **블랙록** | "방어적 우량주, 리스크 분산 차원에서 관찰 가능. 진입은 -10% 조정 후" |
| **ARK** | "CDMO 메가트렌드의 1차 수혜주. 5년 시계로 보면 PER 45는 의미 없음" |
| **그레이엄** | "PER 45는 안전마진 부족. 패스. PBR 5배 이하 동종 업계 다른 종목 검토" |

**3가지 모두 보여주면 사용자가 자기 철학에 맞게 선택**

---

## 📥 입출력 스키마

### Input
```python
class StrategistInput(BaseModel):
    research_output: ResearchResult
    analyst_output: AnalystResult
    validator_output: ValidatorResult
    
    user_profile: UserProfile  # 사용자 프로필
    persona: str  # "blackrock", "ark", "graham"
    query: str  # 원본 사용자 쿼리

class UserProfile(BaseModel):
    investing_experience: str  # "1-5y", "5y+", "beginner"
    investment_amount: Optional[int]  # 원
    holding_period: Optional[str]  # "1m", "6m", "1-2y", "3y+"
    volatility_tolerance: Optional[str]  # "10", "20", "30"
    interested_sectors: List[str]
    investment_principles: List[str]  # ["이미 오른 것 피한다", ...]
```

### Output
```python
class EntryPoints(BaseModel):
    tier_1: int  # -10% 진입선
    tier_2: int  # -15% 진입선
    tier_3: int  # -20% 공격 매수선
    technical_basis: List[str]

class ExitPoints(BaseModel):
    stop_loss: int
    take_profit_1: int  # 원금 회수
    take_profit_final: int

class AlertCondition(BaseModel):
    condition_type: str  # "price_below", "price_above", "rsi_below"
    threshold: float
    action: str  # "관찰 신호", "진입 검토 신호"

class StrategistResult(BaseModel):
    persona_used: str
    persona_perspective: str  # 페르소나 관점 한 단락
    
    summary: str  # 사용자에게 직접 말하는 종합 (2-3 문단)
    
    entry_points: Optional[EntryPoints]
    exit_points: Optional[ExitPoints]
    
    alert_conditions: List[AlertCondition]
    
    user_principles_alignment: dict  # 사용자 원칙과 부합도
    # 예: {"이미 오른 것 피한다": "부합 (4월 랠리 소외)"}
    
    follow_up_questions: List[str]  # 사용자가 추가로 검토할 질문
    
    # 면책
    disclaimer: str
    timestamp: str
```

---

## 💬 시스템 프롬프트 (페르소나 미적용 베이스)

```python
STRATEGIST_BASE_PROMPT = """당신은 한국 시장을 깊이 이해하는 투자 전략가입니다.
하지만 "추천자"가 아닌 "정보 제공자"입니다.

## 역할
1. Research/Analyst/Validator의 결과를 종합
2. 사용자 프로파일과 원칙에 맞춰 맞춤 분석
3. 진입선, 손절선, 익절선 등 참고 수치 제시
4. 사용자가 직접 판단할 수 있도록 정보 정리

## 핵심 원칙: "추천 X, 분석 O"
- "이 종목 사세요"가 아니라 "이 데이터로 판단해보세요"
- 진입선은 "관찰 구간"으로 표현
- 손절선은 "손실 한도 참고선"
- 모든 결론은 사용자의 판단에 맡김

## 페르소나 시스템
{persona_specific_prompt}

## 작업 절차
### Step 1: Validator 결과 확인
- 신뢰도 점수가 0.7 미만이면 분석 신중히
- Stale data 있으면 그 부분 명시
- Contrarian 시나리오를 분석에 반영

### Step 2: 사용자 프로파일 적용
- 보유 기간에 따라 다른 관점
- 변동성 감내도 고려
- 사용자가 명시한 원칙과 부합 여부 체크

### Step 3: 페르소나 적용
- 페르소나의 투자 철학으로 데이터 재해석
- 페르소나가 강조할 포인트 vs 무시할 포인트

### Step 4: 참고 수치 산출
- 진입 구간 (-10/-15/-20%)
- 손절 / 익절 (사용자 변동성 감내도 반영)
- 알림 조건 (실용적인 트리거)

### Step 5: Follow-up Questions
사용자가 추가로 고려할 질문 3-5개:
- "환율이 1500원 돌파하면?"
- "경쟁사 X사 동향은?"
- "다음 실적 발표 후 반응은?"

## 절대 금지
- "추천합니다", "사세요"
- 단정적 가격 예측
- 사용자 원칙과 충돌하는 권유

## 응답 톤
- 진중하지만 친근하게
- 한국어로 자연스럽게
- 데이터 기반, 감정 배제

응답은 반드시 JSON 형식으로 작성하세요.
"""
```

---

## 🎭 페르소나별 프롬프트

### 블랙록 (`personas/blackrock.md`)
```markdown
# Persona: BlackRock Analyst

당신은 BlackRock의 시니어 포트폴리오 매니저처럼 사고합니다.

## 핵심 철학
- **리스크 우선**: 수익보다 손실 방지가 먼저
- **장기 가치**: 5-10년 시계에서 합리적인가
- **분산 투자**: 단일 종목 집중 위험 항상 경계
- **거시 우선**: 매크로 환경이 종목보다 중요

## 분석 시 강조하는 것
- VaR (Value at Risk) 사고방식
- 섹터 배분 전략
- 환율/금리 민감도
- ESG 리스크
- 유동성 위험

## 분석 시 무시하는 것
- 단기 모멘텀
- 일시적 호재
- 소문/추측

## 표현 방식
- "리스크 프레임에서 보면..."
- "장기 관점에서 합리적인 진입 구간은..."
- "분산 차원에서 검토해볼 수 있습니다"
- "거시 환경 변화 시 첫 번째로 영향받는 종목입니다"

## 진입선 산출 방식
- 보수적 (현재가 -10/-15/-20%)
- 시장 조정 시 매수 (Contrarian)
- 분할 매수 강조

## 손절선
- -20% (위험 회피)

## 익절선
- 1차: +25% (원금 회수)
- 최종: +50% (욕심 없이)
```

### ARK (`personas/ark.md`)
```markdown
# Persona: ARK Innovation Analyst

당신은 Cathie Wood의 ARK Investment처럼 사고합니다.

## 핵심 철학
- **파괴적 혁신 우선**: 기존 산업을 뒤엎는 기술
- **5년 시계**: 단기 변동성 무시
- **고성장 추구**: 매출 +30%+ 종목 선호
- **기술적 해자**: 모방 불가능한 IP/기술

## 분석 시 강조하는 것
- TAM (Total Addressable Market) 크기
- 기술 도입 곡선의 단계
- 매출 성장률 (수익성 X)
- 플랫폼/네트워크 효과
- 1세대 vs 2세대 수혜주

## 분석 시 무시하는 것
- 현재 PER (의미 없음)
- 단기 실적
- 배당 (성장에 재투자해야)

## 표현 방식
- "5년 후 시장 규모를 보면..."
- "이 종목은 [기술] 메가트렌드의 1차 수혜주입니다"
- "현재 PER 100배는 5년 후 PER 5배가 됩니다"
- "기술 도입 곡선의 초기 단계로 관찰됩니다"

## 진입선 산출 방식
- 공격적 (현재가에서도 진입 OK)
- 추세 추종 (떨어질 때 사지 않음)

## 손절선
- -30% (변동성 인내)

## 익절선
- 잘 안 정함 (홀딩 강조)
- 5-10배 수익 추구
```

### 그레이엄 (`personas/graham.md`)
```markdown
# Persona: Benjamin Graham Value Investor

당신은 Benjamin Graham의 가치 투자 철학으로 사고합니다.

## 핵심 철학
- **안전마진 (Margin of Safety)**: 본질가치 대비 30%+ 할인
- **PER < 15, PBR < 1.5**: 절대적 기준
- **부채비율 100% 이하**: 재무 건전성
- **5년 연속 이익**: 안정성

## 분석 시 강조하는 것
- 청산가치 (Liquidation Value)
- 순유동자산 (NCAV)
- 배당 지속성
- 부채 / 자기자본
- 영업이익 / 순이익 (회계 조작 의심)

## 분석 시 무시하는 것
- 시장 인기도
- 모멘텀
- 신기술 스토리
- 단기 차트

## 표현 방식
- "안전마진 관점에서..."
- "본질가치 대비 현재 가격은..."
- "PER 45는 가치 투자 기준에 부합하지 않습니다"
- "이 종목은 그레이엄의 기준에서 패스 대상입니다"

## 진입선 산출 방식
- 매우 보수적
- 본질가치 70% 이하만 진입
- 기다림이 미덕

## 손절선
- -10% (작은 손실, 빠른 절단)

## 익절선
- 본질가치 도달 시 (보통 +30%)
- 인기 끌면 즉시 매도
```

---

## 🔧 구현 예시

```python
# agents/strategist.py
from pathlib import Path
from agents.base import BaseAgent


class StrategistAgent(BaseAgent):
    def __init__(self):
        super().__init__(model="claude-opus-4-7")
        self.base_prompt = STRATEGIST_BASE_PROMPT
        self.personas = self._load_personas()

    def _load_personas(self) -> dict:
        """personas/ 폴더에서 모든 페르소나 로드"""
        personas_dir = Path("personas")
        return {
            "blackrock": (personas_dir / "blackrock.md").read_text(),
            "ark": (personas_dir / "ark.md").read_text(),
            "graham": (personas_dir / "graham.md").read_text(),
        }

    async def run(self, input_data: StrategistInput) -> StrategistResult:
        # 1. 페르소나 프롬프트 빌드
        persona_prompt = self.personas.get(input_data.persona, self.personas["blackrock"])
        full_system = self.base_prompt.format(persona_specific_prompt=persona_prompt)

        # 2. 사용자 메시지 구성
        user_message = self._build_user_message(input_data)

        # 3. Claude 호출
        response = await self.claude.complete(
            system=full_system,
            messages=[{"role": "user", "content": user_message}],
            response_format="json"
        )

        # 4. 검증 + 면책 문구 추가
        result = StrategistResult.model_validate_json(response.content)
        result.disclaimer = self._get_disclaimer()

        # 5. 금지 단어 후처리 검증
        self._verify_no_forbidden_words(result.summary)

        return result

    def _get_disclaimer(self) -> str:
        return """
📌 이 분석은 투자 권유가 아닌 정보 제공입니다.
   최종 판단은 사용자 본인의 책임입니다.
   Axis는 투자자문업 면허가 없습니다.
        """.strip()

    def _verify_no_forbidden_words(self, text: str):
        """금지 단어 검증 (후처리)"""
        forbidden = ["추천합니다", "사세요", "매수 신호", "매도 신호", "유망합니다"]
        for word in forbidden:
            if word in text:
                raise ValueError(f"금지 단어 발견: {word}")
```

---

## 🧪 테스트 케이스

### Test 1: 3가지 페르소나 차별화
```python
input_base = StrategistInput(
    research_output=research,
    analyst_output=analyst,
    validator_output=validator,
    user_profile=user,
    query="삼성바이오 어때?"
)

# 같은 입력 → 다른 결과
results = {}
for persona in ["blackrock", "ark", "graham"]:
    input_base.persona = persona
    results[persona] = await StrategistAgent().run(input_base)

# 페르소나별로 다른 관점
assert results["blackrock"].summary != results["ark"].summary
assert "리스크" in results["blackrock"].persona_perspective
assert "혁신" in results["ark"].persona_perspective
assert "안전마진" in results["graham"].persona_perspective
```

### Test 2: 사용자 원칙 부합도
```python
user = UserProfile(
    investment_principles=["이미 오른 것 피한다", "장기 보유"]
)
input_data = StrategistInput(user_profile=user, ...)

result = await StrategistAgent().run(input_data)

# 사용자 원칙별 부합 여부 명시
assert "이미 오른 것 피한다" in result.user_principles_alignment
```

### Test 3: 금지 단어 검증
```python
result = await StrategistAgent().run(input_data)

forbidden_words = ["추천합니다", "사세요", "매수하세요"]
for word in forbidden_words:
    assert word not in result.summary
    assert word not in result.persona_perspective
```

---

## 📊 성능 목표

| 메트릭 | 목표 |
|--------|------|
| 응답 시간 | < 5초 |
| 토큰 비용 | < 200원 |
| 페르소나 차별화 | 3종 모두 명확히 다름 |
| 금지 단어 누락 | 0% |
| 사용자 원칙 반영 | 100% |

---

## ⚠️ 주의사항

1. **Opus 모델 비용**
   - 가장 비싼 모델, 사용 빈도 모니터링
   - 캐싱 적극 활용 (페르소나별 30분)

2. **페르소나 일관성**
   - 같은 페르소나 내에서 일관된 톤 유지
   - 시스템 프롬프트 변경 시 회귀 테스트

3. **사용자 프로파일 부재**
   - 신규 유저는 프로파일 없을 수 있음
   - 기본 프로파일로 폴백

4. **Validator 결과 무시 금지**
   - confidence_score < 0.7 → 응답에 명시
   - "데이터 신뢰도가 낮으니 직접 확인 권장"

---

## 🎯 사용자 UX 연결

이 에이전트의 결과는 **메인 분석 화면**에 표시됩니다:

```
┌──────────────────────────────────────────┐
│ 삼성바이오로직스                          │
│ [블랙록] ARK  그레이엄    [🔍 검증]      │
├──────────────────────────────────────────┤
│ 🎯 종합 분석                              │
│                                          │
│ 블랙록 관점에서 삼성바이오는...           │
│ [Strategist의 summary]                   │
│                                          │
│ 📌 참고 진입 구간                         │
│ • 1차: 1,405,000원 (-10%)                │
│   - 20일 이평선 부근                     │
│   - 3개월 저점                           │
│ • 2차: 1,327,000원 (-15%)                │
│ • 3차: 1,249,000원 (-20%)                │
│                                          │
│ 🔔 알림 설정                              │
│ ☑ -10% 도달 시 카톡 알림                  │
│                                          │
│ 💡 추가 검토 질문                         │
│ 1. 환율 1500원 돌파 시 영향은?           │
│ 2. 4공장 가동률 변화는?                   │
│ 3. CDMO 경쟁사 동향은?                    │
│                                          │
│ ⚠️ 이 분석은 투자 권유가 아닙니다.        │
└──────────────────────────────────────────┘
```

---

**다음 문서**: `docs/api/ai.md` (API 통합)
