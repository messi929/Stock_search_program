# Axis v2 — Cloud Run 배포 가이드

> **대상**: Week B/C 데이터 인프라 Cloud Run Jobs 4개 + 신규 Secret 4개
> **선행**: feature/v2-six-personas 브랜치 main 머지 완료 가정
> **소요**: 30~45분 (Secret 등록 + 빌드 + Job 등록 + Scheduler)

---

## 1. 사전 준비

### 1.1 환경 확인

```powershell
# gcloud 로그인 + 프로젝트
gcloud auth login
gcloud config set project all-of-asset
gcloud config set run/region asia-northeast3

# 프로젝트 번호 (서비스 계정 권한 부여용)
gcloud projects describe all-of-asset --format="value(projectNumber)"
```

### 1.2 외부 API 키 발급

| Key | 용도 | 발급 |
|-----|------|------|
| `FRED_API_KEY` | FRED 매크로 시리즈 (Week B) | https://fredaccount.stlouisfed.org/apikeys |
| `ECOS_API_KEY` | 한국은행 ECOS (Week B) | https://ecos.bok.or.kr/api/ |
| `DART_API_KEY` | 금감원 DART 공시 (Week A/C) | https://opendart.fss.or.kr/ |
| `EDGAR_USER_AGENT` | SEC EDGAR User-Agent (Week C) | 자체 — `"Axis Research <ops@example.com>"` |

> ⚠️ EDGAR_USER_AGENT는 키가 아니라 식별 헤더. 이메일 누락 시 SEC가 차단.

---

## 2. Secret Manager 등록

### 2.1 신규 4개 Secret 등록 (PowerShell)

```powershell
# FRED
"YOUR_FRED_KEY" | gcloud secrets create fred-api-key --data-file=-

# ECOS
"YOUR_ECOS_KEY" | gcloud secrets create ecos-api-key --data-file=-

# DART
"YOUR_DART_KEY" | gcloud secrets create dart-api-key --data-file=-

# EDGAR User-Agent (이메일 포함)
"Axis Research <wogus711929@gmail.com>" | gcloud secrets create edgar-user-agent --data-file=-
```

### 2.2 서비스 계정에 접근 권한 부여

```powershell
$PROJECT_NUMBER = (gcloud projects describe all-of-asset --format="value(projectNumber)")
$SA = "$PROJECT_NUMBER-compute@developer.gserviceaccount.com"

# 4개 Secret 모두에 접근 권한
foreach ($s in @("fred-api-key", "ecos-api-key", "dart-api-key", "edgar-user-agent")) {
    gcloud secrets add-iam-policy-binding $s `
        --member="serviceAccount:$SA" `
        --role="roles/secretmanager.secretAccessor" `
        --quiet
}
```

### 2.3 등록 확인

```powershell
gcloud secrets list --filter="name:(fred OR ecos OR dart OR edgar)"
# 4개 출력되어야 함
```

---

## 3. 이미지 빌드

기존 Dockerfile에 `jobs/` 디렉토리 COPY 추가됨 (이번 PR). 빌드만 다시 하면 됨.

```powershell
# 메인 이미지 (web + jobs 통합)
gcloud builds submit --config=cloudbuild.yaml --quiet

# 이미지 위치 확인
gcloud container images list --filter="name:stock-screener"
```

> 💡 동일 이미지로 web 서버 + 4 Job 모두 실행. `--args`로 entrypoint를 override.

---

## 4. Cloud Run Jobs 4개 등록

### 4.1 daily_macro_collect (FRED + ECOS 일일)

```powershell
$IMAGE = "gcr.io/all-of-asset/stock-screener:latest"
$REGION = "asia-northeast3"

gcloud run jobs create axis-daily-macro `
    --image=$IMAGE `
    --region=$REGION `
    --memory=1Gi --cpu=1 `
    --task-timeout=600 --max-retries=2 `
    --set-secrets="FRED_API_KEY=fred-api-key:latest,ECOS_API_KEY=ecos-api-key:latest,FIREBASE_CREDENTIALS=firebase-key:latest" `
    --command="python" --args="-m,jobs.daily_macro_collect" `
    --quiet
```

### 4.2 daily_options_collect (yfinance 옵션)

```powershell
gcloud run jobs create axis-daily-options `
    --image=$IMAGE `
    --region=$REGION `
    --memory=1Gi --cpu=1 `
    --task-timeout=600 --max-retries=2 `
    --set-secrets="FIREBASE_CREDENTIALS=firebase-key:latest" `
    --command="python" --args="-m,jobs.daily_options_collect" `
    --quiet
```

### 4.3 weekly_event_calendar_sync (DART + EDGAR + yfinance)

```powershell
gcloud run jobs create axis-weekly-events `
    --image=$IMAGE `
    --region=$REGION `
    --memory=1Gi --cpu=1 `
    --task-timeout=900 --max-retries=2 `
    --set-secrets="DART_API_KEY=dart-api-key:latest,EDGAR_USER_AGENT=edgar-user-agent:latest,FIREBASE_CREDENTIALS=firebase-key:latest" `
    --command="python" --args="-m,jobs.weekly_event_calendar_sync" `
    --quiet
```

### 4.4 monthly_regime_calc (Week B Day 5)

```powershell
gcloud run jobs create axis-monthly-regime `
    --image=$IMAGE `
    --region=$REGION `
    --memory=1Gi --cpu=1 `
    --task-timeout=600 --max-retries=2 `
    --set-secrets="FRED_API_KEY=fred-api-key:latest,ECOS_API_KEY=ecos-api-key:latest,FIREBASE_CREDENTIALS=firebase-key:latest" `
    --command="python" --args="-m,jobs.monthly_regime_calc" `
    --quiet
```

### 4.5 등록 확인

```powershell
gcloud run jobs list --region=$REGION --filter="name:axis-"
# 4개 출력되어야 함:
# axis-daily-macro / axis-daily-options / axis-weekly-events / axis-monthly-regime
```

---

## 5. Cloud Scheduler 등록

### 5.1 일정 표

| Job | Cron (KST) | UTC | 사유 |
|-----|-----------|-----|-----|
| daily-macro | `0 6 * * *` | `0 21 * * *` (전날) | 미국 장 마감 후 FRED 갱신 안정 |
| daily-options | `30 6 * * *` | `30 21 * * *` (전날) | yfinance 옵션 갱신 안정 |
| weekly-events | `0 22 * * 0` | `0 13 * * 0` | 일요일 22시 — 다음 주 미리 |
| monthly-regime | `0 6 1 * *` | `0 21 1 * *` (전날) | 매월 1일 사이클 재계산 |

### 5.2 Scheduler 일괄 등록 (PowerShell)

```powershell
$PROJECT_ID = "all-of-asset"
$REGION = "asia-northeast3"
$TIMEZONE = "Asia/Seoul"
$SA_EMAIL = "$PROJECT_ID@appspot.gserviceaccount.com"

function Register-Schedule {
    param($Name, $Cron, $JobName, $TimeoutSec = 600)
    $URI = "https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/${JobName}:run"
    gcloud scheduler jobs create http $Name `
        --location=$REGION `
        --schedule=$Cron `
        --time-zone=$TIMEZONE `
        --uri=$URI `
        --http-method=POST `
        --oauth-service-account-email=$SA_EMAIL `
        --attempt-deadline="${TimeoutSec}s" `
        --quiet
}

Register-Schedule "axis-daily-macro-sched" "0 6 * * *" "axis-daily-macro" 600
Register-Schedule "axis-daily-options-sched" "30 6 * * *" "axis-daily-options" 600
Register-Schedule "axis-weekly-events-sched" "0 22 * * 0" "axis-weekly-events" 900
Register-Schedule "axis-monthly-regime-sched" "0 6 1 * *" "axis-monthly-regime" 600
```

### 5.3 등록 확인

```powershell
gcloud scheduler jobs list --location=$REGION --filter="name:axis-"
# 4개 출력
```

---

## 6. 검증 (단발 실행)

### 6.1 macro 일일 수집 — 가장 안전한 검증

```powershell
gcloud run jobs execute axis-daily-macro --region=$REGION --wait
```

**기대 결과**:
- exit 0
- Firestore `macro_indicators` 컬렉션에 18+ 시리즈 doc 추가
- 로그에 `FRED 12+ / ECOS 6` 성공 카운트

### 6.2 options 수집

```powershell
gcloud run jobs execute axis-daily-options --region=$REGION --wait
```

기본 와치리스트 10종목 × 옵션 시그널. yfinance 응답이 없는 종목은 `available=False`로 graceful skip — exit 0 유지.

### 6.3 events 주간 수집

```powershell
gcloud run jobs execute axis-weekly-events --region=$REGION --wait
```

⚠️ DART_API_KEY / EDGAR_USER_AGENT 누락 시 해당 소스만 skip. 둘 다 정상이면 KR 5종목 + US 5종목 14일 윈도우 이벤트 수집.

### 6.4 monthly regime — Week B 데이터 적재 후 실행

```powershell
gcloud run jobs execute axis-monthly-regime --region=$REGION --wait
```

⚠️ macro_indicators에 cycle_detector REQUIRED_INPUTS이 적재되어 있어야 함. daily-macro 1주일 정도 누적 후 실행 권장.

---

## 7. 운영 모니터링

### 7.1 실행 이력

```powershell
# 최근 실행
gcloud run jobs executions list --job=axis-daily-macro --region=$REGION --limit=5

# 특정 실행 로그
gcloud run jobs executions describe EXECUTION_NAME --region=$REGION
gcloud logging read "resource.type=cloud_run_job AND resource.labels.job_name=axis-daily-macro" --limit=50
```

### 7.2 알림 (Pub/Sub Sink — 권장)

`daily_macro_collect.py`는 매크로 변동 감지 시 `severity=NOTICE` 로그 분리.
Cloud Logging Sink를 Pub/Sub으로 라우팅하여 Slack/텔레그램 알림 가능.

```powershell
# Sink 예시 (이미 구축된 환경에 통합)
gcloud logging sinks create axis-macro-alerts `
    pubsub.googleapis.com/projects/$PROJECT_ID/topics/axis-alerts `
    --log-filter='resource.type="cloud_run_job" AND severity="NOTICE" AND textPayload:"매크로 변동 감지"'
```

---

## 8. 비용 예측

| Job | 실행/월 | 1회 비용 (Cloud Run + 외부 API) | 월 비용 |
|-----|--------|------------------------------|--------|
| axis-daily-macro | 30 | ~₩5 (CR) + 0 (FRED/ECOS 무료) | **₩150** |
| axis-daily-options | 30 | ~₩5 (CR) + 0 (yfinance 무료) | **₩150** |
| axis-weekly-events | 4 | ~₩10 (CR) + 0 (DART/EDGAR 무료) | **₩40** |
| axis-monthly-regime | 1 | ~₩5 (CR) | **₩5** |
| Firestore 쓰기 | — | macro 18 doc/day + events ~50 doc/week | **~₩500** |
| **합계** | — | — | **~₩900/월** |

> Claude API 비용은 별도 (사용자 분석 시점 발생) — `scripts/measure_v2_cost.py` 참조.

---

## 9. 롤백 / 삭제

```powershell
# Scheduler 삭제 (먼저 실행 막기)
foreach ($n in @("axis-daily-macro-sched", "axis-daily-options-sched", "axis-weekly-events-sched", "axis-monthly-regime-sched")) {
    gcloud scheduler jobs delete $n --location=$REGION --quiet
}

# Job 삭제
foreach ($n in @("axis-daily-macro", "axis-daily-options", "axis-weekly-events", "axis-monthly-regime")) {
    gcloud run jobs delete $n --region=$REGION --quiet
}

# Secret 삭제 (영구 — 신중)
foreach ($s in @("fred-api-key", "ecos-api-key", "dart-api-key", "edgar-user-agent")) {
    gcloud secrets delete $s --quiet
}
```

---

## 10. 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|-----|
| Job 실패 + `403` 로그 | Secret 접근 권한 미부여 | §2.2 IAM 부여 재실행 |
| `EDGAR_USER_AGENT 미설정` 에러 | Secret 누락 또는 마운트 실패 | `--set-secrets` 옵션 + Secret 등록 확인 |
| `FRED_API_KEY 미설정` warning | `daily_macro_collect.py`는 키 없으면 FRED skip → ECOS만 | Secret 등록 후 Job update |
| Firestore 쓰기 0건 | `--dry-run` 옵션 실수 또는 firebase-key 마운트 실패 | `--args` 확인, FIREBASE_CREDENTIALS Secret 권한 확인 |
| `pykrx LOGOUT` (heavy job) | KRX IP 차단 — Cloud Run IP 회전으로 자동 해결 | retry 1회 자동, 그래도 fail이면 수동 retry |

---

## 11. 다음 단계 (배포 후)

### 즉시 (배포 직후)
1. **검증 1건** — `gcloud run jobs execute axis-daily-macro --wait` 후 Firestore `macro_indicators` 컬렉션 확인
2. **Frontend staging** — `/api/ai/analyze` macro 페르소나 호출 시 정량 사이클 결과 노출 확인

### 1주일 누적 후
3. **monthly-regime 실 검증** — `gcloud run jobs execute axis-monthly-regime --wait` (cycle_detector REQUIRED_INPUTS 적재 필요)
4. **단계별 실 분석 검증** — `BETA_READINESS.md §5` 절차 따라 Stage 1 → 2 → 3 진행

### 베타 1~2주 내 backlog
5. ticker→CIK 자동 매핑 (현재 weekly-events에서 EDGAR cik_lookup 누락 시 yfinance만)
6. `upcoming_ipo.json` 월 1회 갱신 SOP 문서화
7. `tests/regression/test_60_cases.py`에 `--persona-filter` / `--ticker-filter` / `--smoke` 옵션 추가
   (Stage 1/2 단계 검증을 위한 필터 — 현재는 풀 60건만 실행 가능)

— 배포 가이드 끝 (2026-05-03)
