# Axis - AI 투자 분석 파트너

> **Claude Code 작업 지침**: 이 파일은 프로젝트의 마스터 컨텍스트입니다. 매 작업 시작 시 이 파일을 먼저 읽고, 세부 사항은 `docs/axis/` 폴더의 관련 문서를 참고하세요.

---

## 🎯 프로젝트 개요

**Axis**는 1~5년차 중급 투자자를 위한 AI 기반 한국 주식 분석 도구입니다.

### 한 문장 정의
> "당신의 고민을 들려주면, 블랙록 애널리스트처럼 분석해드립니다. 추천은 하지 않습니다. 판단은 당신의 몫입니다."

### 기존 자산 활용
- 베이스: 기존 [Stock_search_program](https://github.com/messi929/Stock_search_program) 인프라
- 재활용 비율: **약 60%** (수집기, 스크리닝 엔진, Cloud Run, Firestore)
- 신규 개발: **약 40%** (AI 에이전트, 프론트엔드, 인증)

---

## 🚨 절대 원칙 (Hard Rules)

### 1. 법적 안전: "추천" 금지
**모든 AI 응답에서 다음 단어 절대 사용 금지:**
- ❌ 추천합니다, 사세요, 매수 신호, 매도 신호
- ❌ 목표가, 매수가, 손절가 (수치 제시 X)
- ❌ "이 종목은 좋다/나쁘다" 식의 단정

**대체 표현 사용:**
- ✅ "분석 결과", "관찰 구간", "참고 수치"
- ✅ "이 데이터로 판단해보세요"
- ✅ "참고 범위", "관찰 가치"

### 2. 모든 AI 응답 하단 면책 문구 필수
```
📌 이 분석은 투자 권유가 아닌 정보 제공입니다.
   최종 판단은 사용자 본인의 책임입니다.
   Axis는 투자자문업 면허가 없습니다.
```

### 3. 실시간 검증 필수
- AI 답변의 모든 수치는 현재 시점 데이터로 재검증 가능해야 함
- 데이터 신선도 5% 이내: OK
- 5~10%: 경고 표시
- 10% 이상: 재분석 강제

### 4. 페르소나 일관성
- **블랙록**: 리스크 프레임 중심, 장기 가치
- **ARK**: 파괴적 혁신 서사, 고성장
- **그레이엄**: 안전마진, 저평가
- 페르소나는 시스템 프롬프트로 명확히 분리

---

## 🏗 기술 스택

### Backend (기존 유지 + 확장)
- **API**: FastAPI + uvicorn
- **DB**: Firestore (Firebase Admin SDK)
- **Data**: pandas, finance-datareader, pykrx, yfinance
- **Hosting**: GCP Cloud Run (asia-northeast3)
- **신규 추가**: anthropic, langgraph, firebase-admin

### Frontend (신규)
- **Framework**: Next.js 14 (App Router)
- **Language**: TypeScript (strict mode)
- **Styling**: Tailwind + shadcn/ui
- **State**: TanStack Query (서버), Zustand (클라이언트)
- **Auth**: Firebase Auth (카카오/구글)
- **Hosting**: Vercel

### AI Layer
- **Provider**: Anthropic Claude API
- **모델 차등 사용**:
  - Research: Claude Haiku (저비용)
  - Analyst: Claude Sonnet
  - Validator: Claude Sonnet
  - Strategist: Claude Opus (복잡 종합)
- **Orchestration**: LangGraph

### Notification
- 텔레그램 (기존 유지)
- 카카오 비즈 알림톡 (신규)

---

## 📁 디렉토리 구조

```
axis/  (기존 Stock_search_program 확장)
│
├── CLAUDE.md                      # 이 파일 (마스터 컨텍스트)
├── docs/
│   ├── (기존 v7 문서들 — ARCHITECTURE.md, IMPROVEMENT_PLAN_V6.md 등 유지)
│   └── axis/                      # 신규 Axis 계획 문서
│       ├── README.md              # 인덱스
│       ├── ROADMAP.md             # 6주 로드맵
│       ├── ARCHITECTURE.md        # 아키텍처 상세
│       ├── DATABASE.md            # Firestore 스키마
│       ├── LEGAL.md               # 법적 안전장치
│       ├── agents/                # 에이전트별 상세
│       │   ├── research.md
│       │   ├── analyst.md
│       │   ├── validator.md
│       │   └── strategist.md
│       ├── api/                   # API 스펙
│       │   ├── ai.md
│       │   ├── watchlist.md
│       │   └── screener.md
│       └── frontend/
│           ├── pages.md           # 페이지 구조
│           └── components.md      # 핵심 컴포넌트
│
├── 🔄 기존 유지 (Backend)
│   ├── collector.py               # 데이터 수집 (그대로)
│   ├── requirements.txt           # 의존성 업데이트
│   ├── Dockerfile
│   ├── Dockerfile.collector
│   ├── cloudbuild.yaml
│   ├── cloudbuild-collector.yaml
│   ├── deploy-cloud-jobs.sh
│   ├── .env.example
│   └── screener/
│       ├── core/
│       │   ├── data_fetcher.py
│       │   ├── metrics.py         # buy_score, rsi 등 (재활용)
│       │   └── screener.py        # CATEGORIES (재활용)
│       ├── db/
│       │   └── repository.py      # Firestore 접근 (재활용)
│       └── config.py
│
├── ❌ 삭제됨
│   ├── desktop.py                 # 제거 완료
│   ├── client_config.json         # 제거 완료
│   ├── desktop.bat                # 제거 완료
│   └── pywebview, pystray, Pillow # requirements에서 제거 완료
│
├── 🆕 신규 (AI Layer)
│   ├── api/
│   │   ├── main.py                # FastAPI 앱 엔트리
│   │   ├── routes/
│   │   │   ├── screener.py        # 기존 스크리닝
│   │   │   ├── ai.py              # AI 분석 🆕
│   │   │   ├── watchlist.py       # 관심 종목 🆕
│   │   │   └── auth.py            # 인증 🆕
│   │   └── middleware/
│   │       └── firebase_auth.py   # Firebase 토큰 검증 🆕
│   │
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base.py                # 공통 베이스 🆕
│   │   ├── research.py            # Research Agent 🆕
│   │   ├── analyst.py             # Analyst Agent 🆕
│   │   ├── validator.py           # Validator Agent 🆕 ⭐
│   │   ├── strategist.py          # Strategist Agent 🆕
│   │   └── graph.py               # LangGraph orchestration 🆕
│   │
│   ├── personas/
│   │   ├── blackrock.md           # 블랙록 시스템 프롬프트
│   │   ├── ark.md                 # ARK 시스템 프롬프트
│   │   └── graham.md              # 그레이엄 시스템 프롬프트
│   │
│   └── utils/
│       ├── claude_client.py       # Claude API 래퍼
│       ├── cache.py               # 응답 캐싱
│       └── cost_tracker.py        # 비용 추적
│
└── 🆕 신규 (Frontend)
    └── web/                       # Next.js 14
        ├── app/
        ├── components/
        ├── lib/
        └── package.json
```

---

## 🤖 4개 에이전트 (Quick Reference)

| 에이전트 | 역할 | 모델 | 비용 |
|---------|------|------|------|
| **Research** | 시황/뉴스/매크로 통합 | Haiku | ~5원 |
| **Analyst** | 기술적+펀더멘털 해석 | Sonnet | ~35원 |
| **Validator** ⭐ | 실시간 검증 + Contrarian | Sonnet | ~25원 |
| **Strategist** | 종합 + 페르소나 적용 | Opus | ~150원 |

**총 쿼리당 약 215원** (캐싱/Haiku 비중 늘리면 ~130원까지 절감 가능)

상세 스펙: `docs/axis/agents/` 폴더 참고

---

## 🎯 MVP 기능 (5개)

1. **종목 딥다이브** - "삼성바이오 어때?" → 4개 에이전트 종합 리포트
2. **실시간 검증 버튼** ⭐ - 데이터 신선도 체크, 핵심 차별점
3. **페르소나 전환** - 블랙록/ARK/그레이엄 토글
4. **관심 종목 트래커** - 5개(Free) / 30개(Pro), 진입선 + 알림
5. **스마트 리스트** - 기존 스크리너 카테고리 흡수

상세: `docs/axis/ROADMAP.md` 참고

---

## 💰 수익 모델

```
Free Tier:
  - 관심 종목 5개
  - 분석 월 20회
  - 검증 월 10회
  - 페르소나 1개 (블랙록)

Pro Tier (9,900원/월):
  - 관심 종목 30개
  - 무제한 분석/검증
  - 페르소나 3종
  - 커스텀 스크리너 + 알림

Premium Tier (29,900원/월) - v1.0 이후:
  - Pro + PDF 주간 리포트
  - 우선 분석 큐
```

---

## 📅 6주 로드맵 (Quick Reference)

```
Week 1: 기반 확장 + 인증
Week 2: 4개 에이전트 구현
Week 3: LangGraph + API 통합
Week 4: Next.js 시작
Week 5: 핵심 기능 UI
Week 6: 스크리너 + 베타 런칭
```

상세: `docs/axis/ROADMAP.md` 참고

---

## 🔧 코딩 컨벤션

### Python
- Python 3.11+, type hints 필수
- Pydantic v2 모델 사용
- async/await 적극 활용
- 함수/모듈 docstring 한국어 OK

### TypeScript
- strict mode
- 타입 명시 (any 금지)
- 컴포넌트는 함수형 + Hook
- 에러 바운더리 필수

### Git
- Conventional commits: `feat:`, `fix:`, `docs:`, `refactor:`
- 브랜치: `feature/`, `bugfix/`, `hotfix/`
- 커밋 메시지: 한국어 OK

### 일반
- 변수/함수명: 영어 (camelCase JS, snake_case Python)
- 주석: 한국어 OK
- 파일/폴더명: 영어, 소문자

---

## ⚠️ 주의사항 (반드시 확인)

### 1. 데이터 소스 제약
- **네이버 크롤링**: 회색지대, 장기적으로 한국투자증권 OpenAPI 전환 필요
- **pykrx**: 안정적, 우선 사용
- **yfinance**: 미국 시장만

### 2. 비용 관리 필수
- Claude API: 모델 차등 사용 (Haiku 우선)
- Firestore: 읽기 캐싱 적극 활용
- Cloud Run: 콜드 스타트 주의

### 3. 보안
- Firebase Auth 토큰 검증 미들웨어 필수
- 모든 사용자 데이터 격리 (`/users/{uid}/...`)
- API 키는 절대 프론트엔드에 노출 금지

### 4. UX
- 모바일 우선 디자인 (한국 사용자 80%+ 모바일)
- 한국어 UI 기본
- 로딩 상태 명확히 표시 (AI는 5~10초 소요)

---

## 📖 문서 읽는 순서 (신규 작업 시작 시)

1. **CLAUDE.md** (이 파일) - 전체 맥락
2. **docs/axis/ROADMAP.md** - 현재 어느 주차인지
3. 작업 종류에 따라:
   - 에이전트 작업: `docs/axis/agents/{agent_name}.md`
   - API 작업: `docs/axis/api/{endpoint}.md`
   - 프론트 작업: `docs/axis/frontend/`
4. **docs/axis/LEGAL.md** - 법적 안전장치 항상 확인

---

## 🎬 시작하기

### 첫 작업 명령
```bash
# 1. 레포 클론 (이미 있다면 skip)
git clone https://github.com/messi929/Stock_search_program.git axis
cd axis

# 2. 새 브랜치
git checkout -b feature/axis-ai-layer

# 3. 환경 설정
cp .env.example .env
# Anthropic API 키 추가

# 4. 의존성 설치
pip install -r requirements.txt

# 5. 첫 작업: Week 1 시작
# docs/axis/ROADMAP.md의 Week 1 체크리스트 참고
```

### 매 작업 시작 전 체크
- [ ] CLAUDE.md 읽었나?
- [ ] 현재 주차 ROADMAP 확인했나?
- [ ] 관련 docs/axis/ 문서 읽었나?
- [ ] "추천" 단어 사용 안 하는지 확인했나?
- [ ] 면책 문구 포함했나?

---

**마지막 업데이트**: 2026-04-25
**작성자**: JEON + Claude (Axis 설계 대화)
