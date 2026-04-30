# Axis 다음 할 일 (Week 6 + 미해결 항목)

> **작성**: 2026-04-26 (Week 5 종료 시점)
> **갱신**: 2026-04-30 (라운드 1~3 워크스루 + fix 적용)
> **참조**: [PROGRESS.md](PROGRESS.md), [ROADMAP.md](ROADMAP.md), **[REDESIGN.md](REDESIGN.md)** ⭐ post-beta 분석 시간 단축 계획

---

## 🆕 2026-04-30 세션 결과 요약

### ✅ 완료된 것 (라운드 1~3)
- Vercel 프로덕션 배포 (`axis-web-five.vercel.app`)
- Cloud Run `axis-staging` 재배포 + revision 00008-mlw 라이브
- 관리자 권한 부여 (`wogus711929@gmail.com`을 ADMIN_EMAILS에 추가)
- 미인증 워크스루 7개 페이지 검증 완료
- 인증 워크스루 (Firebase 커스텀 토큰 + `window.__axis_auth` 우회)
- 발견된 P0 7건 + P1 4건 모두 fix:
  - `/analyze` 인덱스 페이지 신설 (검색 + 인기 종목 8)
  - 대시보드 NAV 4개 중 2개 404 → 모두 정상 라우트로 교체
  - `?next=` 파라미터로 로그인 후 원래 페이지 복귀 + open-redirect 차단
  - 한국어 404 페이지 (`web/app/not-found.tsx`)
  - 푸터 탭 타겟 17~20px → 44px
  - 로그인 약관 링크 클릭 가능
  - WatchlistPreview Free 5/Pro 30 자동 분기
  - LEGAL: 스크리너 카테고리 6건 권유성 표현 → 중립 변환 (`web/lib/legal-labels.ts`)
  - ValidateButton 라벨 분기 (분석 후/완료/검증 중)
  - 종목명 즉시 표시 (analyst 응답 전 useStockSearch fallback)
  - Strategist max_tokens 2560 → 1500
  - Discoverer 후보 80 → 40
- 도구: `scripts/_mint_admin_token.py` (Firebase 커스텀 토큰 발급)

### ⚠️ 측정 결과 (라운드 3)
- 분석 시간 84.74초 (fresh) / 60.07초 (캐시) — ROADMAP 5~10초 추정의 8~17배
- **근본 원인**: Validator가 critical path에 직렬로 끼어 있음 (Research+Analyst는 이미 병렬)
- **해결 계획**: [REDESIGN.md](REDESIGN.md) Option A (Validator 수동 분리, 84s → ~55s)

---

## 🔥 우선순위 — 사용자 작업 (선결)

| # | 작업 | 예상 시간 | 비용 |
|---|------|----------|------|
| 1 | ~~`web/.env.local` Firebase 값 채움~~ | ✅ 완료 | — |
| 2 | ~~axis-staging 재배포~~ | ✅ 완료 (revision 00008-mlw) | — |
| 3 | ~~Vercel 배포~~ | ✅ 완료 (`axis-web-five.vercel.app`) | — |
| 4 | **Tally / Google Forms 베타 신청 폼 생성 + `NEXT_PUBLIC_BETA_FORM_URL` 등록** | 10분 | 0원 |
| 5 | (선택) `axis.kr` 또는 `allofasset.com` 커스텀 도메인 연결 | 30분 | 도메인비 |
| 6 | Anthropic 콘솔 잔액 확인 (베타 100명 × 5회 ≈ 225,000원/월) | 1분 | — |

### axis-staging 재배포 (Buildpacks 회피)
**중요**: `gcloud run deploy --source=.`이 어쩐 일로 Buildpacks를 골라 web/(Next.js) 빌드 시도 → 실패하므로 분리 명령 사용:
```bash
# 1) Dockerfile로 명시 빌드
gcloud builds submit . \
  --tag asia-northeast3-docker.pkg.dev/all-of-asset/cloud-run-source-deploy/axis-staging/axis-staging:$(date +%Y%m%d-%H%M%S) \
  --region=asia-northeast3 --project=all-of-asset

# 2) deploy
gcloud run deploy axis-staging \
  --image=<위 builds submit가 출력한 IMAGES URL> \
  --region=asia-northeast3 --project=all-of-asset
```
TODO: `scripts/deploy-axis-staging.sh` 작성 ([REDESIGN.md §8.1](REDESIGN.md))

---

## 🛡️ 빈 LEGAL/정책 항목

### A. API 응답 자동 필터링 미적용 ⏳ 미해결
**현재**: `BaseAgent.filter_forbidden()` 메서드 존재하지만 자동 호출 X. 시스템 프롬프트에 의존.
**해결**: `api/routes/ai.py`의 응답 빌더에 자동 후처리 추가
- `_build_full_response()` (analyze) — 모든 string 필드 traversal + filter
- `discover` 응답 — 동일
- `validate` 응답 — Contrarian/blind_spots 필터
**예상 작업량**: 1시간 (REDESIGN.md §6.1)

### B. `scripts/legal_check.py` 미구현 ⏳ 미해결
**LEGAL.md 명시**: 배포 전 코드/문서에서 금지 단어 자동 검출하여 CI 차단.
**해결**: 신규 작성 — `agents/`, `personas/`, `api/`, `web/app/`, `web/components/` 검색.
- 시스템 프롬프트 안의 "금지 단어 리스트 자체"는 화이트리스트 처리 (정의 vs 사용 구분)
- 실패 시 exit 1
**예상 작업량**: 30분 (REDESIGN.md §6.2)

### C. `/terms`, `/privacy` 페이지 ✅ 완료
**상태**: Week 6에서 신규 작성 + 배포 완료. 라운드 1 워크스루에서 정상 렌더 확인.

### D. 카카오 OAuth 미구현 — 베타 skip (현행 유지)
**현재**: 로그인 페이지 "준비 중" 비활성 버튼.
**결정**: 베타 동안은 Google만. 정식 런칭 시 재검토.

### E. v7.5 카테고리 권유성 라벨 ✅ 부분 완료
**현재**: `web/lib/legal-labels.ts` 신설 — 스크리너 카테고리 6건 ("매수"/"추천") 중립 변환 완료.
**남은 부분**: `buy_grade="적극매수"/"매수"` API 응답 시점 변환 (REDESIGN.md §6.3)

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

## 💸 비용 최적화 — 진행 상황 + 남은 옵션

### 라운드 3에서 적용
- ✅ Strategist max_tokens 2560 → 1500
- ✅ Discoverer 후보 80 → 40
- ✅ 시스템 프롬프트 caching 이미 작동 중 (`utils/claude_client.py:198-208`)
- 결과: 분석 시간 91.92초 → 84.74초 (~8% 단축, 비용 효과는 다음 청구에서 확인)

### 남은 큰 옵션 (REDESIGN.md 참고)
1. **Validator를 critical path에서 분리** (REDESIGN.md Option A) — 시간 84s→55s + 호출 1회 절감 (~25원/쿼리)
2. **Strategist Opus → Sonnet 다운그레이드** (REDESIGN.md Option C) — 호출당 370원→50원 (~87% 절감), 품질 검증 필수
3. **Sonnet → Haiku 다운그레이드 검토** (Validator의 Contrarian만) — 정밀도 trade-off

### 손익분기 재검토 (라운드 3 시점)
- Pro 20명 × 9,900 = 198,000원/월
- 현재 비용 ~22,650원/Pro × 20 = 453,000원/월 → **적자 -255,000원**
- Option C(Sonnet) 채택 시 비용 ~150원/쿼리 × 50회 × 20명 = 150,000원/월 → **흑자 +48,000원**
- 결론: 베타 후 Option A·C 평가 필수, 가격 정책(Pro 19,900 / Premium 활성화)도 병행 검토

---

## 🔗 v7.5 main 브랜치 정합성 (머지 시점 결정)

머지 전 정리할 항목:

| v7.5 요소 | LEGAL 충돌 | 처리 상태 |
|----------|-----------|----------|
| "🏆 오늘의 TOP 픽" 섹션 | 추천 리스트로 비춰질 위험 | ⏳ 머지 시 "관찰 가치 종목" 리네이밍 |
| "매수 포인트" 하이라이트 | "매수 신호" 직접 사용 | ⏳ 머지 시 "관찰 시그널" 변환 |
| `buy_grade="적극매수"/"매수"` 라벨 | "매수" 단어 | ⏳ API 응답 wrap 함수 (REDESIGN.md §6.3) |
| 카테고리 이름 "급등 예보", "성장주 매수" | 권유성 어조 | ✅ Axis-side 변환 완료 (`web/lib/legal-labels.ts`) |

→ Axis 프론트는 변환 완료. v7.5 main 머지 시 백엔드 응답 wrap 추가 필요.

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
