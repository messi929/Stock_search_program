# Axis 다음 할 일 (Week 6 + 미해결 항목)

> **작성**: 2026-04-26 (Week 5 종료 시점)
> **참조**: `docs/axis/PROGRESS.md` (Week 1~5 진척), `docs/axis/ROADMAP.md` (원본 6주 일정)

---

## 🔥 우선순위 — 사용자 작업 (선결)

| # | 작업 | 예상 시간 | 비용 |
|---|------|----------|------|
| 1 | `web/.env.local` Firebase 값 채움 — `MESSAGING_SENDER_ID`, `APP_ID` (Firebase 콘솔 → 프로젝트 설정 → "내 앱"에서 확인) | 5분 | 0원 |
| 2 | axis-staging 재배포 (W3 D4 + W4-5 백엔드 변경 반영) | 5-10분 | 0원 |
| 3 | (선택) Vercel 배포 — Next.js 프론트 외부 노출, `axis.kr` 또는 `allofasset.com` 도메인 연결 | 30분 | $0 (Hobby) |

### 재배포 명령어 (참고)
```bash
gcloud run deploy axis-staging \
  --source=. \
  --region=asia-northeast3 \
  --project=all-of-asset \
  --update-secrets="ANTHROPIC_API_KEY=anthropic-api-key:latest,FIREBASE_CREDENTIALS=firebase-key:latest" \
  --set-env-vars="RUN_MODE=server,COLLECT_MODE=readonly,AUTH_ENABLED=true,FIREBASE_PROJECT_ID=stock-search-program,FIREBASE_WEB_API_KEY=AIzaSyDIAvNnqr4_RAB7AkLbhNdHJ9yKycoYiz4,ADMIN_EMAILS=messi929@naver.com"
```

---

## 🛡️ 빈 LEGAL/정책 항목 (Week 6 Day 4 일괄 처리)

### A. API 응답 자동 필터링 미적용
**현재**: `BaseAgent.filter_forbidden()` 메서드 존재하지만 자동 호출 X. 시스템 프롬프트에 의존.
**해결**: `api/routes/ai.py`의 응답 빌더에 자동 후처리 추가
- `_build_full_response()` (analyze) — 모든 string 필드 traversal + filter
- `discover` 응답 — 동일
- `validate` 응답 — Contrarian/blind_spots 필터
**예상 작업량**: 1시간

### B. `scripts/legal_check.py` 미구현
**LEGAL.md 명시**: 배포 전 코드/문서에서 금지 단어 자동 검출하여 CI 차단.
**해결**: 신규 작성 — `agents/`, `personas/`, `api/`, `web/app/`, `web/components/` 검색.
- 시스템 프롬프트 안의 "금지 단어 리스트 자체"는 화이트리스트 처리 (정의 vs 사용 구분)
- 실패 시 exit 1
**예상 작업량**: 30분

### C. `/terms`, `/privacy` 페이지 누락
**현재**: 랜딩 footer에 링크 있지만 페이지 없음 → 404.
**해결**: `web/app/terms/page.tsx`, `web/app/privacy/page.tsx` 작성
- 내용은 `docs/axis/LEGAL.md`의 "이용약관 핵심 조항" + "개인정보 처리방침 핵심" 활용
- v7.5 main 브랜치에 이미 같은 라우트 존재할 가능성 → 백엔드 라우트 충돌 체크 필요
**예상 작업량**: 1시간

### D. 카카오 OAuth 미구현
**현재**: 로그인 페이지에 "준비 중" 비활성 버튼.
**해결**: 두 가지 경로
1. 비활성 유지 + Google만 (베타 단계 충분)
2. Firebase Custom Token + 카카오 REST API 연동 (별도 백엔드 라우트 + frontend 처리)
**예상 작업량**: 1번은 0분, 2번은 4-6시간
**추천**: 베타에서는 1번 유지. 정식 런칭 시 2번 검토.

---

## 📅 Week 6 (베타 런칭)

### Day 1 — `/screener/[id]` 결과 페이지
- 동적 라우트 + Next.js 16 `params Promise`
- `/api/scan?category={id}` (v7.5) 호출하여 종목 리스트 표시
- 컬럼 표시는 `SmartListCategory.columns` 따라 동적
- 종목 클릭 → `/analyze/{ticker}` 이동
- Pro 카테고리 접근 시 `402` → /pricing 안내

### Day 2 — 커스텀 스크리너 (Pro)
- `/screener/custom` 페이지 (가이드: pages.md 461줄)
- 조건 빌더 UI (PER 범위, RSI, 외국인 연속매수 등)
- 저장 → Firestore `users/{uid}/custom_screeners/{id}`
- 신규 백엔드 라우트 필요: `POST/GET /api/ai/screeners/custom`

### Day 3 — 알림 시스템
**Day 3 MVP 진행 (W6 D3)**: 사용자 토글 UI(`/settings/notifications`) + 백엔드 저장만 완료. Opt-in 미리 수집 → v1.1에서 발송 시스템 켜면 즉시 발송.

**🔮 v1.1 이관 (Day 3 풀 구현)**:
- **Mailgun 발송 통합**
  - `MAILGUN_API_KEY`, `MAILGUN_DOMAIN` Cloud Run secret 등록
  - `utils/mailgun_client.py` — 템플릿 발송 래퍼 (HTML/Text 분기, 헤더 면책)
  - 인증 도메인 (axis.kr / allofasset.com) DNS SPF/DKIM 설정
- **일일 시황 브리핑 잡** (`jobs/daily_briefing.py`)
  - Cloud Run Job + Cloud Scheduler `0 22 * * *` (UTC = 07:00 KST)
  - Research Agent 1회 호출 → 결과 캐싱 → opt-in 사용자 모두에게 발송
  - 1일 1회 실행, 사용자 N명 = Haiku 9원 + Mailgun N건 (~$0.0008/건)
- **진입선 도달 알림 잡** (`jobs/entry_point_check.py`)
  - Cloud Run Job + Cloud Scheduler 매시간 (장중만 09-15 KST)
  - 모든 opt-in 사용자의 `users/{uid}/watchlist_meta` 스캔
  - 현재가 vs 저장된 tier_1/2/3 비교 → 도달 시 1회 발송 + `notified_at` 마킹 (중복 차단)
  - Claude 호출 0회 (순수 가격 비교)
- **카카오 비즈 알림톡** (한국 사용자 친화)
  - 사업자 등록 후 카카오톡 채널 개설 + 발신 프로필 등록
  - 알림톡 템플릿 심사 (1-2주, 권유성 단어 검수 필요)
  - REST API 연동: `utils/kakao_biz_client.py`
  - Mailgun과 채널 토글 (사용자가 둘 다 선택 가능)
- **개인화** (v1.2+)
  - 관심 종목별 페르소나 매칭 알림
  - 시황 브리핑에 사용자 보유 섹터 우선 노출

**작업량 추산**: Mailgun + 일일 시황 1.5h, 진입선 알림 1.5h, 카카오 비즈 4-6h (사업자 인증 별도)

### Day 4 — 법적 안전장치 sweep
- 위 [B] `scripts/legal_check.py` 구현 + CI 통합
- 위 [A] 백엔드 응답 자동 필터링
- 위 [C] `/terms`, `/privacy` 페이지
- 모든 분석 응답 직렬화 → grep "추천|사세요|매수 신호" 0건 확인
- E2E 시나리오 재실행

### Day 5 — 베타 런칭

**Day 5 코드 완료 (W6 D5)**:
- 랜딩 "Closed Beta" 배지 + Feature #4 v1.1 솔직 표시 + 베타 섹션
- /pricing 페이지 (3-tier + FAQ, 결제 placeholder)
- `NEXT_PUBLIC_BETA_FORM_URL` env 변수 → 외부 폼 임베드
- `docs/axis/BETA_GUIDE.md` — 테스터 안내문 (피드백 보상 포함)

**🔧 사용자 작업 (런칭 전 필수)**:
1. **베타 신청 폼 생성** — Google Forms / Tally / Notion 중 택1
   - 질문 권장: 이메일·이름·투자경력·관심 분야·어떤 점이 궁금한지
   - 생성 후 `web/.env.local`에 `NEXT_PUBLIC_BETA_FORM_URL` 입력
2. **Vercel production 배포**
   - `vercel link` → 프로젝트 연결
   - 환경 변수 등록: `NEXT_PUBLIC_FIREBASE_*`, `NEXT_PUBLIC_API_BASE_URL`, `NEXT_PUBLIC_BETA_FORM_URL`
   - `vercel --prod` 또는 GitHub 연동 자동 배포
3. **도메인 연결** — `axis.kr` 또는 `allofasset.com` (Cloudflare/Vercel)
4. **Cloud Run custom domain** (선택) — `api.axis.kr`로 백엔드 매핑
5. **Firebase Auth 도메인 화이트리스트** — Vercel 도메인 + custom 도메인 추가
6. **Anthropic API 잔액 확인** — 베타 100명 × 평균 5회 분석 = ~225,000원/월 예상
7. **모니터링**:
   - Cloud Logging (이미 활성)
   - (옵션) Sentry 프론트엔드 통합 — `@sentry/nextjs`
8. **공지** — X (`@axis_kr` 계정 생성), 투자 커뮤니티, 스레드

---

## 💸 비용 최적화 (Week 6 또는 v1.1 검토)

### 현재 1쿼리 비용 (실측)
- Strategist Opus 370원이 전체 비용의 80% 차지
- ROADMAP 추정 215원 vs 실측 453원 (2.1배)

### 검토할 최적화
1. **Strategist 응답 토큰 축소** — 현재 max_tokens 2560 + 출력 ~2200 토큰. 1500으로 줄이면 ~250원
2. **시스템 프롬프트 caching 효과** — Opus는 1024+ tokens부터 cache. 현재 cache_w 2834 → 다음 호출부터 cache_r 적용되어 input 90% 절감 (호출당 ~30원 절감)
3. **Discoverer 후보 80→40** — input 11,400 → 6,000 토큰. 호출당 70원 → ~50원
4. **Sonnet → Haiku 다운그레이드 검토** — Validator의 Contrarian만 Haiku로? 정밀도 trade-off
5. **Pro Tier 9,900원 vs 비용 검증** — 평균 사용량 50회/월 가정 시 22,650원 비용 → **현재 적자**. 토큰 최적화 필수.

### 손익분기 재검토
- Pro 20명 × 9,900 = 198,000원/월
- 현재 비용 ~22,650원/Pro × 20 = 453,000원/월 → **적자 -255,000원**
- 토큰 50% 절감 시 비용 ~11,300원 × 20 = 226,000원 → **여전히 적자 -28,000원**
- 결론: **Pro 가격 19,900원 또는 Premium tier 활성화 필요**

---

## 🔗 v7.5 main 브랜치 정합성 (머지 시점 결정)

머지 전 정리할 항목:

| v7.5 요소 | LEGAL 충돌 | 처리 옵션 |
|----------|-----------|----------|
| "🏆 오늘의 TOP 픽" 섹션 | 추천 리스트로 비춰질 위험 | "관찰 가치 종목" 으로 리네이밍 |
| "매수 포인트" 하이라이트 | "매수 신호" 직접 사용 | "관찰 시그널" 또는 "참고 구간" |
| `buy_grade="적극매수"/"매수"` 라벨 | "매수" 단어 | API 응답 시점에 score_tier로 변환 |
| 카테고리 이름 "급등 예보", "성장주 매수" | 권유성 어조 | "급등 관찰", "성장 관찰" 검토 |

→ **권장**: Week 6 법적 sweep 단계에서 `screener/api/routes.py` 응답 wrap 함수 추가하여 v7.5 자체는 그대로 두되 Axis-side에서 변환 후 노출.

---

## 🧪 미적용 검증 워크플로우 (계속 활용 권장)

이번 5주 동안 reviewer subagent로 20건 fix를 차단했음. Week 6에서도 유지:

- 백엔드 신규 라우트 작성 후 → reviewer로 패턴 일관성 검증
- frontend 신규 페이지 작성 후 → reviewer로 a11y/race/cost 검증
- 배포 직전 → reviewer로 LEGAL sweep + 누락 항목 검증

매 라운드 비용: ~0원 (general-purpose subagent + 토큰 cap 짧음)

---

## 📋 체크리스트 (다음 세션 시작 시)

- [ ] `web/.env.local` Firebase 값 입력 완료?
- [ ] axis-staging 재배포 완료? (curl `/api/ai/profile` 401 응답 확인)
- [ ] Anthropic 콘솔 잔액 ($10+ 권장)
- [ ] Week 6 Day 1부터 시작 (`/screener/[id]`)
- [ ] reviewer subagent 워크플로우 유지

---

**다음 세션 진입점**: `docs/axis/PROGRESS.md` 읽고 → `docs/axis/NEXT_STEPS.md` (이 문서) 읽고 → Week 6 Day 1 시작
