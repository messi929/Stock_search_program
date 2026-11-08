#!/bin/bash
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Axis — 매크로 일정 자동 갱신 Job 배포
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
# Job (메인 이미지, python -m jobs.macro_calendar_sync):
#   axis-macro-calendar   월요일 05:00 KST — FOMC·금통위·CPI·고용·GDP 일정을 공식 출처에서
#                         받아 Firestore config/macro_calendar 갱신. 서비스는 6시간 캐시로 읽음.
#
# ⚠️ 출처 하나라도 실패하면 잡이 실패(exit 1)로 끝난다 — 기존 일정은 유지되므로 서비스 영향은
#    없지만, 실패가 계속되면 페이지 구조 변경을 의심하고 파서를 손볼 것.
#
# 사용법:
#   ./deploy-macro-calendar-job.sh                # 이미지 빌드 + Job + Scheduler
#   ./deploy-macro-calendar-job.sh --skip-build   # 이미지가 최신이면(권장)

set -euo pipefail

# Windows Git Bash에서 gcloud 셸 스크립트가 python을 못 찾으면 GCLOUD_BIN=gcloud.cmd 로 실행
if [ -n "${GCLOUD_BIN:-}" ]; then
    gcloud() { "${GCLOUD_BIN}" "$@"; }
fi

PROJECT_ID="${GCP_PROJECT:-all-of-asset}"
REGION="asia-northeast3"
TIMEZONE="Asia/Seoul"
IMAGE_NAME="stock-screener"
JOB_NAME="axis-macro-calendar"
SCHED_CRON="0 5 * * 1"   # 월요일 05:00 KST
JOB_ARGS="-m,jobs.macro_calendar_sync"

SKIP_BUILD=false
for arg in "$@"; do
    case $arg in
        --skip-build) SKIP_BUILD=true ;;
    esac
done

IMAGE="gcr.io/${PROJECT_ID}/${IMAGE_NAME}:latest"
PROJECT_NUMBER=$(gcloud projects describe "${PROJECT_ID}" --format="value(projectNumber)")
SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
SCHED_SA="${SA}"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  프로젝트: ${PROJECT_ID}  리전: ${REGION}"
echo "  Job:      ${JOB_NAME}  (${SCHED_CRON} ${TIMEZONE})"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

for s in firebase-key fred-api-key; do
    gcloud secrets describe "$s" --project="${PROJECT_ID}" --quiet >/dev/null 2>&1 \
        || { echo "ERROR: 필수 시크릿 '$s' 없음"; exit 1; }
done
SECRETS="FIREBASE_CREDENTIALS=firebase-key:latest,FRED_API_KEY=fred-api-key:latest"

if [ "$SKIP_BUILD" = false ]; then
    echo ""; echo "  이미지 빌드..."
    gcloud builds submit --config=cloudbuild.yaml --project="${PROJECT_ID}" --quiet .
fi

# ── Cloud Run Job ─────────────────────────────
echo ""; echo "  Job 배포: ${JOB_NAME}"
if gcloud run jobs describe "${JOB_NAME}" --region="${REGION}" --project="${PROJECT_ID}" --quiet >/dev/null 2>&1; then
    gcloud run jobs update "${JOB_NAME}" --image="${IMAGE}" --region="${REGION}" --project="${PROJECT_ID}" \
        --memory=512Mi --cpu=1 --task-timeout=300 --max-retries=1 \
        --set-secrets="${SECRETS}" --command="python" --args="${JOB_ARGS}" --quiet
    echo "    -> updated"
else
    gcloud run jobs create "${JOB_NAME}" --image="${IMAGE}" --region="${REGION}" --project="${PROJECT_ID}" \
        --memory=512Mi --cpu=1 --task-timeout=300 --max-retries=1 \
        --set-secrets="${SECRETS}" --command="python" --args="${JOB_ARGS}" --quiet
    echo "    -> created"
fi

# ── Cloud Scheduler ───────────────────────────
URI="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/${JOB_NAME}:run"
echo ""; echo "  Scheduler 등록: ${JOB_NAME}-sched -> ${SCHED_CRON}"
gcloud scheduler jobs create http "${JOB_NAME}-sched" \
    --location="${REGION}" --project="${PROJECT_ID}" \
    --schedule="${SCHED_CRON}" --time-zone="${TIMEZONE}" \
    --uri="${URI}" --http-method=POST \
    --oauth-service-account-email="${SCHED_SA}" \
    --attempt-deadline="600s" --quiet 2>/dev/null || \
gcloud scheduler jobs update http "${JOB_NAME}-sched" \
    --location="${REGION}" --project="${PROJECT_ID}" \
    --schedule="${SCHED_CRON}" --time-zone="${TIMEZONE}" \
    --uri="${URI}" --http-method=POST \
    --oauth-service-account-email="${SCHED_SA}" \
    --attempt-deadline="600s" --quiet

echo ""
echo "  최초 1회 실행:"
echo "    gcloud run jobs execute ${JOB_NAME} --region=${REGION} --project=${PROJECT_ID} --wait"
echo ""; echo "  완료."
