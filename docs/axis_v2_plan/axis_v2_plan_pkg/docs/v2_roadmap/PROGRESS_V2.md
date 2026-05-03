# Axis v2 — 6 Persona Expansion 진척 기록

> **브랜치**: `feature/v2-six-personas` (axis-ai-layer에서 분기, 2026-05-02)
> **현재 위치**: Week E 종료 (2026-05-03) — 베타 출시 준비 완료

---

## 📅 Week E — 검증 + 최적화 + 베타 준비

### Day 1-2 — 60건 회귀 테스트 매트릭스 ✅ (commit pending)

| 산출물 | 비고 |
|--------|------|
| `tests/regression/test_60_cases.py` | 6 페르소나 × 10 종목 매트릭스 (mock 모드 + `--real` 통합 모드) |
| 73 단위 테스트 PASS | 매트릭스 정합성 60 + 라우팅 + 차별성 + LEGAL + 시간시계 |

**테스트 매트릭스 다양성**: 한국 5종목 + 미국 4종목 + ETF 1종목.
- 한국: 005930/207940/010060/005380/035720
- 미국: AAPL/RKLB/NVDA/JPM
- ETF: TLT (매크로 케이스)

`--real` 모드는 ANTHROPIC_API_KEY + Firestore 필요 (예상 비용 ~₩12,000).

### Day 3 — LEGAL 강화 + persona_consistency_check ✅ (commit pending)

| 산출물 | 비고 |
|--------|------|
| `scripts/legal_check.py` 강화 | "신호" + "시그널" 변형 양쪽 차단 (agents/base.py와 일치) |
| `scripts/persona_consistency_check.py` | 6 페르소나 프롬프트 정합성 + 백엔드/프론트엔드 alignment |

**legal_check** 89 파일 0 위반.
**persona_consistency_check** 6 페르소나 통과:
- 모든 프롬프트에 LEGAL Hard Rules + 절대 금지 키워드
- event 페르소나 v2.1 핵심 키워드 (확실성/scenario_analysis/summary_neutral/current_position_vs_history)
- macro 6 국면 키워드 (Goldilocks/Reflation/Stagflation/Risk-Off/Recovery/Late Cycle)
- korean 5 핵심 키워드 (외국인/재벌/밸류업/거버넌스/공매도)
- backend ALL_PERSONAS == frontend types/persona.ts (6개 일치)

### Day 4 — 비용 측정 + 최적화 옵션 ✅ (commit pending)

| 산출물 | 비고 |
|--------|------|
| `scripts/measure_v2_cost.py` | 페르소나별 1회 호출 토큰/비용 추정 (theoretical) |

**1회 분석 비용 (warm cache 가정)**:
- Strategist 페르소나(blackrock/ark/graham): research+analyst+validator+strategist = **₩259**
- Event Analyst: **₩51**
- Macro PM: **₩43**
- Korean Specialist: **₩46**

**최적화 옵션 검토**:
- Option 1: Strategist Sonnet 다운그레이드 → ₩190 → ₩38 (절감 80%) — 회귀 테스트 60건 재실행 후 결정
- Option 2: 시스템 프롬프트 캐싱 — 이미 자동 적용 (1024+ chars 시 cache_control)
- Option 3: research/analyst/validator Firestore 캐시 → Strategist만 페르소나 수만큼 — backlog

### Day 5 — 베타 준비 보고서 + 최종 검증 ✅ (commit pending)

| 산출물 | 비고 |
|--------|------|
| `docs/v2_roadmap/BETA_READINESS.md` | 6 페르소나 동작 검증 + 비용 정책 + 한계 + 출시 체크리스트 |
| PROGRESS_V2.md 최종 갱신 | Week C/D/E 섹션 통합 |

**베타 출시 결정 체크리스트**:
- ✅ 회귀 테스트 통과율 100% (73/73 mock)
- ✅ LEGAL strict 0건
- ✅ 6 페르소나 분기 정상 (route_by_persona 8 케이스)
- ✅ graceful degradation (event/macro/korean 모두 fallback 응답)
- ✅ 페르소나 차별성 (persona 필드 식별자 일관)
- ✅ 시간 시계 일관 (frontend ↔ backend)
- ✅ TypeScript tsc --noEmit clean
- ✅ 비용 정책 산정
- ⏳ 분석 시간 실측 (Cloud Run staging 별도)
- ⏳ Cloud Run 안정성 (배포 별도)

---

## ✅ 프론트엔드 마감 + 3단계 검증 (2026-05-03 후속)

Week D Day 5 산출물 점검에서 발견 — **신규 3 페르소나 결과 카드 UI가 누락**되어 있어
사용자가 event/macro/korean 탭 클릭 시 백엔드 400 에러 + 빈 화면.

추가 commit (5건):
1. `feat(v2/web): 6 페르소나 결과 카드 + 백엔드 직렬화 + SSE 분기` (`e1b3051`)
   - 백엔드: `_PERSONAS` 6개로 확장, `valid_persona` 갱신, analyze 응답에 event/macro/korean 직렬화, SSE `event_complete`/`macro_complete`/`korean_complete` 이벤트
   - 프론트엔드 타입: `EventAnalystResult`/`MacroPmResult`/`KoreanSpecialistResult` + nested 12 타입
   - 신규 카드: `EventAnalystCard` (4차원 확실성 + 시나리오 + 영향 매핑), `MacroPmCard` (6 국면 + 4 사이클 게이지 + US/KR 막대), `KoreanSpecialistCard` (SVG 5각형 차트)
   - `AnalyzeView` 페르소나별 분기

2. `fix(v2): Pydantic default — Claude 응답 누락 시 검증 통과` (`0613f00`)
   - 3단계 풀 E2E에서 발견: Claude Sonnet이 응답에 `scenario_analysis` 등 종종 누락 → Pydantic 검증 실패 → Refused fallback
   - 모든 신규 페르소나 모델에 `Field(default_factory=...)` 추가
   - 임시 방어책 — 근본 해결은 §6 backlog (페르소나 시스템 프롬프트 강화)

### 3단계 검증 결과

| 단계 | 결과 |
|------|------|
| 1. `next build` | ✅ Compiled successfully + TypeScript clean (15 라우트 정적/동적) |
| 2. Chrome DevTools mock 렌더 | ✅ 데스크톱 + 모바일(375x812) 풀 렌더, 콘솔 에러 0건, 5각형 차트 + 4 사이클 게이지 + 4차원 배지 정상, a11y tab role + alt text |
| 3. 풀 E2E (FastAPI uvicorn + 실 Sonnet) | ✅ SSE 시퀀스 (start → event_complete → complete) 정확, 실 LLM 응답 mode=Full Analysis / final_score=8.8 / sample_size=11 |

전체 회귀: **645 PASS / 18 skipped(integration)**.

---

## ✅ Week E 종료 — Axis v2 베타 출시 준비 완료

**5일 누적 (Week E)**:
- Commit 4건 (Day 1-2 + 3 + 4 + 5)
- 코드 ~1,200줄 추가 (회귀 테스트 + 검증 스크립트 + 보고서)
- 단위 테스트 73 신규 PASS

**Week A~E 전체 누적**:
- **23 모듈** (Week A 6 + B 7 + C 7 + D 3 페르소나 + E 검증)
- **639 단위 테스트** PASS (A 168 + B 204 + C 124 + D 70 + E 73)
- **6 commit/주차 = 28 commit 전체**
- **6 페르소나 LangGraph 라우팅** + Frontend 통합
- **LEGAL 정책** + fabrication 안전망 + graceful degradation 모두 적용
- **비용 산정**: 분석당 ₩43~₩259

상세는 `docs/v2_roadmap/BETA_READINESS.md` 참조.

---

## 📅 Week D — 페르소나 구현 + LangGraph + Frontend 통합

### Day 1-2 — Event Analyst 페르소나 ✅ (commit `a4962f0`)

| 산출물 | 비고 |
|--------|------|
| `personas/event.md` | 시스템 프롬프트 v2.1 (4차원 확실성 + scenario + summary_neutral + current_position_vs_history) |
| `agents/event_analyst.py` | Pydantic 입출력 + 데이터 라우팅 + 사후 일관성 보정 + LEGAL 후처리 |
| `tests/test_event_analyst.py` | 29 테스트 |

**핵심 동작**:
- 데이터 수집 라우팅: KR=공매도, US=options+yfinance, IPO 2차 수혜 매핑
- LLM 유사 이벤트 추론(event_inference_cache) — async safe
- 사후 일관성: final_score 재계산 / mode/badge 강제 / sample_reliability 자동 분류
- fabrication_warning 자동 첨부
- 단정어 후처리 필터 (filter_forbidden)
- 확실성 < 3 사전 차단 (Refused 모드 — Claude 호출 skip)

### Day 3 — Macro PM + Korean Specialist ✅ (commit `a3c5378`)

| 산출물 | 비고 |
|--------|------|
| `agents/macro_pm.py` + `personas/macro.md` | 4 사이클 + 6 국면 + 동적 가중치 |
| `agents/korean_specialist.py` + `personas/korean.md` | 6단계 분석 + 5변수 가중 점수 |
| 23 단위 테스트 | Macro 13 + Korean 10 |

**Macro PM 핵심**:
- 동적 가중치: KR 종목 60%/40%, US 종목 90%/10%, ETF/매크로 70%/30%
- Week B 통합: cycle_detector + regime_detector 정량 결과를 Claude 입력에 주입
- 사후 일관성: regime은 정량 결과 강제, weighting은 결정값 강제

**Korean Specialist 핵심**:
- 6단계 분석 (외국인/재벌/밸류업/테마/정책/매크로)
- Week A 6 모듈 통합: korea_supply + chaebol + governance + buyback + valueup + short
- 부분 실패 graceful (각 모듈 독립 try/except)
- 5 점수 가중 평균 (외국인 35%/거버넌스 20%/밸류업 20%/테마 15%/정책 10%)

### Day 4 — LangGraph 6 페르소나 통합 ✅ (commit `3e4c374`)

| 산출물 | 비고 |
|--------|------|
| `agents/graph.py` | 6 페르소나 분기 + state 확장 |
| `tests/test_graph_routing.py` | 18 테스트 |

**아키텍처**:
- 페르소나 그룹: STRATEGIST_PERSONAS={blackrock,ark,graham}, DATA_DRIVEN_PERSONAS={event,macro,korean}
- START → route_by_persona 분기:
  - strategist_flow → fanout(research+analyst)→validator→strategist
  - event/macro/korean → 단일 노드 → END
- AnalysisState에 event_output/macro_output/korean_output + event_type/event_target/primary_ticker 추가
- Graceful degradation: 각 노드 try/except → fallback 응답 빌더

### Day 5 — Frontend 6 페르소나 UI ✅ (commit `f646ec4`)

| 산출물 | 비고 |
|--------|------|
| `web/types/persona.ts` | PersonaId enum 6개 + PERSONA_META + 그룹 헬퍼 |
| `web/store/personaStore.ts` | v1→v2 마이그레이션 (구 enum이면 'blackrock' 복귀) |
| `web/components/persona/PersonaSwitch.tsx` | 6 탭 + 모바일 가로 스크롤 + a11y |
| `web/components/persona/PersonaGuideModal.tsx` | "각 페르소나는 어떻게 다른가요?" 모달 |
| `web/components/analyze/AnalyzeView.tsx` | 인라인 PersonaTabs 제거 → PersonaSwitch 사용 |
| `web/types/api.ts` | Persona/StrategistResult가 PersonaId 사용 (단일 source) |

**TypeScript**: tsc --noEmit clean.

---

## 📅 Week C — 이벤트 데이터 인프라

### Day 1 — yfinance 옵션 시그널 ✅ (commit `5a50ac2`)

| 산출물 | 비고 |
|--------|------|
| `utils/data_collectors/options_signals.py` | calculate_options_signals + VKOSPI 보조, PCR(volume+OI) + ATM IV |
| 단위 테스트 18건 | mock yfinance, ATM band ±5%, PCR/IV 분기, 30분 캐시, graceful |

`option_chain(date)` positional 인자, `fast_info → info` fallback. LEGAL: 단정 표현 회피 ("Put 우세/Call 우세/균형"만).

### Day 2 — 기업 이벤트 (DART + EDGAR + yfinance) ✅ (commit `805d244`)

| 산출물 | 비고 |
|--------|------|
| `utils/data_collectors/dart_event_collector.py` | 7 카테고리 (M&A/buyback/CB/증자/분할/배당/실적), buyback subtype은 dart_buyback에 위임 |
| `utils/data_collectors/edgar_collector.py` | SEC submissions API + 22개 8-K Item 매핑, User-Agent 강제 |
| `utils/data_collectors/yfinance_event_collector.py` | earnings_dates + dividends + quarterly_income_stmt |
| 단위 테스트 52건 | DART 분류 9 + EDGAR client 14 + yfinance event 9 + buyback 위임 + 8-K dedupe |

EDGAR User-Agent에 이메일 누락 시 ValueError. yfinance는 신구 컬럼 양쪽 graceful 매핑 (EPS Estimate / epsEstimate).

### Day 3 — 매크로 이벤트 메타 + IPO 큐레이션 ✅ (commit `f8ff2e7`)

| 산출물 | 비고 |
|--------|------|
| `data/macro_event_metadata.json` | 7 이벤트 (FOMC/BOK/US_CPI/KR_CPI/US_GDP/KR_GDP/US_EMPLOYMENT) 변동성 통계 |
| `data/upcoming_ipo.json` | 5건 수동 큐레이션 (SpaceX→RKLB/ASTS/IRDM, 케이뱅크→323410, LG CNS, Stripe, Databricks) |
| `utils/data_collectors/event_metadata.py` | get_event_meta + find_ipos_for_secondary + get_high_certainty_ipos |
| 단위 테스트 16건 | 스키마 정합성 + LEGAL 경고 필수 + 2차 수혜 매핑 검증 |

LEGAL: `fabrication_warning` + `no_recommendation_disclaimer` 필수 필드.

### Day 4 — LLM 유사 이벤트 추론 캐시 ✅ (commit `c399720`)

| 산출물 | 비고 |
|--------|------|
| `utils/data_collectors/event_inference_cache.py` | Claude API + 24h 캐시 + SIMILAR_EVENT_PROMPT |
| 단위 테스트 28건 (이후 30건) | 표본 신뢰도 + JSON 추출 + 단정 표현 차단 + 캐시 hit/miss + API 실패 graceful |

**LEGAL/Fabrication 안전망 (자동 첨부)**:
- 표본 < 5: `statistical_summary_suppressed=True` (정성 분석만)
- 표본 5-9: "참고용" / 표본 ≥ 10: "신뢰 가능 (단, fabrication 경고 유지)"
- `fabrication_warning` + `verification_needed` (3건) + `no_recommendation_disclaimer` 강제
- `FORBIDDEN_PATTERNS_KO` 정규식 — "매수신호"/"매수 시그널" 변형까지 차단

### Day 5 — Jobs + Reviewer + LEGAL ✅ (commit pending)

| 산출물 | 비고 |
|--------|------|
| `jobs/daily_options_collect.py` | 와치리스트 미국 종목 옵션 + VKOSPI, dry-run 지원 |
| `jobs/weekly_event_calendar_sync.py` | DART + yfinance + EDGAR 통합, KR/US 분리, env 미설정 시 부분 skip |
| `tests/data_collectors/test_event_jobs.py` | 7 통합 테스트 (dry-run, 부분 실패, EDGAR cik_lookup 분기) |

**Reviewer subagent 호출 (5 모듈 일괄)** — HIGH 4 / MEDIUM 7 / LOW 6 발견 → HIGH 즉시 fix:
- HIGH: `_scrub_forbidden` 단순 substring → 정규식 + 변형/동의어 차단 (FORBIDDEN_PATTERNS_KO)
- HIGH: `sample_size` int 캐스트가 문자열에 폭파 → `_safe_int_sample_size` 추출 헬퍼
- HIGH: dart_event_collector batch.commit 예외 미격리 → chunk 단위 try/except
- HIGH: `_ITEM_RE` 8-K 코드 regex가 "10.01"을 "0.01"로 오매칭 → `(?<!\d)...(?!\d)` 가드
- MEDIUM (적용): 옵션 만기일 명시적 sorted, yfinance df sort_index 후 head/tail
- LOW: 동기 래퍼 docstring에 "이벤트 루프 외부 전용" 강조

**LEGAL sweep**: 모든 LLM 응답에 fabrication 경고 + no_recommendation_disclaimer 자동 첨부 (event_inference_cache 검증). DART/EDGAR/yfinance 수집 모듈은 raw data 보관만 — 단정 표현 생성 X.

**전체 회귀**: 496 PASS (Week A 168 + Week B 204 + Week C 124).

---

## ✅ Week C 종료 — 이벤트 데이터 인프라 완성

**5일 누적**:
- Commit 5건 (Day 1~4 + Day 5)
- 코드 ~3,400줄 추가 (모듈 ~2,200 + 테스트 ~1,200)
- 테스트 124 신규 PASS
- Reviewer 1회 호출 (5 모듈 일괄)

**산출 모듈**:
1. `options_signals.py` — yfinance 옵션 PCR/ATM IV, VKOSPI 보조
2. `dart_event_collector.py` — DART 7 이벤트 카테고리 (buyback 위임)
3. `edgar_collector.py` — SEC 8-K 22개 Item 매핑
4. `yfinance_event_collector.py` — 미국 실적/배당 일정
5. `event_metadata.py` + `data/macro_event_metadata.json` + `data/upcoming_ipo.json` — 매크로 변동성 메타 + 수동 IPO 큐레이션
6. `event_inference_cache.py` — Claude LLM 유사 이벤트 추론 + LEGAL 안전망
7. `daily_options_collect.py` — 일일 옵션 수집 Job
8. `weekly_event_calendar_sync.py` — 주간 KR/US 이벤트 통합 Job

**Cloud Run Job 등록 가이드 (배포 시)**:
```bash
# Daily options (06:30 KST = 21:30 UTC 전날)
gcloud run jobs create axis-daily-options \
  --image=<axis-staging image> --command=python --args=-m,jobs.daily_options_collect \
  --region=asia-northeast3
gcloud scheduler jobs create http daily-options \
  --schedule="30 21 * * *" --time-zone="UTC" --uri=<job-trigger-url>

# Weekly events (매주 일요일 22:00 KST = 13:00 UTC)
gcloud run jobs create axis-weekly-events \
  --command=python --args=-m,jobs.weekly_event_calendar_sync \
  --set-secrets=DART_API_KEY=dart-api-key:latest,EDGAR_USER_AGENT=edgar-ua:latest
gcloud scheduler jobs create http weekly-events --schedule="0 13 * * 0" --time-zone="UTC"
```

### 잔여 TODO (별도 PR)

| TODO | 우선순위 | 작업량 |
|------|---------|--------|
| EDGAR ticker→CIK 매핑 자동 빌드 (현재 cik_lookup 수동 주입) | 🟡 중 | 2h |
| KRX 코스피200 옵션 IV/PCR 보조 (yfinance VKOSPI는 시장 전체) | 🟡 중 | 3h |
| upcoming_ipo.json 월 1회 갱신 SOP 문서화 | 🟢 저 | 30m |
| Claude API 비용 monitoring (event_inference 호출 추적) | 🟠 높 (운영 전) | 1h |

---

## 📅 Week B — 매크로 데이터 인프라

### Day 1 — FRED API ✅ (commit `40d4396`)

| 산출물 | 비고 |
|--------|------|
| `utils/data_collectors/fred_client.py` | FREDClient + FRED_SERIES 12 매핑 (금리/경기/인플레/통화/원자재) |
| 단위 테스트 35건 | 매핑/마스킹/페이지/예외 |

실데이터 검증 (5 시리즈 × 1년, 7초): Fed 4.33→3.64% 인하 사이클, 10Y-2Y 스프레드 정상화 (0.30→0.52), CPI +3% 인플레.

### Day 1.5 — Reviewer Phase 1 일괄 fix ✅ (commit `af3d5f1`)

8개 reviewer subagent 병렬 검토 → HIGH 10/MEDIUM 17/LOW 9 발견. Phase 1 13건 즉시 적용 (보안/LEGAL/점수 정확성).
PROGRESS_V2.md에 검증 워크플로우 정책 명문화 (모듈 작성 직후 reviewer 호출 의무).

### Day 5 — 일일/월별 Job + Week B 종료 ✅ (commit pending)

| 산출물 | 비고 |
|--------|------|
| `jobs/daily_macro_collect.py` | FRED 13 + ECOS 6 verified = 19 시리즈 일일 수집 + 변동 감지 |
| `jobs/monthly_regime_calc.py` | 사이클 + 국면 재계산 + 국면 전환 감지 + Firestore macro_regime_history |
| `tests/data_collectors/test_macro_jobs.py` | 단위 + 통합 테스트 25건 |
| `fred_client.py` | gdp_yoy_us 추가 (A191RL1Q225SBEA) — cycle_detector 입력용 |

**Reviewer 1회 호출 (Job 모듈)** — HIGH 1 / MEDIUM 2 / LOW 2 발견 → 모두 fix:
- HIGH: CYCLE_INPUT_FIELDS 매핑 불일치 (US gdp_yoy → "gdp_yoy_us" FRED_SERIES에 미존재) → FRED_SERIES에 추가 + KR unemployment/gdp 미수집 명시 (DATA_QUALITY_KNOWN_GAPS)
- MEDIUM: significant_change 임계 단위 불일치 → indicator_key별 rule (절대값/percent/percent_pp 분리)
- MEDIUM: GDP 분기 데이터 14일 윈도우 부족 → freq별 동적 (분기 ±45일/95일)
- LOW: 변동 감지 시 exit 1 → exit 0 + Cloud Logging severity NOTICE 분리
- LOW: 같은 일자 재실행 시 transition 손실 → exclude_date 파라미터로 자기 자신 제외

**LEGAL sweep**: grep 권유성 단어 0건 (모든 매칭이 안전한 컨텍스트 — pykrx 컬럼명 / LEGAL 경고 docstring / 통계 용어).

**전체 회귀**: 372 PASS (Week A 168 + Week B 204).

---

## ✅ Week B 종료 — 매크로 데이터 인프라 완성

**5일 누적**:
- Commit 6건 (Day 1~5 + Phase 1 fix)
- 코드 ~5,800줄 추가
- 테스트 204 신규 PASS
- Reviewer 5회 호출 (Day 1 일괄 + Day 2~5 모듈별)

**산출 모듈**:
1. `fred_client.py` — FRED 13 시리즈 (금리/경기/인플레/통화/원자재/GDP)
2. `ecos_client.py` — ECOS 8 통계 (6 verified, 2 갱신 TODO)
3. `cycle_detector.py` — 4 사이클 판정 (금리/경기/인플레/통화)
4. `regime_detector.py` — 6 국면 매핑 (Goldilocks/Reflation/Stagflation/Risk-Off/Recovery/Late Cycle + Transition)
5. `macro_calendar.json` — 60 매크로 이벤트 (FOMC/BOK/CPI/GDP/고용)
6. `daily_macro_collect.py` — 일일 수집 Job + 변동 감지
7. `monthly_regime_calc.py` — 월별 사이클+국면 재계산 + 전환 감지

**Cloud Run Job 등록 가이드 (배포 시)**:
```bash
# Daily (06:00 KST = 21:00 UTC 전날)
gcloud run jobs create axis-daily-macro-collect \
  --image=<axis-staging image> --command=python --args=-m,jobs.daily_macro_collect \
  --set-secrets=FRED_API_KEY=fred-api-key:latest,ECOS_API_KEY=ecos-api-key:latest \
  --region=asia-northeast3
gcloud scheduler jobs create http daily-macro \
  --schedule="0 21 * * *" --time-zone="UTC" --uri=<job-trigger-url>

# Monthly (매월 1일 06:00 KST)
gcloud run jobs create axis-monthly-regime --image=<...> --args=-m,jobs.monthly_regime_calc
gcloud scheduler jobs create http monthly-regime --schedule="0 21 1 * *" --time-zone="UTC"
```

### 잔여 TODO (별도 PR)

| TODO | 우선순위 | 작업량 |
|------|---------|--------|
| ECOS gdp_yoy + cpi_core 코드 갱신 (한국은행 개편) | 🟡 중 | 1-2h |
| KR unemployment_rate ECOS_CODES 추가 | 🟡 중 | 1h |
| Cloud Run Secret Manager 등록 (FRED/ECOS/DART 키) | 🔴 높 (배포 전) | 30m |
| Firestore composite index 등록 (macro_indicators ticker+date) | 🔴 높 (운영 전) | 15m |
| KRX 외국인 5년 풀 백필 (Week A 잔여) | 🔴 높 | ~3h Cloud Run Job |

---

### Day 4 — 6대 국면 매핑 + 매크로 캘린더 ✅ (commit `df2d2af`)

| 산출물 | 비고 |
|--------|------|
| `utils/data_collectors/regime_detector.py` | 6 국면 매핑 (Goldilocks/Reflation/Stagflation/Risk-Off/Recovery/Late Cycle) + Transition |
| `data/macro_calendar.json` | 2026 FOMC 8회 + BOK 8회 + CPI 24회 + GDP 8회 + 고용 12회 = 60건 |
| 단위 테스트 28건 | 6 국면 명확 매칭 + 4 알려진 시점 + 동률 처리 + 캘린더 + LEGAL |

**4 알려진 시점 검증 (학계 합의 일치)**:
- 2022-09: Late Cycle 4/4
- 2020-04: Recovery 4/4
- 2017-06: Goldilocks 3/4
- 2008-12: Recovery/Risk-Off 동률 3/3 + transition_to

**Reviewer 1회 호출** — MEDIUM 3 / LOW 2 발견 → 모두 fix:
- Recovery vs Reflation 구조적 중첩 해소 — Recovery=수축 후기만, Reflation=확장 초기만 (학계 정의 부합)
- MIN_PRIMARY_SCORE 2→3 강화 (50% confidence를 primary로 단정 X, 75% 이상만 명확)
- detect_regime_from_cycles KeyError → ValueError (cycle_detector와 일관성)
- 캘린더 fallback 영구 캐시 문제 — 파일 미존재 시 캐시 X (다음 호출 재시도 가능)
- macro_calendar.json _meta에 fed/bok/bls/bea/kostat URL + verification_checklist 추가

### Day 3 — 4대 사이클 판정 ✅ (commit `81f4ff1`)

| 산출물 | 비고 |
|--------|------|
| `utils/data_collectors/cycle_detector.py` | 4 순수 함수 + detect_all_cycles 헬퍼 |
| 단위 테스트 55건 | 경계값 + 알려진 시점 4개 + confidence + country |

**알려진 시점 검증 (학계 합의 일치)**:
- 2022-09 Stagflation → 인상 후반 + 고인플레 가속 + 확장 ✅
- 2020-04 Covid → 인하 시작 + 디플레 우려 + 수축 후기 ✅
- 2017-06 Goldilocks → 인상 후반 + 저인플레 + 확장 ✅
- 2008-12 리먼 → 인하 시작 + 디플레 우려 + 수축 후기 ✅

**Reviewer 1회 호출 (정책 적용)** — HIGH 1 / MEDIUM 2 / LOW 2 발견 → HIGH+MEDIUM 즉시 fix:
- HIGH: 경기 분기 모순 logic — GDP 양수+IP 음수가 강제로 수축 → 명시적 전환기 분류
- MEDIUM: confidence 단위 표준화 (`_normalize_confidence` + STRONG_* 상수)
- MEDIUM: country 인자 추가 (US 1.5% / KR 2.0% 잠재성장률 분리)
- LOW: detect_all_cycles 입력 검증 (REQUIRED_INPUTS + ValueError)

### Day 2 — ECOS API ✅ (commit `2fb0c9e`)

| 산출물 | 비고 |
|--------|------|
| `utils/data_collectors/ecos_client.py` | ECOSClient + ECOS_CODES 8 매핑 (httpx 직접 + freq별 날짜 변환) |
| 단위 테스트 56건 | 매핑/마스킹/페이지/Q 검증/에러 분기 |

**Reviewer 1회 호출 (정책 적용)** — HIGH 2 / MEDIUM 2 / LOW 2 발견 → 즉시 fix.

**실데이터 검증 결과 (8 통계)**:
| 통계 | 코드 | verified | 비고 |
|------|------|----------|------|
| base_rate | 722Y001/0101000/M | ✅ | 3.5→3.0% (인하 사이클) |
| treasury_3y | 817Y002/010200000/D | ✅ | 신규 코드 (721Y001 → 817Y002) |
| treasury_10y | 817Y002/010210000/D | ✅ | 신규 코드 |
| industrial_production | 901Y033/AB00/M | ✅ | I31AA → AB00 + 원계열(item_code2=1) |
| cpi_total | 901Y009/0/M | ✅ | +1.5% |
| usd_krw | 731Y001/0000001/D | ✅ | 1395 → 1470 |
| gdp_yoy | 200Y002/10101/Q | ❌ | ERROR-101 — stat_code 한국은행 개편 |
| cpi_core | 901Y009/QA/M | ❌ | INFO-200 — item_code 변경 |

unverified 2건 (gdp_yoy/cpi_core)은 `verified=False` 마킹 + 갱신 TODO. Day 3 사이클 판정 모듈에서 우회 처리.

---

## 🚧 ECOS 코드 갱신 TODO (별도 PR)

ECOS는 한국은행 통계 분류 개편으로 코드가 변경됨 (spec macro.md §2.4 경고).
다음 두 항목은 한국은행 ECOS 사이트 또는 StatisticTableList API로 신규 코드 재조회 필요:

1. **gdp_yoy (분기별 실질 GDP 성장률)**: 200Y002 무효 → 200Y011/200Y115 등 후보
2. **cpi_core (근원물가)**: 901Y009/QA 무효 → 901Y009의 다른 item_code로 매핑

작업량: 1~2시간 (ECOS 사이트 직접 조회 + 갱신).

---

## 📅 Week A — 한국 시장 데이터 인프라

### Day 1 — 외국인/기관 수급 백필 ✅ (commit `47cc967`)

| 산출물 | 비고 |
|--------|------|
| `utils/data_collectors/korea_supply.py` | KoreaSupplyCollector — 방식A(일자×시장×4투자자) + 방식B(종목별 5년 외국인 보유) |
| `jobs/backfill_korea_supply.py` | CLI Job (sample/full/dry-run) — KOSPI 시총 상위 sample 자동 선정 |
| `tests/data_collectors/test_korea_supply.py` | 23 테스트 PASS — 컬럼 매핑/rate limit/Firestore batch |

**검증 보류**:
- KRX가 로컬 IP 차단 ("LOGOUT" 응답) → 실데이터 sample 미검증
- dry-run으로 코드 흐름만 21 호출 정상 발송 확인

### Day 2 — 분석 헬퍼 + 일일 증분 ✅ (commit `80cc784`)

| 산출물 | 비고 |
|--------|------|
| `KoreaSupplyAnalyzer` (korea_supply.py) | 5종 interpretation_signal 분류 + 4개 헬퍼 함수 |
| `jobs/daily_korea_collect.py` | yesterday + gap 7영업일 자동 보충 + dry-run |
| 단위 테스트 22건 추가 | analyzer 13 + daily Job 9 |

### Day 3 — 재벌 매핑 + 지주사 NAV ✅ (commit `0fd9c03`)

| 산출물 | 비고 |
|--------|------|
| `data/chaebol_groups.json` | 공정위 2024 상위 10대 그룹 (verified) |
| `utils/data_collectors/holding_company.py` | 5개 지주사 (LG/SK/GS/한화/롯데지주) NAV + 5단계 분류 |
| 단위 테스트 25건 추가 | NAV/분류/Firestore mock |

**실측 검증 결과** (Firestore 운영 시총):
- LG 26.52% (중간), SK 86.87% (매우 높음), GS -252% (프리미엄/비상장 NAV 미산입), 한화 67.39% (매우 높음), 롯데지주 21.02% (중간)

### Day 4 — 자사주 정책 (DART) ✅ (commit `4d16f76`)

| 산출물 | 비고 |
|--------|------|
| `utils/data_collectors/dart_client.py` | DART OpenAPI 래퍼 + corpCode.xml ZIP + 페이지네이션 + API 키 마스킹 |
| `utils/data_collectors/dart_buyback.py` | 5종 분류 (burn/buy_decision/buy_complete/trust/dispose) + summarize_history |
| 단위 테스트 35건 추가 | 분류 15 + 마스킹 2 + Client 10 + Collector 8 |

**실데이터 검증** (5종목 × 3년, 22초): 분류 정확도 100% — 삼성전자 2025-02 소각결정 정확 포착.

### Day 5 — 밸류업 + 거버넌스 + 공매도 ✅ (commit pending)

| 산출물 | 비고 |
|--------|------|
| `data/valueup_index.json` | KRX 코리아 밸류업 지수 30종목 (출시 시점 핵심) + 분기 갱신 schema |
| `utils/data_collectors/valueup_index.py` | is_in_valueup_index, get_constituents, get_recent_changes |
| `utils/data_collectors/governance_score.py` | 5변수 자체 평가 (0~10점/등급) + data_completeness 표시 |
| `data/short_selling_policy.json` | 한국 공매도 정책 8건 변동 이력 (2008~2025) |
| `utils/data_collectors/short_selling.py` | KoreaShortSellingCollector + Analyzer + analyze_short_signals |
| 단위 테스트 63건 추가 | valueup 10 + governance 25 + short_selling 28 |

**Week A 종료 — 누적 168 PASS** (Day1: 23 + Day2: 22 + Day3: 25 + Day4: 35 + Day5: 63)

---

---

## 🚧 사용자/외부 작업 TODO (작업 완료 후 별도 timing)

### 🔴 KRX 외국인/기관 5년 풀 백필 (필수)

**현재 상태**: Day 1~2 코드 완성, sample 100×5일 dry-run만 검증.
**결정**: 최종 시스템 테스트는 **전체 종목 5년 실데이터**로 진행 — sample은 임시 검증용.

**실행 옵션**:
1. ⭐ **Cloud Run Job 1회 실행 (권장)** — Week A 종료 후 야간 자동 실행
   - Dockerfile에 `jobs/backfill_korea_supply.py` 진입점 추가
   - `gcloud run jobs create axis-backfill-korea-supply --command=python --args=-m,jobs.backfill_korea_supply,--mode,full`
   - 1회 실행 → ~3시간, Firestore 쓰기 ~$2.3
2. 로컬 야간 실행 — 노트북 점유 ~3시간, KRX IP 차단 풀린 후
3. (병행) 일일 증분 16:30 — `jobs/daily_korea_collect.py` (Cloud Scheduler 등록)

**예상 비용**: pykrx 무료 + Firestore 쓰기 1.25M doc × $0.18/100K = **약 $2.3 (1회)**

**선결 조건**:
- KRX IP 차단 해제 확인 (또는 Cloud Run의 별도 IP 사용)
- Firestore composite index 생성 (`historical_supply` 컬렉션의 `ticker + date`) — Firestore가 첫 쿼리 시 자동 안내

### 🔴 DART 자사주 공시 3년 백필 (Day 4 완료 후)

Day 4 코드 완성 직후 같은 Cloud Run Job 패턴으로 1회 실행. 일일 한도 10K, 3년 백필은 약 5,000~10,000건 → 1일 내 완료.

### 🟡 Cloud Run Secret Manager 등록

DART 키를 Cloud Run Job에서 사용하려면 Secret Manager 등록 필요:
```powershell
gcloud secrets create dart-api-key --data-file=- --project=all-of-asset
# (프롬프트에서 키 붙여넣기 후 Ctrl+Z)
gcloud secrets add-iam-policy-binding dart-api-key \
  --member=serviceAccount:1043976673827-compute@developer.gserviceaccount.com \
  --role=roles/secretmanager.secretAccessor --project=all-of-asset
```

---

**최종 업데이트**: 2026-05-02 (Day 4 작업 시작 시점)

---

## 🔍 검증 워크플로우 정책 (잊지 말 것)

CLAUDE_V2.md "Reviewer Subagent 호출 시점" 정책을 명문화. 매 모듈 작성 직후 적용.

### 표준 검증 단계 (모든 신규 데이터/페르소나/에이전트 모듈에 적용)

| 순서 | 단계 | 도구 | 의무성 |
|------|------|------|--------|
| 1 | **단위 테스트 작성** | pytest (mock 기반) | 🔴 필수 |
| 2 | **테스트 실행 + 회귀 확인** | `py -m pytest tests/data_collectors/` | 🔴 필수 |
| 3 | **실데이터 1회 검증** | 임시 스크립트 (외부 API 모듈만) | 🟠 강력 권장 |
| 4 | **Reviewer subagent 호출** ⭐ | `Agent(subagent_type="general-purpose")` | 🔴 필수 (이전 누락) |
| 5 | **발견 이슈 fix + 회귀 재실행** | 위 1~3 반복 | 🔴 필수 |
| 6 | **`scripts/legal_check.py`** | LEGAL 자동 검출 | 🟡 페르소나 모듈만 (Week D부터) |
| 7 | **commit** | git commit (Conventional commits) | 🔴 필수 |
| 8 | **PROGRESS_V2 갱신** | 본 문서 Day 섹션 | 🔴 필수 |

### Reviewer 검증 관점 (모듈 유형별)

**모든 모듈 공통**:
- LEGAL: 권유성 표현 ("매수/추천/사세요") 0건
- 보안: API 키 하드코딩 X, 로그/예외 마스킹 O
- 비용: 캐싱/rate limit 적절, 호출 폭증 방지
- 에러 처리: 외부 의존성 (API/DB) 예외 graceful 처리
- 데이터 정확성: 단위/날짜 형식 일관, NaN/None 안전

**Korean Specialist 모듈 (Week A)**:
- pykrx 시그니처 정확 (특히 `observation_start` 등 인자명)
- 한국 시장 특수성 (휴장일, 정정 공시, 분기 갱신 데이터)
- 재벌/지주사/밸류업 데이터 한계 명시 (`verified` / `data_completeness`)

**Macro PM 모듈 (Week B)**:
- FRED/ECOS 시리즈 ID 정확성 (특히 ISM PMI 무료 미제공 → INDPRO 대안 명시)
- 사이클 판정 경계값 합리성 (미국과 학계 합의 일치)
- 후행 데이터 표시 ("최근 발표 기준")

**Event Analyst 모듈 (Week C)**:
- 이벤트 확실성 점수 logic
- 단기 트레이딩 영역 — LEGAL 위험 가장 높음

### 위반 시 즉시 조치

- HIGH: commit 차단, 즉시 fix
- MEDIUM: 다음 commit 전 fix
- LOW: 별도 트래킹 (PROGRESS_V2 TODO 섹션)

### 검증 이력 (Week A → B Day 1 누적)

이 정책 명시 이전에 작성된 8개 모듈에 대한 일괄 reviewer 검토는 2026-05-02 진행.
이후 신규 모듈은 본 정책 준수.

---
