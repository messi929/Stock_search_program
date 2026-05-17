# Axis 시스템 아키텍처

> **목적**: Claude Code가 전체 시스템 구조를 이해하고 일관된 결정을 내릴 수 있도록

---

## 🏗 전체 시스템 다이어그램

```
┌────────────────────────────────────────────────────────────────────┐
│                          User (Browser/Mobile)                      │
└───────────────────────────────┬────────────────────────────────────┘
                                │ HTTPS
                                ↓
┌────────────────────────────────────────────────────────────────────┐
│                      Frontend (Vercel)                              │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ Next.js 14 (App Router)                                      │  │
│  │ ├─ TypeScript + Tailwind + shadcn/ui                         │  │
│  │ ├─ TanStack Query (server state)                            │  │
│  │ ├─ Zustand (client state)                                   │  │
│  │ └─ Firebase Auth Client                                     │  │
│  └──────────────────────────────────────────────────────────────┘  │
└───────────────────────────────┬────────────────────────────────────┘
                                │ Bearer Token (Firebase JWT)
                                ↓
┌────────────────────────────────────────────────────────────────────┐
│                     Backend (GCP Cloud Run)                         │
│                  asia-northeast3 (Seoul)                            │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ FastAPI + uvicorn                                            │  │
│  │                                                              │  │
│  │ Middleware:                                                  │  │
│  │ ├─ Firebase Auth Token 검증                                  │  │
│  │ ├─ Rate Limiting (Free/Pro 차등)                            │  │
│  │ └─ CORS                                                      │  │
│  │                                                              │  │
│  │ Routes:                                                      │  │
│  │ ├─ /api/ai/*         → AI 에이전트 호출                      │  │
│  │ ├─ /api/watchlist/*  → 관심 종목 CRUD                        │  │
│  │ ├─ /api/screener/*   → 스크리닝                              │  │
│  │ ├─ /api/auth/*       → 인증 보조                             │  │
│  │ └─ /api/screener/*   → 기존 스크리닝 (유지)                  │  │
│  └──────────────────────────────────────────────────────────────┘  │
└──────┬─────────────────────────┬──────────────────────────┬────────┘
       │                         │                          │
       ↓                         ↓                          ↓
┌──────────────────┐   ┌──────────────────────┐   ┌──────────────────┐
│   AI Agents      │   │     Firestore        │   │  Claude API      │
│   (LangGraph)    │   │ (asia-northeast3)    │   │  (Anthropic)     │
│                  │   │                      │   │                  │
│ ├─ Research      │   │ Collections:         │   │ Models:          │
│ ├─ Analyst       │   │ ├─ stocks            │   │ ├─ Haiku         │
│ ├─ Validator     │   │ ├─ themes            │   │ ├─ Sonnet 4.6    │
│ └─ Strategist    │   │ ├─ history           │   │ └─ Opus 4.7      │
│                  │   │ ├─ users             │   │                  │
│ Caching:         │   │ │  ├─ watchlist      │   │ Features:        │
│ ├─ Redis (옵션)  │   │ │  ├─ analyses       │   │ ├─ Streaming     │
│ └─ Memory cache  │   │ │  └─ ai_usage       │   │ ├─ Tool use      │
└──────────────────┘   │ └─ ai_recommendations│   │ └─ JSON mode     │
                       └──────────────────────┘   └──────────────────┘
                                ↑
                                │
                                │
┌────────────────────────────────────────────────────────────────────┐
│              Data Collector (기존 자산 - 유지)                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ collector.py (Cloud Run Job 또는 로컬 PC)                   │  │
│  │                                                              │  │
│  │ Schedules:                                                   │  │
│  │ ├─ Heavy 4회: 06:30, 09:30, 16:00, 22:30                    │  │
│  │ └─ Light 다회: 장중 30분/60분 간격                           │  │
│  │                                                              │  │
│  │ Tasks:                                                       │  │
│  │ ├─ KR 스냅샷 (KOSPI/KOSDAQ)                                  │  │
│  │ ├─ US 스냅샷 (S&P500/NASDAQ)                                │  │
│  │ ├─ 펀더멘털 (네이버 크롤링)                                  │  │
│  │ ├─ 외국인/기관 (pykrx)                                       │  │
│  │ ├─ 테마 분류                                                 │  │
│  │ ├─ OHLCV 히스토리                                            │  │
│  │ └─ 기술지표 계산 (buy_score, RSI 등)                         │  │
│  └──────────────────────────────────────────────────────────────┘  │
└────────┬───────────────────────────────────────────────────────────┘
         │
         ↓
┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐
│  Naver Finance   │   │     pykrx        │   │   yfinance       │
│  (크롤링)        │   │   (KRX 공식)     │   │  (US 시장)       │
└──────────────────┘   └──────────────────┘   └──────────────────┘


┌────────────────────────────────────────────────────────────────────┐
│                      Notification Layer                             │
│                                                                    │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐     │
│  │  Telegram    │    │ Kakao Biz    │    │ Email (SendGrid) │     │
│  │  (기존)      │    │ (신규)        │    │ (옵션)            │     │
│  └──────────────┘    └──────────────┘    └──────────────────┘     │
└────────────────────────────────────────────────────────────────────┘
```

---

## 🎯 핵심 설계 원칙

### 1. 기존 자산 최대 활용
- `collector.py` → 그대로 유지 (이미 안정적)
- `screener/core/` → 그대로 활용 (이미 정교함)
- `Firestore 스키마` → 확장만 (기존 컬렉션 유지)

### 2. 명확한 책임 분리
```
Frontend  : UI/UX, 사용자 입력
Backend   : 비즈니스 로직, 인증, AI 오케스트레이션
Agents    : Claude API 호출, 데이터 해석
Collector : 외부 데이터 수집 (독립 프로세스)
Firestore : 단일 진실의 원천 (Single Source of Truth)
```

### 3. 비용 최적화
- 모델 차등: Haiku → Sonnet → Opus
- 캐싱 적극: 1시간 / 30분 TTL
- SSE 스트리밍: UX 개선 + 부분 캐싱

### 4. 검증 가능성
- 모든 AI 응답은 Validator 통과 필수
- 모든 수치는 출처 + 시점 명시
- 사용자가 언제든 재검증 가능

---

## 🔄 핵심 데이터 흐름

### 시나리오 1: 종목 분석 요청

```
사용자: "삼성바이오로직스 어때?"
   ↓
[Frontend] 
   - 사용자 인증 토큰 검증
   - POST /api/ai/analyze
   ↓
[Backend - FastAPI]
   - Firebase 토큰 검증
   - Free/Pro 사용량 체크
   - LangGraph 실행
   ↓
[LangGraph Orchestration]
   ├─ Research Agent    (병렬, ~3초)
   │   - Firestore에서 themes, news 가져옴
   │   - Claude Haiku 호출
   │   - 시황/뉴스 요약 반환
   │
   └─ Analyst Agent     (병렬, ~4초)
       - Firestore에서 stock data 가져옴 (이미 buy_score 등 계산됨)
       - Claude Sonnet 호출
       - 기술적/펀더멘털 해석 반환
   ↓
   ↓ (병렬 완료)
   ↓
[Validator Agent]      (~3초)
   - Research + Analyst 결과 받음
   - FinanceDataReader로 실시간 가격 재조회
   - Claude Sonnet 호출
   - PASS / WARN / FAIL 판정
   - Contrarian 시나리오 3개 생성
   ↓
   ├─ FAIL & retry < 2 → Research/Analyst 재실행
   └─ PASS / WARN → 다음 단계
   ↓
[Strategist Agent]     (~5초)
   - 모든 결과 + 사용자 프로파일 + 페르소나 받음
   - Claude Opus 호출
   - 종합 분석 + 진입선 + 알림 조건 생성
   - 면책 문구 자동 추가
   ↓
[Backend]
   - Firestore에 분석 이력 저장
   - 사용량 카운터 증가
   - SSE로 클라이언트에 스트리밍
   ↓
[Frontend]
   - 각 에이전트 결과를 카드로 점진 표시
   - "🔍 검증" 버튼 노출
   - 페르소나 전환 토글
```

**총 소요 시간**: 6-12초 (병렬 처리 덕분)
**총 비용**: ~215원 / 쿼리

### 시나리오 2: 검증 버튼 클릭

```
사용자: "🔍 검증" 버튼 클릭
   ↓
[Frontend]
   - 분석 ID 전달
   - POST /api/ai/validate/{analysis_id}
   ↓
[Backend]
   - Firestore에서 원본 분석 결과 로드
   - Validator Agent만 재실행
   ↓
[Validator Agent]
   - 모든 수치 실시간 재조회
   - 신선도 판정
   - 결과 반환 (~2초)
   ↓
[Frontend]
   - 신선도 뱃지 업데이트
   - FAIL이면 자동 재분석 버튼 표시
```

### 시나리오 3: 페르소나 전환

```
사용자: "ARK 관점으로 보고 싶어" (탭 클릭)
   ↓
[Frontend]
   - 캐시 확인 (페르소나별 30분 TTL)
   - 캐시 없으면 POST /api/ai/analyze (persona=ark)
   ↓
[Backend]
   - Research/Analyst 결과는 캐시 활용
   - Strategist만 재실행 (페르소나 변경)
   ↓
[Strategist Agent]
   - ARK 페르소나 프롬프트 적용
   - 다른 관점의 분석 생성 (~5초)
   ↓
[Frontend]
   - 새 결과 표시
```

---

## 🗄 데이터 저장 전략

### Firestore 컬렉션 구조

```
firestore/
├── stocks/              # 기존 - 종목 데이터 (kr, us, etf)
├── themes/              # 기존 - 테마 분류
├── history/             # 기존 - OHLCV 히스토리
├── sync_metadata/       # 기존 - 수집 상태
├── supply_history/      # 기존 - 수급 이력
├── score_history/       # 기존 - buy_score 일별
│
├── users/               # 신규 - 사용자 데이터
│   └── {uid}/
│       ├── profile      # 프로필
│       ├── watchlist    # 관심 종목
│       ├── analyses     # 분석 이력
│       ├── ai_usage     # 사용량
│       └── custom_screeners
│
└── ai_recommendations/  # 신규 - 익명 통계
```

**상세 스키마**: `docs/DATABASE.md` 참고

---

## 🔐 인증 & 권한

### Firebase Auth 흐름

```
[Frontend Login]
   - 카카오/구글 OAuth 시작
   - Firebase에서 ID Token 받음
   ↓
[API 호출 시]
   - Authorization: Bearer {ID_TOKEN}
   ↓
[Backend Middleware]
   - firebase_admin.auth.verify_id_token(token)
   - 검증 성공 → request.state.user["uid"] 저장
   - 검증 실패 → 401
   ↓
[Route Handler]
   - get_current_user() Depends로 uid 사용
   - Firestore /users/{uid}/... 접근
```

### 권한 매트릭스

| 기능 | Free | Pro | Premium |
|------|------|-----|---------|
| 종목 분석 | 월 20회 | 무제한 | 무제한 |
| 검증 버튼 | 월 10회 | 무제한 | 무제한 |
| 페르소나 | 1개 (블랙록) | 3개 | 3개 |
| 관심 종목 | 5개 | 30개 | 30개 |
| 커스텀 스크리너 | ❌ | ✅ | ✅ |
| 진입선 알림 | ✅ | ✅ | ✅ |
| 주간 PDF | ❌ | ❌ | ✅ |

---

## 📡 API 통신

### REST API (대부분)
- Frontend ↔ Backend: HTTPS + JSON
- 타입 안전성: TypeScript ↔ Pydantic

### SSE (Server-Sent Events) - AI 분석 시
- AI 응답이 5-10초 걸리므로 스트리밍
- 각 에이전트 결과를 순차적으로 전송
- 사용자는 점진적으로 카드 채워지는 것 확인

```typescript
// 클라이언트
const eventSource = new EventSource("/api/ai/analyze?ticker=207940");
eventSource.addEventListener("research", (e) => {
  setResearchResult(JSON.parse(e.data));
});
eventSource.addEventListener("analyst", (e) => {
  setAnalystResult(JSON.parse(e.data));
});
// ...
```

---

## 🚨 주요 의사결정 포인트

### 1. 왜 Firebase + Firestore?
- ✅ 기존 자산 활용 (이미 사용 중)
- ✅ 카카오 로그인 OAuth 지원
- ✅ Realtime 업데이트 가능 (관심 종목 알림)
- ✅ 무료 티어 충분

### 2. 왜 LangGraph (CrewAI 대신)?
- ✅ 조건부 라우팅 (Validator FAIL → 재시도)
- ✅ State 관리 강력
- ✅ Anthropic 공식 파트너
- ⚠️ 러닝 커브 있음 (단점)

### 3. 왜 Next.js (React Native 대신)?
- ✅ 웹 우선 (모바일 브라우저로 충분)
- ✅ Vercel 배포 쉬움
- ✅ 기존 백엔드 (Cloud Run)와 분리 깔끔
- ❌ 네이티브 푸시 알림 어려움 → 카톡으로 대체

### 4. 왜 Cloud Run (AWS Lambda 대신)?
- ✅ 기존 사용 중 (이전 비용 0)
- ✅ 컨테이너 기반, 의존성 자유
- ✅ 한국 리전 (asia-northeast3)
- ✅ Min instances로 콜드 스타트 회피

---

## 📊 모니터링 & 관측성

### 추적해야 할 메트릭

```
Application:
├─ API 응답 시간 (p50, p95, p99)
├─ AI 분석 평균 시간
├─ Claude API 비용 (일별/월별)
├─ Firestore 읽기/쓰기 (비용)
└─ 에러율

Business:
├─ DAU / MAU
├─ Free → Pro 전환율
├─ 분석 횟수 / 유저
├─ 검증 버튼 사용률
├─ 페르소나별 사용 비율
└─ 유저 이탈률

Technical:
├─ Cloud Run 콜드 스타트
├─ Firestore 응답 시간
├─ Claude API 에러율
└─ Collector 성공률 (기존 시스템)
```

### 도구
- **로깅**: loguru (기존) + Cloud Logging
- **메트릭**: Cloud Monitoring (GCP)
- **알림**: 텔레그램 (기존)
- **에러**: Sentry (옵션, v1.0)

---

## 🚀 배포 전략

### 환경 분리
```
Development:
├─ Local Python (uvicorn dev)
├─ Local Next.js (npm run dev)
└─ Firebase Emulator (옵션)

Staging:
├─ Cloud Run (별도 서비스)
├─ Vercel Preview Branches
└─ Firestore (별도 프로젝트)

Production:
├─ Cloud Run (메인)
├─ Vercel Production
└─ Firestore (기존 프로젝트)
```

### CI/CD
```yaml
# GitHub Actions (제안)
on: 
  push:
    branches: [main]
jobs:
  backend:
    - Cloud Build → Cloud Run 배포
  frontend:
    - Vercel 자동 배포
```

---

## 📚 참고 자료

- 기존 시스템: [Stock_search_program](https://github.com/messi929/Stock_search_program)
- LangGraph: https://langchain-ai.github.io/langgraph/
- Anthropic API: https://docs.anthropic.com/
- Firebase Admin: https://firebase.google.com/docs/admin/setup
- Next.js 14: https://nextjs.org/docs

---

**다음 문서**: 
- `docs/DATABASE.md` - Firestore 스키마 상세
- `docs/api/ai.md` - AI API 스펙
- `docs/LEGAL.md` - 법적 안전장치
