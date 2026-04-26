# Axis 진행 사항 — Week 1~5 완료 (2026-04-26 기준)

> **브랜치**: `feature/axis-ai-layer` (main의 v7.5와 분리 운영)
> **현재 위치**: Week 5 종료 / Week 6(베타 런칭 준비) 대기
> **누적 커밋**: 19건

---

## 🎯 프로젝트 개요

**Axis** — 1~5년차 중급 투자자를 위한 AI 기반 한국 주식 분석 도구.

### 핵심 차별점
- **4-Agent LangGraph 파이프라인** (Research/Analyst/Validator/Strategist)
- **실시간 검증 ⭐** — 가격/PER/PBR/ROE를 결정론적 코드로 재조회 + Contrarian 시나리오는 Claude가 강제 생성
- **3 페르소나** — 같은 종목, 다른 관점 (블랙록·ARK·그레이엄)
- **LEGAL 절대 원칙** — "추천" 단어 절대 금지, 모든 응답에 면책 문구

### v7.5와 관계
- 기존 자산 60% 재활용 (`screener/core/`, `collector.py`, Firestore, Cloud Run)
- 신규 40% (AI 에이전트, Next.js 프론트, Discoverer)
- main 브랜치 v7.5는 그대로 운영, Axis는 별도 Cloud Run 서비스(`axis-staging`)에 배포

---

## 📅 주차별 진척

### Week 1 — 기반 환경 (3 커밋)

| 커밋 | 작업 |
|------|------|
| `f204440` | 데스크톱 클라이언트 제거, 디렉토리 구조 (`api/`, `agents/`, `personas/`, `utils/`, `docs/axis/`) |
| `42588a6` | AI 레이어 스캐폴딩, v7.5 미들웨어 재사용 (옵션 C 하이브리드 결정) |
| `4c75a14` | Claude API 클라이언트(`utils/claude_client.py`) + 비용 추적 + 메모리 캐시 |

**검증**: smoke test "안녕하세요" → Haiku 0.2원 응답 ✓

---

### Week 2 — 4 에이전트 (5 커밋)

| 에이전트 | 모델 | 비용/호출 | 핵심 |
|---------|------|----------|------|
| Research | Haiku 4.5 | ~9원 | 시황·뉴스·매크로·외국인/기관 수급 |
| Analyst | Sonnet 4.6 | ~34원 | v7.5 buy_score 해석, score_tier 중립 변환 |
| **Validator** ⭐ | Sonnet 4.6 | ~40원 | 가격 코드 재조회 + Contrarian Claude 분리 설계 |
| Strategist | Opus 4.7 | ~370원 | 페르소나 3종 동적 system prompt |

**핵심 패턴**:
- `BaseAgent.call_claude_json()` — JSON prefill 제거(Sonnet 4.6 미지원), `extract_json` + `json-repair` 폴백
- `default_cache` 메모리 TTL 1시간 — 같은 입력 재호출 0원
- 시스템 프롬프트 cache_control 자동 적용 (1024+ tokens)

---

### Week 3 — LangGraph + API + 배포 (5 커밋)

| 커밋 | 내용 |
|------|------|
| `aab406d` | LangGraph 4 노드 그래프 + `/api/ai/{personas, analyze, validate}` + SSE 스트리밍 |
| `6bc7969` | `/api/ai/watchlist/{ticker}/entry-points` (PUT/GET/DELETE), `/api/ai/usage`, `/api/screener/smart-lists` |
| `ecb53b6` | Discoverer Agent + `/api/ai/discover` (자연어 종목 발견, ~70원) |
| `38fcc38` | E2E HTTP 통합 시나리오 통과 (4 에이전트 86초, 재검증 0.1초 캐시) |
| `4e85bc8` | **Cloud Run `axis-staging` 배포 성공** |

**LangGraph 흐름**:
```
START → fanout → (research || analyst 병렬) → validator
       ├─ requires_reanalysis & retry<2 → fanout (재시도, 최대 2회)
       └─ → strategist → END
```

**Cloud Run**:
- URL: `https://axis-staging-1043976673827.asia-northeast3.run.app`
- Secret: `anthropic-api-key:1` (신규), `firebase-key` (v7.5 공유)
- 1Gi/1vCPU, min=0/max=2

---

### Week 4 — 프론트엔드 시작 (3 커밋)

| Day | 커밋 | 작업 |
|-----|------|------|
| 1 | `405dc1e` | Next.js 16 셋업, shadcn 4.5, Firebase/TanStack/Zustand, 랜딩 |
| 2-3 | `9d41893` | Google 로그인, 4문항 온보딩, 보호 대시보드 |
| 4-5 | `7bb803a` | 시장 상태 위젯, 관심종목 미리보기, 스크리너 + **검증 fix 5건** |

**스택 (Next.js 14 → 16으로 업그레이드)**:
- Next.js 16.2.4 + React 19.2 + TypeScript 5
- Tailwind 4 (PostCSS), shadcn 4.5 (`@base-ui/react` 기반 — `asChild` 대체)
- Firebase 12 / TanStack Query 5 / Zustand 5

---

### Week 5 — 분석 페이지 + 관심종목 추가 (3 커밋)

| Day | 커밋 | 작업 |
|-----|------|------|
| 1 | `1d16ba0` | `/analyze/[ticker]` SSE 스트리밍 + 4 에이전트 카드 |
| 2-3 | `e0e1070` | ⭐ 검증 버튼 + 관찰 구간 저장 + 관심 종목 추가 |
| 4-5 | `574c0dd` | Free 페르소나 가드 + `/watchlist/add` 3 탭 + race 차단 3건 |

---

## 🌐 라이브 시스템

### Backend (axis-staging)
URL: `https://axis-staging-1043976673827.asia-northeast3.run.app`

**Axis 신규 라우트 (10개)**:
- `GET /api/ai/personas`
- `POST /api/ai/analyze` (LangGraph + SSE 옵션)
- `POST /api/ai/validate/{ticker}`
- `POST /api/ai/discover`
- `GET /api/ai/usage`
- `GET/PUT/DELETE /api/ai/watchlist/{ticker}/entry-points`
- `GET/PUT /api/ai/profile`
- `GET /api/screener/smart-lists`

**v7.5 라우트 (~70개)**: Lemon Squeezy 결제, 관심종목, 트라이얼, 관리자 등 모두 같은 컨테이너에 공존.

### Frontend (로컬 dev only)
- Next.js 16 Turbopack, ready ~500ms
- 라우트 8개:
  ```
  /                  랜딩
  /login             Google OAuth
  /onboarding        4문항
  /dashboard         시장상태 + 관심미리보기 + 프로파일
  /screener          17 카테고리 SmartListGrid
  /watchlist/add     Search / Discover / Themes 3 탭
  /analyze/[ticker]  4 에이전트 SSE + 액션 3개
  /pricing, /terms 등 미구현 (랜딩 footer 링크만)
  ```

---

## 🔍 검증 워크플로우 효과

병행 reviewer 에이전트(general-purpose subagent)가 사용자에게 도달하기 전 **총 20건 fix**:

| 라운드 | 발견 | 핵심 |
|-------|------|------|
| W3 D4 Discoverer | 4건 | agent_name 일관성, 할루시네이션 강화 (Claude는 ticker만, 나머지는 candidate dict에서 재구성) |
| W4 D4-5 web 일반 | 5건 | useUserProfile race, Firestore 직접 쓰기 → 백엔드 라우트 경유, 401 token refresh, SSE multi-line spec, 다크모드 |
| W5 D2-3 액션 패턴 가이드 | 8건 | shadcn `<Button>` 직접, canonical persona = `strategist.persona_used`, Set dedupe, 인라인 면책 |
| W5 D4-5 final | 3건 | DiscoverTab dedupe + isPending 가드, AddToWatchlist closure stale → `useAddToWatchlist`, ThemesTab debounce 800ms |

---

## 💰 비용

### 1회 풀 분석 비용 실측 (Cloud Run staging)
```
Research 1회   = 9원   (Haiku, in 1800/out 1100)
Analyst 1회    = 34원  (Sonnet, in 2518/out 1100)
Validator 1회  = 40원  (Sonnet, in 2200/out 1500 + json-repair)
Strategist 1회 = 370원 (Opus, in 2900/out 2200, system cache_w 2834)
─────────────────────────────────────
합계: ~453원/쿼리 (ROADMAP 추정 215원 대비 2.1배)
```

### 캐시 효과
- 같은 입력 재호출: `default_cache` 히트 → **0원**
- 페르소나 토글: Strategist만 재호출 → ~370원
- 검증 버튼: Validator만 → 캐시 히트 시 0원, 0.1초

### 누적 개발 비용 (Week 1-5 테스트)
- ~3,500원 (스모크/단위/통합/staging E2E + Strategist 검증 재실행)

---

## 📦 누적 파일 통계

```
backend (Python)
  agents/        7 파일 (5 에이전트 + base + graph + __init__)
  api/           5 파일 (routes/ai.py 큰 편, screener.py, middleware/)
  personas/      4 파일 (3 페르소나 .md + __init__)
  utils/         4 파일 (claude_client, cost_tracker, cache, __init__)
  data/          1 파일 (macro_events.json)
  tests/         8 파일 (각 에이전트 + graph + ai_route + integration + discoverer)
  docs/axis/     6 파일 (CLAUDE/ROADMAP/ARCHITECTURE/DATABASE/LEGAL/INTEGRATION_NOTES + 4 agents/3 api/2 frontend)

frontend (Next.js)
  app/           7 페이지 (랜딩/auth 3개/dashboard 3개/analyze 동적)
  components/    14 파일 (analyze 8개, watchlist 3개, dashboard 2개, screener 1개, legal/ui)
  hooks/         8 파일
  lib/           4 파일
  store/types/   2 파일
```

---

## 🚧 미해결 / 대기 사항

### 사용자 작업 필요
1. **`.env.local` Firebase 값 채움** — `NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID` + `APP_ID` (Firebase 콘솔 프로젝트 설정)
2. (선택) **카카오 OAuth** — Firebase native 미지원, REST API + custom token 별도 구현 필요 (Week 6)

### 배포 대기
1. **axis-staging 재배포** — 다음 신규 백엔드 라우트가 staging에 아직 반영 안 됨:
   - `GET/PUT /api/ai/profile` (W4 D4-5)
   - `GET /api/screener/smart-lists` (W3 D4)
   - `POST /api/ai/discover` (W3 D4-B)
   - `GET/PUT/DELETE /api/ai/watchlist/{ticker}/entry-points` (W3 D4-A)
   - `GET /api/ai/usage` (W3 D4-A)

   재배포 명령:
   ```bash
   gcloud run deploy axis-staging \
     --source=. \
     --region=asia-northeast3 \
     --project=all-of-asset \
     --update-secrets="ANTHROPIC_API_KEY=anthropic-api-key:latest,FIREBASE_CREDENTIALS=firebase-key:latest" \
     --set-env-vars="RUN_MODE=server,COLLECT_MODE=readonly,AUTH_ENABLED=true,FIREBASE_PROJECT_ID=stock-search-program,FIREBASE_WEB_API_KEY=...,ADMIN_EMAILS=messi929@naver.com"
   ```
   소요 5-10분, 비용 ~0원 (Cloud Build 무료 한도)

2. **Vercel 배포** — Next.js 프론트 외부 노출 (도메인 결정 후)
3. **도메인** — `axis.kr` / `allofasset.com` 결정 + Cloudflare/Vercel 연결

### v7.5와의 정합성 (머지 시점에 결정)
- v7.5 "TOP 픽", "매수 포인트", `buy_grade="적극매수"` UI는 LEGAL 충돌
- Axis는 score_tier "상위/준상위/중간/관찰"로 중립 변환 — main 머지 시 v7.5 UI도 변경할지 결정 필요

---

## 🎬 Week 6 (베타 런칭 준비)

ROADMAP 기준:
- **Day 1-2**: Smart Lists 결과 페이지 (`/screener/[id]`) + 커스텀 스크리너 (Pro)
- **Day 3**: 알림 시스템 (Mailgun + Cloud Scheduler) — 진입선 도달 / 일일 시황
- **Day 4**: 법적 안전장치 sweep (`scripts/legal_check.py`) + 약관/개인정보처리방침 페이지
- **Day 5**: 랜딩 카피 다듬기 + 베타 신청 폼 + axis-staging 재배포 + Vercel 배포

**완료 기준**:
- [ ] 도메인 접속 가능 (axis.kr or allofasset.com)
- [ ] 베타 유저 100명 신청 (X/투자 커뮤니티 공지)
- [ ] 첫 Pro 전환 (목표 5명)
- [ ] 피드백 10건 이상 수집

---

## 🔧 운영 정보

### Anthropic API
- 키: `.env`에 `ANTHROPIC_API_KEY` (sk-ant-api...108자), MOA backend에서 옮겨옴
- Cloud Run secret: `anthropic-api-key:1` (Secret Manager)
- 콘솔: https://console.anthropic.com/

### GCP
- 프로젝트: `all-of-asset`
- Region: `asia-northeast3` (서울)
- 서비스 계정: `1043976673827-compute@developer.gserviceaccount.com`
- 서비스: `stock-screener` (v7.5 운영) + `axis-staging` (Axis)

### Firebase
- 프로젝트: `stock-search-program` (v7.5와 공유)
- Web API key: `AIzaSyDIAvNnqr4_RAB7AkLbhNdHJ9yKycoYiz4` (공개 가능)
- Auth: Google 활성, 이메일/비밀번호 비활성, 카카오 미설정

### Connected MCPs (개발용)
- ✓ sequential-thinking
- ✓ magic (21st.dev — UI 컴포넌트)
- ✓ context7 (라이브러리 docs)
- ✓ playwright (E2E 테스트, Week 6에 사용 예정)
- ✓ youtube-transcript

---

**최종 업데이트**: 2026-04-26 (Week 5 종료 시점, 19 commits)
**다음 세션 시작점**: Week 6 Day 1 (`/screener/[id]` 결과 페이지 + 알림 시스템)
