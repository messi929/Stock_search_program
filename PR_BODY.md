# Axis v2 — 6 Persona Expansion (Week A~E)

> **PR 생성 URL**: https://github.com/messi929/Stock_search_program/pull/new/feature/v2-six-personas
>
> **이 파일은 PR 본문 템플릿입니다 — 위 링크에서 새 PR 만들 때 복붙하세요.**

---

## Summary

기존 3 페르소나(blackrock/ark/graham) 위에 **데이터 기반 3 페르소나(event/macro/korean)**를 추가한 5주 작업.

- **23 신규 모듈** (Week A 6 + B 7 + C 7 + D 3 페르소나)
- **645 단위 테스트 PASS** (전 회귀 + 18 통합 테스트는 `--run-integration` 시에만)
- **6 페르소나 LangGraph 라우팅** + Frontend UI 통합
- **LEGAL 정책** + fabrication 안전망 + graceful degradation

상세: [docs/v2_roadmap/PROGRESS_V2.md](docs/axis_v2_plan/axis_v2_plan_pkg/docs/v2_roadmap/PROGRESS_V2.md), [BETA_READINESS.md](docs/axis_v2_plan/axis_v2_plan_pkg/docs/v2_roadmap/BETA_READINESS.md)

---

## 변경 사항 (Week별)

### Week A — 한국 시장 데이터 인프라 (6 모듈)
- `korea_supply.py` — 외국인/기관 수급 (KRX, 5년 백필 + 일일 증분)
- `chaebol_groups.json` + `holding_company.py` — 공정위 10대 그룹 + 지주사 NAV
- `dart_client.py` + `dart_buyback.py` — DART 자사주 5종 분류
- `valueup_index.py` — KRX 코리아 밸류업 지수
- `governance_score.py` — 5변수 정량 거버넌스 (자체 평가)
- `short_selling.py` — pykrx 공매도 + 정책 이력

### Week B — 매크로 데이터 인프라 (7 모듈)
- `fred_client.py` — FRED 13 시리즈 (금리/경기/인플레/통화/원자재)
- `ecos_client.py` — 한국은행 ECOS 8 통계 (6 verified)
- `cycle_detector.py` — 4 사이클 정량 판정 (학계 합의 기점 검증)
- `regime_detector.py` — 6 매크로 국면 매핑 + 전환기
- `macro_calendar.json` — 60 매크로 이벤트 (FOMC/BOK/CPI/GDP/고용)
- `daily_macro_collect.py` + `monthly_regime_calc.py` — Cloud Run Jobs

### Week C — 이벤트 데이터 인프라 (7 모듈)
- `options_signals.py` — yfinance PCR/ATM IV + VKOSPI 보조
- `dart_event_collector.py` — 7 이벤트 카테고리 (M&A/buyback/CB/증자/분할/배당/실적)
- `edgar_collector.py` — SEC 8-K 22 Item 매핑 (User-Agent 강제)
- `yfinance_event_collector.py` — 미국 실적/배당 일정
- `macro_event_metadata.json` + `upcoming_ipo.json` + `event_metadata.py`
- `event_inference_cache.py` — Claude LLM 유사 이벤트 추론 + LEGAL 안전망
- `daily_options_collect.py` + `weekly_event_calendar_sync.py` — Cloud Run Jobs

### Week D — 페르소나 + LangGraph + Frontend (3 페르소나 + 라우팅 + UI)
- `agents/event_analyst.py` + `personas/event.md` (v2.1)
- `agents/macro_pm.py` + `personas/macro.md` (4 사이클 + 6 국면 + 동적 가중치)
- `agents/korean_specialist.py` + `personas/korean.md` (6단계 + 5변수 가중)
- `agents/graph.py` — START → route_by_persona 분기 (strategist 흐름 vs 데이터 페르소나)
- `web/types/persona.ts` + `web/components/persona/PersonaSwitch.tsx` + `PersonaGuideModal.tsx`

### Week E — 검증 + 최적화 + 베타 준비
- `tests/regression/test_60_cases.py` — 6 × 10 매트릭스 (mock + `--real`)
- `scripts/persona_consistency_check.py` — 페르소나 캐릭터 일관성
- `scripts/measure_v2_cost.py` — 페르소나별 비용 추정 (Strategist ₩259, 데이터 페르소나 ₩43~51)
- `docs/v2_roadmap/BETA_READINESS.md` — 베타 출시 체크리스트
- `docs/v2_roadmap/DEPLOY_V2.md` — Cloud Run 배포 가이드 + 일괄 스크립트

### 인프라 (베타 출시 전 필요)
- pytest-asyncio 도입 + integration 마커 (기존 18 통합 테스트 자동 skip)
- `Dockerfile`에 `jobs/` COPY 추가 (단일 이미지로 web + 4 Job 통합)
- `deploy-v2-axis-jobs.sh` (Phase 1~4 일괄 배포)

---

## 테스트 결과

```
$ pytest tests/ -q
645 passed, 18 skipped (integration — --run-integration 시 실행)
```

- **LEGAL**: `scripts/legal_check.py` 89파일 0위반
- **페르소나 일관성**: `scripts/persona_consistency_check.py` 6 페르소나 통과
- **TypeScript**: `tsc --noEmit` clean
- **단정 표현 차단**: 정규식 + "신호/시그널" 변형 양쪽

---

## 비용

| 페르소나 | 1회 호출 | 모델 |
|---------|---------|-----|
| blackrock/ark/graham | **₩259** | Opus + Sonnet |
| event | **₩51** | Sonnet |
| macro | **₩43** | Sonnet |
| korean | **₩46** | Sonnet |

Cloud Run 운영 비용: **~₩900/월** (4 Job × 30회 + Firestore 쓰기)

---

## 알려진 한계

1. **LLM Fabrication** (event 페르소나) — 표본 < 5 통계 비표시 + fabrication_warning 자동
2. **macro_indicators Firestore 의존** — daily-macro Job 1주일 누적 후 monthly-regime 정상 동작
3. **EDGAR ticker→CIK 수동 매핑** — 추후 자동화
4. **upcoming_ipo.json 수동 큐레이션** — 월 1회 갱신 SOP
5. **Strategist Sonnet 다운그레이드 검증** — backlog (절감 80% 가능성)

---

## Test plan

### 머지 전 (이번 PR에서 완료)
- [x] 단위 테스트 645 PASS (mock)
- [x] LEGAL strict 0건
- [x] 페르소나 일관성 check 통과
- [x] TypeScript clean

### 머지 후 — Cloud 배포 (DEPLOY_V2.md §1~5)
- [ ] `gcloud secrets create` 4개 (fred/ecos/dart/edgar-user-agent)
- [ ] `bash deploy-v2-axis-jobs.sh` — Cloud Run Jobs 4개 + Scheduler 4개 등록
- [ ] `gcloud run jobs execute axis-daily-macro --wait` — 검증 1회
- [ ] daily-macro 1주일 누적 (macro 페르소나 정량 결과 검증 선결)

### 머지 후 — 단계별 실 분석 검증 (BETA_READINESS.md §5)
- [ ] **Stage 1 Smoke** (~₩200, 1분) — staging에서 event 페르소나 1회 호출
- [ ] **Stage 2 Mini** (~₩1,200, 5분) — 6 페르소나 × 1 종목, 페르소나 분기 + 비용 실측
- [ ] **Stage 3 Full** (~₩12,000, 30~60분) — `pytest tests/regression/test_60_cases.py --real`
  · 선결 조건: Stage 1/2 통과 + daily-macro 1주일 누적 + weekly-events 1회 실행
  · 합격: 60건 중 ≥57 ok / LEGAL 0건 / 평균 시간 < 90초

### 머지 후 — Frontend
- [ ] staging — 6 페르소나 토글 + 모바일 가로 스크롤 + a11y 키보드

---

## 머지 전략

**제안**: `--no-ff` merge로 50 commit 그대로 보존 (Week 단위 역사 추적 가능).
강한 reset 또는 squash는 회피 — Week A~E commit 메시지가 그 자체로 산출물 인덱스 역할.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
