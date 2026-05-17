#!/bin/bash
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Axis v2 — Cloud Run Jobs 배포 (Week B/C 데이터 인프라)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
# 4 Jobs:
#   axis-daily-macro       매일 06:00 KST  (FRED + ECOS)
#   axis-daily-options     매일 06:30 KST  (yfinance 옵션 + VKOSPI)
#   axis-weekly-events     일요일 22:00 KST (DART + EDGAR + yfinance 실적)
#   axis-monthly-regime    매월 1일 06:00  (cycle + regime 재계산)
#
# 사용법:
#   chmod +x deploy-v2-axis-jobs.sh
#   ./deploy-v2-axis-jobs.sh                # 전체 배포 (이미지 빌드 포함)
#   ./deploy-v2-axis-jobs.sh --skip-build   # 이미지 빌드 생략
#   ./deploy-v2-axis-jobs.sh --check-only   # Secret/Job 등록 상태만 확인
#
# 사전 준비 (최초 1회):
#   docs/v2_roadmap/DEPLOY_V2.md §1~2 참고
#   - gcloud 인증 + 프로젝트 설정
#   - 4 Secret 등록: fred-api-key / ecos-api-key / dart-api-key / edgar-user-agent

set -euo pipefail

REGION="asia-northeast3"
TIMEZONE="Asia/Seoul"
IMAGE_NAME="stock-screener"

SKIP_BUILD=false
CHECK_ONLY=false
for arg in "$@"; do
    case $arg in
        --skip-build) SKIP_BUILD=true ;;
        --check-only) CHECK_ONLY=true ;;
    esac
done

# ──────────────────────────────────────────────
# Phase 1: 사전 검증
# ──────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Phase 1: 사전 검증 (gcloud + Secret)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

ACCOUNT=$(gcloud config get-value account 2>/dev/null)
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
if [ -z "$ACCOUNT" ] || [ -z "$PROJECT_ID" ]; then
    echo "ERROR: gcloud 인증 또는 프로젝트 미설정"
    exit 1
fi
echo "  계정: ${ACCOUNT}"
echo "  프로젝트: ${PROJECT_ID}"
echo "  리전: ${REGION}"

PROJECT_NUMBER=$(gcloud projects describe "${PROJECT_ID}" --format="value(projectNumber)" 2>/dev/null)
SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
SCHED_SA="${PROJECT_ID}@appspot.gserviceaccount.com"
IMAGE="gcr.io/${PROJECT_ID}/${IMAGE_NAME}:latest"

# Secret 존재 + 접근 권한
REQUIRED_SECRETS=("firebase-key" "fred-api-key" "ecos-api-key" "dart-api-key" "edgar-user-agent")
echo ""
echo "  Secret Manager 확인..."
MISSING=()
for secret in "${REQUIRED_SECRETS[@]}"; do
    if gcloud secrets describe "$secret" --project="${PROJECT_ID}" --quiet >/dev/null 2>&1; then
        echo "    ✓ $secret"
    else
        echo "    ✗ $secret (누락)"
        MISSING+=("$secret")
    fi
done
if [ ${#MISSING[@]} -gt 0 ]; then
    echo ""
    echo "ERROR: 다음 Secret 등록 필요: ${MISSING[*]}"
    echo "  docs/v2_roadmap/DEPLOY_V2.md §2.1 참고"
    exit 1
fi

# IAM 권한 부여 (이미 있으면 무시)
echo ""
echo "  Secret 접근 권한 부여..."
for secret in "${REQUIRED_SECRETS[@]}"; do
    gcloud secrets add-iam-policy-binding "$secret" \
        --member="serviceAccount:${SA}" \
        --role="roles/secretmanager.secretAccessor" \
        --quiet >/dev/null 2>&1 || true
done
echo "    완료"

if [ "$CHECK_ONLY" = true ]; then
    echo ""
    echo "  --check-only 모드 — 배포 단계 생략"
    gcloud run jobs list --region=$REGION --filter="name:axis-" --format="table(name,lastModifier.email,updateTime)" || true
    exit 0
fi

# ──────────────────────────────────────────────
# Phase 2: 이미지 빌드
# ──────────────────────────────────────────────
if [ "$SKIP_BUILD" = false ]; then
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  Phase 2: 이미지 빌드 (메인 Dockerfile)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  이미지: ${IMAGE}"
    gcloud builds submit --config=cloudbuild.yaml --quiet
    echo "  Phase 2 완료"
else
    echo ""
    echo "  Phase 2 스킵 (--skip-build)"
fi

# ──────────────────────────────────────────────
# Phase 3: Cloud Run Jobs 4개
# ──────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Phase 3: Cloud Run Jobs 4개 배포"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

deploy_job() {
    local NAME=$1 MEM=$2 TIMEOUT=$3 SEC=$4 ARGS=$5
    echo "  [$NAME] mem=${MEM}, timeout=${TIMEOUT}s"
    if gcloud run jobs describe "${NAME}" --region="${REGION}" --quiet >/dev/null 2>&1; then
        gcloud run jobs update "${NAME}" \
            --image="${IMAGE}" \
            --region="${REGION}" --memory="${MEM}" --cpu=1 \
            --task-timeout="${TIMEOUT}" --max-retries=2 \
            --set-secrets="${SEC}" \
            --command="python" --args="${ARGS}" --quiet
        echo "    -> updated"
    else
        gcloud run jobs create "${NAME}" \
            --image="${IMAGE}" \
            --region="${REGION}" --memory="${MEM}" --cpu=1 \
            --task-timeout="${TIMEOUT}" --max-retries=2 \
            --set-secrets="${SEC}" \
            --command="python" --args="${ARGS}" --quiet
        echo "    -> created"
    fi
}

deploy_job "axis-daily-macro" "1Gi" "600" \
    "FRED_API_KEY=fred-api-key:latest,ECOS_API_KEY=ecos-api-key:latest,FIREBASE_CREDENTIALS=firebase-key:latest" \
    "-m,jobs.daily_macro_collect"

deploy_job "axis-daily-options" "1Gi" "600" \
    "FIREBASE_CREDENTIALS=firebase-key:latest" \
    "-m,jobs.daily_options_collect"

deploy_job "axis-weekly-events" "1Gi" "900" \
    "DART_API_KEY=dart-api-key:latest,EDGAR_USER_AGENT=edgar-user-agent:latest,FIREBASE_CREDENTIALS=firebase-key:latest" \
    "-m,jobs.weekly_event_calendar_sync"

deploy_job "axis-monthly-regime" "1Gi" "600" \
    "FRED_API_KEY=fred-api-key:latest,ECOS_API_KEY=ecos-api-key:latest,FIREBASE_CREDENTIALS=firebase-key:latest" \
    "-m,jobs.monthly_regime_calc"

echo ""
echo "  Phase 3 완료 — Job 4개"

# ──────────────────────────────────────────────
# Phase 4: Cloud Scheduler 4개
# ──────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Phase 4: Cloud Scheduler 4개 등록"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

create_schedule() {
    local NAME=$1 CRON=$2 JOB=$3 TIMEOUT=$4
    local URI="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/${JOB}:run"

    gcloud scheduler jobs create http "${NAME}" \
        --location="${REGION}" --schedule="${CRON}" --time-zone="${TIMEZONE}" \
        --uri="${URI}" --http-method=POST \
        --oauth-service-account-email="${SCHED_SA}" \
        --attempt-deadline="${TIMEOUT}s" --quiet 2>/dev/null || \
    gcloud scheduler jobs update http "${NAME}" \
        --location="${REGION}" --schedule="${CRON}" --time-zone="${TIMEZONE}" \
        --uri="${URI}" --http-method=POST \
        --oauth-service-account-email="${SCHED_SA}" \
        --attempt-deadline="${TIMEOUT}s" --quiet

    echo "    ${NAME} -> ${CRON}"
}

create_schedule "axis-daily-macro-sched"   "0 6 * * *"   "axis-daily-macro"   "600"
create_schedule "axis-daily-options-sched" "30 6 * * *"  "axis-daily-options" "600"
create_schedule "axis-weekly-events-sched" "0 22 * * 0"  "axis-weekly-events" "900"
create_schedule "axis-monthly-regime-sched" "0 6 1 * *"  "axis-monthly-regime" "600"

echo ""
echo "  Phase 4 완료 — Scheduler 4개"

# ──────────────────────────────────────────────
# 완료 요약
# ──────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Axis v2 배포 완료"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  Cloud Run Jobs: 4개 (daily-macro, daily-options, weekly-events, monthly-regime)"
echo "  Scheduler:      4개 (06:00 / 06:30 / 일22:00 / 매월1일06:00 KST)"
echo ""
echo "  검증 명령:"
echo "    gcloud run jobs execute axis-daily-macro --region=${REGION} --wait"
echo "    gcloud run jobs executions list --job=axis-daily-macro --region=${REGION}"
echo ""
echo "  상세: docs/v2_roadmap/DEPLOY_V2.md"
echo ""
