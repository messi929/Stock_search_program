# Week C — 이벤트 데이터 인프라 작업 가이드

> **목표**: Event Analyst 페르소나에 필요한 이벤트 캘린더, 옵션/공매도, LLM 유사 이벤트 추론 시스템 구축
> **소요**: 5일
> **선행 의존성**: Week A의 short_selling.py, Week B의 macro_calendar.json 활용
> **후속**: Week D Event Analyst 페르소나 구현

---

## 🎯 산출물

```
data/
├── macro_event_metadata.json        # 이벤트 카테고리별 통계 메타
└── upcoming_ipo.json                # 수동 큐레이션 IPO

utils/data_collectors/
├── dart_event_collector.py          # 한국 기업 이벤트 (Day 2)
├── edgar_collector.py               # 미국 SEC 8-K (Day 2)
├── yfinance_event_collector.py      # 미국 실적/배당 (Day 2)
├── options_signals.py               # 옵션 IV/PCR (Day 1)
└── event_inference_cache.py         # LLM 유사 이벤트 추론 (Day 4)

jobs/
├── daily_options_collect.py         # 일일 옵션 데이터
└── weekly_event_calendar_sync.py    # 주간 이벤트 갱신
```

---

## 📅 Day별 작업

### Day 1 — yfinance 옵션 시그널

**상세 스펙**: `docs/data_infra/event.md` Section 3

#### 작업
1. `utils/data_collectors/options_signals.py`
   - `calculate_options_signals(ticker)`
   - **option_chain(date=None, tz=None) 시그니처 정확히 사용**
   - Put/Call ratio (volume + OI 양쪽), ATM IV
2. 한국: 코스피200 VKOSPI 보조 (yfinance `^VKOSPI` 시도)
3. 캐싱 30분 TTL

#### 검증
- [ ] AAPL, RKLB 등 5개 종목 옵션 시그널 정상 계산
- [ ] 옵션 거래량 0인 종목 graceful handling

---

### Day 2 — 기업 이벤트 (DART + EDGAR + yfinance)

**상세 스펙**: `docs/data_infra/event.md` Section 2

#### 작업
1. **DART 이벤트** (Week A의 dart_buyback.py 확장)
   - 실적 발표일, M&A, 신주발행 등 추가 분류
2. **EDGAR 8-K** 수집
   - User-Agent 필수 (`Axis Research <email>`)
   - rate limit 10 req/sec
3. **yfinance 실적/배당**
   - `ticker.earnings_dates`, `ticker.dividends`
   - **quarterly_earnings 대신 quarterly_income_stmt 권장**

#### 검증
- [ ] 한국 5종목 + 미국 5종목 이벤트 캘린더 수집
- [ ] EDGAR User-Agent 차단 없음

---

### Day 3 — 매크로 이벤트 메타 + IPO 큐레이션

#### 작업
1. `data/macro_event_metadata.json` 작성
   - FOMC, US_CPI, US_GDP 등 카테고리별 통상 변동성 통계
2. `data/upcoming_ipo.json` 초기 데이터
   - 수동 큐레이션 (현재 알려진 IPO 예정 5~10건)
   - 2차 수혜 매핑 포함 (예: SpaceX → RKLB/ASTS)

#### 검증
- [ ] 메타데이터 JSON 스키마 일관성
- [ ] IPO 큐레이션 데이터 합리성

---

### Day 4 — LLM 유사 이벤트 추론 시스템 (옵션 C Phase 1)

**상세 스펙**: `docs/data_infra/event.md` Section 5

#### 작업
1. `utils/data_collectors/event_inference_cache.py`
   - Claude API 호출 + 캐싱 (24시간 TTL)
   - SIMILAR_EVENT_PROMPT 템플릿
   - **응답에 fabrication 경고 자동 첨부**
   - 표본 수 < 5: "통계 미제시" / 5-9: "표본 부족" / ≥10: "신뢰 가능"

#### 작업 시 주의사항
⚠️ **LLM이 그럴듯한 가짜 사례 만들어낼 위험** — 반드시 응답에 명시:
- "LLM 학습 데이터 기반 추정"
- "각 사례 외부 검증 권장"
- `data_confidence` 필드로 사례별 신뢰도 표시

#### 검증
- [ ] SpaceX IPO + RKLB 케이스로 추론 결과 검증
- [ ] fabrication 경고 자동 첨부 확인
- [ ] 캐시 hit/miss 동작 확인

---

### Day 5 — 통합 + Reviewer

#### 작업
1. **일일 수집 Job** (`jobs/daily_options_collect.py`)
   - 옵션 데이터 + 신용/공매도 (Week A 모듈 재사용) 통합
2. **주간 이벤트 캘린더** (`jobs/weekly_event_calendar_sync.py`)
   - DART + EDGAR + 매크로 캘린더 통합 갱신
3. **Reviewer subagent 호출** (5회)
   - options_signals, dart_event_collector, edgar_collector, yfinance_event_collector, event_inference_cache
4. **LEGAL 검증** (특히 LLM 추론 응답)

#### 검증
- [ ] 5개 모듈 reviewer 통과
- [ ] LEGAL strict 통과 (event 페르소나 영역은 가장 위험)

---

## ✅ Week C 완료 기준

- [ ] 5개 모듈 구현
- [ ] LLM 추론 + 캐싱 동작
- [ ] reviewer 5회 통과
- [ ] LEGAL strict 통과
- [ ] PROGRESS_V2.md 업데이트

---

## 🚨 위험 신호

1. **yfinance 차단**: 라이브러리 비공식 → 백오프 + 캐시 폴백
2. **EDGAR User-Agent 누락**: 즉시 차단
3. **LLM fabrication**: 사례별 신뢰도 명시 필수
4. **DART 한도 초과**: Week A와 한도 공유, 일일 모니터링

---

## 📊 Day별 체크리스트

| Day | 산출물 | 커밋 메시지 |
|-----|-------|-----------|
| 1 | options_signals.py | feat(v2/event): yfinance options signals |
| 2 | dart/edgar/yfinance event collectors | feat(v2/event): corporate event calendars |
| 3 | macro_event_metadata.json + upcoming_ipo.json | feat(v2/event): event metadata + IPO curation |
| 4 | event_inference_cache.py | feat(v2/event): LLM similar event inference |
| 5 | jobs + reviewer + LEGAL | feat(v2/event): daily/weekly jobs + validation |
