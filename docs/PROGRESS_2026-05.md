# Axis 진행 기록 — 2026-05-21 ~ 2026-05-24

> 도메인 라이브부터 정식 오픈 + 사용성 안정화까지 4일간의 누적 작업과 남은 과제.
> 상세 커밋 메시지는 `git log --since="2026-05-21"` 참조.

---

## 0. 현재 production 상태 (2026-05-24 기준)

| 영역 | 상태 |
|---|---|
| 도메인 | `axislytics.com` 라이브 (Cloudflare Proxy + Cloud Run SNI 우회) |
| 로그인 | Firebase Google OAuth 정상 (프로젝트 `stock-search-program`) |
| 프론트 | Vercel `axis-web` (배포 `axis-6ptub1h27...` 등) |
| 백엔드 | Cloud Run `stock-screener-00041-qp4` (asia-northeast3, min-instances=1) |
| Cloud Run Jobs (6) | `axis-backfill-korea-supply`, `axis-daily-korea-collect`(16:30 KST), `axis-daily-macro`(06:00), `axis-daily-options`(06:30), `axis-weekly-events`(일 22:00), `axis-monthly-regime`(매월 1일 06:00) |
| 데이터 | KR 외국인/기관 수급 4 카테고리 2021-01-04 ~ 어제, ~6.5M docs (Korean Specialist 풀가동) |
| 결제 | LS 미연결(Pro CTA 작동 안 함) — 출시 차단 항목 |

---

## 1. 날짜별 완료 작업

### 2026-05-21 — 도메인 출시 + 정식 오픈 리뉴얼

| 영역 | 작업 | 커밋 |
|---|---|---|
| 도메인 | axislytics.com 라이브 확정 (SNI 우회 Origin Rules) + Firebase 승인도메인 추가 + Google 로그인 OAuth 진행 확인 | 76d9d94, 5a9a18b |
| 페르소나 명칭 | 블랙록 → **안정·리스크관리**, ARK → **고성장·혁신**, 그레이엄 → **가치·저평가** (UI 라벨, 내부 id 유지) | c07654b |
| 분석 UX | 자동 실행 제거 + **종목 → 형태 선택 → 실행** 2단 구조 chooser | 31fb5ec |
| 페르소나 잠금 UI | Pro 페르소나에 🔒 배지 + apiStream 에러 detail 노출 | 177efea |
| 관리자 | 영구 Pro 부여 스크립트 (`grant_admin_pro.py`) | d77d3ec |

### 2026-05-22 — KR 5년 백필 + 인프라 + 1차 UX 검증

| 영역 | 작업 | 커밋 |
|---|---|---|
| KR 데이터 | KRX 로그인 요구 해소 (계정 + Secret 등록) + pykrx 1.2.8 + Dockerfile Pillow 유지 | 7885dc9, 8fcd859 |
| KR 백필 | 5년 mdw6q: 1405 영업일 / 3.3M docs / fail=0 / 5h31m | (PROGRESS_V2) |
| Backend env | prod에 `ANTHROPIC_API_KEY` + `ADMIN_EMAILS`(본인 gmail 포함) 연결 | (서비스 update) |
| CORS | `CORSMiddleware` 최외곽으로 + 프론트 API base prod 정정 (스테이징 호출 → 콜드스타트 CORS 차단 사라짐) | 45ac1de |
| US 분석 | yfinance 기관보유 스냅샷 info 필드 (Event Analyst 카드) | da7bd73 |
| UX 검증 6건 | 모바일 네비 fixed, 요금제 6종 정정, 매크로 빈상태, 베타 dead path, PersonaSwitch confirm, 대시보드 종목명 | e3751a9 |
| 외국인 누락 발견 | 백필 결과 외국인 필드 전량 누락 → "외국인합계" 카테고리명 변경 발견 | c3b31a7 |

### 2026-05-23 — 외국인 재백필 + Korean Specialist 풀가동

| 영역 | 작업 | 커밋 |
|---|---|---|
| 외국인 재백필 | `--investors` flag + 카테고리명 매핑 수정 → d2xcl 2h4m / 외국인 3.26M docs / ok 94% | bc17ff0 |
| chooser 시각 | 1단계/2단계 강조 배지·연결선·들여쓰기 + 시장(🇰🇷/🇺🇸) 배지 + 한국 시장 페르소나 KR-only 잠금 | 9996d73 |
| Korean Specialist | Pydantic field_validator(잘못된 타입 정규화) + 시스템프롬프트 5점수 강제 + completeness all-zero 탐지 | 1b83fce, 05feda4 |
| 정식 오픈 | 홈/요금제 베타 게이팅 전면 제거 + 3단계 시작 + Free·Pro CTA `/login` | 0078ffe |
| 관심종목·프로필 | ✕ 삭제 버튼(confirm) + `/settings/profile` 편집 페이지(5 영역) + 대시보드 ⚙️ 수정 링크 | ce59dff |

### 2026-05-24 — 운영 안정성 + 진입·회복 관찰선 + 4 UX 정비

| 영역 | 작업 | 커밋 |
|---|---|---|
| daily 잡 | `axis-daily-korea-collect` Cloud Run Job + Scheduler(16:30 KST) 등록 + Firestore composite index ticker+date 생성 | (gcloud) |
| daily 자동 회복 | 첫 실행 KRX 일회성 응답 이슈 → 다음 자동 실행 ok=6/fail=0 회복 확인 | — |
| 풀스택 재검증 6건 | 친화 에러 매핑, sticky 헤더, 매크로 sentinel, 시간 카피, 캐시 표시, `/analyze` 안내 일반화 | 721bd3c |
| 진입·회복 관찰선 | 거리 % + 페르소나 진입 철학 한 줄 + exit_points(상단 관찰선) 카드 노출 | cd99d68 |
| Strategist 페르소나 차등 | take_profit 페르소나별 가이드 명시 + strategist_node 친화 fallback + 3 페르소나 실측 검증 (값 명확히 차등) | f5c5d26 |
| 4 UX 정비 | 헤더 가격 fallback, 데이터 갱신 시각, 공유 링크, 계정 영구 삭제(GDPR) | c8438f7 |
| SEO | metadataBase + OpenGraph + Twitter card + canonical | e8f8663 |

---

## 2. 핵심 검증 결과

### 3 페르소나 차등 실측 (005930, 2026-05-24)

| 항목 | 안정 (Blackrock) | 고성장 (ARK) | 가치 (Graham) |
|---|---|---|---|
| 진입 1차 / % | ₩267K / **-8.7%** | ₩278K / **-5.0%** | ₩251K / **-14.2%** |
| 진입 3차 / % | ₩226K / -22.7% | ₩240K / -17.9% | ₩198K / **-32.3%** |
| 손실 한도 / % | ₩268K / -8.4% | ₩234K / **-20.0%** | ₩270K / -7.7% |
| 최종 차익 / % | ₩365K / +24.8% | ₩525K / **+79.5%** | ₩380K / +29.9% |
| 철학 | 보수적·단계적 | 공격적·적극 | 매우 보수·안전마진 |

→ 같은 종목·시점에서 페르소나만 바꿔도 진입·회복 가이드가 명확히 차등. 시스템 프롬프트 강화 효과 결정적.

### Korean Specialist (005930)
- 외국인 30일 누적 순매도 **-15.1조원** 정확 반영
- 5축 점수: 외국인 2.5 / 거버넌스 6.0 / 밸류업 6.0 / 테마 5.5 / 정책 6.5 / 종합 4.75 (이전 일괄 0/10 → 데이터·프롬프트 강화 후 정상)

---

## 3. 남은 과제 (우선순위)

### 🔴 Critical — 수익화/출시 차단

#### LS 결제 미연결 (Pro CTA dead path)
- prod env에 `LEMONSQUEEZY_API_KEY` 미설정 → Pro 결제 페이지 진입 안 됨
- 홈/요금제 "💎 Pro로 시작" 클릭 → `/login` → 대시보드까지만, 실제 결제 흐름 없음
- 본인(admin grant)은 영향 0이지만 외부 사용자 Pro 전환 0
- **관련 메모리**: [[project_ls_domain_plan]] (LS 거절 후 미진행)
- **결정 필요**: (a) LS 재신청 (b) Toss Payments 등 한국 결제로 전환 (c) 정식 오픈 더 연기

### 🟡 Moderate — 운영 안정성

#### Anthropic 자동 충전 한도
- 2026-05-24 내 2회 "credit balance too low"로 신규 분석 막힘
- console.anthropic.com에서 자동 충전 한도 확인 권장 (사용자 본인)

#### daily-korea-collect 응답 일관성
- 어제(05-23) 첫 실행 calls=8/fail=8 (JSONDecodeError on 20260522), 오늘 자동 회복 (ok=6/fail=0)
- 일회성으로 보이나 며칠 더 모니터링 권장

### 🟢 Nice-to-have

| # | 항목 | 작업량 |
|---|---|---|
| 1 | `og:image` PNG 추가 (`web/public/og.png` 1200×630) — 공유 시 미리보기 카드 | 30분 (디자인 + 추가) |
| 2 | macro_indicators 누적 충분 후 매크로 카드 정량 사이클 채워지는지 재검증 | 시간 누적 대기 |
| 3 | `SaveEntryPointsButton` 작동 라이브 검증 (저장 후 /watchlist 진입선 메타 반영) | 10분 |
| 4 | 분석 결과 캐시 hit/miss를 elapsed 휴리스틱 대신 백엔드 `from_cache` 메타로 명확화 | 1시간 |
| 5 | 모바일 bottom nav에 "⚙️ 설정" 6번째 항목 vs 데스크탑 사이드바만 추가 검토 | 결정 영역 |
| 6 | 검색에 한글 종목명 풀텍스트 작동 (예: "삼성") 추가 검증 | 5분 |

### ⚪ 별건 트래킹

- daily-macro 잡 N일 누적 후 macro_indicators 실제 정량 사이클 채워지는지 (현재는 LLM 추론 fallback)
- Korean Specialist 점수가 가끔 0으로 떨어지는 케이스 모니터링 (Claude 응답 변동성)
- 백엔드 미들웨어 순서·CORS 매크로 카드 빈상태 등은 fix 완료, 회귀 점검 정도면 충분

---

## 4. 참고 — 자주 쓰는 운영 명령

```powershell
# 백엔드 재배포 (cloudbuild.yaml = build + deploy)
gcloud builds submit --config=cloudbuild.yaml --project=all-of-asset

# 서비스 image만 갱신 (env/secret 보존)
gcloud run services update stock-screener --region=asia-northeast3 `
  --project=all-of-asset --image="gcr.io/all-of-asset/stock-screener:latest"

# Cloud Run Jobs 모두 :latest 재pull
foreach ($j in @("axis-backfill-korea-supply","axis-daily-korea-collect",
                 "axis-daily-macro","axis-daily-options",
                 "axis-monthly-regime","axis-weekly-events")) {
  gcloud run jobs update $j --region=asia-northeast3 --project=all-of-asset `
    --image="gcr.io/all-of-asset/stock-screener:latest" --quiet
}

# 프론트 배포 (Vercel)
cd web && vercel --prod --yes

# 관리자 영구 Pro 부여
PYTHONPATH=. py scripts/grant_admin_pro.py <email>

# KR 외국인만 재백필 (코드/이미지 갱신 후)
gcloud run jobs execute axis-backfill-korea-supply --region=asia-northeast3
# (잡 args가 `--investors 외국인`으로 설정돼 있어야)
```

---

**마지막 업데이트**: 2026-05-24
**문서 위치**: `docs/PROGRESS_2026-05.md`

> **후속 (5/26~27)**: KIS(한국투자증권 OpenAPI) Phase 0~3 도입 + UI 풀스택 통합. 별도 문서:
> [`PROGRESS_2026-05-26-27_KIS.md`](./PROGRESS_2026-05-26-27_KIS.md)
