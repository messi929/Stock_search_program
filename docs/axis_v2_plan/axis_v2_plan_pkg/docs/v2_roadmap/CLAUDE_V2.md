# Axis v2 — 6 Persona Expansion 마스터 인스트럭션

> **Claude Code 작업 지침**: 이 파일은 5주 작업의 **마스터 컨텍스트**입니다.
> 위치: `docs/v2_roadmap/CLAUDE_V2.md`
> 모든 새 작업 세션 시작 시 이 파일을 가장 먼저 읽으세요.
> 세부 사항은 같은 폴더 + `docs/personas/`, `docs/data_infra/` 참고.

---

## 🎯 작업 개요

기존 Axis 시스템(3개 페르소나: 블랙록/ARK/그레이엄)을 **6개 페르소나로 확장**합니다.

**신규 추가 3개 페르소나**:
1. 📅 **Event Analyst** — 이벤트 드리븐 통계 분석 (단기 1w-3m)
2. 🌐 **Macro PM** — 거시 사이클 + 자산 배분 (중기 6m-2y)
3. 🇰🇷 **Korean Market Specialist** — 한국 시장 특수성 (3m-2y)

**작업 기간**: 5주 (Week A ~ E)

**현재 시스템 상태** (작업 시작 전):
- ✅ Backend: FastAPI + LangGraph + 4 Agent 구조 안정화
- ✅ Frontend: Next.js 16 + 3 페르소나 토글
- ✅ Cloud Run + Firestore 운영 중
- ✅ 베타 런칭 직전 (axis-staging revision 00008-mlw)

---

## 🚨 절대 원칙 (Hard Rules)

### 1. 기존 시스템 안정성 우선
- **main 브랜치 영향 최소화**: 모든 작업은 `feature/v2-six-personas` 브랜치에서
- **기존 3 페르소나는 절대 손대지 않기**: 검증된 시스템
- **신규 페르소나는 별도 모듈**: `agents/event_analyst.py`, `agents/macro_pm.py`, `agents/korean_specialist.py`
- **데이터 인프라 추가는 비파괴적**: 기존 `screener/` 모듈 확장만, 변경 X

### 2. LEGAL 절대 원칙 유지
- 모든 신규 시스템 프롬프트에 LEGAL Hard Rules 명시
- 모든 응답에 면책 문구 자동 삽입
- `scripts/legal_check.py` 통과 필수
- **Event Analyst는 특히 주의**: 단기 트레이딩 영역이라 LEGAL 위험 높음

### 3. 페르소나 일관성 원칙
- 각 페르소나는 자기 영역에서만 발언
- 책임 영역 침범 X (예: Event Analyst가 매크로 사이클 판정 X)
- 한국 시장 특수성은 Korean Specialist만 다룸 (다른 페르소나는 글로벌 framework)

### 4. 비용 인식 운영
- Strategist 페르소나당 1 호출 (~370원)
- 6개 페르소나 모두 활성화 시 페르소나당 비용 누적 주의
- 캐싱 적극 활용 (페르소나별 30분 TTL)
- 작업 중 비용 모니터링 (cost_tracker.py)

### 5. Reviewer Subagent 워크플로우 유지
- 신규 코드 작성 후 → general-purpose subagent로 검증
- 발견 이슈 즉시 fix (베타 도달 전 차단)
- 워크플로우는 기존 PROGRESS.md 검증 패턴 그대로

---

## 📚 문서 읽는 순서 (세션 시작 시)

### 새 세션 시작 시
1. **이 파일 (CLAUDE_V2.md)** — 전체 5주 컨텍스트
2. **현재 작업 주차 확인**: `docs/v2_roadmap/WEEK_{A|B|C|D|E}.md`
3. **현재 작업 페르소나의 시스템 프롬프트**: `docs/personas/{event|macro|korean}.md`
4. **기존 LEGAL 원칙**: `docs/axis/LEGAL.md` (변경 금지)

### 작업 종류별 추가 문서
- **데이터 수집 작업**: `docs/data_infra/{korea|macro|event}.md`
- **시스템 프롬프트 작업**: `docs/personas/{persona}.md`
- **LangGraph 통합**: `docs/v2_roadmap/INTEGRATION.md`
- **검증 작업**: `docs/v2_roadmap/VALIDATION.md`

---

## 📅 5주 작업 개요

### Week A — 한국 시장 데이터 인프라
**목표**: Korean Specialist에 필요한 모든 데이터 수집 모듈

- 외국인/기관 5년 히스토리
- 재벌 그룹 매핑 + 지주사 NAV
- 자사주 정책 (소각 vs 보유)
- 밸류업 인덱스 종목
- 거버넌스 점수 (자체 평가)

→ 상세: `docs/v2_roadmap/WEEK_A.md`

### Week B — 매크로 데이터 인프라
**목표**: Macro PM에 필요한 모든 매크로 지표 + 사이클 판정

- FRED API + ECOS API 연동
- 4대 사이클 자동 판정 (금리/경기/통화/인플레)
- 6대 매크로 국면 매핑 DB

→ 상세: `docs/v2_roadmap/WEEK_B.md`

### Week C — 이벤트 데이터 인프라
**목표**: Event Analyst에 필요한 데이터 + LLM 추론 시스템

- 이벤트 캘린더 자동 수집
- 옵션/신용/공매도 데이터 통합
- LLM 기반 유사 이벤트 추론 + 캐싱

→ 상세: `docs/v2_roadmap/WEEK_C.md`

### Week D — 페르소나 구현 + 통합
**목표**: 3개 페르소나 코드 작성 + LangGraph 통합

- Event Analyst 구현
- Macro PM 구현
- Korean Specialist 구현
- Strategist 6 페르소나 분기 처리
- Frontend PersonaSwitch 6개 확장

→ 상세: `docs/v2_roadmap/WEEK_D.md`

### Week E — 검증 + 최적화
**목표**: 회귀 테스트 + Reviewer 검증 + 베타 준비

- 6 페르소나 × 10 종목 = 60건 회귀 테스트
- Reviewer subagent 검증
- LEGAL sweep
- 비용/성능 측정

→ 상세: `docs/v2_roadmap/WEEK_E.md`

---

## 🏗 신규 시스템 아키텍처 (확장 후)

```
LangGraph (확장)

  START
    ↓
  fanout
    ├─→ research (Haiku)
    └─→ analyst (Sonnet)
              ↓
          validator (수동 트리거 - REDESIGN.md Option A 적용 가정)
              ↓
        strategist 분기 (페르소나에 따라)
              │
    ┌─────────┼─────────┬─────────┬─────────┬─────────┐
    ↓         ↓         ↓         ↓         ↓         ↓
  blackrock  ark   graham  event_analyst  macro_pm  korean_specialist
    │         │     │       │              │           │
    │         │     │       │              │           │
    └─────────┴─────┴───────┴──────────────┴───────────┘
                                ↓
                              END
```

**중요**: 각 페르소나는 다음 데이터에 접근 권한 다름:

| 데이터 | Blackrock | ARK | Graham | Event | Macro | Korean |
|--------|-----------|-----|--------|-------|-------|--------|
| 종목 펀더멘털 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 외국인/기관 수급 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅✅ (5년) |
| 매크로 지표 | ✅ | - | - | ✅ | ✅✅ | ✅ |
| 이벤트 캘린더 | - | - | - | ✅✅ | ✅ | ✅ |
| 옵션/신용/공매도 | - | - | - | ✅✅ | - | ✅ |
| 재벌/지주사 | - | - | - | - | - | ✅✅ |
| 밸류업 데이터 | - | - | - | - | - | ✅✅ |

---

## 🎯 의존성 그래프 (작업 순서)

```
Week A (한국 데이터)
  ├─ 외국인 5년 히스토리 ──┐
  ├─ 재벌/지주사 매핑 ─────┤
  ├─ 자사주 정책 ──────────┤
  ├─ 밸류업 데이터 ────────┤
  └─ 거버넌스 점수 ────────┴─→ Korean Specialist 구현 (Week D)

Week B (매크로 데이터)
  ├─ FRED API 연동 ───────┐
  ├─ ECOS API 연동 ───────┤
  ├─ 4대 사이클 판정 ─────┤
  └─ 6대 국면 매핑 ───────┴─→ Macro PM 구현 (Week D)

Week C (이벤트 데이터)
  ├─ 이벤트 캘린더 ───────┐
  ├─ 옵션 데이터 ─────────┤
  ├─ 신용/공매도 ─────────┤
  └─ LLM 추론 + 캐싱 ─────┴─→ Event Analyst 구현 (Week D)

Week D (구현 + 통합)
  ├─ Event Analyst Agent
  ├─ Macro PM Agent
  ├─ Korean Specialist Agent
  ├─ Strategist 분기 처리
  ├─ LangGraph 업데이트
  └─ Frontend PersonaSwitch 확장
                            ↓
Week E (검증)
  ├─ 회귀 테스트 60건
  ├─ Reviewer 검증
  ├─ LEGAL sweep
  └─ 베타 준비
```

**병렬 가능**: Week A, B, C는 서로 독립적 (데이터 소스 다름) — 인프라 구축 단계
**순차 필수**: Week D는 Week A/B/C 완료 후 시작

---

## ⚙️ 코딩 컨벤션 (v2 작업)

### Python
- 신규 페르소나는 모두 `agents/{persona_name}.py` 단일 파일
- `agents/base.py`의 BaseAgent 상속
- Pydantic v2 모델로 입출력 정의
- 시스템 프롬프트는 `personas/{persona_name}.md` 별도 파일
- 데이터 모듈은 `screener/` 또는 `utils/data_collectors/`

### TypeScript
- 페르소나 6개 추가에 따른 타입 확장: `web/types/persona.ts`
- `PersonaSwitch.tsx` 컴포넌트 확장 (6개 탭)
- 페르소나별 카드 컴포넌트 재사용 (StrategistCard generic)

### 네이밍
- Python: `event_analyst`, `macro_pm`, `korean_specialist` (snake_case)
- TypeScript: `EventAnalyst`, `MacroPM`, `KoreanSpecialist` (PascalCase)
- DB: `users/{uid}/analyses/{id}` 안의 `persona` 필드에 위 ID 저장

---

## 🛡 LEGAL 검증 자동화

### 매 단계 필수 실행

```bash
# 코드 작성 후 즉시
python scripts/legal_check.py --target=agents/event_analyst.py

# 시스템 프롬프트 변경 후
python scripts/legal_check.py --target=personas/event.md

# Week 종료 시 전체 sweep
python scripts/legal_check.py --target=all --strict

# 베타 직전 최종
python scripts/legal_check.py --target=all --strict --include-tests
```

### 금지 단어 + 패턴 (v2 확장판)

기존 v1 금지 단어에 추가:
```python
ADDITIONAL_FORBIDDEN_V2 = [
    # 이벤트 페르소나 위험 표현
    "임박", "기대주", "매매 타이밍", "급등 예상",
    "곧 오를", "이번에 가는", "지금 들어가",
    
    # 매크로 PM 위험 표현
    "이 국면에서 사세요", "지금 진입",
    
    # 한국 시장 위험 표현
    "외국인이 사니까", "밸류업 수혜주",
    "테마 진입 시점",
]
```

### 검증 빈도
- 신규 시스템 프롬프트 작성: **즉시 검증**
- 신규 페르소나 응답 테스트: **5건 검증**
- Week 종료: **전체 sweep**
- 베타 출시 전: **strict mode 통과 필수**

---

## 🔍 Reviewer Subagent 호출 시점

기존 워크플로우 유지 + 페르소나 특화 검증 추가:

### 호출 시점
1. **데이터 모듈 작성 후** (Week A/B/C 각 모듈 단위)
   - 검증: 데이터 정합성, 에러 처리, 캐싱 logic
   
2. **신규 페르소나 시스템 프롬프트 v2 작성 후** (Week D)
   - 검증: LEGAL 통과, 페르소나 차별성, 응답 일관성
   
3. **LangGraph 통합 후** (Week D)
   - 검증: 분기 처리, 에러 라우팅, 비용 추적
   
4. **Frontend PersonaSwitch 확장 후** (Week D)
   - 검증: 권한 매트릭스, UI race condition, a11y
   
5. **회귀 테스트 직후** (Week E)
   - 검증: 60건 결과 일관성, LEGAL 0건, 차별성 점수

### Reviewer 호출 패턴

```
"Review {feature_path} for the following:
1. LEGAL compliance (forbidden words, missing disclaimer)
2. Persona consistency (each persona stays in its lane)
3. Cost awareness (caching, model tier appropriateness)
4. Korean market specifics (외국인 우선, 밸류업 부합도) [Korean Specialist만]
5. Event certainty score logic [Event Analyst만]
6. Macro regime detection logic [Macro PM만]
"
```

---

## 💰 비용 관리

### 페르소나별 예상 비용 (1 쿼리당)

| 페르소나 | 모델 | 입력 토큰 | 출력 토큰 | 예상 비용 |
|---------|------|---------|---------|---------|
| Event Analyst | Sonnet 4.6 | 3500 | 2000 | ~50원 |
| Macro PM | Sonnet 4.6 | 3000 | 1800 | ~45원 |
| Korean Specialist | Sonnet 4.6 | 3200 | 1900 | ~48원 |

**참고**: Strategist Opus 사용 시 페르소나당 ~370원, Sonnet 다운그레이드 시 ~50원

### 작업 중 비용 모니터링

```python
# 매일 아침 실행
from utils.cost_tracker import get_daily_cost
print(get_daily_cost(date='2026-MM-DD'))
```

### 절감 전략
- 페르소나별 캐싱 30분 TTL 유지
- 시스템 프롬프트 cache_control 적용 (1024+ tokens 자동)
- 동일 종목 분석 재호출 시 캐시 히트 우선

---

## 🚦 Daily Standup 체크리스트

매 작업 세션 시작 시:

- [ ] 이 파일 (CLAUDE_V2.md) 다시 읽었나?
- [ ] 현재 Week 계획 (`WEEK_{X}.md`) 확인했나?
- [ ] 어제 작업 커밋 확인했나? (`git log --since="yesterday"`)
- [ ] LEGAL 검증 실행했나? (어제 코드 변경 있었으면)
- [ ] 비용 일별 확인했나?

매 작업 세션 종료 시:

- [ ] 코드 변경 커밋했나?
- [ ] LEGAL 검증 통과했나?
- [ ] PROGRESS_V2.md 업데이트했나?
- [ ] Reviewer 호출 필요한 변경 있었나?

---

## 📝 v2 작업 추적 문서

작업 진행 상황 추적용:
- `docs/v2_roadmap/PROGRESS_V2.md` (이 작업 동안 매일 업데이트)

기존 시스템 문서 (변경 X):
- `CLAUDE.md` (v1 마스터 - 유지)
- `docs/axis/PROGRESS.md` (v1 진척 - 유지)
- `docs/axis/LEGAL.md` (LEGAL 원칙 - 유지)

---

## 🎬 시작하기

### 첫 작업 진입점

```bash
# 1. v2 브랜치 생성
git checkout -b feature/v2-six-personas

# 2. v2 문서 디렉토리 확인
ls docs/personas/
ls docs/data_infra/
ls docs/v2_roadmap/

# 3. Week A 시작
# docs/v2_roadmap/WEEK_A.md 읽기
# Day 1-2 외국인 5년 히스토리 작업 착수

# 4. 매일 작업 후
git add -A
git commit -m "feat(v2): {작업 내용}"
python scripts/legal_check.py
```

### 첫 Claude Code 프롬프트

```
docs/v2_roadmap/CLAUDE_V2.md를 먼저 읽어줘.
그다음 docs/v2_roadmap/WEEK_A.md를 읽고 Day 1-2 작업을 확인해줘.
docs/data_infra/korea_market.md도 함께 읽어서 외국인 5년 히스토리 수집 모듈의 상세 스펙을 파악해줘.

준비되면 Day 1-2 작업 계획을 먼저 알려줘:
1. 어떤 파일을 생성할지
2. pykrx 호출 패턴 어떻게 할지
3. Firestore 컬렉션 스키마는 어떻게 할지
4. 에러 처리/재시도 전략

내 확인 후에 실제 코드 작성 시작.
```

---

## ⚠️ 위험 신호 (즉시 사용자에게 보고)

다음 상황 발생 시 작업 중단 + 사용자 확인:

1. **LEGAL 검증 실패**: 금지 단어 발견 → 즉시 시스템 프롬프트 수정
2. **페르소나 일관성 깨짐**: 한 페르소나가 다른 페르소나 영역 침범
3. **비용 폭증**: 일일 비용 1만원 초과
4. **데이터 소스 불안정**: pykrx/FRED API 24시간 장애
5. **기존 시스템 회귀**: 3 페르소나 (블랙록/ARK/그레이엄) 동작 변경
6. **Cloud Run 배포 실패**: staging 환경에서 새 페르소나 동작 X

---

**최종 업데이트**: 2026-04-30
**작성자**: JEON + Claude (Axis v2 페르소나 확장 설계 대화)
**버전**: v2.0 plan
**상태**: 작업 시작 전 (Week A Day 1 대기)
