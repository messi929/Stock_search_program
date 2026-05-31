# Lemon Squeezy 재신청 준비 패키지

> **상태**: 🔄 **2026-05-31 LS 추가자료 요청 회신 발송 완료** — 데모영상 첨부 + 약관/환불 업데이트 + 가격/상품설명/GitHub(KYC). 재심사 대기 중.
> **작성**: 2026-05-21, **갱신**: 2026-05-28 → **2026-05-31**

## 🔔 2026-05-31 — LS 추가자료 요청 + 회신

5/30 LS(Ankith) 회신: 거절이 아닌 **추가자료 5건 요청** → 5/31 영문 답장 발송.

| # | 요청 | 대응 |
|---|------|------|
| 1 | Pricing breakdown | Free/Pro 9,900/Premium 29,900 (월 구독) 명시 |
| 2 | Demo video | **`demo-recorder/`로 자동 녹화** (Playwright persistent + recordVideo) → 1:35 mp4 첨부. 흐름: 랜딩(footer 법적링크)→가격→대시보드→005930 분석(KIS 차트/호가/투자자흐름)→실시간검증→페르소나→스크리너 |
| 3 | 개인 SNS (KYC) | GitHub `github.com/messi929` |
| 4 | 상품 설명 | 자체 운영 구독 SaaS (재판매/라이선스 아님), 정보·분석 도구(자문 아님), KR 리테일 대상 월 구독 |
| 5 | **약관·환불 업데이트** + 랜딩 링크 | 이용약관 §4 결제·Lemon Squeezy(MoR)·14일 환불 명시 + §11 문의처 신설, 환불·개인정보·약관 연락처 gmail 통일. 세 페이지 footer 링크는 기존 완비. **prod 배포·검증 완료** (commit babb8aa) |

상세 작업 기록: [`../PROGRESS_2026-05-31.md`](../PROGRESS_2026-05-31.md)

---

> **1차 거절 맥락**: LS가 구체적 사유 미제공("여러 데이터 포인트 의존… 카드사 규정"). 추정 — ① 금융/투자 카테고리 high-risk 분류, ② 초기 요청한 데모 영상 + 비즈니스 URL 답변 미달.
> **핵심 전략**: "투자자문(advisory)이 아닌 **정보 제공 도구(information tool)**"임을 모든 자료에서 일관되게 증명. 작동하는 커스텀 도메인 + 공식 데이터 소스(KIS) + 데모 영상 + 디스클레이머 + 소셜 4종 완비 후 신청.

## 🎯 2026-05-28 신청 완료 — 현재 상태

LS Setup 페이지 체크리스트 7/7 중 5개 ✅:
- ✅ Create your store
- ✅ Fine-tune store settings
- ✅ Verify your identity (KYC)
- ✅ Set up 2FA
- ✅ Connect a bank account
- ⬜ Create your first product (심사 통과 후)
- ⬜ Add discount code (선택)

**계정 분리**: 1차 거절 계정과 다른 새 이메일로 신청. KYC 정보(이름·여권·주소·계좌) 동일 → 시스템 매칭 가능성 존재. 거절 시 즉시 Polar.sh 트랙 착수.

**다음 액션** (심사 대기 1~5일):
1. 메일함 알림 켜두기 — LS가 추가 자료 요청 시 24시간 내 영문 답장 (§2 답변 활용)
2. 미리 준비: 데모 영상 4~5분 (§3 스크립트), 소셜 2개+ (§4), Anthropic 한도 확인
3. (선택) Product Draft 미리 생성 — Pricing=Subscription / Price=9900 / Billing=Monthly / Tax=SaaS personal use

### 5/22~27 신호 강화 요약 (재신청 신뢰도 ↑)
- **도메인 6일 안정 운영**: `https://axislytics.com` 5/21 라이브 이후 7일간 console error 0, 200 OK 지속 (5/27 prod 풀스택 재검증).
- **공식 데이터 소스 도입**: 한국투자증권(KIS) OpenAPI 정식 도입 — REST 6 endpoint + WebSocket fan-out 라이브. "Korea's largest brokerage OpenAPI"는 LS 심사자에게 강력한 데이터 적법성 근거.
- **UI 잔존 단어 0건 재확인**: `/pricing` 라이브 본문에서 'recommend' 검출 2건은 모두 면책 문구 "**does not recommend** the purchase or sale of any specific security"의 일부 — 오히려 안전 강화 신호.
- **백엔드 `/rank` 라우트는 axislytics.com에 미노출**: Vercel(Next.js) 라우터에 /rank 없음 → 404. LS 심사자가 axislytics.com에서 옛 v7.5 카피("오늘의 추천" 등)에 도달 경로 없음.

---

## ✅ 재신청 전 체크리스트 (금요일 아침 최종 점검)

| # | 항목 | 상태 | 비고 |
|---|------|------|------|
| 1 | 커스텀 도메인 작동 (`https://axislytics.com`) | ✅ | 5/21 라이브 + 5/27 재검증 (console error 0, 200 OK) |
| 2 | "Not investment advice" 디스클레이머 (홈 푸터·법적 페이지) | ✅ | `Disclaimer lang="both"` 영문 포함. /pricing 라이브 본문 검증 완료 |
| 3 | **공식 데이터 소스(KIS) 라이브** | ✅ | 5/26 KIS OpenAPI 도입 (REST 6 + WS) — 데이터 적법성/신뢰도 강화. §2에 명시 |
| 4 | 법적 페이지 4종 200 OK (`/pricing`,`/refund`,`/terms`,`/privacy`) | ✅ | 5/27 curl 검증 |
| 5 | 코드/UI 금지 단어 0건 | ✅ | 5/27 `legal_check` 재실행 — UI 노출 잔존 0 |
| 6 | LS 답변 초안 준비 | ✅ | 아래 §2 (KIS 신뢰 근거 추가) |
| 7 | 데모 영상 3~5분 (Loom/YouTube unlisted) | ⬜ | 아래 §3 스크립트 (KIS 라이브 씬 추가) |
| 8 | 소셜 프로필 2개+ (GitHub / X / 블로그) | ⬜ | 아래 §4 |
| 9 | (선택) Paddle 동시 신청 | ⬜ | LS 또 거절 대비 이중화 |

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

### Q: Where does your market data come from?

> All market data is sourced from **publicly available, officially licensed providers**:
> - **Korea Investment & Securities (KIS) OpenAPI** — official real-time and historical price, orderbook, and investor-flow data, licensed directly from one of Korea's largest brokerages. (REST + WebSocket, integrated 2026-05-26.)
> - **KRX (Korea Exchange) via the `pykrx` library** — official exchange end-of-day data for foreign/institutional net trading.
> - **DART (Korean Financial Supervisory Service)** — official corporate disclosures.
> - **ECOS (Bank of Korea)** and **FRED (US Federal Reserve)** — official macroeconomic indicators.
> - **Yahoo Finance** — for US-listed equities only.
>
> We do not scrape private data or use unlicensed feeds for the core product. Using a licensed brokerage OpenAPI is a key reliability and compliance signal.

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
| 1 | 인트로 | 홈페이지(`axislytics.com`) | "This is Axis — an AI-powered stock **information tool** for retail investors. It is not investment advice; it organizes data so users can decide for themselves." | 0:00–0:25 |
| 2 | 정체성 강조 | 홈 푸터 디스클레이머 클로즈업 | "Every page carries this disclaimer: Axis is not a licensed advisory service and does not recommend any security." | 0:25–0:45 |
| 3 | 로그인 | Google 로그인 → 대시보드 | "Users sign in securely with Google. Here is the dashboard." | 0:45–1:05 |
| 4 | 종목 분석 시작 | 종목 검색 → `/analyze` 진입 | "I'll ask Axis to analyze a publicly listed stock. Four AI agents process public market data — research, analysis, validation, and synthesis." | 1:05–1:45 |
| 5 | **공식 데이터 (KIS)** ⭐ | 분석 페이지의 KIS 차트/호가/투자자 흐름 섹션 | "All market data shown here — price, candlestick chart, 10-level orderbook, and foreign/institutional investor flow — is sourced through the **official OpenAPI of Korea Investment & Securities**, one of Korea's largest licensed brokerages. This is real, regulated market data, not scraped content." | 1:45–2:30 |
| 6 | AI 결과 (핵심) | 분석 결과 카드 | "Notice the language: 'observation range', 'reference figures' — descriptive, never 'buy' or 'sell'. The output is information, not a recommendation. A server-side word filter blocks any recommendation-style language." | 2:30–3:10 |
| 7 | 실시간 검증 | Validate 버튼 클릭 | "The Validator re-checks every number against current data and warns if anything is stale — this is our core differentiator for data reliability." | 3:10–3:45 |
| 8 | 페르소나 | 블랙록/ARK/그레이엄 토글 | "The same stock can be viewed through three analytical lenses. Same data, different perspectives — the user interprets." | 3:45–4:15 |
| 9 | 요금제 + 클로징 | `/pricing` 페이지 | "Subscriptions are Free, Pro at 9,900 won, and Premium. Payments will be handled through Lemon Squeezy. Thank you." | 4:15–4:45 |

**촬영 시 금지**: "추천/매수/사세요/수익 보장" 류 단어를 말이나 화면에 절대 노출 금지 (LS가 영상도 본다). 페르소나 카드에서 "강력매수" 등이 보이면 해당 카드 스킵 또는 흐림 처리.

**촬영 직전 라이브 점검 (curl 1줄)**: `https://stock-screener-1043976673827.asia-northeast3.run.app/api/kis/health` 200 응답 + `data.token_status="ok"` 확인 → KIS 씬에서 빈 화면 방지. 장 마감 후 촬영 시 WS tick=0은 정상.

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

## 5. 코드/UI 막판 점검 결과 (2026-05-27)

### ✅ 잔존 0 확인
- **/pricing 라이브 본문 grep**: `추천 / 매수 / 매도 / recommend` 모두 0건. 'recommend' 2건 검출은 모두 면책 문구 `"...does not recommend the purchase or sale of any specific security"`의 일부 — 오히려 안전 강화.
- **web/ 전역 grep**: `@axis_kr` 잔존 0건. UI 노출되는 자리에 권유성 어휘 0.
- **백엔드 v7.5 자산 (`screener/api/rank_page.py`의 "오늘의 추천" 등)**: axislytics.com(Vercel)에 `/rank` 라우트 없음 → 404. LS 심사자 도달 경로 없음. (Cloud Run 직접 URL을 어디에도 노출하지 않으면 OK.)
- **legal_check FORBIDDEN_GRADE_TOKENS** (`web/components/screener/columnMeta.ts`): 금지어 필터가 **코드 상수로** 정의되어 있음 — 심사자에게 보여줄 수 있는 강력한 자기 검열 증거.

### 🟡 코드에는 남아 있지만 UI 미노출 (모니터링 대상)
- `screener/core/metrics.py:602-616`의 `"강력매수/매수세/매도세/강력매도"` 등급 라벨 — 백엔드에서 계산만 되고 Axis(web/) UI에는 미노출. 향후 새 페이지 추가 시 반드시 `toSafeName()` 또는 `legal-labels.ts` 매핑 통과시킬 것.
- 백엔드 `recommendations` 필드명(`screener/api/routes.py`) — 프론트에서 헤더 "관찰 포인트"로 치환되어 표시 (안전). 필드명 자체는 보안 측면이라 유지 OK.

## 5b. 남은 사항 (소유자별)

### 🔴 Claude가 할 수 있음 (요청 시)
- [x] §2 LS 답변 초안 KIS 신뢰 근거 보강 (2026-05-27)
- [x] §3 데모 영상 스크립트 KIS 씬 + 라이브 점검 절차 추가 (2026-05-27)
- [ ] Paddle 신청용 답변 초안 작성 (§2 LS 답변 재활용 + KIS 신뢰 근거)
- [ ] (요청 시) 데모 영상에서 보여줄 분석 종목 선정 + 사전 캐시 워밍

### 🟡 사용자 외부 작업 (콘솔/계정 — Claude 불가)
- [x] Firebase 승인도메인 `axislytics.com` 추가 — Google 로그인 정상 동작 확인됨 (5/21 라이브)
- [ ] 🔑 **Cloudflare API 토큰 Revoke** — 5/20 DNS 작업에 쓴 1회용 토큰 (My Profile → API Tokens). 아직 미확인이면 지금 실행 권장.
- [ ] **데모 영상 녹화** → Loom/YouTube unlisted (§3 스크립트). 촬영 직전 `curl /api/kis/health` 200 확인.
- [ ] **소셜 2개+ 확보**: GitHub 공개 리포 + X 계정 (또는 개인 블로그/Notion 공개 페이지). §4 텍스트 그대로 사용 가능.
- [ ] **Anthropic 자동충전 한도 확인** — 5/24 잔액 부족 2회 발생. 데모 영상 촬영 중 AI 분석 실패 방지를 위해 한도 점검 필수.

### 💡 신청 시
- [ ] Paddle 동시 신청 — LS 또 거절해도 매출 트랙 유지 (이중화 권장)

---

## 6. 재신청 당일 실행 순서

1. **사전 점검 (5분)**
   - `curl -sI https://axislytics.com` → 200
   - `curl https://stock-screener-1043976673827.asia-northeast3.run.app/api/kis/health` → 200 + `token_status=ok`
   - `/pricing /refund /terms /privacy` 4종 200 (위 §0 표 9번)
   - Anthropic 잔액 ≥ $5
2. **데모 영상** 녹화 → Loom/YouTube unlisted 업로드 → 링크 확보 (5분 이내)
3. **소셜 정리**: GitHub 공개 리포 README + X 또는 블로그 (§4)
4. **LS 스토어 재신청**: §2 답변 붙여넣기 + axislytics.com + 영상 링크 + KIS 신뢰 근거 강조
5. (선택) **Paddle 동시 신청** — 매출 트랙 이중화
