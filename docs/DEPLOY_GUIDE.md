# Stock Screener Pro — 배포 가이드

> v7.3 (2026-04-12) | Cloud Run + Firebase + 전문가 포트폴리오 + SEO 랜딩 + 관리자 대시보드

---

## 1. 웹 서비스 배포 (Cloud Run)

### 빌드 + 배포 (한 줄)

```bash
gcloud builds submit --config=cloudbuild.yaml
```

### 수동 배포 (이미지 빌드 후)

```bash
# 이미지 빌드
docker build -t gcr.io/stock-search-program/stock-screener .

# 푸시
docker push gcr.io/stock-search-program/stock-screener

# 배포
gcloud run deploy stock-screener \
  --image=gcr.io/stock-search-program/stock-screener \
  --region=asia-northeast3 \
  --memory=1Gi --cpu=1 \
  --min-instances=1 --max-instances=3 \
  --timeout=3600 \
  --allow-unauthenticated \
  --update-env-vars="RUN_MODE=server,COLLECT_MODE=readonly" \
  --set-secrets="FIREBASE_CREDENTIALS=firebase-key:latest,ADMIN_KEY=admin-key:latest"

# ⚠️ v7.1 주의: cloudbuild.yaml은 `--update-env-vars` 사용 (LS/Firebase 수동 env 보존).
#    최초 배포에는 `--set-env-vars`도 가능하나, 이후 갱신부터는 반드시 `--update-env-vars` 권장.
```

### 배포 확인

```bash
gcloud run services describe stock-screener --region=asia-northeast3 --format='value(status.url)'
# → https://stock-screener-119320994983.asia-northeast3.run.app
```

---

## 2. 수집기 배포 (Cloud Run Jobs)

### 전체 배포 (스크립트)

```bash
chmod +x deploy-cloud-jobs.sh
./deploy-cloud-jobs.sh
```

### 개별 Job 업데이트

```bash
# 이미지 빌드
gcloud builds submit --config=cloudbuild-collector.yaml

# Heavy Job 업데이트
gcloud run jobs update collector-heavy \
  --region=asia-northeast3 \
  --image=gcr.io/stock-search-program/stock-collector \
  --memory=2Gi --cpu=1 --task-timeout=900

# Light-KR Job 업데이트
gcloud run jobs update collector-light-kr \
  --region=asia-northeast3 \
  --image=gcr.io/stock-search-program/stock-collector \
  --memory=1Gi --cpu=1 --task-timeout=300
```

### 수동 실행 테스트

```bash
gcloud run jobs execute collector-heavy --region=asia-northeast3 --wait
```

---

## 3. 커스텀 도메인 + HTTPS

### 방법 A: Cloud Run 도메인 매핑 (권장)

```bash
# 1) 도메인 소유권 확인 (GCP 콘솔에서 TXT 레코드 추가)
# https://console.cloud.google.com/run/domains

# 2) 도메인 매핑
gcloud beta run domain-mappings create \
  --service=stock-screener \
  --domain=screener.yourdomain.com \
  --region=asia-northeast3

# 3) DNS 설정
# CNAME: screener.yourdomain.com → ghs.googlehosted.com.
# 또는 A 레코드: Google이 제공하는 IP 주소
```

HTTPS는 Cloud Run이 자동 제공 (Let's Encrypt).

### 방법 B: Cloudflare Proxy (빠른 설정)

1. Cloudflare에 도메인 추가
2. DNS에 CNAME 레코드 추가: `screener` → `stock-screener-119320994983.asia-northeast3.run.app`
3. Proxy 활성화 (주황색 구름)
4. SSL/TLS → Full (strict)

장점: CDN 캐싱, DDoS 보호, 무료 SSL, 한국 PoP

### 방법 C: Firebase Hosting (리다이렉트)

```json
// firebase.json
{
  "hosting": {
    "public": "public",
    "rewrites": [{
      "source": "**",
      "run": {
        "serviceId": "stock-screener",
        "region": "asia-northeast3"
      }
    }]
  }
}
```

```bash
firebase deploy --only hosting
```

---

## 4. 환경변수

### 기본

| 변수 | 값 | 설명 |
|------|-----|------|
| `RUN_MODE` | `server` | 서버 모드 |
| `COLLECT_MODE` | `readonly` | Cloud Run에서 크롤링 비활성화 |
| `PORT` | `8501` | 서버 포트 |
| `ADMIN_KEY` | Secret Manager | 관리자 키 |
| `FIREBASE_CREDENTIALS` | Secret Manager | Firebase 서비스 계정 JSON |
| `CLOUD_RUN_URL` | `https://stock-screener-...` | Collector가 reload 호출할 URL |

### 상용화 (v7.0 — 인증 + 결제)

| 변수 | 값 | 설명 |
|------|-----|------|
| `AUTH_ENABLED` | `true` | Firebase 인증 활성화 (false면 모든 요청이 tier=pro로 bypass) |
| `FIREBASE_WEB_API_KEY` | Firebase 콘솔 값 | 프론트 Firebase config용 (AIza...) |
| `FIREBASE_PROJECT_ID` | `stock-search-program` | Firebase 프로젝트 ID |
| `FIREBASE_CREDENTIALS` | Secret (`firebase-key`) | 서비스 계정 JSON (백엔드 토큰 검증용) |
| `ADMIN_EMAILS` | 콤마구분 | 자동 Pro 승격 + `/admin` 접근 허용 이메일 목록 |
| `ADMIN_KEY` | (선택) 랜덤 문자열 | `/admin` 대체 접근 키 (`X-Admin-Key` 헤더) |
| `LEMONSQUEEZY_API_KEY` | Secret Manager | LS API 키 (`lemon-ls-api-key`) |
| `LEMONSQUEEZY_STORE_ID` | 숫자 ID | LS 스토어 ID |
| `LEMONSQUEEZY_VARIANT_MONTHLY` | 숫자 ID | 월간 Variant ID |
| `LEMONSQUEEZY_VARIANT_YEARLY` | 숫자 ID | 연간 Variant ID |
| `LEMONSQUEEZY_WEBHOOK_SECRET` | Secret Manager | LS webhook signing secret |

### v7.2 추가 — 체험/세션 튜닝 (선택)

| 변수 | 기본 | 설명 |
|------|------|------|
| `TRIAL_DAYS` | `7` | 무료 체험 일수 |
| `MAX_ACTIVE_SESSIONS` | `2` | 동시 접속 허용 세션 수 (초과 시 오래된 세션 자동 종료) |
| `UNIQUE_IP_WARN` | `4` | 30일 unique IP 경고 기준 (토스트 알림) |
| `UNIQUE_IP_FLAG` | `5` | 30일 unique IP 자동 suspicious 플래그 기준 |

### Lemon Squeezy 배포 명령어

```bash
# 1) Secret Manager에 민감 정보 저장
echo -n "..." | gcloud secrets create lemon-ls-api-key --data-file=-
echo -n "..." | gcloud secrets create lemon-ls-webhook-secret --data-file=-

# 2) Cloud Run 환경변수 업데이트
gcloud run services update stock-screener \
  --region=asia-northeast3 \
  --update-env-vars="AUTH_ENABLED=true,FIREBASE_WEB_API_KEY=AIza...,FIREBASE_PROJECT_ID=stock-search-program,LEMONSQUEEZY_STORE_ID=12345,LEMONSQUEEZY_VARIANT_MONTHLY=678901,LEMONSQUEEZY_VARIANT_YEARLY=678902" \
  --update-secrets="LEMONSQUEEZY_API_KEY=lemon-ls-api-key:latest,LEMONSQUEEZY_WEBHOOK_SECRET=lemon-ls-webhook-secret:latest"

# 3) Webhook 엔드포인트 등록 (Lemon Squeezy 대시보드)
#    Settings → Webhooks → https://<your-domain>/api/webhooks/lemonsqueezy
#    Events: subscription_created, subscription_updated, subscription_resumed,
#            subscription_cancelled, subscription_expired,
#            subscription_payment_success, subscription_payment_failed
```

---

## 5. Cloud Scheduler (20개 cron)

| 유형 | 시간 (KST) | 간격 | Job |
|------|-----------|------|-----|
| Heavy | 06:30, 09:30, 16:00, 22:30 | 4회/일 | collector-heavy |
| Light KR | 10:00~15:00 | 30분 | collector-light-kr |
| Light US | 00:00~05:00 | 60분 | collector-light-us |

---

## 6. v6.1 변경사항 배포 체크리스트

```
[ ] gcloud builds submit --config=cloudbuild.yaml         # 웹 서비스
[ ] gcloud builds submit --config=cloudbuild-collector.yaml # 수집기
[ ] gcloud run jobs update collector-heavy ...             # Heavy Job (히스토리 확대)
[ ] gcloud run jobs update collector-light-kr ...          # Light-KR
[ ] gcloud run jobs execute collector-heavy --wait         # 테스트 실행
[ ] 브라우저에서 UI 확인
```

---

## 7. v7.1 변경사항 배포 체크리스트 (2026-04-12)

### 코드 변경 (이미 workspace에 반영)
- 결제: Stripe → **Lemon Squeezy** (`lemon_routes.py`, `httpx` 기반)
- 법적 페이지 4종: `/pricing`, `/terms`, `/privacy`, `/refund`
- 카테고리 tier 노출: `CategoryInfo.tier` + Free 먼저 정렬 + 프론트 PRO 배지
- 프론트 UI: Watchlist Insights, Bulk Portfolio Modal, Contact Modal, Site Footer, Tooltip 강화
- 인프라: `cloudbuild.yaml` `--update-env-vars` 전환

### 배포 순서
```
[1] 법적 페이지 먼저 배포 (LS 승인 선결조건)
    gcloud builds submit --config=cloudbuild.yaml

[2] 4개 URL 접속 확인
    https://<cloud-run-url>/pricing
    https://<cloud-run-url>/terms
    https://<cloud-run-url>/privacy
    https://<cloud-run-url>/refund

[3] Lemon Squeezy 대시보드 설정
    - Store 생성 + Variant 2개 (월 ₩79,000 / 연 ₩700,000)
    - API Key 발급
    - Webhook: https://<cloud-run-url>/api/webhooks/lemonsqueezy
      Events: subscription_created, subscription_updated, subscription_resumed,
              subscription_cancelled, subscription_expired,
              subscription_payment_success, subscription_payment_failed
    - 승인 소요: 당일~1일

[4] Firebase Console
    - Authentication → Google 로그인 활성화
    - 승인 도메인에 Cloud Run URL 추가

[5] Secret Manager + env 설정 (§4 참조)
    echo -n "..." | gcloud secrets create lemon-ls-api-key --data-file=-
    echo -n "..." | gcloud secrets create lemon-ls-webhook-secret --data-file=-
    gcloud run services update stock-screener --region=asia-northeast3 \
      --update-env-vars="AUTH_ENABLED=true,FIREBASE_WEB_API_KEY=...,LEMONSQUEEZY_STORE_ID=...,LEMONSQUEEZY_VARIANT_MONTHLY=...,LEMONSQUEEZY_VARIANT_YEARLY=..." \
      --update-secrets="LEMONSQUEEZY_API_KEY=lemon-ls-api-key:latest,LEMONSQUEEZY_WEBHOOK_SECRET=lemon-ls-webhook-secret:latest"

[6] E2E 테스트
    회원가입 → Free 제한 확인 → Pro 카테고리 chip 잠금 표시 →
    결제 → Pro 해금 → 관심종목 → Bulk 포트폴리오 담기 → 해지 → Free 복귀
```

### 가격 정책 (확정)
| 플랜 | 가격 (KRW) | 비고 |
|------|-----------|------|
| Free | ₩0 | 6개 Free 카테고리 (surge, bluechip, recommend, watchlist, etf, foreign_inst) |
| Pro 월간 | ₩79,000 / 월 | 전체 카테고리 + 백테스트 + 포트폴리오 + CSV/Excel |
| Pro 연간 | ₩700,000 / 년 | 약 26% 할인 (월 ₩58,333 환산) |

KRW 표기 유지 — Lemon Squeezy가 MoR로 통화 환산을 자동 처리.

---

## 8. v7.2 배포 체크리스트 (2026-04-12 후반)

### 코드 변경
- 7일 무료 체험(명시적 시작) — `start_trial()`, `/api/user/start-trial`
- 세션/IP 추적 — `services/security.py`, `/api/auth/session-*`
- 관리자 대시보드 — `/admin`, `api/admin_routes.py`
- Phase A 악용 방지 — 이메일 인증, 일회용 도메인, +alias 정규화, IP당 trial 1회

### Firebase Console 선결 작업
1. Firebase 프로젝트 `stock-search-program` 확인/생성
2. Authentication → 이메일/비밀번호 + Google 활성화
3. Authentication → Settings → **Authorized domains**에 Cloud Run URL 추가
4. 프로젝트 설정 → 일반 → 내 앱에 웹 앱 등록 → `apiKey` 복사 (`AIza...`)
5. 프로젝트 설정 → 서비스 계정 → "새 비공개 키 생성" → JSON 다운로드

### Cloud Run 선결 작업
```bash
# Secret Manager API 활성화 (최초 1회)
gcloud services enable secretmanager.googleapis.com

# Firebase 서비스 계정 시크릿 생성
gcloud secrets create firebase-key --data-file=path/to/firebase-adminsdk.json

# Cloud Run 기본 SA에 시크릿 읽기 권한
gcloud secrets add-iam-policy-binding firebase-key \
  --member=serviceAccount:<PROJECT_NUMBER>-compute@developer.gserviceaccount.com \
  --role=roles/secretmanager.secretAccessor

# 환경변수 + 시크릿 일괄 설정
gcloud run services update stock-screener --region=asia-northeast3 \
  --update-env-vars="AUTH_ENABLED=true,FIREBASE_WEB_API_KEY=AIza...,FIREBASE_PROJECT_ID=stock-search-program,ADMIN_EMAILS=admin1@example.com,admin2@example.com" \
  --update-secrets="FIREBASE_CREDENTIALS=firebase-key:latest"

# Cloud Run ingress 공개 (필요 시)
gcloud run services add-iam-policy-binding stock-screener \
  --region=asia-northeast3 --member=allUsers --role=roles/run.invoker
```

### 검증
```bash
# 1. 서비스 상태
curl https://<url>/api/status
# → {"status":"ready",...}

# 2. Firebase 설정 노출
curl https://<url>/api/auth-config
# → {"apiKey":"AIza...","authDomain":"...","projectId":"..."}

# 3. 인증 없이 Pro 차단 확인
curl https://<url>/api/scan?category=growth
# → 403 {"detail":"'growth'은(는) Pro 기능입니다.","upgrade":true,"free_categories":[...]}

# 4. 관리자 대시보드 접근
# 브라우저: https://<url>/admin → ADMIN_EMAILS 계정으로 로그인
```

### 관리자 대시보드 기능
- **통계:** 전체/Pro/Free/체험중/의심/정지 카운트
- **사용자 목록:** 필터 (all/suspicious/suspended/trial/pro/free) + 검색 (이메일/UID)
- **사용자 상세:** 로그인 이력(최근 30) + 활성 세션 + 30일 unique IP
- **액션:** 정지/해제/체험연장(1~90일)/메모

### Firestore 스키마 (v7.2)
```
users/{uid}
  email, normalized_email, email_verified, tier, created_at
  trial_started, trial_ends_at, trial_claimed_at, trial_blocked_reason
  signup_ip_hash
  lemon_customer_id, subscription{...}
  suspended, suspicious, admin_note, is_admin_role
  
  /login_history/{auto} — ip, ip_hash, user_agent, timestamp
  /active_sessions/{sid} — ip, ip_hash, user_agent, created_at, last_seen

trial_ips/{auto} — uid, email, normalized_email, ip_hash, created_at
```

### 악용 방지 동작 기준
- **일회용 도메인:** `tempmail`, `10minutemail`, `mailinator`, `yopmail`, `trashmail` 등 70+ 도메인 + 키워드 매칭 (`tempmail`, `disposable`, `throwaway` 포함)
- **이메일 정규화:** Gmail 점(`u.s.e.r@gmail.com`) + alias(`user+x@gmail.com`) → `user@gmail.com`, googlemail.com → gmail.com
- **IP 한도:** 24시간 내 같은 IP(해시)로 2번째 계정 trial 시 차단 (`trial_blocked_reason=ip_limit`)
- **동시접속:** 기본 2개 허용, 초과 시 오래된 세션 자동 제거
- **unique IP 플래그:** 30일 내 4개+ 경고 토스트, 5개+ `suspicious=true` 자동 플래그

### 로그아웃 UX
프론트 `doLogout()` — 세션 종료 호출 → 메모리 상태 초기화 → Firebase signOut → `location.replace('/')` 강제 (이전 세션 상태 잔존 방지).

---

## 9. v7.3 완성도 업그레이드 (2026-04-12 후반)

### 공개 SEO 페이지 (신규)
| URL | 용도 | 캐시 |
|-----|------|------|
| `/rank` | 오늘 날짜로 리다이렉트 | - |
| `/rank/today` | 오늘 날짜로 리다이렉트 | - |
| `/rank/<YYYY-MM-DD>` | 해당일 TOP 종목 리포트 (5섹션) | 10분 |
| `/backtest-report` | 시그널 백테스트 공개 리포트 | 30분 |
| `/sitemap.xml` | 검색엔진 사이트맵 | - |
| `/robots.txt` | 크롤링 규칙 | - |

**SEO 표준:**
- `<title>`, `description`, canonical, `og:*`, `twitter:*`, JSON-LD Article 구조화 데이터
- `robots: index,follow` / 민감 경로 `Disallow`
- Cache-Control: `public, max-age=600~1800` (CDN 친화)

**검색엔진 등록 필수 작업 (배포 후):**
1. [Google Search Console](https://search.google.com/search-console) → 속성 추가 → `/sitemap.xml` 제출
2. [네이버 웹마스터 도구](https://searchadvisor.naver.com/) → 사이트 등록 → `/sitemap.xml` 제출 (한국 유입 핵심)
3. 일반적으로 제출 후 1~2주 내 색인 시작

### 포트폴리오 전문가 분석 (`/api/portfolio/risk` 확장)
**추가 응답 필드:**
- `health_score` (0~100) + `health_grade` (S/A/B/C/D/F)
- `annualized_return`, `sharpe_ratio`, `max_drawdown`, `avg_correlation`
- `top_weight_*`, `market_split`(KR/US), `positions`(각 종목 비중·섹터)
- `recommendations[]` — 8개 룰 기반 자동 조언 (success/info/warning/danger)

**프론트:** SVG 도넛 섹터 차트 + 가중 바 + 상관관계 Top 4 + 시장 분할 + 건강도 배지(그라디언트 6색).

### 종목 상세 모달
- 🎯 매수 포인트 하이라이트 (7개 시그널 자동 감지)
- 📝 메모 (localStorage 400ms debounce)
- 🏷 태그 (localStorage, 20자 제한, XSS 방어)

### 알림 시그널 4종
- 🎯 매수점수 진입 (50/70점)
- 🚀 관심종목 급등 시그널 (예보 4+/돌파 3+/동반매수)
- 📊 등락률 (±X%)
- 🔥 전체 급등주 (일 1회)
- 토스트 + Browser Notification + `alertSeen` 중복 방지

### 모바일 카드뷰
- `setViewMode('table'|'card')` + localStorage
- 640px 이하 기본 카드, 토글 버튼 상시 노출

### 데이터 신선도
- KST 시간 기반 🟢 장중 / 🟡 장전 / 🟠 장후 / ⚪ 장마감
- 장중 30분+ 업데이트 없으면 경고

### CSV/Excel
- UTF-8 BOM 명시 (Excel 한글 호환)
- RFC 5987 파일명 인코딩 (`filename*=UTF-8''...`) + ASCII fallback

### 섹터 흐름 트리맵
- Squarified 재귀 분할
- 사각형 크기=규모, 색=방향, 투명도=강도
- 트리맵/그리드 뷰 토글

### 관심종목 태그 필터
- 관심종목 카테고리 상단 태그 칩 바 (자동 생성, 개수 표시)
- 클릭 시 해당 태그 종목만 필터링

### PUBLIC_PATHS 확장
```python
PUBLIC_PATHS = {"/", "/api/status", "/api/categories", "/favicon.ico",
                "/api/auth-config", "/api/webhooks/lemonsqueezy", "/api/lemon-config",
                "/pricing", "/terms", "/privacy", "/refund", "/admin", "/rank",
                "/backtest-report", "/sitemap.xml", "/robots.txt"}
PUBLIC_PREFIXES = ("/static/", "/rank/")
```
