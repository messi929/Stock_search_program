# Axis Project Documents

> Claude Code에 전달할 프로젝트 계획 문서 모음

---

## 📚 문서 구조

```
axis_plan/
├── CLAUDE.md                    # 🌟 마스터 컨텍스트 (가장 먼저 읽기)
├── README.md                    # 이 파일 (인덱스)
└── docs/
    ├── ROADMAP.md              # 6주 일정 + 체크리스트
    ├── ARCHITECTURE.md         # 전체 시스템 설계
    ├── DATABASE.md             # Firestore 스키마
    ├── LEGAL.md                # 법적 안전장치 (필수)
    │
    ├── agents/                 # 4개 AI 에이전트
    │   ├── research.md         # 시황/뉴스 (Haiku)
    │   ├── analyst.md          # 기술/펀더멘털 (Sonnet)
    │   ├── validator.md        # 검증 ⭐ (Sonnet)
    │   └── strategist.md       # 종합/페르소나 (Opus)
    │
    ├── api/                    # 백엔드 API 스펙
    │   ├── ai.md               # AI 분석 엔드포인트
    │   ├── watchlist.md        # 관심 종목 CRUD
    │   └── screener.md         # 스크리너
    │
    └── frontend/               # 프론트엔드 설계
        ├── pages.md            # Next.js 페이지 구조
        └── components.md       # 핵심 React 컴포넌트
```

---

## 🚀 Claude Code 첫 실행 가이드

### 1단계: 레포 셋업
```bash
# 1. 기존 레포 클론
git clone https://github.com/messi929/Stock_search_program.git axis
cd axis

# 2. 새 브랜치 생성
git checkout -b feature/axis-ai-layer

# 3. 이 계획 문서들을 프로젝트에 복사
cp -r ~/Downloads/axis_plan/CLAUDE.md ./
cp -r ~/Downloads/axis_plan/docs ./
```

### 2단계: Claude Code 시작
```bash
claude
```

### 3단계: 첫 프롬프트
```
프로젝트 루트의 CLAUDE.md를 먼저 읽어줘.
그다음 docs/ROADMAP.md를 읽고 Week 1 체크리스트를 확인해줘.

준비되면 Week 1 Day 1-2 작업부터 시작해줘:
1. 프로젝트 리팩토링 (desktop.py 등 삭제)
2. requirements.txt 업데이트 (anthropic, langgraph 추가)
3. 디렉토리 구조 변경 (api/, agents/, personas/, utils/)

작업 전에 어떻게 할지 계획을 먼저 알려줘.
```

---

## 📖 문서 읽는 순서 (Claude Code용)

### 새로운 작업 시작 시
1. **CLAUDE.md** (필수) - 전체 프로젝트 맥락
2. **docs/ROADMAP.md** - 현재 어느 주차인지 확인
3. **docs/LEGAL.md** - 법적 원칙 (항상 준수)

### 작업 종류별 추가 문서

**AI 에이전트 작업 시:**
- `docs/agents/{agent_name}.md`
- `docs/ARCHITECTURE.md` (LangGraph 부분)

**Backend API 작업 시:**
- `docs/api/{endpoint}.md`
- `docs/DATABASE.md`

**Frontend 작업 시:**
- `docs/frontend/pages.md`
- `docs/frontend/components.md`

---

## ⚡ 핵심 원칙 (Quick Reference)

### 1. 절대 사용 금지 단어
```
❌ 추천합니다, 사세요, 매수하세요
❌ 매수 신호, 매도 신호, 유망주
❌ 목표가, 매수가
```

### 2. 모든 AI 응답에 면책 문구
```
📌 본 분석은 투자 권유가 아닌 정보 제공입니다.
   최종 판단은 사용자 본인의 책임입니다.
   Axis는 투자자문업 면허가 없습니다.
```

### 3. 핵심 차별점
- **실시간 검증**: 모든 수치 재검증 가능
- **페르소나**: 블랙록/ARK/그레이엄 3종
- **Contrarian**: 반대 시나리오 강제 생성

### 4. 기술 스택
```
Backend  : FastAPI + LangGraph + Anthropic Claude
DB       : Firestore (asia-northeast3)
Frontend : Next.js 14 + TypeScript + Tailwind
Auth     : Firebase Auth (카카오/구글)
Hosting  : Cloud Run + Vercel
```

---

## 📅 6주 로드맵 (한눈에)

| 주차 | 주제 | 핵심 산출물 |
|-----|------|-----------|
| 1 | 기반 + 인증 | Firebase Auth + Claude API |
| 2 | 4개 에이전트 | 독립 호출 가능한 4개 에이전트 |
| 3 | LangGraph + API | `/api/ai/analyze` 작동 |
| 4 | Next.js 시작 | 인증 + 대시보드 |
| 5 | 핵심 UI | MVP 5개 기능 |
| 6 | 스크리너 + 런칭 | 베타 100명 모집 |

---

## 🎯 MVP 5개 기능

1. **종목 딥다이브** - "삼성바이오 어때?" → 4개 에이전트 분석
2. **실시간 검증 버튼** ⭐ - 핵심 차별점
3. **페르소나 전환** - 블랙록/ARK/그레이엄
4. **관심 종목 트래커** - 5개(Free) / 30개(Pro)
5. **스마트 리스트** - 기존 스크리너 흡수

---

## 💰 수익 모델

```
Free      : 분석 월 20회, 검증 월 10회, 페르소나 1개
Pro 9.9k  : 무제한, 페르소나 3개, 커스텀 스크리너
Premium   : 추후 (PDF 리포트 등)

손익분기  : Pro 20명
6개월 목표: Pro 100명 → 99만원 매출
```

---

## 🔧 환경 변수 (.env)

```bash
# 기존
GOOGLE_APPLICATION_CREDENTIALS=path/to/serviceAccountKey.json
FIREBASE_PROJECT_ID=axis-investing
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# 신규
ANTHROPIC_API_KEY=sk-ant-...
KAKAO_REST_API_KEY=
KAKAO_BIZ_TEMPLATE_ID=

# Frontend (web/.env.local)
NEXT_PUBLIC_FIREBASE_API_KEY=
NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=axis-investing.firebaseapp.com
NEXT_PUBLIC_FIREBASE_PROJECT_ID=axis-investing
NEXT_PUBLIC_API_BASE_URL=https://stock-screener-119320994983.asia-northeast3.run.app
```

---

## ⚠️ 주의사항 모음

### 비용 관리
- Claude API 모델 차등 사용 (Haiku 우선)
- Firestore 읽기 캐싱
- Cloud Run min instances 0~1

### 데이터 소스
- 네이버 크롤링 → 회색지대 (장기적으로 한투 OpenAPI)
- pykrx → 안정적, 우선 사용
- yfinance → 미국만

### 보안
- Firebase 토큰 검증 미들웨어 필수
- 사용자별 데이터 격리 (`/users/{uid}/...`)
- API 키 프론트엔드 노출 금지

### UX
- 모바일 우선 (한국 80%+ 모바일)
- 다크 모드 디폴트 (투자자 선호)
- 한국어 우선

---

## 🐛 알려진 이슈 / 결정 사항

### 결정된 것
- ✅ 프론트엔드: Next.js 완전 새로
- ✅ desktop.py: 삭제
- ✅ 기존 collector.py: 그대로 유지
- ✅ Firestore 스키마: 기존 + 확장
- ✅ 페르소나: 3종 (블랙록/ARK/그레이엄)

### 추후 결정
- ❓ 결제 시스템 (Toss / 카카오페이 / Stripe)
- ❓ 도메인 (axis.kr / axisai.io / axis.investing)
- ❓ 한투 OpenAPI 전환 시점

---

## 📞 작업 시 막히면

### 컨텍스트 손실 시
```
CLAUDE.md를 다시 읽고, 현재 작업 중인 부분을 docs/ROADMAP.md에서 확인해줘.
```

### 법적 안전 의문 시
```
docs/LEGAL.md를 확인하고, 의심스러우면 보수적으로 처리해줘.
```

### API 스펙 의문 시
```
docs/api/{관련 파일}.md 를 참고해줘.
```

---

## 🚀 다음 단계

1. ✅ 계획 문서 완성
2. ⬜ 레포 클론 + 브랜치 생성
3. ⬜ CLAUDE.md + docs/ 배치
4. ⬜ Claude Code Week 1 시작
5. ⬜ Firebase 프로젝트 생성
6. ⬜ Anthropic API 키 발급
7. ⬜ 첫 에이전트 (Research) 구현

---

**작성일**: 2026-04-25  
**작성자**: JEON + Claude (Axis 설계 대화)  
**버전**: v1.0  
**상태**: 작성 완료, Claude Code 전달 준비 완료

---

> 💡 **Tip**: 매주 금요일 진행 상황을 새 대화로 공유해주시면, 일관된 맥락으로 피드백 드릴 수 있습니다.
