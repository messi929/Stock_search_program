# Week A — 한국 시장 데이터 인프라 작업 가이드

> **목표**: Korean Specialist 페르소나에 필요한 모든 데이터 수집/처리 모듈 구축
> **소요**: 5일 (Day 1~5)
> **선행 의존성**: 없음 (독립 작업)
> **후속**: Week D Korean Specialist 페르소나 구현

---

## 🎯 이번 주차 산출물

```
data/
├── chaebol_groups.json              # 재벌 그룹 매핑
└── short_selling_policy.json        # 공매도 정책 이력

utils/data_collectors/
├── korea_supply.py                  # 외국인/기관 수급 (Day 1-2)
├── holding_company.py               # 지주사 NAV (Day 3)
├── dart_buyback.py                  # 자사주 정책 (Day 4)
├── valueup_index.py                 # 밸류업 인덱스 (Day 5)
├── governance_score.py              # 자체 거버넌스 (Day 5)
└── short_selling.py                 # 공매도/대차 (Day 5)

jobs/
├── backfill_korea_supply.py         # 5년 백필 (Day 1)
└── daily_korea_collect.py           # 일일 증분 (Day 2)

tests/data_collectors/
├── test_korea_supply.py
├── test_holding_company.py
├── test_dart_buyback.py
├── test_valueup_index.py
└── test_short_selling.py
```

---

## 📅 Day별 작업 상세

### Day 1 — 외국인/기관 수급 백필

**상세 스펙**: `docs/data_infra/korea_market.md` Section 1

#### 작업 순서

1. **모듈 스켈레톤 작성** (`utils/data_collectors/korea_supply.py`)
   - `KoreaSupplyCollector` 클래스
   - 두 가지 수집 방식: 일자별 전체 종목 (방식 A) + 종목별 시계열 (방식 B)
   - rate limit: 1초/호출

2. **백필 Job 작성** (`jobs/backfill_korea_supply.py`)
   - 5년 (2021-01-01 ~ 2025-12-31) 데이터 1회 수집
   - 야간 실행 가정 (3시간 소요)
   - 진행 상황 로깅 (loguru)
   - Firestore batch write (500개씩)

3. **단위 테스트** (`tests/data_collectors/test_korea_supply.py`)
   - mock pykrx 응답으로 컬럼 매핑 검증
   - rate limit 호출 검증
   - Firestore 쓰기 batch 검증

#### Claude Code 프롬프트 예시

```
docs/data_infra/korea_market.md의 Section 1을 다시 읽어주세요.

이제 다음 작업을 진행해주세요:

1. utils/data_collectors/korea_supply.py 생성
   - KoreaSupplyCollector 클래스
   - 메서드: collect_daily_snapshot(date), collect_ticker_holding_series(ticker, fromdate, todate)
   - pykrx 함수: get_market_trading_value_and_volume_by_ticker, get_exhaustion_rates_of_foreign_investment_by_date
   - 정확한 인자명 사용 (observation_start, todate 등)

2. jobs/backfill_korea_supply.py 생성
   - 5년 백필 (2021-01-01 ~ 어제)
   - 야간 실행, 진행 로깅

3. tests/data_collectors/test_korea_supply.py 작성
   - mock 응답 + 컬럼 매핑 검증

준비되면 어떻게 진행할지 계획을 먼저 알려주세요.
```

#### 검증 (Day 1 종료 시)

- [ ] 100개 sample 종목으로 1주일치 데이터 수집 성공
- [ ] Firestore에 doc 100 × 5 = 500개 저장 확인
- [ ] pykrx rate limit 위반 없음 (1초/호출 준수)
- [ ] Reviewer subagent 호출 (선택): "Review utils/data_collectors/korea_supply.py for pykrx usage correctness, rate limiting, error handling"

---

### Day 2 — 외국인 5년 추이 분석 함수

**상세 스펙**: `docs/data_infra/korea_market.md` Section 1.4

#### 작업 순서

1. **분석 헬퍼 함수** (`utils/data_collectors/korea_supply.py`에 추가)
   - `get_foreign_5y_trend(ticker)` — 외국인 보유 5년 추이 + 통계
   - `get_consecutive_buy_days(ticker, days_back=30)` — 최근 연속 순매수일
   - `get_30d_net_buy(ticker)` — 30일 누적 순매수
   - `get_dual_buy_signal(ticker)` — 외국인+기관 동시 매수일

2. **일일 증분 Job** (`jobs/daily_korea_collect.py`)
   - 매일 16:30 실행
   - 어제 거래일 데이터만 수집
   - 백필 데이터 누락 감지 + 자동 보충

3. **테스트 보강**

#### 검증

- [ ] 5년 추이 함수가 정상값 반환 (sample 종목)
- [ ] 연속 매수일 계산 정확 (sample 데이터로 검증)
- [ ] 일일 증분 Job dry-run 성공

---

### Day 3 — 재벌 그룹 + 지주사 NAV

**상세 스펙**: `docs/data_infra/korea_market.md` Section 2

#### 작업 순서

1. **재벌 그룹 정적 테이블** (`data/chaebol_groups.json`)
   - 공정위 88개 그룹 중 시총 큰 30개 그룹 우선 작성
   - 그룹 내 상장 종목 매핑
   - LLM 보조로 누락 보충

2. **지주사 NAV 계산** (`utils/data_collectors/holding_company.py`)
   - `HOLDING_COMPANIES` 상수 (30~40개 지주사)
   - `calculate_nav_discount(holding_ticker)` 함수
   - 자회사 시총 실시간 조회 (기존 `screener` 모듈 활용)

3. **테스트**
   - LG, SK, 한화 등 주요 지주사 NAV 계산 결과 검증

#### 작업 시 주의사항

⚠️ 자회사 지분율은 **분기 1회 수동 갱신** 가정.
- 현재는 정적 데이터로 시작
- 분기 갱신 시점 명시 (`data/holding_company_subsidiaries.json` 마지막 갱신일)

#### 검증

- [ ] 30개 그룹 매핑 작성됨
- [ ] LG, SK 등 5개 지주사 NAV 계산 결과 합리적
- [ ] 지주사 디스카운트율 분류 (낮음/중간/높음/매우 높음) 정확

---

### Day 4 — 자사주 정책 (DART 파싱)

**상세 스펙**: `docs/data_infra/korea_market.md` Section 3

#### 작업 순서

1. **DART API 클라이언트** (`utils/data_collectors/dart_client.py`)
   - DART OpenAPI 인증키 환경변수
   - `fetch_disclosures(start, end, types)` 헬퍼

2. **자사주 파싱 모듈** (`utils/data_collectors/dart_buyback.py`)
   - `fetch_buyback_disclosures(start_date, end_date)` 
   - `classify_buyback_action(title, content)` — soak/buy_and_hold/esop 분류
   - Firestore 저장 (`buyback_history` 컬렉션)

3. **백필 Job**
   - 최근 3년치 자사주 공시 1회 백필
   - DART API 일일 한도 (10K) 준수

4. **테스트**
   - 실제 자사주 소각 공시 텍스트로 분류 정확도 확인

#### 검증

- [ ] 삼성전자, SK하이닉스 등 5개 종목 자사주 이력 수집 성공
- [ ] 소각 vs 보유 분류 정확
- [ ] DART API rate limit 준수

---

### Day 5 — 밸류업 + 거버넌스 + 공매도

**상세 스펙**: `docs/data_infra/korea_market.md` Section 4, 5, 6

#### 작업 순서 (병렬 가능)

##### 5A. 밸류업 인덱스 (`utils/data_collectors/valueup_index.py`)
- KRX 밸류업 지수 100개 종목 수집
- ETF 보유 종목으로 fallback (KODEX 379800)
- 분기별 리밸런싱 시점 추적
- `is_in_valueup_index(ticker)` 함수

##### 5B. 거버넌스 자체 평가 (`utils/data_collectors/governance_score.py`)
- 5개 변수 자체 평가 logic
- `calculate_governance_score(ticker)` → 0~10점 + 등급
- 외부 평가 미참조 명시

##### 5C. 공매도/대차 (`utils/data_collectors/short_selling.py`)
- pykrx `get_shorting_balance_by_date`, `get_shorting_volume_by_date`
- 정책 이력 정적 데이터 (`data/short_selling_policy.json`)
- `analyze_short_signals(ticker)` 함수

#### 검증

- [ ] 밸류업 인덱스 100개 종목 list 확보
- [ ] 거버넌스 점수 5개 종목 sample 검증
- [ ] 공매도 잔고 분석 결과 합리적

---

## ✅ Week A 완료 기준

- [ ] 6개 모듈 모두 구현 완료
- [ ] 단위 테스트 통과 (각 모듈)
- [ ] 백필 1회 실행 (외국인 5년 + 자사주 3년)
- [ ] 일일 증분 Cloud Run Job 등록
- [ ] reviewer subagent 6회 호출 (모듈당 1회)
- [ ] LEGAL 검증 (`scripts/legal_check.py`) 통과
- [ ] PROGRESS_V2.md Week A 섹션 작성

---

## 🚨 위험 신호 (사용자 알림 필요)

다음 발생 시 작업 중단 + 사용자 확인:

1. **pykrx 호출 24시간 이상 실패**: 라이브러리 이슈 또는 KRX 차단
2. **DART API 한도 초과**: 일일 10K 초과 → 백필 분할 필요
3. **재벌 그룹 매핑 30%+ 누락**: 데이터 소스 보강 필요
4. **백필 비용 초과**: Firestore 쓰기 비용 $5+ 발생 시

---

## 📊 Day별 체크리스트 (자가 점검)

### Day 1 종료 시
- [ ] korea_supply.py 작성 완료
- [ ] 100 종목 sample 백필 성공
- [ ] git commit: "feat(v2/korea): foreign/institution supply collector"

### Day 2 종료 시
- [ ] 5년 추이 분석 함수 4개 구현
- [ ] 일일 증분 Job dry-run 성공
- [ ] git commit: "feat(v2/korea): supply analysis helpers + daily increment job"

### Day 3 종료 시
- [ ] chaebol_groups.json 30개 그룹
- [ ] holding_company.py NAV 계산 5개 지주사 검증
- [ ] git commit: "feat(v2/korea): chaebol mapping + holding company NAV"

### Day 4 종료 시
- [ ] dart_buyback.py 구현
- [ ] 3년 백필 5개 종목 sample 성공
- [ ] git commit: "feat(v2/korea): DART buyback classification"

### Day 5 종료 시
- [ ] 3개 모듈 (valueup, governance, short_selling) 구현
- [ ] reviewer subagent 6회 호출 완료
- [ ] LEGAL 검증 통과
- [ ] git commit: "feat(v2/korea): valueup index + governance + short selling"
- [ ] PROGRESS_V2.md 업데이트
- [ ] **Week A 종료 보고**: 사용자에게 진행 상황 + Week B 시작 의사 확인
