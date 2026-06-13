#!/bin/bash
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Axis — 알림 발송 Job 배포 (이메일/Mailgun)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
# Job 2종 (둘 다 메인 이미지, python -m jobs.notify_send):
#   axis-notify-entry       --mode entry      장중 30분(09:00~15:30 KST 평일)
#   axis-notify-briefing    --mode briefing   아침 1회(07:00 KST 평일)
#
# Mailgun 시크릿(mailgun-api-key/domain/from)이 모두 있어야 스케줄러를 생성한다.
# 없으면 Job만 생성(수동 --dry-run 테스트용)하고 스케줄러는 건너뛴다 →
# 빈 발송 루프와 "시크릿 추가 시 백로그 일괄 발송" 사고를 방지.
#
# 사용법:
#   chmod +x deploy-notify-job.sh
#   ./deploy-notify-job.sh                # 이미지 빌드 + Job(+가능 시 Scheduler) 배포
#   ./deploy-notify-job.sh --skip-build   # 이미지 빌드 생략
#
# Mailgun 시크릿 등록(최초 1회, 도메인 DNS 인증 완료 후):
#   printf '%s' "<API_KEY>"  | gcloud secrets create mailgun-api-key --data-file=- --project all-of-asset
#   printf '%s' "mg.도메인"  | gcloud secrets create mailgun-domain  --data-file=- --project all-of-asset
#   printf '%s' "Axis <noreply@mg.도메인>" | gcloud secrets create mailgun-from --data-file=- --project all-of-asset

set -euo pipefail

PROJECT_ID="${GCP_PROJECT:-all-of-asset}"
REGION="asia-northeast3"
TIMEZONE="Asia/Seoul"
IMAGE_NAME="stock-screener"
APP_BASE_URL="${APP_BASE_URL:-https://axislytics.com}"

SKIP_BUILD=false
for arg in "$@"; do
    case $arg in
        --skip-build) SKIP_BUILD=true ;;
    esac
done

IMAGE="gcr.io/${PROJECT_ID}/${IMAGE_NAME}:latest"
PROJECT_NUMBER=$(gcloud projects describe "${PROJECT_ID}" --format="value(projectNumber)")
SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
SCHED_SA="${PROJECT_ID}@appspot.gserviceaccount.com"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  프로젝트: ${PROJECT_ID}  리전: ${REGION}"
echo "  이미지:   ${IMAGE}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── Secret 확인 ───────────────────────────────
secret_exists() { gcloud secrets describe "$1" --project="${PROJECT_ID}" --quiet >/dev/null 2>&1; }

if ! secret_exists firebase-key; then
    echo "ERROR: 필수 시크릿 'firebase-key' 없음"; exit 1
fi

SECRETS="FIREBASE_CREDENTIALS=firebase-key:latest"
MAILGUN_READY=true
for s in mailgun-api-key mailgun-domain mailgun-from; do
    if secret_exists "$s"; then
        echo "    ✓ $s"
    else
        echo "    ✗ $s (없음)"; MAILGUN_READY=false
    fi
done

if [ "$MAILGUN_READY" = true ]; then
    SECRETS="${SECRETS},MAILGUN_API_KEY=mailgun-api-key:latest,MAILGUN_DOMAIN=mailgun-domain:latest,MAILGUN_FROM=mailgun-from:latest"
fi

# SA 접근 권한 부여
for s in firebase-key mailgun-api-key mailgun-domain mailgun-from; do
    secret_exists "$s" && gcloud secrets add-iam-policy-binding "$s" \
        --member="serviceAccount:${SA}" --role="roles/secretmanager.secretAccessor" \
        --project="${PROJECT_ID}" --quiet >/dev/null 2>&1 || true
done

# ── 이미지 빌드 ───────────────────────────────
if [ "$SKIP_BUILD" = false ]; then
    echo ""; echo "  이미지 빌드..."
    gcloud builds submit --config=cloudbuild.yaml --project="${PROJECT_ID}" --quiet .
fi

# briefing 잡은 생성을 위해 ANTHROPIC_API_KEY 추가
BRIEF_SECRETS="${SECRETS},ANTHROPIC_API_KEY=anthropic-api-key:latest"
secret_exists anthropic-api-key && gcloud secrets add-iam-policy-binding anthropic-api-key \
    --member="serviceAccount:${SA}" --role="roles/secretmanager.secretAccessor" \
    --project="${PROJECT_ID}" --quiet >/dev/null 2>&1 || true

# ── Cloud Run Jobs ────────────────────────────
deploy_job() {
    local NAME=$1 SEC=$2 ARGS=$3 TIMEOUT=$4
    echo ""; echo "  Job 배포: ${NAME}"
    if gcloud run jobs describe "${NAME}" --region="${REGION}" --project="${PROJECT_ID}" --quiet >/dev/null 2>&1; then
        gcloud run jobs update "${NAME}" --image="${IMAGE}" --region="${REGION}" --project="${PROJECT_ID}" \
            --memory=1Gi --cpu=1 --task-timeout="${TIMEOUT}" --max-retries=1 \
            --set-secrets="${SEC}" --set-env-vars="APP_BASE_URL=${APP_BASE_URL}" \
            --command="python" --args="${ARGS}" --quiet
        echo "    -> updated"
    else
        gcloud run jobs create "${NAME}" --image="${IMAGE}" --region="${REGION}" --project="${PROJECT_ID}" \
            --memory=1Gi --cpu=1 --task-timeout="${TIMEOUT}" --max-retries=1 \
            --set-secrets="${SEC}" --set-env-vars="APP_BASE_URL=${APP_BASE_URL}" \
            --command="python" --args="${ARGS}" --quiet
        echo "    -> created"
    fi
}

deploy_job "axis-notify-entry"    "${SECRETS}"       "-m,jobs.notify_send"                  "600"
deploy_job "axis-notify-briefing" "${BRIEF_SECRETS}" "-m,jobs.notify_send,--mode,briefing"  "600"

# ── Cloud Scheduler (Mailgun 준비된 경우만) ────
create_schedule() {
    local NAME=$1 JOB=$2 CRON=$3
    local URI="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/${JOB}:run"
    gcloud scheduler jobs create http "${NAME}" \
        --location="${REGION}" --project="${PROJECT_ID}" \
        --schedule="${CRON}" --time-zone="${TIMEZONE}" \
        --uri="${URI}" --http-method=POST \
        --oauth-service-account-email="${SCHED_SA}" \
        --attempt-deadline="600s" --quiet 2>/dev/null || \
    gcloud scheduler jobs update http "${NAME}" \
        --location="${REGION}" --project="${PROJECT_ID}" \
        --schedule="${CRON}" --time-zone="${TIMEZONE}" \
        --uri="${URI}" --http-method=POST \
        --oauth-service-account-email="${SCHED_SA}" \
        --attempt-deadline="600s" --quiet
    echo "    ${NAME} -> ${CRON}"
}

if [ "$MAILGUN_READY" = true ]; then
    echo ""; echo "  Scheduler 등록"
    create_schedule "axis-notify-entry-sched"    "axis-notify-entry"    "*/30 9-15 * * 1-5"
    create_schedule "axis-notify-briefing-sched" "axis-notify-briefing" "0 7 * * 1-5"
else
    echo ""
    echo "  ⚠️ Mailgun 시크릿 미완성 — Scheduler 건너뜀(자동 발송 비활성)."
    echo "     시크릿 3개 등록 후 이 스크립트를 다시 실행하면 스케줄러가 생성됩니다."
    echo "     수동 테스트:"
    echo "       gcloud run jobs execute axis-notify-briefing --region=${REGION} --project=${PROJECT_ID} --wait"
fi

echo ""; echo "  완료."
