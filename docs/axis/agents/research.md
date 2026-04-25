# Research Agent

> **역할**: 시장이 지금 어떻게 돌아가는지 파악하는 신문기자

---

## 📋 기본 정보

| 항목 | 값 |
|------|-----|
| **모델** | `claude-haiku-4-5-20251001` |
| **예상 비용** | ~5원/쿼리 |
| **응답 시간 목표** | < 3초 |
| **캐시 TTL** | 1시간 (시황은 자주 변하지만 캐싱 가능) |

---

## 🎯 책임 범위

### 담당
- 한국 증시 시황 (코스피/코스닥/섹터 동향)
- 종목 관련 뉴스 수집 + 요약
- 매크로 이벤트 (FOMC, 관세, 지정학)
- 외국인/기관 수급 트렌드 (기존 `screener` 데이터 활용)

### 담당 X
- 종목 자체의 펀더멘털/기술적 분석 (→ Analyst)
- 가격 검증 (→ Validator)
- 최종 판단 (→ Strategist)

---

## 🛠 사용 데이터 소스

### 1. 기존 자산 (재활용)
```python
from screener.db.repository import load_themes, load_stocks
# 기존에 수집된 테마 정보 + 외국인/기관 수급
```

### 2. 신규 추가
```python
# 네이버 뉴스 RSS
NEWS_RSS_URL = "https://news.naver.com/main/list.naver?mid=shm&sid1=101"

# FRED API (미 경제지표)
FRED_API_KEY = os.getenv("FRED_API_KEY")

# 매크로 이벤트 캘린더 (수동 큐레이션)
MACRO_EVENTS_PATH = "data/macro_events.json"
```

---

## 📥 입출력 스키마

### Input (Pydantic)
```python
from pydantic import BaseModel
from typing import Optional, List

class ResearchInput(BaseModel):
    query: str  # 사용자 자연어 쿼리
    ticker: Optional[str] = None  # 특정 종목 컨텍스트
    sector: Optional[str] = None  # 섹터 컨텍스트
    timeframe_days: int = 7  # 분석 기간 (뉴스 등)
```

### Output (Pydantic)
```python
class NewsItem(BaseModel):
    headline: str
    source: str
    published_at: str
    impact: str  # "positive", "negative", "neutral"
    relevance_score: float  # 0-1

class MacroContext(BaseModel):
    fomc_next: Optional[str]  # "2026-05-07"
    key_risks: List[str]
    key_opportunities: List[str]

class SectorStatus(BaseModel):
    name: str
    status: str  # "강세", "약세", "횡보"
    key_drivers: List[str]
    rally_participation: str  # "참여 중", "소외", "급등 후 조정"

class ResearchResult(BaseModel):
    market_sentiment: str  # "낙관적", "신중", "비관적"
    relevant_news: List[NewsItem]
    macro_context: MacroContext
    sector_status: List[SectorStatus]
    foreign_inst_flow: dict  # 외국인/기관 매수 상위 섹터
    summary: str  # 2-3문장 요약
    timestamp: str  # ISO format
```

---

## 💬 시스템 프롬프트

```python
RESEARCH_SYSTEM_PROMPT = """당신은 한국 증시 전문 시황 분석가입니다.
블룸버그 터미널 스타일의 객관적 데이터 중심 보고서를 작성합니다.

## 역할
- 시황, 뉴스, 매크로 이벤트의 사실 관계 정리
- 주관적 판단/추천은 절대 하지 않음
- 기관/외국인 수급 흐름 추적

## 작업 절차
1. 입력된 query를 분석하여 어떤 정보가 필요한지 판단
2. 제공된 데이터(뉴스/매크로/수급)에서 관련 정보 추출
3. 시장 심리와 섹터 동향 종합
4. JSON 스키마에 맞춰 출력

## 출력 원칙
- 모든 사실에 출처 명시 (네이버뉴스, 한경 등)
- 시점 표시 ("4월 22일 종가 기준" 등)
- 모호한 표현 금지 ("약", "대략" 사용 X, 정확한 수치)
- 언급 종목/수치는 모두 검증 가능해야 함

## 절대 금지
- "추천합니다", "사세요", "유망합니다" 등 권유성 표현
- 특정 종목의 매수/매도 시그널 제시
- 미래 가격 예측 (확정적 어조)
- 출처 없는 주관적 판단

## 권장 표현
- "관찰됩니다" / "확인됩니다"
- "나타납니다" / "보고되었습니다"
- "데이터에 따르면..."
- "관찰 가치가 있습니다"

## 필수 면책 문구 (응답 끝에 자동 추가됨)
이 응답에는 면책 문구가 후처리로 자동 추가되니,
당신은 콘텐츠에만 집중하세요.

응답은 반드시 JSON 형식으로 작성하세요.
"""
```

---

## 🔧 구현 예시

```python
# agents/research.py
from typing import Optional
import json
from pydantic import BaseModel

from utils.claude_client import ClaudeClient
from agents.base import BaseAgent
from screener.db.repository import load_themes, load_stocks


class ResearchAgent(BaseAgent):
    def __init__(self):
        super().__init__(model="claude-haiku-4-5-20251001")
        self.system_prompt = RESEARCH_SYSTEM_PROMPT

    async def run(self, input_data: ResearchInput) -> ResearchResult:
        # 1. 기존 데이터 수집
        context = self._gather_context(input_data)

        # 2. Claude 호출
        user_message = self._build_user_message(input_data, context)
        response = await self.claude.complete(
            system=self.system_prompt,
            messages=[{"role": "user", "content": user_message}],
            response_format="json"
        )

        # 3. Pydantic 검증
        result = ResearchResult.model_validate_json(response.content)

        # 4. 비용 로깅
        self.log_cost(response.usage)

        return result

    def _gather_context(self, input_data: ResearchInput) -> dict:
        """기존 Firestore 데이터에서 컨텍스트 수집"""
        context = {}

        # 외국인/기관 수급 (기존 데이터)
        kr_stocks = load_stocks("kr")
        if "foreign_consecutive" in kr_stocks.columns:
            context["top_foreign_buy"] = (
                kr_stocks
                .nlargest(10, "foreign_consecutive")[["ticker", "name", "foreign_consecutive"]]
                .to_dict("records")
            )

        # 테마 동향
        themes = load_themes()
        context["active_themes"] = themes

        # 뉴스 (RSS 크롤링)
        if input_data.ticker:
            context["news"] = self._fetch_naver_news(input_data.ticker)

        # 매크로 이벤트
        context["macro_events"] = self._load_macro_events()

        return context

    def _fetch_naver_news(self, ticker: str) -> list:
        """네이버 뉴스 RSS에서 종목 관련 뉴스"""
        # 구현 예정
        pass

    def _load_macro_events(self) -> list:
        """data/macro_events.json 로드"""
        with open("data/macro_events.json") as f:
            return json.load(f)
```

---

## 🧪 테스트 케이스

### Test 1: 종목 시황 분석
```python
input = ResearchInput(
    query="삼성바이오로직스 시황",
    ticker="207940"
)
result = await ResearchAgent().run(input)

assert result.market_sentiment in ["낙관적", "신중", "비관적"]
assert len(result.relevant_news) > 0
assert "삼성바이오" in result.summary
```

### Test 2: 섹터 시황
```python
input = ResearchInput(
    query="AI 반도체 섹터 분석",
    sector="반도체"
)
result = await ResearchAgent().run(input)

assert any(s.name == "반도체" for s in result.sector_status)
```

### Test 3: 매크로 이벤트
```python
input = ResearchInput(
    query="이번 주 주요 매크로 이벤트"
)
result = await ResearchAgent().run(input)

assert result.macro_context.fomc_next is not None
assert len(result.macro_context.key_risks) > 0
```

---

## 📊 성능 목표

| 메트릭 | 목표 | 측정 방법 |
|--------|------|----------|
| 응답 시간 | < 3초 | 로그 평균 |
| 토큰 비용 | < 8원 | cost_tracker |
| 캐시 적중률 | > 30% | 동일 쿼리 1시간 내 |
| 면책 문구 누락 | 0% | 자동 검증 |

---

## ⚠️ 주의사항

1. **네이버 크롤링 빈도 제한**
   - 동일 IP에서 분당 30회 미만
   - User-Agent 헤더 필수
   - 차단 시 기존 데이터 폴백

2. **뉴스 신뢰도 필터**
   - 1차 출처 우선 (한경, 매경, 연합)
   - 블로그/카페 글 제외
   - 광고성 콘텐츠 필터

3. **JSON 파싱 실패 대비**
   - 1회 재시도 (프롬프트 강화)
   - 실패 시 raw text + 에러 로그
   - 사용자에게는 일반 응답 표시

---

**상세 구현 시 참고**: `docs/api/ai.md`의 `/api/ai/analyze` 플로우
