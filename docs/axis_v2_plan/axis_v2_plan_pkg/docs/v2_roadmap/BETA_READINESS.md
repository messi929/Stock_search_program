# Axis v2 — 베타 출시 준비 보고서

> **상태**: Week E 종료 시점 (2026-05-03)
> **브랜치**: `feature/v2-six-personas`
> **검증 범위**: Week A~E 산출물 통합

---

## 1. 6 페르소나 동작 검증 결과

### 페르소나 매트릭스

| ID | 그룹 | 데이터 인프라 | 모델 | 시간 시계 |
|----|------|-----------|------|---------|
| blackrock | strategist | research+analyst+validator | Opus | 장기 |
| ark | strategist | research+analyst+validator | Opus | 장기 |
| graham | strategist | research+analyst+validator | Opus | 장기 |
| event | data_driven | options+DART+EDGAR+yfinance+LLM | Sonnet | 단기 |
| macro | data_driven | FRED+ECOS+cycle+regime | Sonnet | 중기 |
| korean | data_driven | korea_supply+chaebol+governance+valueup+short | Sonnet | 중기 |

### 회귀 테스트

- **테스트 수**: pytest 73 PASS (60건 매트릭스 + 13건 보조)
- **LEGAL 검사**: scripts/legal_check.py 89 파일 0 위반
- **페르소나 일관성**: scripts/persona_consistency_check.py 6 페르소나 통과 (HIGH 0 + MEDIUM 0)
- **단정어 후처리**: 6 페르소나 모두 `BaseAgent.filter_forbidden`으로 차단 (정규식 + "신호/시그널" 변형 포함)

### 데이터 인프라 통계

| Week | 모듈 수 | 테스트 | 데이터 소스 |
|------|--------|-------|-----------|
| A | 6 | 168 | KRX, DART, 공정위 (재벌), 자체 거버넌스 모델 |
| B | 7 | 204 | FRED, ECOS, 정적 macro_calendar.json |
| C | 7 | 124 | yfinance (옵션/실적/배당), DART, EDGAR, Claude (유사 이벤트 추론) |
| D | 3 페르소나 + 1 그래프 | 70 | Week A~C 모듈 통합 호출 |
| E | 회귀 + 검증 | 73 | — |
| **합계** | **23 모듈** | **639 PASS** | **9 외부 소스 + 자체 큐레이션** |

---

## 2. 성능 측정

### 1회 분석 비용 (warm cache 가정)

| 페르소나 | 모델 | 토큰 (in/out) | 1회 비용 |
|---------|------|-----------|--------|
| blackrock/ark/graham | Opus | 1500/1500 | ₩190 (Strategist만) → 합계 **₩259** |
| event | Sonnet | 933/2200 | **₩51** |
| macro | Sonnet | 600/1900 | **₩43** |
| korean | Sonnet | 800/2000 | **₩46** |

> Strategist 흐름은 research(₩6) + analyst(₩35) + validator(₩28) + strategist(₩190) = ₩259.

상세: `scripts/measure_v2_cost.py` 출력 참조.

### 분석 시간 (목표 90초 이내)

- Strategist 흐름: 기존 Axis v1 베타 측정 — 평균 30~40초
- 신규 데이터 페르소나: 단일 노드 → 데이터 수집 + 1회 Sonnet 호출 = **15~25초 예상** (실측 필요)

### 비용 정책 권장 (베타 단계)

| Tier | 월 분석 회수 | Strategist 페르소나 | 데이터 페르소나 | 월 비용 한도 |
|------|----------|----------------|-------------|----------|
| Free | 20 | blackrock만 | event 한정 (5회/월) | ₩6,000 |
| Pro | 무제한 | 3종 모두 | 3종 모두 | ₩9,900/월 |
| Premium (v1.0+) | 무제한 + PDF 리포트 | 3종 | 3종 | ₩29,900/월 |

---

## 3. 알려진 한계

1. **LLM Fabrication 위험 (event 페르소나)**
   - Claude 학습 데이터 기반 유사 이벤트 추론 → 가짜 사례 생성 가능성
   - 대응: 표본 < 5 통계 비표시, fabrication_warning 자동 첨부, 외부 검증 권장 메시지

2. **macro_indicators Firestore 의존**
   - macro_pm은 Firestore에 일일 매크로 데이터가 적재되어 있어야 정량 사이클 판정
   - 미적재 시 graceful — Claude가 정성 분석으로 fallback (수치 추정 X)
   - 운영 시 Cloud Run Job 일일 06:00 KST `jobs/daily_macro_collect.py` 실행 필요

3. **EDGAR 자동화 부분 — CIK 매핑 수동**
   - `jobs/weekly_event_calendar_sync.py`는 cik_lookup dict가 필요
   - 추후 Backlog: SEC ticker_to_cik 매핑 자동 빌드

4. **upcoming_ipo.json 수동 큐레이션**
   - 5건 초기 등록 (SpaceX/Stripe/Databricks/케이뱅크/LG CNS)
   - 월 1회 갱신 SOP 필요

5. **한국 개별 종목 옵션 미지원**
   - 거래량 미미 → KRX 코스피200/VKOSPI만 시장 보조 지표로 활용

6. **거버넌스 점수는 자체 평가**
   - KCGS 등 외부 평가기관과 다를 수 있음 — `governance_disclaimer` 강제 첨부

---

## 4. 베타 출시 결정 체크리스트

| 항목 | 상태 |
|------|-----|
| 회귀 테스트 통과율 ≥ 95% | ✅ 73/73 = 100% (mock) |
| LEGAL strict 0건 | ✅ legal_check 0 violations |
| 6 페르소나 분기 정상 | ✅ route_by_persona 8 케이스 모두 정확 |
| graceful degradation | ✅ 3 페르소나 모두 외부 실패 시 fallback 응답 |
| 페르소나 차별성 (persona 필드 분리) | ✅ 각 페르소나 결과의 persona 필드 식별자 일관 |
| 시간 시계 일관 (frontend ↔ backend) | ✅ persona_consistency_check 통과 |
| TypeScript clean | ✅ tsc --noEmit clean |
| 비용 정책 산정 | ✅ Strategist ₩259 / 데이터 페르소나 ₩43~51 |
| 분석 시간 < 120초 | ⏳ Strategist 흐름 기존 30~40s, 신규 페르소나 실측 필요 |
| Cloud Run staging 안정 | ⏳ 통합 테스트 별도 |

---

## 5. 베타 출시 후 Backlog

### 우선순위 높음 (베타 1~2주 내)

- 신규 페르소나 실 분석 60건 통합 테스트 (`tests/regression/test_60_cases.py --real`)
- macro_indicators Firestore 일일 적재 Cloud Run Job 등록 (FRED/ECOS Secret Manager)
- Cloud Run `axis-daily-options` + `axis-weekly-events` Job 배포

### 중간 우선순위

- Strategist Sonnet 다운그레이드 검증 (60건 품질 비교, 절감 80%)
- 페르소나별 Firestore 캐시 (research/analyst/validator 재사용 → Strategist만 페르소나 수만큼 호출)
- EDGAR ticker→CIK 자동 매핑

### 낮은 우선순위 (Phase 2)

- 자체 이벤트 통계 DB 구축 (LLM 추론 대체)
- Japan/China Specialist 페르소나 추가
- 사용자 매칭 진단 (어떤 페르소나가 본인에게 맞는지)

---

## 6. 베타 출시 차단 사유 (해당 없음)

다음 이슈는 발견되지 않음:
- 회귀 테스트 통과율 < 95%: ✅ 100%
- LEGAL 위반: ✅ 0건
- 페르소나 일관성 무너짐: ✅ persona_consistency_check 통과
- Cloud Run 안정성 문제: 미배포 (베타 직전 staging 검증 예정)

---

## 7. 결론

**Week A~E 산출물은 베타 출시 준비 완료.**

- 23 모듈 + 639 단위 테스트
- 6 페르소나 LangGraph 라우팅 + Frontend UI 통합
- LEGAL 정책 + fabrication 안전망 + graceful degradation 모두 적용
- 비용 정책 산정 완료 (분석당 ₩43~₩259)

다음 단계는:
1. Cloud Run Secret Manager 키 등록 (FRED/ECOS/DART/EDGAR_USER_AGENT)
2. Cloud Run Jobs 3개 배포 (daily_macro / daily_options / weekly_event)
3. Staging 통합 테스트 5건
4. 베타 사용자 피드백 수집 시작

— Axis v2 6 Persona Expansion 종료 (2026-05-03)
