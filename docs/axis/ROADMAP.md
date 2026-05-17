# Axis 6주 개발 로드맵

> **목적**: Claude Code가 6주 동안 헷갈리지 않고 따라올 수 있는 주간 체크리스트

---

## 📊 전체 일정 개요

| Week | 핵심 목표 | 산출물 |
|------|----------|--------|
| 1 | 기반 확장 + 인증 | Firebase Auth + Claude API 환경 |
| 2 | 4개 에이전트 구현 | 각 에이전트 독립 실행 가능 |
| 3 | LangGraph + API 통합 | `/api/ai/analyze` 작동 |
| 4 | Next.js 프론트엔드 시작 | 인증 + 대시보드 기본 |
| 5 | 핵심 기능 UI | MVP 5개 기능 모두 동작 |
| 6 | 스크리너 + 베타 런칭 | 100명 베타 모집 |

---

## 🚀 Week 1: 기반 확장 + 인증

### 목표
기존 Stock_search_program을 Axis로 확장할 토대 구축

### Day 1-2 (월-화): 프로젝트 리팩토링

**작업 체크리스트:**
- [ ] 새 브랜치 생성 (`feature/axis-ai-layer`)
- [ ] 기존 파일 삭제
  - [ ] `desktop.py`
  - [ ] `client_config.json`
  - [ ] `desktop.bat`
- [ ] `requirements.txt` 업데이트
  - [ ] 제거: `pywebview`, `pystray`, `Pillow` (Pillow는 다른 곳에서 쓰면 유지)
  - [ ] 추가:
    ```
    anthropic>=0.40.0
    langgraph>=0.2.0
    langchain-anthropic>=0.2.0
    pydantic>=2.0.0
    ```
- [ ] 디렉토리 구조 생성
  ```bash
  mkdir -p api/routes api/middleware
  mkdir -p agents personas utils
  mkdir -p docs/agents docs/api docs/frontend
  ```
- [ ] `CLAUDE.md` 루트에 배치
- [ ] 모든 docs 파일 `docs/` 폴더에 배치

**Claude Code 프롬프트 예시:**
```
프로젝트 디렉토리 구조를 다음과 같이 변경해줘:

1. 다음 파일들 삭제:
   - desktop.py
   - client_config.json
   - desktop.bat

2. requirements.txt에서 pywebview, pystray 제거하고
   anthropic>=0.40.0, langgraph>=0.2.0 추가해줘

3. 새 디렉토리 생성:
   - api/routes/, api/middleware/
   - agents/, personas/, utils/
   - docs/agents/, docs/api/, docs/frontend/

4. 기존 screener/ 폴더는 그대로 둬.
5. 변경 사항을 git에 커밋해줘 (메시지: "refactor: prepare for Axis AI layer")
```

### Day 3-4 (수-목): Firebase Auth 통합

**작업 체크리스트:**
- [ ] Firebase 프로젝트 생성 (콘솔에서)
  - 프로젝트명: `axis-investing` (또는 원하는 이름)
  - 위치: `asia-northeast3` (서울)
- [ ] Firebase Auth 설정
  - [ ] 카카오 로그인 OAuth 설정
  - [ ] 구글 로그인 활성화
  - [ ] 이메일/비밀번호 비활성화 (소셜만 사용)
- [ ] Firebase Admin SDK 키 생성
  - [ ] Service Account 키 다운로드
  - [ ] `.env`에 `FIREBASE_PROJECT_ID` 추가
- [ ] `api/middleware/firebase_auth.py` 구현
  - 자세한 스펙: `docs/api/auth.md` 참고
- [ ] `users` 컬렉션 스키마 정의
  - 자세한 스펙: `docs/DATABASE.md` 참고
- [ ] 카카오 디벨로퍼스에서 앱 등록
  - [ ] REST API 키 발급
  - [ ] Redirect URI 등록
  - [ ] `.env`에 `KAKAO_REST_API_KEY` 추가

**Claude Code 프롬프트 예시:**
```
Firebase Auth 미들웨어를 구현해줘.

1. api/middleware/firebase_auth.py 생성
2. 다음 기능 포함:
   - Authorization 헤더에서 Bearer 토큰 추출
   - firebase_admin.auth.verify_id_token()으로 검증
   - 검증 실패 시 401 반환
   - 검증 성공 시 request.state.user에 uid 저장

3. FastAPI Depends로 사용 가능한 헬퍼 함수도 만들어줘:
   async def get_current_user(request: Request) -> str:
       return request.state.user["uid"]

docs/api/auth.md를 참고해서 작성해줘.
```

### Day 5 (금): Claude API 환경 설정

**작업 체크리스트:**
- [ ] Anthropic API 키 발급
  - https://console.anthropic.com/
  - `.env`에 `ANTHROPIC_API_KEY` 추가
- [ ] `utils/claude_client.py` 구현
  - 4개 모델 쉽게 전환
  - 비용 로깅
  - 에러 핸들링 + 재시도
- [ ] `utils/cost_tracker.py` 구현
  - Firestore에 비용 누적 저장
- [ ] `utils/cache.py` 기본 구조
  - 동일 쿼리 캐싱 (1시간 TTL)
- [ ] 첫 테스트
  - `python -m utils.claude_client --test`
  - "안녕하세요" 응답 확인

### Week 1 완료 기준
- [ ] 카카오 로그인으로 가입/로그인 가능
- [ ] Firebase에서 유저 확인 가능
- [ ] Python에서 Claude API 호출 성공
- [ ] 비용 추적 로그 출력 확인

---

## 🤖 Week 2: 4개 에이전트 구현

### 목표
각 에이전트가 독립적으로 동작 (LangGraph 통합 전)

### Day 1 (월): Research Agent

**작업 체크리스트:**
- [ ] `agents/base.py` 작성 (공통 베이스 클래스)
- [ ] `agents/research.py` 구현
- [ ] 입출력 Pydantic 모델 정의
- [ ] 시스템 프롬프트 작성
- [ ] 단위 테스트 (`tests/test_research.py`)
- [ ] 예제 실행: "삼성바이오로직스 시황 분석"

**상세 스펙**: `docs/agents/research.md` 참고

### Day 2 (화): Analyst Agent

**작업 체크리스트:**
- [ ] `agents/analyst.py` 구현
- [ ] 기존 `screener/db/repository.py`의 `load_stocks()` 활용
- [ ] 기존 `buy_score`, `rsi`, `foreign_consecutive` 등 활용
- [ ] 시스템 프롬프트 (페르소나 미적용 버전)
- [ ] 단위 테스트
- [ ] 예제 실행: "삼성바이오 기술적/펀더멘털 분석"

**상세 스펙**: `docs/agents/analyst.md` 참고

### Day 3-4 (수-목): Validator Agent ⭐ 핵심

**작업 체크리스트:**
- [ ] `agents/validator.py` 구현
- [ ] 수치 자동 추출 로직
  - 정규식으로 숫자 + 단위 패턴 매칭
  - 종목명/티커 추출
- [ ] 실시간 가격 재조회
  - FinanceDataReader 사용
  - 캐싱 5분 TTL
- [ ] 편차 계산
  - 5% 미만: PASS
  - 5~10%: WARN
  - 10% 이상: FAIL
- [ ] Contrarian 시나리오 생성
- [ ] 단위 테스트
- [ ] 예제 실행: 의도적으로 stale 데이터 입력해서 FAIL 트리거

**상세 스펙**: `docs/agents/validator.md` 참고

### Day 5 (금): Strategist Agent + 페르소나 프롬프트

**작업 체크리스트:**
- [ ] `personas/blackrock.md` 작성
- [ ] `personas/ark.md` 작성
- [ ] `personas/graham.md` 작성
- [ ] `agents/strategist.py` 구현
- [ ] 페르소나별 프롬프트 동적 로딩
- [ ] 입력: 다른 3개 에이전트 결과
- [ ] 출력: 최종 종합 + 진입선 + 알림 조건
- [ ] 단위 테스트
- [ ] 예제 실행: 페르소나 3종 모두 테스트

**상세 스펙**: `docs/agents/strategist.md` 참고

### Week 2 완료 기준
- [ ] 4개 에이전트 모두 독립 실행 가능
- [ ] 각 에이전트 토큰 비용 측정됨
- [ ] 단위 테스트 통과
- [ ] 면책 문구 자동 삽입 확인

---

## 🔗 Week 3: LangGraph + API 통합

### 목표
4개 에이전트를 하나의 파이프라인으로, FastAPI로 노출

### Day 1-2 (월-화): LangGraph 오케스트레이션

**작업 체크리스트:**
- [ ] `agents/graph.py` 구현
- [ ] State 스키마 정의 (Pydantic)
  ```python
  class AnalysisState(BaseModel):
      query: str
      ticker: Optional[str]
      persona: str = "blackrock"
      research_output: Optional[ResearchResult]
      analyst_output: Optional[AnalystResult]
      validator_output: Optional[ValidatorResult]
      strategist_output: Optional[StrategistResult]
      retry_count: int = 0
      stale_data: bool = False
  ```
- [ ] 노드 정의
  - [ ] research_node (병렬 시작)
  - [ ] analyst_node (병렬 시작)
  - [ ] validator_node (게이트)
  - [ ] strategist_node (최종)
- [ ] 조건부 라우팅
  - [ ] Validator FAIL → Research/Analyst 재실행 (retry_count < 2)
  - [ ] Validator PASS → Strategist
- [ ] 통합 테스트

### Day 3 (수): FastAPI AI 라우트

**작업 체크리스트:**
- [ ] `api/routes/ai.py` 구현
- [ ] 엔드포인트:
  - [ ] `POST /api/ai/analyze` - 종목 분석
  - [ ] `POST /api/ai/validate` - 분석 결과 재검증
  - [ ] `GET /api/ai/personas` - 페르소나 목록
- [ ] SSE 스트리밍 지원
  - 각 에이전트 진행 상황을 클라이언트로 push
- [ ] Free/Pro 사용량 체크 미들웨어

**상세 스펙**: `docs/api/ai.md` 참고

### Day 4 (목): 관심 종목 + 스크리너 API

**작업 체크리스트:**
- [ ] `api/routes/watchlist.py`
  - [ ] `GET /api/watchlist` - 목록 조회
  - [ ] `POST /api/watchlist` - 추가
  - [ ] `PATCH /api/watchlist/{ticker}` - 진입선 수정
  - [ ] `DELETE /api/watchlist/{ticker}` - 삭제
- [ ] `api/routes/screener.py`
  - [ ] `GET /api/screener/smart-lists` - 스마트 리스트 카테고리
  - [ ] `POST /api/screener/custom` - 커스텀 스크리닝 실행
  - [ ] `POST /api/screener/save` - 조건 저장 (Pro)
- [ ] AI 추천 API
  - [ ] `POST /api/ai/recommend` - 자연어 종목 추천

**상세 스펙**: `docs/api/watchlist.md`, `docs/api/screener.md`

### Day 5 (금): 통합 테스트

**작업 체크리스트:**
- [ ] Postman 컬렉션 작성
- [ ] 시나리오 테스트
  - [ ] 가입 → 종목 검색 → 관심 추가 → AI 분석 → 검증
- [ ] 부하 테스트 (10명 동시 분석)
- [ ] Cloud Run 배포 테스트

### Week 3 완료 기준
- [ ] `curl`로 전체 플로우 동작
- [ ] Cloud Run에 배포되어 외부 접근 가능
- [ ] AI 분석 평균 응답 시간 < 10초
- [ ] 비용 1쿼리당 ~215원 확인

---

## 🎨 Week 4: Next.js 프론트엔드 시작

### 목표
인증 + 기본 UX 플로우

### Day 1 (월): Next.js 프로젝트 셋업

**작업 체크리스트:**
- [ ] `web/` 폴더에 Next.js 14 생성
  ```bash
  npx create-next-app@latest web --typescript --tailwind --app
  ```
- [ ] shadcn/ui 초기화
  ```bash
  cd web && npx shadcn-ui@latest init
  ```
- [ ] 필수 컴포넌트 설치
  ```bash
  npx shadcn-ui@latest add button card dialog input
  npx shadcn-ui@latest add dropdown-menu toast tabs
  ```
- [ ] Firebase 클라이언트 SDK 설치
  ```bash
  npm install firebase
  npm install @tanstack/react-query
  npm install zustand
  ```
- [ ] Vercel 배포 파이프라인 설정

### Day 2-3 (화-수): 인증 + 온보딩

**작업 체크리스트:**
- [ ] `web/lib/firebase.ts` - Firebase 클라이언트 초기화
- [ ] `web/lib/api.ts` - Cloud Run API 호출 헬퍼
- [ ] 카카오 로그인 페이지
- [ ] 구글 로그인 페이지
- [ ] 4문항 온보딩 플로우
  - 투자 경력 (1-5년차 / 5년+ / 초보)
  - 관심 섹터 (멀티셀렉트)
  - 선호 페르소나 (블랙록 디폴트)
  - 알림 설정 (카톡/이메일)
- [ ] 프로필 저장 → users 컬렉션

### Day 4-5 (목-금): 대시보드 메인

**작업 체크리스트:**
- [ ] 레이아웃 구조
  - 상단: 시장 지표 위젯
  - 중앙: 관심 종목 리스트
  - 하단: 최근 분석 이력
- [ ] 시장 지표 카드 (코스피/코스닥/환율/VKOSPI)
- [ ] 관심 종목 테이블
  - 종목명, 현재가, 등락률, 진입선
- [ ] 진입선 시각화
  - 현재가까지 거리 표시
- [ ] 모바일 반응형 (Tailwind breakpoints)

**상세 스펙**: `docs/frontend/pages.md` 참고

### Week 4 완료 기준
- [ ] Vercel에 배포되어 axis.kr (또는 Vercel 도메인) 접근 가능
- [ ] 카카오 로그인 가능
- [ ] 대시보드에서 시장 지표 확인 가능
- [ ] 관심 종목 표시됨 (DB에서 로드)

---

## 🔥 Week 5: 핵심 기능 UI

### 목표
MVP 5개 기능 완성

### Day 1-2 (월-화): 종목 딥다이브 화면

**작업 체크리스트:**
- [ ] `app/(dashboard)/analyze/[ticker]/page.tsx`
- [ ] SSE 스트리밍 수신
- [ ] 각 에이전트 결과 카드
  - Research / Analyst / Validator / Strategist
- [ ] 펼치기/접기 (Accordion)
- [ ] 로딩 상태 표시
- [ ] 에러 핸들링

### Day 3 (수): 검증 버튼 ⭐

**작업 체크리스트:**
- [ ] `components/analyze/ValidateButton.tsx`
- [ ] 모든 분석 결과 하단에 배치
- [ ] 클릭 → POST `/api/ai/validate`
- [ ] 결과 표시
  - ✅ 신선도 OK (5% 이내)
  - ⚠️ 주의 (5-10%)
  - ❌ 재분석 필요 (10%+)
- [ ] 자동 재분석 버튼

### Day 4 (목): 페르소나 전환

**작업 체크리스트:**
- [ ] `components/analyze/PersonaSwitch.tsx`
- [ ] 탭 UI (블랙록 / ARK / 그레이엄)
- [ ] 클릭 시 해당 페르소나로 재분석
- [ ] 결과 캐싱 (페르소나별 별도 저장)
- [ ] Free 유저: 블랙록만 활성화

### Day 5 (금): 관심 종목 추가 UX

**작업 체크리스트:**
- [ ] 하이브리드 등록 화면
  - 검색 + 자동완성
  - AI 추천 자연어 입력
  - 큐레이션 테마 9개
- [ ] 진입선 설정 화면
  - 직접 설정
  - AI 참고 수치 (Pro)
- [ ] 알림 채널 선택
- [ ] 5개/30개 제한 처리

**상세 스펙**: `docs/frontend/pages.md` 참고

### Week 5 완료 기준
- [ ] 종목 검색 → 분석 → 검증 → 관심 추가 전체 플로우 작동
- [ ] 페르소나 전환 결과 차별화됨
- [ ] 모바일 UX 매끄러움
- [ ] 면책 문구 모든 분석에 표시

---

## 🚢 Week 6: 스크리너 + 베타 런칭

### 목표
전체 기능 통합, 100명 베타 모집

### Day 1-2 (월-화): 스마트 리스트 + 커스텀 스크리너

**작업 체크리스트:**
- [ ] 기존 `screener/core/screener.py`의 `CATEGORIES` 재활용
- [ ] 스마트 리스트 화면
  - 6카테고리 × 4-5리스트 = 24-30개
  - 각 리스트 클릭 → 결과
- [ ] 커스텀 스크리너 (Pro)
  - 조건 빌더 UI
  - 저장 / 알림 설정
- [ ] AI 한줄 해석 (Research Agent)

### Day 3 (수): 알림 시스템

**작업 체크리스트:**
- [ ] 카카오 비즈 알림톡 API 연동
- [ ] 알림 트리거
  - 진입선 도달
  - 커스텀 스크리너 새 매칭
  - 일일 시황 브리핑
- [ ] 사용자 알림 설정 화면
- [ ] n8n 또는 Cloud Scheduler로 매일 7시 브리핑

### Day 4 (목): QA + 법적 안전장치

**작업 체크리스트:**
- [ ] 전체 플로우 E2E 테스트
- [ ] "추천", "사세요" 등 금지 단어 검색
  ```bash
  grep -r "추천" web/ api/ agents/ personas/
  ```
- [ ] 모든 AI 응답에 면책 문구 확인
- [ ] 이용약관 작성
- [ ] 개인정보처리방침 작성
- [ ] 회원 탈퇴 기능
- [ ] 데이터 다운로드 기능 (GDPR-style)

### Day 5 (금): 베타 런칭

**작업 체크리스트:**
- [ ] 랜딩 페이지 (Framer or Next.js)
- [ ] 베타 신청 폼
- [ ] X/스레드/투자 커뮤니티 공지
- [ ] Notion 연동 피드백 수집
- [ ] 헬프 문서 (FAQ)
- [ ] 모니터링 대시보드 설정

**랜딩 페이지 카피 예시:**
```
"유튜버 말고, AI 애널리스트와 함께"

블랙록처럼 분석합니다.
ARK처럼 미래를 봅니다.
그레이엄처럼 가치를 찾습니다.

[베타 신청 - 100명 한정 무료 6개월]
```

### Week 6 완료 기준
- [ ] axis.kr 도메인으로 접속 가능
- [ ] 베타 유저 100명 신청
- [ ] 첫 Pro 전환 (목표: 5명)
- [ ] 피드백 10건 이상 수집

---

## 📊 주간 체크인 (매주 금요일)

각 주차 마지막 날 이 양식으로 자가 점검:

```markdown
# Week N 회고

## 완료한 것
- [x] ...

## 미완료한 것
- [ ] ... (이유: ...)

## 막힌 부분
1. 이슈 설명
   - 시도한 해결책
   - 도움 필요한 부분

## 다음 주 조정 필요한 것
- 일정 변경
- 스코프 조정

## 비용 현황
- Claude API: $X
- Firestore: $X
- 총: $X

## 학습한 것
- ...
```

---

## 🚨 일정 지연 시 우선순위

만약 일정이 밀린다면 **반드시 살릴 것**:

1. **검증 시스템** (핵심 차별점)
2. **종목 딥다이브** (메인 가치)
3. **인증** (사용자 식별 필수)
4. **관심 종목** (재방문 유도)

**과감히 자를 수 있는 것**:
1. 페르소나 3종 → 1종으로 시작
2. 커스텀 스크리너 → v1.0으로 연기
3. 카톡 알림 → 텔레그램만 우선
4. 모바일 최적화 → 웹 우선

---

**마지막 업데이트**: 2026-04-25
