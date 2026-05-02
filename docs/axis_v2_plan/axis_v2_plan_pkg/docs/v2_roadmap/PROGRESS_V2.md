# Axis v2 — 6 Persona Expansion 진척 기록

> **브랜치**: `feature/v2-six-personas` (axis-ai-layer에서 분기, 2026-05-02)
> **현재 위치**: Week A Day 4 진행 중

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

### Day 4 — 6대 국면 매핑 + 매크로 캘린더 ✅ (commit pending)

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
