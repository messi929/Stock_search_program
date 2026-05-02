# Axis v2 — 6 Persona Expansion 작업 패키지

> **Claude Code 전달용 작업 문서 패키지**
> **목적**: 기존 3 페르소나(블랙록/ARK/그레이엄) → 6 페르소나로 확장
> **소요**: 5주 (Week A ~ E)
> **신규 페르소나**: Event Analyst, Macro PM, Korean Specialist
> **작업 시작 전**: `docs/v2_roadmap/CLAUDE_V2.md` 먼저 읽기

---

## 📚 문서 인덱스

### 1. 마스터 컨텍스트 (가장 먼저 읽기)
- **`docs/v2_roadmap/CLAUDE_V2.md`** — 전체 5주 작업의 마스터 인스트럭션
  - 절대 원칙 (LEGAL, 기존 시스템 안정성)
  - 5주 작업 개요
  - 의존성 그래프
  - 데이터 접근 권한 매트릭스
  - 비용 인식

### 2. 주차별 작업 가이드
- **`docs/v2_roadmap/WEEK_A.md`** — 한국 시장 데이터 인프라 (Day 1~5)
- **`docs/v2_roadmap/WEEK_B.md`** — 매크로 데이터 인프라 (Day 1~5)
- **`docs/v2_roadmap/WEEK_C.md`** — 이벤트 데이터 인프라 (Day 1~5)
- **`docs/v2_roadmap/WEEK_D.md`** — 페르소나 구현 + LangGraph + Frontend (Day 1~5)
- **`docs/v2_roadmap/WEEK_E.md`** — 검증 + 최적화 + 베타 준비 (Day 1~5)

### 3. 데이터 인프라 상세 스펙
- **`docs/data_infra/korea_market.md`** — 한국 시장 8종 데이터 (외국인/재벌/지주사/자사주/밸류업/거버넌스/공매도)
- **`docs/data_infra/macro.md`** — FRED + ECOS + 4 사이클 + 6 국면
- **`docs/data_infra/event.md`** — 이벤트 캘린더 + 옵션 + LLM 유사 이벤트 추론

### 4. 페르소나 시스템 프롬프트
- **`docs/personas/event.md`** — Event Analyst v2.1 (시뮬레이션 보완 4개 반영)
- **`docs/personas/macro.md`** — Macro PM v1
- **`docs/personas/korean.md`** — Korean Specialist v1

### 5. 통합 + 검증
- **`docs/v2_roadmap/INTEGRATION.md`** — LangGraph 분기 + Frontend 6 페르소나 UI
- **`docs/v2_roadmap/VALIDATION.md`** — LEGAL + Reviewer + 60건 회귀 테스트

---

## 🎬 시작하는 방법

### 첫 작업 진입점

```bash
# 1. 새 브랜치 생성 (기존 시스템 보호)
git checkout -b feature/v2-six-personas

# 2. 마스터 인스트럭션 읽기
cat docs/v2_roadmap/CLAUDE_V2.md

# 3. Week A 시작
cat docs/v2_roadmap/WEEK_A.md

# 4. 한국 시장 데이터 인프라 스펙 확인
cat docs/data_infra/korea_market.md
```

### Claude Code에 던질 첫 프롬프트

```
docs/v2_roadmap/CLAUDE_V2.md를 먼저 읽어주세요.
그다음 docs/v2_roadmap/WEEK_A.md를 읽고 Day 1-2 작업을 확인해주세요.
docs/data_infra/korea_market.md도 함께 읽어서 외국인 5년 히스토리 수집 모듈의 상세 스펙을 파악해주세요.

준비되면 Day 1 작업 계획을 먼저 알려주세요:
1. 어떤 파일을 생성할지
2. pykrx 호출 패턴 어떻게 할지 (정확한 함수명: get_market_trading_value_and_volume_by_ticker, get_exhaustion_rates_of_foreign_investment_by_date)
3. Firestore 컬렉션 스키마는 어떻게 할지
4. 에러 처리/재시도 전략

내 확인 후에 실제 코드 작성 시작해주세요.
```

---

## ✅ 자체 검증 결과 (작성 완료 시)

이 문서들은 작성 과정에서 **5가지 체크포인트**로 자체 검증 완료:

1. ✅ **기술적 정확성**: pykrx, fredapi, yfinance 실제 1.2.7/0.5.2/1.3.0 시그니처 검증
2. ✅ **의존성 모순**: Week A/B/C 독립, Week D는 A+B+C 의존, Week E는 D 의존
3. ✅ **LEGAL 위배 표현**: 사용자 노출 영역 0건 (메타 정의 영역만 사용)
4. ✅ **현실성**: 작업량 추정 검증 (백필 비용/시간 명시)
5. ✅ **CLAUDE_V2.md 일관성**: 페르소나 이름/모듈 경로/Week 매핑 일치

### 자체 검증에서 발견 + 수정한 오류 7건

1. **pykrx**: `get_market_trading_value_by_investor`의 `detail` 인자 → 실제로 없음. 수정 완료.
2. **pykrx**: `get_shorting_balance_by_ticker(date, market)` ← 종목별 시계열이 아닌 일자 스냅샷. 종목별 시계열은 `get_shorting_balance_by_date(fromdate, todate, ticker)` 사용.
3. **pykrx**: 외국인 보유 비중 시계열 함수 정정 (`_by_date` vs `_by_ticker` 구분).
4. **fredapi**: `get_series` 인자 `start/end` → 실제는 `observation_start/observation_end`.
5. **yfinance**: `option_chain(date=None, tz=None)` 시그니처 — `date`가 첫 인자.
6. **yfinance**: `quarterly_earnings` deprecated 가능성 → `quarterly_income_stmt` 또는 `earnings_dates` 권장.
7. **LEGAL**: `event.md`에서 "임박" 사용자 노출 영역 2곳 발견 → 통계 표현으로 변경.

---

## 📊 작업 통계

| 항목 | 개수 |
|------|------|
| 문서 파일 | 14개 |
| 총 라인 수 | ~5,000 |
| 검증 라운드 | 매 문서마다 5체크 + 최종 sweep |
| 발견된 오류 | 7건 (모두 수정 완료) |

---

## 🚦 다음 단계

1. **이 패키지를 Claude Code에 전달**
2. **`feature/v2-six-personas` 브랜치 생성**
3. **Week A Day 1부터 순차 진행**
4. **매 Week 종료 시 사용자 보고 + 다음 Week 진행 의사 확인**
5. **Week E 완료 후 베타 출시 결정**

---

## ⚠️ 베타 출시 전 추가 결정 필요 사항

이 패키지에는 **결정 보류된 항목**이 있습니다:

1. **비용 정책** (Free / Pro / Premium 페르소나 분배) — 시스템 완성 후 별도 논의
2. **Strategist Sonnet 다운그레이드 여부** — Week E에서 비용 측정 후 결정
3. **자체 이벤트 통계 DB 구축 시점** — 베타 후 사용자 피드백 보고 결정 (현재는 LLM 추론 + 캐싱)

이 3가지는 베타 출시 후 또는 별도 마일스톤에서 다룹니다.
