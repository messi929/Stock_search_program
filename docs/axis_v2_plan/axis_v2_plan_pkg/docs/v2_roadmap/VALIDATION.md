# 검증 프로토콜 — LEGAL + Reviewer + 회귀 테스트

> **위치**: `docs/v2_roadmap/VALIDATION.md`
> **연관**: 모든 Week 문서, `docs/v2_roadmap/CLAUDE_V2.md`

---

## 🎯 검증 3대 축

1. **LEGAL 검증** (자동, 매 작업 후)
2. **Reviewer Subagent** (수동, 모듈 단위)
3. **회귀 테스트** (자동, Week E)

---

## 1. LEGAL 검증 자동화

### 1.1 `scripts/legal_check.py` 강화

```python
# scripts/legal_check.py

FORBIDDEN_V1 = [
    # 기존 시스템에서 사용 중
    "추천", "사세요", "매수 신호", "매도 신호",
    "유망", "목표가", "매수가", "손절가",
]

FORBIDDEN_V2 = [
    # 신규 페르소나 위험 표현
    "임박", "기대주", "매매 타이밍", "급등 예상",
    "곧 오를", "이번에 가는", "지금 들어가",
    "이 국면에서 사세요", "지금 진입",
    "외국인이 사니까", "밸류업 수혜주",
    "테마 진입 시점", "급등 임박",
]

REQUIRED_DISCLAIMERS = {
    "event": "통계 진술이며 매매 권유가 아닙니다",
    "macro": "거시 경제 지표 기반 정보 제공",
    "korean": "한국 시장 구조적 특수성 반영 정보",
    "all": "최종 투자 판단은 사용자 본인의 책임",
}


def check_file(path: str, mode: str = "default"):
    """파일에서 금지 단어 + 필수 면책 검증
    
    mode:
      - default: 사용자 노출 영역만 검사
      - strict: 메타 정의 영역도 검사
    """
    with open(path) as f:
        content = f.read()
    
    # 금지 단어 정의 라인 제거 (default mode)
    if mode == "default":
        # "- ❌ ..." 라인은 제외
        content = re.sub(r'(?m)^- ❌.*$', '', content)
        # FORBIDDEN_V1, FORBIDDEN_V2 = [...] 같은 정의는 제외
        content = re.sub(r'FORBIDDEN_V[12]\s*=\s*\[[\s\S]*?\]', '', content)
    
    violations = []
    for word in FORBIDDEN_V1 + FORBIDDEN_V2:
        if word in content:
            for i, line in enumerate(content.split("\n"), 1):
                if word in line:
                    violations.append({
                        "file": path,
                        "line": i,
                        "word": word,
                        "context": line.strip()[:100]
                    })
    
    return violations


def check_disclaimer_required(path: str, persona_id: str):
    """페르소나 응답에 필수 면책 포함 검증"""
    with open(path) as f:
        content = f.read()
    
    persona_disclaimer = REQUIRED_DISCLAIMERS.get(persona_id)
    common_disclaimer = REQUIRED_DISCLAIMERS["all"]
    
    issues = []
    if persona_disclaimer and persona_disclaimer not in content:
        issues.append(f"페르소나 면책 누락: {persona_disclaimer}")
    if common_disclaimer not in content:
        issues.append(f"공통 면책 누락: {common_disclaimer}")
    
    return issues


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True, help="파일 경로 또는 'all'")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--include-tests", action="store_true")
    args = parser.parse_args()
    
    files_to_check = []
    if args.target == "all":
        files_to_check = collect_all_files(args.include_tests)
    else:
        files_to_check = [args.target]
    
    all_violations = []
    for f in files_to_check:
        violations = check_file(f, mode="strict" if args.strict else "default")
        all_violations.extend(violations)
    
    if all_violations:
        print("❌ LEGAL 위반 발견:")
        for v in all_violations:
            print(f"  {v['file']}:{v['line']} [{v['word']}] {v['context']}")
        sys.exit(1)
    else:
        print("✅ LEGAL 검증 통과")
```

### 1.2 사용 시나리오

```bash
# 코드 작성 후 즉시
python scripts/legal_check.py --target=agents/event_analyst.py

# 시스템 프롬프트 변경 후
python scripts/legal_check.py --target=docs/personas/event.md

# Week 종료 시 전체
python scripts/legal_check.py --target=all --strict

# 베타 직전 최종
python scripts/legal_check.py --target=all --strict --include-tests
```

---

## 2. Reviewer Subagent 호출

### 2.1 호출 패턴 표준화

```
"Review {feature_path} for the following:

1. **LEGAL compliance**
   - 금지 단어: {FORBIDDEN_V1 + FORBIDDEN_V2}
   - 필수 면책 포함

2. **Persona consistency** (해당 시)
   - 페르소나가 자기 영역에서만 발언
   - 책임 영역 침범 X

3. **Cost awareness**
   - 캐싱 적절히 활용
   - 모델 tier 적절성 (Opus vs Sonnet vs Haiku)
   - 페르소나당 비용 추적

4. **Data accuracy** (해당 시)
   - pykrx/fredapi/yfinance 실제 시그니처 사용
   - rate limit 준수
   - 에러 처리 + 재시도

5. **Specific concerns** (페르소나별)
   - Event Analyst: certainty score logic, fabrication warnings
   - Macro PM: regime detection, dynamic Korea weighting
   - Korean Specialist: 외국인 우선, 자체 거버넌스 한계 명시

발견 이슈는 severity로 분류:
- 🔴 Critical: 즉시 fix 필수 (LEGAL 위반, 데이터 오류)
- 🟠 High: 24시간 내 fix
- 🟡 Medium: backlog 등록
- 🟢 Low: 추후 개선
"
```

### 2.2 호출 시점 (Week별)

| Week | 호출 시점 | 대상 |
|------|---------|------|
| A | Day 1, 2, 3, 4, 5 종료 | 6개 모듈 (각 1회) |
| B | Day 5 종료 | 4개 모듈 (FRED, ECOS, cycle, regime) |
| C | Day 5 종료 | 5개 모듈 (options, dart_event, edgar, yfinance_event, llm_inference) |
| D | Day 2, 3, 4, 5 종료 | 페르소나 3개 + LangGraph + Frontend |
| E | Day 3 종료 | 회귀 테스트 + LangGraph + Frontend 통합 |

**총 reviewer 호출 횟수**: ~25회

---

## 3. 회귀 테스트 (Week E)

### 3.1 매트릭스: 6 페르소나 × 10 종목

```python
# tests/regression/test_60_cases.py

import pytest
from agents import (
    blackrock_strategist, ark_strategist, graham_strategist,
    event_analyst, macro_pm, korean_specialist
)

PERSONAS = {
    "blackrock": blackrock_strategist,
    "ark": ark_strategist,
    "graham": graham_strategist,
    "event": event_analyst,
    "macro": macro_pm,
    "korean": korean_specialist,
}

TICKERS = [
    {"ticker": "005930", "name": "삼성전자", "market": "KR"},
    {"ticker": "207940", "name": "삼성바이오로직스", "market": "KR"},
    {"ticker": "010060", "name": "OCI홀딩스", "market": "KR"},
    {"ticker": "005380", "name": "현대차", "market": "KR"},
    {"ticker": "035720", "name": "카카오", "market": "KR"},
    {"ticker": "AAPL", "name": "Apple", "market": "US"},
    {"ticker": "RKLB", "name": "Rocket Lab", "market": "US"},
    {"ticker": "NVDA", "name": "NVIDIA", "market": "US"},
    {"ticker": "JPM", "name": "JPMorgan", "market": "US"},
    {"ticker": "TLT", "name": "20Y Treasury ETF", "market": "US"},
]


@pytest.mark.parametrize("persona_id,persona", PERSONAS.items())
@pytest.mark.parametrize("ticker_info", TICKERS)
async def test_regression(persona_id: str, persona, ticker_info: dict):
    """6 × 10 = 60 케이스"""
    result = await persona.analyze(ticker_info["ticker"])
    
    # 1. 응답 스키마 검증
    assert validate_response_schema(persona_id, result)
    
    # 2. LEGAL 검증
    violations = check_legal(result)
    assert not violations, f"LEGAL violations: {violations}"
    
    # 3. 데이터 정확성
    assert validate_data_accuracy(persona_id, ticker_info, result)
    
    # 4. 시간 시계 정합성
    assert validate_time_horizon(persona_id, result)
    
    # 5. 한국 특화 페르소나는 미국 종목에 graceful 응답
    if persona_id == "korean" and ticker_info["market"] == "US":
        assert result.get("not_applicable_reason") is not None
    
    # 결과 저장 (수동 리뷰용)
    save_result(persona_id, ticker_info["ticker"], result)
```

### 3.2 검증 항목 5종

#### A. 차별성 (Differentiation)
**같은 종목 6 페르소나 결론이 다른가?**

```python
def test_persona_differentiation(ticker: str):
    results = {p: PERSONAS[p].analyze(ticker) for p in PERSONAS}
    
    summaries = [r["summary_neutral"] for r in results.values()]
    similarity = calculate_similarity(summaries)  # 코사인 유사도 등
    
    assert similarity < 0.7, "페르소나 차별성 부족"
```

#### B. 일관성 (Consistency)
**같은 페르소나가 다른 종목에 일관 캐릭터?**

```python
def test_persona_consistency(persona_id: str):
    results = [PERSONAS[persona_id].analyze(t["ticker"]) for t in TICKERS]
    
    # 페르소나 시그니처 표현 빈도 검증
    persona_keywords = PERSONA_SIGNATURE_KEYWORDS[persona_id]
    keyword_frequency = count_keywords(results, persona_keywords)
    
    assert keyword_frequency > 0.5, "페르소나 일관성 부족"
```

#### C. LEGAL 준수
60건 모두 금지 단어 0건 (위 LEGAL check 통과)

#### D. 데이터 정확성
응답에 표시된 통계가 실제 수집 데이터와 일치

#### E. 시간 시계
- Event: 1주~3개월 시계 표현
- Macro: 6개월~2년 시계 표현
- Korean: 3개월~2년 시계 표현
- Blackrock: 5~10년
- ARK: 5년
- Graham: 2~5년

---

## 4. 통합 시나리오 테스트

```python
# tests/regression/test_integration_scenarios.py

@pytest.mark.asyncio
async def test_event_korean_combo():
    """이벤트 + 한국 페르소나 동시 호출 (자사주 소각 발표 시나리오)"""
    result = await run_multi_persona_analysis(
        ticker="005930",
        selected_personas=["event", "korean"],
    )
    
    # 1. 두 페르소나 모두 응답
    assert "event" in result["persona_analyses"]
    assert "korean" in result["persona_analyses"]
    
    # 2. base_pipeline 1회만 실행 (비용)
    assert result["base_pipeline_call_count"] == 1
    
    # 3. 자사주 소각 = 양쪽 모두 다룸 (각자 관점)
    event_analysis = result["persona_analyses"]["event"]
    korean_analysis = result["persona_analyses"]["korean"]
    
    assert "자사주" in event_analysis["summary_neutral"]
    assert "자사주" in korean_analysis["summary_neutral"]
    
    # 4. 결론은 다름 (페르소나 차별성)
    similarity = calculate_similarity(
        event_analysis["summary_neutral"],
        korean_analysis["summary_neutral"]
    )
    assert similarity < 0.7


@pytest.mark.asyncio
async def test_us_stock_korean_specialist_graceful():
    """미국 종목에 한국 페르소나 호출 시 graceful 응답"""
    result = await korean_specialist.analyze("AAPL")
    
    assert result.get("not_applicable_reason") is not None
    assert "한국 시장 전용" in result["not_applicable_reason"]
```

---

## 5. 베타 출시 차단 사유

다음 발견 시 베타 출시 연기:

| Severity | 사유 | 대응 |
|----------|------|------|
| 🔴 Critical | LEGAL 위반 1건 이상 | 즉시 fix, 회귀 재실행 |
| 🔴 Critical | 회귀 테스트 통과율 < 95% | 실패 케이스 fix |
| 🔴 Critical | 분석 시간 > 120초 | 캐싱/병렬화 강화 |
| 🟠 High | 페르소나 일관성 무너짐 | 시스템 프롬프트 fine-tune |
| 🟠 High | Cloud Run 안정성 문제 | 인프라 점검 |
| 🟡 Medium | 데이터 부재 graceful 부족 | 페르소나 응답 보완 |

---

## 6. 검증 결과 보고서 양식

Week E 종료 시 다음 보고서 자동 생성:

```markdown
# v2 검증 결과 보고서

생성일: YYYY-MM-DD
버전: v2.0

## 1. 회귀 테스트 결과
- 60건 중 통과: X건 (Y%)
- 실패 케이스: ...

## 2. LEGAL 검증
- 금지 단어 발견: 0건 ✅
- 필수 면책 포함: 100% ✅

## 3. Reviewer 이슈
- Critical: 0
- High: 0
- Medium: X
- Low: Y

## 4. 비용 측정
- 페르소나당 평균 비용: ...
- 6 페르소나 동시 호출: ...
- 캐시 적중률: ...

## 5. 분석 시간 측정
- 평균: X초
- 95th percentile: Y초

## 6. 베타 출시 권고
- 차단 사유: 없음 / 있음 (목록)
- 권고: 출시 가능 / 연기
```
