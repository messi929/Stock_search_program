# MARKETING.md — 마케팅 전략 & 콘텐츠 공장

> 0→1(첫 사용자 확보) 단계의 마케팅 전략과, 이를 위해 구현한 "콘텐츠 공장" 기능 문서.
> 최종 갱신: 2026-06-26

---

## 1. 상황 정의 (왜 이 전략인가)

- **현 상태**: 가입자 ≈ 0. 이것은 유입/전환 최적화 문제가 아니라 **0→1 문제**다.
- **목표(1차)**: 진짜 첫 사용자 **10~50명**. 바이럴 불필요 — 특정 통증을 가진 50명만 찾으면 된다.
- **채널**: **스레드(Threads) 단일**. 팔로워 0이어도 알고리즘이 비팔로워에게 노출, 텍스트+이미지 위주라 익명 운영에 적합, 한국 주식/재테크 커뮤니티 활발.
- **창업자 노출**: 글/익명 콘텐츠 OK, **얼굴 X**.
- **예산**: ≈ 0 (콘텐츠/시간으로 승부).

### 핵심 포지셔닝
법적 제약(추천·목표가 금지, [LEGAL.md](LEGAL.md))을 **약점이 아니라 무기**로 사용한다.

> "종목 추천 안 합니다. AI한테 양쪽 다 뜯어보게 시키고, 판단은 당신이 하세요."

차별점 = **실시간 검증 + 반대의견(Contrarian)**. 대부분의 '주식 AI' 콘텐츠가 환각·낙관 일변도인 시장에서 정반대로 신뢰를 쌓는다.

---

## 2. 콘텐츠 엔진 — 4가지 반복 포맷

매번 새로 짜내지 않고, 제품 출력물(AI 분석)을 그대로 콘텐츠화한다.

| 키 | 포맷 | 톤 / 목적 |
|----|------|-----------|
| `curiosity` | 호기심 (AI한테 물어봤더니) | 수치 1~2개 흥미롭게 + "검증 돌려보니…" 호기심 유발 |
| `contrarian` | 반대의견 (반대로 보면) | 약점·과열·리스크 관찰 포인트, 반대 시나리오 사고 유도 |
| `trust` | 신뢰 (데이터 검증) | "AI 답변 그대로 믿어도 되나" — 신선도/재검증 브랜드 메시지 |
| `cta` | 댓글 모집 (종목 남겨주세요) | 참여 유도, "궁금한 종목 댓글로" → 댓글=리드+다음 소재 |

기본 3종 = `curiosity, contrarian, cta`.

### 전환 경로 (스레드 → 가입)
1. 게시물엔 결과 절반만 노출 → "전체 분석은 프로필 링크"
2. 프로필 링크 = `/stocks/[ticker]` 공개 페이지 → 검색 → 로그인 게이트 → AI 딥다이브
3. 무료 1회 경험 → 가입. (유입 측정은 공유링크 UTM → `/admin/funnel`)

### 운영 원칙
- 유용한 글 8 : 홍보 2 (스레드는 광고성 글 도달을 죽임)
- **법적 라인 사수** — 댓글 분석에도 추천/목표가 금지, 면책 습관화
- 10~50명 단계에선 가입자 한 명 한 명과 직접 대화(피드백이 진짜 자산)
- 확장 후보: 디시 주식갤·블라인드·클리앙 재테크 (동일 콘텐츠 재활용)

---

## 3. 콘텐츠 공장 (기능) — Phase 1 ✅ 배포 완료

스레드용 종목 글을 AI로 **자동 생성 → 검수 → 복사**하는 내부 도구. 2026-06-26 prod 배포(커밋 `a13d855`, `f5bd2fe`).

### 아키텍처
```
[종목] → build_instant_snapshot (스크리너 스냅샷, 실수치 PER/RSI/등락)
       → MarketerAgent (Haiku, 구조화출력 ThreadsPost{hook,body,hashtags})
       → filter_forbidden (추천·목표가 가드) + 압축 면책 1줄
       → Firestore marketing_drafts/{id} (status: draft|approved|archived)
       → 관리자 검수 UI / 일괄생성 CLI
```

| 구성 | 파일 |
|------|------|
| 생성 에이전트 | `agents/marketer.py` (MarketerAgent, FORMATS, generate_batch, pick_hot_tickers) |
| 백엔드 API | `api/routes/marketing.py` (`/api/admin/marketing/*`, 관리자 게이트) |
| 프론트 (웹 검수) | `web/app/(dashboard)/admin/marketing/page.tsx` + `web/lib/marketing.ts` |
| 로컬 실행 도구 | `jobs/marketing_generate.py` + `marketing.bat` |

### API (모두 관리자 전용 — `_is_admin` 게이트)
- `GET  /api/admin/marketing/formats` — 포맷 목록 + 기본값 + 최대 글자수(500)
- `GET  /api/admin/marketing/drafts?status=` — 초안 목록(최신순)
- `POST /api/admin/marketing/generate` — `{tickers?, formats?, hot_count?}`. tickers 비우면 화제종목 자동(pick_hot_tickers)
- `PATCH /api/admin/marketing/drafts/{id}` — `{text?, status?}`
- `DELETE /api/admin/marketing/drafts/{id}`

### 비용
- 종목 × 포맷 1건당 Haiku ~5원. (예: 3종목 × 3포맷 = 9건 ≈ 45원)

### 법적 안전
- 글에는 풀 4줄 면책 대신 **압축 1줄** 사용(500자 제약): `📌 투자 권유 아님 · 정보 제공일 뿐 판단은 본인 몫 (Axis)`
- `filter_forbidden`로 추천/매수·매도/목표가/시그널 등 자동 치환. 검수 시 `filtered` 뱃지로 경고 노출.

---

## 4. 사용법

### A. 웹 (어디서나)
`axislytics.com` 로그인(관리자) → 관리자 콘솔 → **마케팅** 탭
→ 종목/포맷 선택(비우면 자동) → ✨초안 생성 → 카드에서 편집·복사·승인.

### B. 로컬 실행 파일 (PC 더블클릭)
바탕화면 **「Axis 마케팅 글 생성기」** 아이콘 = 프로젝트 루트 `marketing.bat`.
- 더블클릭 → 종목/포맷 입력(엔터로 자동) → 로컬에서 일괄 생성
- `prime_name_store`로 **실수치(PER/RSI/등락/외국인)**가 들어간 글 생성
- Firestore에 저장 → 웹 마케팅 탭에 그대로 뜸 (PC 양산 → 웹/모바일 검수)
- CLI 직접 실행: `py -m jobs.marketing_generate [--tickers 005930,000660] [--formats curiosity,cta] [--hot 5] [--dry-run]`

> ⚠️ **`.bat`은 반드시 CRLF 줄바꿈**이어야 함. LF면 cmd.exe가 실행 못 함(초기 버그였음).
> `.gitattributes`에 `*.bat eol=crlf` 고정으로 재발 방지.

---

## 5. Phase 2 — Threads 자동 발행 (미구현)

검수·승인한 초안을 Threads API로 바로 발행.

### Threads API 사실
- 2단계: 컨테이너 생성 `POST /{user-id}/threads` → 발행 `POST /{user-id}/threads_publish`
- base: `https://graph.threads.net/v1.0/`, 텍스트 **500자**, 하루 **250개**
- 이미지는 **공개 URL** 필요 → 기존 OG카드 `/stocks/[ticker]/opengraph-image` 그대로 첨부 가능

### 선행 조건 (JEON 직접 셋업 — 며칠 소요)
1. Meta 앱 생성(Threads use case)
2. 인스타그램 **비즈니스/크리에이터** 계정을 Threads에 연결
3. **비즈니스 계정 인증** (승인 지연 가능)
4. 장기 토큰(60일, refresh) 발급 → 본인 1계정이라 OAuth 유저플로우 불필요

### 구현 예정
- `utils/threads_client.py` (컨테이너 생성→발행, 토큰 갱신, OG카드 첨부)
- 라우트 `POST /api/admin/marketing/drafts/{id}/publish` + UI "승인 → 자동 발행" 버튼
- Secret: `THREADS_ACCESS_TOKEN`, `THREADS_USER_ID`
- (선택) Cloud Run Jobs 예약 발행

---

## 6. 알려진 한계 / 메모
- Haiku 특성상 가끔 어색한 표현("봉투 데이터" 등) 발생 → 검수 탭에서 수정. 잦으면 프롬프트 강화.
- 스냅샷 미적재 환경(서버 밖·종목 미보유)에선 수치 없는 일반론 글이 나옴 → 로컬은 `prime_name_store`로 해결.
- 관련 문서: [LEGAL.md](LEGAL.md)(절대 원칙), [UNIT_ECONOMICS.md](UNIT_ECONOMICS.md)(비용), [PROGRESS.md](PROGRESS.md).
