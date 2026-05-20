# Lemon Squeezy 재신청 준비 패키지

> **목표일**: 2026-05-22 (금) 재신청
> **작성**: 2026-05-21
> **1차 거절 맥락**: LS가 구체적 사유 미제공("여러 데이터 포인트 의존… 카드사 규정"). 추정 — ① 금융/투자 카테고리 high-risk 분류, ② 초기 요청한 데모 영상 + 비즈니스 URL 답변 미달.
> **핵심 전략**: "투자자문(advisory)이 아닌 **정보 제공 도구(information tool)**"임을 모든 자료에서 일관되게 증명. 작동하는 커스텀 도메인 + 데모 영상 + 디스클레이머 + 소셜 4종 완비 후 신청.

---

## ✅ 재신청 전 체크리스트 (금요일 아침 최종 점검)

| # | 항목 | 상태 | 비고 |
|---|------|------|------|
| 1 | 커스텀 도메인 작동 (`https://axislytics.com`) | ✅ | 2026-05-21 라이브 (HTTP 200, Next.js 렌더). SSL 자동발급 멈춤 → `vercel certs issue`로 해결 |
| 2 | "Not investment advice" 디스클레이머 (홈 푸터·법적 페이지) | ✅ | `Disclaimer lang="both"` 영문 포함 |
| 3 | 데모 영상 3~5분 (Loom/YouTube unlisted) | ⬜ | 아래 §3 스크립트 |
| 4 | 소셜 프로필 2개+ (GitHub / X / 블로그) | ⬜ | 아래 §4 |
| 5 | 환불정책 페이지 (`/refund`) 접근 가능 | ✅ | 7일 이내 |
| 6 | LS 답변 초안 준비 | ✅ | 아래 §2 |
| 7 | (선택) Paddle 동시 신청 | ⬜ | LS 또 거절 대비 이중화 |

---

## 1. 서비스 한 줄 정의 (모든 자료 공통 — 영문)

> **Axis is an AI-powered stock *analysis and information* tool for retail investors in Korea. It organizes market data and presents multi-perspective analysis. It does NOT provide investment advice, recommendations, or buy/sell signals — all decisions are left to the user.**

한국어:
> Axis는 한국 개인 투자자를 위한 AI 기반 주식 **분석·정보 제공** 도구입니다. 시장 데이터를 정리하고 다각도 분석을 제시하며, 투자 자문·종목 추천·매매 신호를 제공하지 않습니다. 모든 판단은 사용자 몫입니다.

**왜 이 문장이 중요한가**: LS/카드사가 가장 경계하는 건 "financial advisory / signals / guaranteed returns". "information tool"로 포지셔닝하면 카테고리 리스크를 낮춘다. 1차 거절의 추정 사유를 정면으로 무력화.

---

## 2. LS 신청 폼 / 후속 이메일 답변 초안 (영문)

LS는 신규 스토어에 "무엇을 파는지 / 어떻게 작동하는지 / 비즈니스 모델 / 작동하는 URL"을 묻는다. 아래를 그대로 붙여넣거나 약간 다듬어 사용.

### Q: What does your business sell? / What is your product?

> Axis is a subscription-based SaaS web application that provides AI-assisted stock market **analysis and data organization** for individual retail investors in South Korea.
>
> The product does **not** sell financial advice, trading signals, or managed portfolios. It is an information and research tool — comparable to a financial data dashboard or charting service. Users read AI-generated analysis of publicly available market data and make their own independent decisions.
>
> Subscription tiers:
> - **Free** — 0 KRW: limited monthly analyses, 5 watchlist items
> - **Pro** — 9,900 KRW/month: unlimited analyses, 30 watchlist items, all features
> - **Premium** — 29,900 KRW/month (launching later): weekly PDF reports, priority queue

### Q: How does the product work?

> 1. The user logs in (Google OAuth via Firebase) and asks about a publicly listed stock.
> 2. Four AI agents (built on Anthropic's Claude API) process publicly available market data: a Research agent gathers context, an Analyst interprets fundamentals/technicals, a Validator re-checks every figure against current data, and a Strategist synthesizes the findings.
> 3. The output is presented as **neutral, descriptive analysis** ("observation range", "reference figures") with a mandatory disclaimer. No "buy/sell" language is used — this is enforced both in the AI prompts and by an automated server-side word filter.
> 4. Users can save stocks to a watchlist and view the same data through three analytical "lenses" (risk-focused, growth-focused, value-focused).

### Q: Is this regulated financial advice?

> No. Axis is explicitly an information-provision tool, not a licensed investment advisory service. Under Korean law (Financial Investment Services and Capital Markets Act), we provide objective data organization to all users identically — no individualized advice, no return guarantees, no buy/sell recommendations. Every page and every AI response carries a disclaimer stating that the service is not investment advice and that all decisions are the user's responsibility. We enforce a forbidden-word filter in code to prevent any recommendation-style language.

### Q: Business / website URL

> https://axislytics.com  (live demo + full product)
> Demo video: [Loom/YouTube link — §3]

### Q: Refund policy

> Full refund within 7 days of purchase for low-usage accounts. Published at https://axislytics.com/refund

---

## 3. 데모 영상 스크립트 (3~5분)

**형식 권장**: 화면 녹화(한국어 UI) + **영어 자막 또는 영어 음성 내레이션** (LS 심사자는 영어권). Loom 또는 YouTube *unlisted*. 깔끔한 1테이크.

**촬영 전 준비**: `https://axislytics.com` 접속 가능 상태(SSL 완료) + 테스트 계정 로그인 + 분석할 종목 1개(예: 삼성전자) 미리 정함.

| # | 씬 | 화면 | 내레이션 (영문 — 자막/음성) | 시간 |
|---|-----|------|------------------------------|------|
| 1 | 인트로 | 홈페이지(`axislytics.com`) | "This is Axis — an AI-powered stock **information tool** for retail investors. It is not investment advice; it organizes data so users can decide for themselves." | 0:00–0:30 |
| 2 | 정체성 강조 | 홈 푸터 디스클레이머 클로즈업 | "Every page carries this disclaimer: Axis is not a licensed advisory service and does not recommend any security." | 0:30–0:50 |
| 3 | 로그인 | Google 로그인 → 대시보드 | "Users sign in securely with Google. Here is the dashboard." | 0:50–1:15 |
| 4 | 종목 분석 | 종목 검색 → `/analyze` 분석 진행 | "I'll ask Axis to analyze a publicly listed stock. Four AI agents process public market data — research, analysis, validation, and synthesis." | 1:15–2:15 |
| 5 | 결과 (핵심) | 분석 결과 카드 | "Notice the language: 'observation range', 'reference figures' — descriptive, never 'buy' or 'sell'. The output is information, not a recommendation." | 2:15–3:00 |
| 6 | 실시간 검증 | Validate 버튼 클릭 | "The Validator re-checks every number against current data and warns if anything is stale — this is our core differentiator for data reliability." | 3:00–3:40 |
| 7 | 페르소나 | 블랙록/ARK/그레이엄 토글 | "The same stock can be viewed through three analytical lenses. Same data, different perspectives — the user interprets." | 3:40–4:15 |
| 8 | 요금제 + 클로징 | `/pricing` 페이지 | "Subscriptions are Free, Pro at 9,900 won, and Premium. Payments will be handled through Lemon Squeezy. Thank you." | 4:15–4:45 |

**촬영 시 금지**: "추천/매수/사세요/수익 보장" 류 단어를 말이나 화면에 절대 노출 금지 (LS가 영상도 본다).

---

## 4. 소셜 프로필 텍스트 (최소 2개 확보)

### A. GitHub (가장 빠름 — 공개 리포 1개면 충분)
- 리포 소개(About) 한 줄:
  > Axis — AI-powered stock analysis & information tool for retail investors. Not investment advice.
- README 상단 배지 + 위 §1 한 줄 정의 + 스크린샷 1~2장 + `https://axislytics.com` 링크.

### B. X (Twitter) — `@axis_kr` (홈에서 이미 언급 중 → 실제 생성 필요)
- Bio (160자):
  > AI stock analysis & information tool for KR retail investors 🇰🇷 | Multi-agent analysis + real-time data validation | Not investment advice | axislytics.com
- 핀 트윗: 제품 한 줄 소개 + 데모 영상 링크.

### C. (선택) 개인 블로그 / Notion 공개 페이지
- "Axis를 만든 이유" 1편 — 정보 제공 도구 정체성 서술.

> **LS 관점**: 소셜은 "실재하는 사업체"임을 증명하는 신뢰 신호. GitHub 공개 리포 + X 계정이면 2개 충족.

---

## 5. 주의 / 정리할 점

### ✅ 코드 수정 완료 (2026-05-21)
- **`/pricing` "추천" 배지 → "인기"** (`web/app/pricing/page.tsx`) — 종목 추천 오해 소지 제거. legal_check 98파일 0건 재확인.
- **홈 `@axis_kr` 문구 제거** (`web/app/page.tsx`) — 빈 X 계정 노출 방지. "오픈되면 순차 안내 이메일" 중립 문구로 교체. (X 계정 생성 후 되살리려면 베타 섹션 fallback 문구 복원.)
- ✅ 디스클레이머·환불·약관·개인정보 페이지는 이미 완비.

> ⚠️ 위 코드 수정은 아직 **Vercel 배포 전** — 금요일 전 `git push`(자동 배포) 또는 `vercel --prod` 필요. 안 하면 라이브 사이트에는 옛 카피가 보임.

## 5b. 남은 사항 (소유자별)

### 🔴 Claude가 할 수 있음 (요청 시)
- [ ] 위 코드 수정 사항 **Vercel production 배포** (빌드/배포)
- [ ] Paddle 신청용 답변 초안 작성 (§2 LS 답변 재활용)

### 🟡 사용자 외부 작업 (콘솔/계정 — Claude 불가)
- [ ] **Firebase 승인도메인에 `axislytics.com` 추가** 🔴최우선 — 안 하면 도메인에서 Google 로그인 불가 → 데모 영상 촬영 불가. (Firebase Console → Authentication → Settings → Authorized domains)
- [ ] 🔑 **Cloudflare API 토큰 Revoke** — 어제 DNS 작업에 쓴 1회용 토큰 (My Profile → API Tokens)
- [ ] **데모 영상 녹화** → Loom/YouTube unlisted (§3 스크립트)
- [ ] **소셜 2개+ 확보**: GitHub 공개 리포 + X `@axis_kr` 생성 (§4 텍스트)
- [ ] (선택) Vercel/Cloud Run `FRONTEND_URL`·`NEXT_PUBLIC_API_BASE_URL`이 새 도메인 반영하는지 점검

### 💡 신청 시
- [ ] Paddle 동시 신청 — LS 또 거절해도 매출 트랙 유지 (이중화 권장)

---

## 6. 금요일 실행 순서

1. `https://axislytics.com` 접속 확인 (SSL OK)
2. 데모 영상 녹화 → Loom/YouTube unlisted 업로드 → 링크 확보
3. GitHub 공개 리포 + X 계정 정리 (§4)
4. `/pricing` "추천" 배지 + `@axis_kr` 문구 점검 (§5)
5. LS 스토어 재신청 → §2 답변 붙여넣기 + 도메인 + 영상 링크 제출
6. (선택) Paddle 신청 병행
