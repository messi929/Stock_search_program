# Week B — 매크로 데이터 인프라 작업 가이드

> **목표**: Macro PM 페르소나에 필요한 매크로 지표 + 사이클 자동 판정 시스템 구축
> **소요**: 5일 (Day 1~5)
> **선행 의존성**: 없음 (Week A와 병렬 가능)
> **후속**: Week D Macro PM 페르소나 구현

---

## 🎯 이번 주차 산출물

```
data/
└── macro_calendar.json              # FOMC, 한은, CPI 일정

utils/data_collectors/
├── fred_client.py                   # FRED API (Day 1)
├── ecos_client.py                   # ECOS API (Day 2)
├── cycle_detector.py                # 4대 사이클 판정 (Day 3)
└── regime_detector.py               # 6대 국면 매핑 (Day 4)

jobs/
├── daily_macro_collect.py           # 일일 매크로 수집
└── monthly_regime_calc.py           # 월별 사이클 + 국면 계산

tests/data_collectors/
├── test_fred_client.py
├── test_ecos_client.py
├── test_cycle_detector.py
└── test_regime_detector.py
```

---

## 📅 Day별 작업 상세

### Day 1 — FRED API 연동

**상세 스펙**: `docs/data_infra/macro.md` Section 1

#### 작업 순서

1. **FRED 인증키 발급**
   - https://fred.stlouisfed.org/ 가입
   - API Key 발급 (`FRED_API_KEY` 환경변수)
   - Cloud Run secret 등록

2. **`utils/data_collectors/fred_client.py` 작성**
   - `FREDClient` 클래스
   - 메서드: `get_series()`, `get_latest_value()`
   - **인자명 정확히 사용**: `observation_start`, `observation_end`
   - 핵심 시리즈 ID 상수 (`FRED_SERIES`)

3. **백필 + 일일 수집**
   - 핵심 12개 시리즈만 우선 (금리 4 + 경기 4 + 인플레 3 + 통화 1)
   - 5년 백필 (각 시리즈 1회 호출)
   - 일별 자동 갱신 모듈

4. **테스트**
   - mock fredapi 응답으로 컬럼 매핑 검증
   - 단위 변환 (소수 vs %) 검증

#### Claude Code 프롬프트 예시

```
docs/data_infra/macro.md의 Section 1을 읽어주세요.

이제 다음을 진행해주세요:

1. utils/data_collectors/fred_client.py 생성
   - FREDClient 클래스
   - 인자명 주의: observation_start, observation_end (start, end 아님)
   - FRED_SERIES 상수 (DFF, DGS2, DGS10, T10Y2Y, INDPRO, UNRATE, CPIAUCSL, CPILFESL, DTWEXBGS 등)

2. ISM PMI 대안:
   - INDPRO (산업생산) + UNRATE (실업률) 조합으로 경기 사이클 판정
   - 응답에 "PMI 대신 산업생산 사용" 명시

3. tests/data_collectors/test_fred_client.py 작성

준비되면 어떻게 진행할지 계획 먼저 알려주세요.
```

#### 검증

- [ ] FRED 12개 시리즈 5년 백필 성공
- [ ] Firestore `macro_indicators` 컬렉션 검증
- [ ] 단위 일관성 (% vs 소수)

---

### Day 2 — ECOS API 연동

**상세 스펙**: `docs/data_infra/macro.md` Section 2

#### 작업 순서

1. **ECOS 인증키 발급**
   - https://ecos.bok.or.kr/api/ 가입
   - 인증키 발급
   - 환경변수 등록

2. **`utils/data_collectors/ecos_client.py` 작성**
   - `ECOSClient` 클래스 (HTTP 직접 호출)
   - 메서드: `get_statistic_search()`
   - **freq별 날짜 형식 주의**: D=YYYYMMDD, M=YYYYMM, Q=YYYYn, A=YYYY

3. **핵심 통계 코드 매핑**
   - `ECOS_CODES` 상수
   - 통계표 코드 + 통계항목 코드 정확

4. **분기 검증 스크립트**
   - 통계 코드 유효성 자동 검증
   - 코드 변경 감지 시 알림

#### 작업 시 주의사항

⚠️ **ECOS는 통계표 + 통계항목 + 주기 + 날짜 + 항목 코드 조합이 정확해야 응답 옴**
- 잘못된 조합은 빈 응답 반환
- 디버깅: 한국은행 ECOS 사이트에서 먼저 데이터 조회 → URL 패턴 분석

#### 검증

- [ ] 한국 기준금리 5년 시계열 수집 성공
- [ ] CPI, GDP, USD/KRW 수집 성공
- [ ] 통계 코드 유효성 검증 스크립트 통과

---

### Day 3 — 4대 사이클 판정 모듈

**상세 스펙**: `docs/data_infra/macro.md` Section 4

#### 작업 순서

1. **`utils/data_collectors/cycle_detector.py` 작성**
   - 4개 함수: 금리/경기/통화/인플레 판정
   - 각 함수는 dict 반환 (stage + confidence + rationale)

2. **단위 테스트** (가장 중요한 단계)
   - 경계값 테스트 (예: GDP 1.5%, CPI 3%, 4%)
   - 알려진 과거 시점 데이터로 결과 검증
     - 2008-12: Risk-Off
     - 2017-06: Goldilocks
     - 2022-09: Stagflation
     - 2020-04: Recovery 시작

3. **단위 시점 검증 자동화**
   - 과거 시점 매크로 데이터 → 판정 결과
   - 학계/언론 합의와 일치하는지 평가

#### 검증

- [ ] 4개 사이클 판정 함수 모두 구현
- [ ] 단위 테스트 (경계값) 통과
- [ ] 4개 알려진 시점 판정 결과 합리적

---

### Day 4 — 6대 국면 매핑 + 매크로 캘린더

**상세 스펙**: `docs/data_infra/macro.md` Section 5, 6

#### 작업 순서

1. **`utils/data_collectors/regime_detector.py` 작성**
   - `detect_macro_regime()` — 4개 사이클 → 6 국면 매핑
   - 점수 동률/모호 처리 (transition 표시)
   - confidence 점수 계산

2. **`data/macro_calendar.json` 생성**
   - FOMC 8개/년 + BOK 8개/년 + 주요 CPI/GDP 발표일
   - 2026~2027 일정 작성
   - 분기별 갱신 자동화 가능 부분 식별 (Fed 사이트 XML)

3. **`utils/data_collectors/regime_history.py`**
   - 일별 또는 월별 국면 변화 추적
   - Firestore `macro_regime_history` 컬렉션

#### 검증

- [ ] 6 국면 매핑 함수 단위 테스트
- [ ] 4개 알려진 시점 국면 판정 검증
- [ ] macro_calendar.json 2026 일정 완성

---

### Day 5 — 일일 수집 Job + 통합

#### 작업 순서

1. **`jobs/daily_macro_collect.py`**
   - 매일 06:00 (미국 장 마감 후) Cloud Run Job
   - FRED + ECOS 갱신
   - 변동 큰 지표는 알림 트리거

2. **`jobs/monthly_regime_calc.py`**
   - 월 1회 + 매크로 발표 직후 트리거
   - 4 사이클 + 6 국면 재계산
   - 국면 전환 시 로깅 + 알림

3. **Reviewer subagent 호출** (4회)
   - fred_client.py
   - ecos_client.py
   - cycle_detector.py
   - regime_detector.py

4. **LEGAL 검증 + 통합 테스트**
   - 매크로 데이터에 권유성 표현 X (사이클 판정만, 매수 권유 X)
   - 통합 시나리오: 현재 시점 매크로 → 국면 판정

#### 검증

- [ ] Cloud Run Job 등록
- [ ] reviewer 4회 통과
- [ ] LEGAL 검증 통과

---

## ✅ Week B 완료 기준

- [ ] 4개 모듈 모두 구현 완료 (FRED, ECOS, cycle, regime)
- [ ] 백필: FRED 12개 시리즈 5년, ECOS 8개 통계 5년
- [ ] 일일 + 월별 Cloud Run Job 등록
- [ ] reviewer subagent 4회 호출
- [ ] LEGAL 검증 통과
- [ ] PROGRESS_V2.md Week B 섹션 작성

---

## 🚨 위험 신호

1. **FRED API rate limit 도달**: 정상 사용 시 거의 불가능 → 코드 버그 의심
2. **ECOS 통계 코드 변경**: 한국은행 분류 개편 → 매핑 갱신 필요
3. **사이클 판정 결과 학계 합의와 다름**: 임계값 조정 필요
4. **매크로 캘린더 누락**: Fed/BOK 일정 일부 누락 시 사용자 알림

---

## 📊 Day별 체크리스트

### Day 1 종료
- [ ] fred_client.py 구현
- [ ] FRED 5년 백필 완료
- [ ] git commit: "feat(v2/macro): FRED API client + backfill"

### Day 2 종료
- [ ] ecos_client.py 구현
- [ ] ECOS 5년 백필 완료
- [ ] git commit: "feat(v2/macro): ECOS API client + Korean macro indicators"

### Day 3 종료
- [ ] cycle_detector.py 구현 (4개 사이클 판정)
- [ ] 단위 테스트 통과
- [ ] git commit: "feat(v2/macro): 4-cycle stage detection"

### Day 4 종료
- [ ] regime_detector.py 구현
- [ ] macro_calendar.json 작성
- [ ] git commit: "feat(v2/macro): 6-regime mapping + calendar"

### Day 5 종료
- [ ] 일일/월별 Cloud Run Job 등록
- [ ] reviewer 4회 + LEGAL 검증 통과
- [ ] PROGRESS_V2.md 업데이트
- [ ] **Week B 종료 보고**: 사용자에게 보고 + Week C 시작 의사 확인
