# MARKETING.md — 마케팅 전략 & 콘텐츠 공장

> 0→1(첫 사용자 확보) 단계의 마케팅 전략과, 이를 위해 구현한 "콘텐츠 공장" 기능 문서.
> 최종 갱신: 2026-06-27

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
3. 무료 1회 경험 → 가입. (클릭 측정은 Threads 자체 링크 분석. UTM 가입귀속은 미구현 — §7 참고)

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

## 5. Phase 2 — Threads 자동 발행 ✅ 배포 완료 (2026-06-27)

검수·승인한 초안을 Threads API로 바로 발행. 커밋 `f50bc39`, `f587b18`. 발급 절차 = [THREADS_PUBLISHING.md](THREADS_PUBLISHING.md).

### 토큰 (✅ 확보)
- 발행 계정 `@axislystics`(공개), Meta 앱 "Axis"(앱ID `2849320188770068`)
- **콘솔 "사용자 토큰 생성기"로 장기 토큰 직접 발급** = 1계정 정석 지름길(OAuth 브라우저플로우/curl 불필요)
  - 함정: 앱 역할에 Threads Tester 추가 → **발행계정 본인으로 threads.net 설정→웹사이트 권한→초대 탭에서 'Axis' 글자 클릭해 수락**(삭제버튼=거절) → 콘솔 하드새로고침 → 토큰 생성
- `THREADS_USER_ID`(숫자, `/me`로 획득) + `THREADS_ACCESS_TOKEN`(60일, ~2026-08-25 만료, refresh 필요). 값=`API_KEYS.local.txt` 11번. GCP Secret 등록 완료.

### 구현 (배포됨)
| 구성 | 파일 |
|------|------|
| 발행 클라이언트 | `utils/threads_client.py` (2단계 발행, **httpx UTF-8**, 재시도, is_enabled/publish_text/get_me/refresh_token) |
| 발행 라우트 | `POST /api/admin/marketing/drafts/{id}/publish`(발행 전 `filter_forbidden` 재검증→status=published+permalink), `GET /publish-status` |
| 발행 버튼 | 검수 카드 🚀발행 (publish_status=enabled일 때) |

> ⚠️ **한글 발행은 반드시 Python httpx(UTF-8)** — Windows Git Bash로 `curl --data-urlencode "text=한글"` 하면 깨짐. ⚠️ Threads API는 **글 삭제 미지원**(테스트글은 앱에서 수동삭제).

---

## 6. 일일 콘텐츠 엔진 — 새벽 미국시장 브리핑 + 양쪽관점 (✅ 배포)

매일 자동으로 2종 생성 → 검수 큐 → 🚀발행. Cloud Run Job `axis-threads-daily` + 스케줄러 **평일 07:30 KST**. `jobs/daily_threads_content.py`.

### 🌙 새벽 미국시장 브리핑 (`agents/briefing.py`, **Sonnet**)
- **지수**: FinanceDataReader로 S&P500/나스닥/다우/필라델피아반도체(SOXX)/VIX/원달러 종가·등락
- **왜(분석)+근거**: `utils/news_rss.fetch_overnight_us_news()`(Google News RSS '뉴욕증시'/'나스닥 반도체')에서 등락 원인 헤드라인을 받아, **①무슨일 ②왜(구체적 촉발요인 — "매도세/투심위축" 동어반복 금지) ③근거(출처/사실)** 구조로 작성
- **환각 금지**: 원인은 **제공된 헤드라인 안에서만** 도출, 근거 없으면 추측 X. 순한국어. ~25원/건.
- (예) 반도체 -4.7% → "오픈AI IPO 연기설로 AI·기술주 투심 위축 + 마이크론 실적 경계감"

### 📊 양쪽관점 종목글 = 기존 `marketer.contrarian` 재활용 (Haiku ~5원)

### 운영 모드
- 기본 = **검수 큐**(생성만, 발행 X) → `/admin/marketing`에서 보고 🚀발행
- 완전 자동발행 전환 = 잡 args에 `--publish` 추가(`deploy-threads-job.sh`)
- 하루 비용 ≈ 브리핑 25원 + 종목글 10원 = **~35원**

---

## 7. 채널 구조 + Threads 프로필

### 채널 (2개 사이트가 역할 분담, Threads가 허브)
- 🌙 **StockBizView** (stockbizview.com) = **시황분석** ← 브리핑 글이 연결
- 📈 **Axis** (axislytics.com) = **종목분석** ← 양쪽관점 종목글이 연결
- Threads `@axislystics` = 두 채널 먹여주는 콘텐츠 허브

### 프로필 (확정 2026-06-27) — Threads API로 수정 불가, 수동 입력
- **이름**(프로필 상단 노출): `Axis · 데이터로 읽는 투자 기준`
- **사용자이름/핸들**(게시글마다 노출): `axislystics` → 오타처럼 보이고 도메인 불일치, **`axislytics`로 변경 권장**
- **소개(bio)** — 방어/면책 톤 금지(자신감):
  ```
  새벽 미국장 정리부터 화제 종목까지, 매일.
  강점만 보면 물리기 쉽죠. 약점도 같이.
  🌙 시황 · 📈 종목분석 ↓
  ```
- **로고**: 실제 폰트(Century Gothic Bold) 'axis' 소문자 워드마크 + 민트 축라인. `바탕화면\axis_logo\axis_avatar.png`(다크·원형크롭 안전) + light/transparent. (※ Pillow 손그림 도형은 아마추어 → 실폰트 워드마크가 정답)
- **링크**: Threads 멀티링크(최대 5, 제목만 노출·URL 숨김). 시황=StockBizView, 종목=Axis. 웹은 저장 버그 잦음 → **모바일 앱 권장**.

> 전환 추적: **UTM 캡처 로직은 미구현**(URL에 utm 붙여도 무시됨). 클릭수는 **Threads 자체 링크 분석**으로 확인. 가입 귀속이 필요해지면 그때 캡처 구현.

---

## 8. 알려진 한계 / 메모
- Haiku 특성상 가끔 어색한 표현 발생 → 검수 탭에서 수정. (브리핑은 Sonnet이라 품질↑)
- 스냅샷 미적재 환경(서버 밖·종목 미보유)에선 수치 없는 일반론 글이 나옴 → 로컬은 `prime_name_store`로 해결.
- 토큰 60일 만료(~2026-08-25) 전 refresh 필요 — 자동 갱신 Job은 후속.
- 관련 문서: [THREADS_PUBLISHING.md](THREADS_PUBLISHING.md)(토큰 발급), [LEGAL.md](LEGAL.md)(절대 원칙), [UNIT_ECONOMICS.md](UNIT_ECONOMICS.md)(비용), [PROGRESS.md](PROGRESS.md).
