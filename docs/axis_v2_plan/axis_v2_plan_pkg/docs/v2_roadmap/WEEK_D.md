# Week D — 페르소나 구현 + LangGraph + Frontend 통합

> **목표**: 3개 신규 페르소나 구현 + LangGraph 통합 + Frontend 6 페르소나 UI
> **소요**: 5일
> **선행 의존성**: Week A, B, C 완료 (모든 데이터 인프라 준비)
> **후속**: Week E 검증

---

## 🎯 산출물

```
agents/
├── event_analyst.py                 # 이벤트 페르소나 (Day 1-2)
├── macro_pm.py                      # 매크로 PM (Day 3)
└── korean_specialist.py             # 한국 시장 전문가 (Day 3)

personas/                            # 시스템 프롬프트 별도 파일
├── event.md                         # v2.1 (시뮬레이션 보완 반영)
├── macro.md                         # v1
└── korean.md                        # v1

graph.py 업데이트                    # 6 페르소나 분기 처리

web/
├── components/PersonaSwitch.tsx     # 6 페르소나 탭 확장
├── components/PersonaCard/          # 페르소나별 카드 (재사용 generic)
└── types/persona.ts                 # 6개 enum 확장
```

---

## 📅 Day별 작업

### Day 1 — Event Analyst 페르소나 (1/2)

**시스템 프롬프트**: `docs/personas/event.md` (v2.1)

#### 작업
1. **시스템 프롬프트 v2.1 작성**
   - v2 (`docs/personas/event.md`)에 시뮬레이션 보완 4개 추가:
     - Scenario Analysis (bullish/base/bearish + 확률)
     - summary_neutral 한국어 강제
     - current_position_vs_history 명시 강제
     - 통계 한계 명시
   - LEGAL Hard Rules 강화 (옵션 B: 통계 기반 표현)
2. **`agents/event_analyst.py`**
   - BaseAgent 상속
   - Pydantic v2 입출력 모델
   - 데이터 수집: Week C 모듈들 호출
3. **단위 테스트 (5개 종목)**
   - RKLB (IPO 2차 수혜)
   - 005930 (실적 발표)
   - SPY (FOMC 매크로)
   - 207940 (자사주 소각)
   - TSLA (M&A 루머 - 확실성 낮음 케이스)

---

### Day 2 — Event Analyst 페르소나 (2/2)

#### 작업
1. **응답 JSON 스키마 검증**
   - 모든 필수 필드 존재
   - certainty_breakdown 4차원 정확
   - reference_observation_zones 표현 정확
2. **확실성 점수 분기 처리**
   - 9-10: Full Analysis 배지
   - 7-8: 신뢰 가능 배지
   - 5-6: Cautious + 경고
   - 3-4: Probabilistic Only
   - 0-2: 분석 거부 (별도 응답)
3. **Reviewer 호출**
   - "Review agents/event_analyst.py for LEGAL compliance, certainty score logic, fabrication warnings"

---

### Day 3 — Macro PM + Korean Specialist (병렬)

#### Macro PM 작업
1. **시스템 프롬프트** (`docs/personas/macro.md` v1)
2. **`agents/macro_pm.py`**
   - regime_detector 호출
   - 동적 가중치: 한국 종목이면 한국 매크로 우선
   - 6 국면별 자산/섹터 매핑 출력

#### Korean Specialist 작업
1. **시스템 프롬프트** (`docs/personas/korean.md` v1)
2. **`agents/korean_specialist.py`**
   - Week A 6개 모듈 모두 호출
   - 6단계 분석 프레임워크
   - 한국 특수 점수 (가중 평균)

#### Reviewer 호출 (2회)
- "Review agents/macro_pm.py for regime detection logic and Korean market dynamic weighting"
- "Review agents/korean_specialist.py for Korean market specifics, governance score limits, valueup data accuracy"

---

### Day 4 — LangGraph 통합

#### 작업
1. **`graph.py` 업데이트**
   - Strategist 분기 6개로 확장
   - 페르소나별 데이터 라우팅
   - 비용 추적 통합 (페르소나당 호출 비용)
2. **데이터 접근 권한 매트릭스 적용**
   ```
   Event Analyst → 옵션/이벤트 캘린더/공매도/LLM 추론
   Macro PM → FRED/ECOS/regime
   Korean Specialist → 외국인/재벌/밸류업/거버넌스/공매도
   ```
3. **에러 라우팅**
   - 페르소나별 데이터 부족 시 graceful degradation
   - "데이터 일시 부재" 메시지

#### 검증
- [ ] 6 페르소나 모두 호출 시 정상 동작
- [ ] 일부 페르소나만 활성화 시 정상 동작
- [ ] 에러 발생 시 graceful

---

### Day 5 — Frontend 6 페르소나 UI

#### 작업
1. **`web/types/persona.ts`**
   - PersonaId enum 확장: `blackrock | ark | graham | event | macro | korean`
   - 페르소나별 메타 (이름, 아이콘, 색상, 시계)
2. **`web/components/PersonaSwitch.tsx`**
   - 3 → 6 탭 확장
   - 모바일 대응 (가로 스크롤 또는 더보기 메뉴)
3. **페르소나별 카드 UI**
   - Event Analyst: 확실성 점수 배지, 시나리오 분석, 참고 통계 구간
   - Macro PM: 6 국면 시각화, 4 사이클 게이지
   - Korean Specialist: 한국 특수 점수 5각형 차트
4. **사용자 가이드 모달**
   - "각 페르소나는 어떻게 다른가요?" 도움말

#### 검증
- [ ] 6 페르소나 토글 정상 동작
- [ ] 모바일 + 데스크탑 모두 확인
- [ ] a11y (탭 키보드 네비게이션)

---

## ✅ Week D 완료 기준

- [ ] 3개 페르소나 코드 작성 완료
- [ ] 3개 시스템 프롬프트 v1+ 작성
- [ ] LangGraph 6 페르소나 분기 동작
- [ ] Frontend 6 페르소나 UI 완성
- [ ] reviewer subagent 5회 호출
- [ ] LEGAL 검증 strict 통과
- [ ] 5개 종목 × 6 페르소나 = 30건 분석 정상 완료

---

## 🚨 위험 신호

1. **페르소나 응답 일관성 깨짐**: 시스템 프롬프트 fine-tuning 필요
2. **데이터 부재로 페르소나 분석 불가**: graceful degradation 강화
3. **Frontend 모바일 UI 깨짐**: 6개 탭 horizontal scroll 처리
4. **LangGraph 분기 비용 폭증**: 캐싱 전략 재검토

---

## 📊 Day별 체크리스트

| Day | 산출물 | 커밋 |
|-----|-------|-----|
| 1 | event_analyst.py + personas/event.md v2.1 | feat(v2/persona): event analyst v1 |
| 2 | event_analyst 검증 + reviewer | feat(v2/persona): event analyst validated |
| 3 | macro_pm.py + korean_specialist.py | feat(v2/persona): macro pm + korean specialist |
| 4 | graph.py 6 분기 통합 | feat(v2/graph): 6-persona routing |
| 5 | PersonaSwitch 6 탭 + 카드 UI | feat(v2/web): 6-persona UI |
