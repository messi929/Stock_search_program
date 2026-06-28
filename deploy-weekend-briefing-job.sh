#!/bin/bash
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Axis — 주말 결산 브리핑 생성 Job 배포
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
# Job (메인 이미지, python -m jobs.weekend_briefing):
#   axis-weekend-briefing   일요일 22:00 KST — 주말 주요 소식 + 금요일 미국장 마감 →
#                           다음 거래일(월요일) 국내장 관전 브리핑 생성
#
# 기본은 **검수 큐 모드**(생성만, 발행 X) → /admin/marketing에서 검수 후 수동 발행.
# 완전 자동발행으로 전환하려면 아래 JOB_ARGS에 ,--publish 를 추가하고 재실행.
# (자동발행은 THREADS_ACCESS_TOKEN/THREADS_USER_ID 시크릿이 있어야 동작)
#
# 이미지는 daily 잡(deploy-threads-job.sh)과 동일(stock-screener)이므로, 이미지가
# 최신이면 --skip-build로 빠르게 Job/Scheduler만 갱신할 수 있다.
#
# 사용법:
#   chmod +x deploy-weekend-briefing-job.sh
#   ./deploy-weekend-briefing-job.sh                # 이미지 빌드 + Job + Scheduler 배포
#   ./deploy-weekend-briefing-job.sh --skip-build   # 이미지 빌드 생략(권장: 이미지 최신 시)

set -euo pipefail

PROJECT_ID="${GCP_PROJECT:-all-of-asset}"
REGION="asia-northeast3"
TIMEZONE="Asia/Seoul"
IMAGE_NAME="stock-screener"
JOB_NAME="axis-weekend-briefing"
SCHED_CRON="0 22 * * 0"   # 일요일 22:00 KST

# 검수 큐 모드(기본). 완전 자동발행은 끝에 ,--publish 추가.
JOB_ARGS="-m,jobs.weekend_briefing"

SKIP_BUILD=false
for arg in "$@"; do
    case $arg in
        --skip-build) SKIP_BUILD=true ;;
    esac
done

IMAGE="gcr.io/${PROJECT_ID}/${IMAGE_NAME}:latest"
PROJECT_NUMBER=$(gcloud projects describe "${PROJECT_ID}" --format="value(projectNumber)")
SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
# 스케줄러 OAuth SA — 이 프로젝트엔 App Engine이 없어 appspot SA가 없다.
# 기존 axis-* 스케줄러와 동일하게 compute SA를 사용한다.
SCHED_SA="${SA}"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  프로젝트: ${PROJECT_ID}  리전: ${REGION}"
echo "  Job:      ${JOB_NAME}  (${SCHED_CRON} ${TIMEZONE})"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

secret_exists() { gcloud secrets describe "$1" --project="${PROJECT_ID}" --quiet >/dev/null 2>&1; }

# ── 필수 시크릿 ───────────────────────────────
for s in firebase-key anthropic-api-key; do
    secret_exists "$s" || { echo "ERROR: 필수 시크릿 '$s' 없음"; exit 1; }
done

SECRETS="FIREBASE_CREDENTIALS=firebase-key:latest,ANTHROPIC_API_KEY=anthropic-api-key:latest"

# Threads 시크릿(있으면 주입 — 자동발행 모드용)
THREADS_READY=true
for s in THREADS_ACCESS_TOKEN THREADS_USER_ID; do
    if secret_exists "$s"; then echo "    ✓ $s"; else echo "    ✗ $s (없음)"; THREADS_READY=false; fi
done
if [ "$THREADS_READY" = true ]; then
    SECRETS="${SECRETS},THREADS_ACCESS_TOKEN=THREADS_ACCESS_TOKEN:latest,THREADS_USER_ID=THREADS_USER_ID:latest"
fi

# SA 시크릿 접근 권한
for s in firebase-key anthropic-api-key THREADS_ACCESS_TOKEN THREADS_USER_ID; do
    secret_exists "$s" && gcloud secrets add-iam-policy-binding "$s" \
        --member="serviceAccount:${SA}" --role="roles/secretmanager.secretAccessor" \
        --project="${PROJECT_ID}" --quiet >/dev/null 2>&1 || true
done

# ── 이미지 빌드 ───────────────────────────────
if [ "$SKIP_BUILD" = false ]; then
    echo ""; echo "  이미지 빌드..."
    gcloud builds submit --config=cloudbuild.yaml --project="${PROJECT_ID}" --quiet .
fi

# ── Cloud Run Job ─────────────────────────────
echo ""; echo "  Job 배포: ${JOB_NAME}  (args: ${JOB_ARGS})"
if gcloud run jobs describe "${JOB_NAME}" --region="${REGION}" --project="${PROJECT_ID}" --quiet >/dev/null 2>&1; then
    gcloud run jobs update "${JOB_NAME}" --image="${IMAGE}" --region="${REGION}" --project="${PROJECT_ID}" \
        --memory=1Gi --cpu=1 --task-timeout=600 --max-retries=1 \
        --set-secrets="${SECRETS}" --command="python" --args="${JOB_ARGS}" --quiet
    echo "    -> updated"
else
    gcloud run jobs create "${JOB_NAME}" --image="${IMAGE}" --region="${REGION}" --project="${PROJECT_ID}" \
        --memory=1Gi --cpu=1 --task-timeout=600 --max-retries=1 \
        --set-secrets="${SECRETS}" --command="python" --args="${JOB_ARGS}" --quiet
    echo "    -> created"
fi

# ── Cloud Scheduler ───────────────────────────
# 검수 큐 모드는 초안 생성만(무해)이라 스케줄러를 항상 생성한다.
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
if [ "$THREADS_READY" = false ]; then
    echo "  ℹ️ Threads 시크릿 미등록 — 검수 큐 모드(초안 생성만)로 동작."
    echo "     발행 버튼/자동발행은 THREADS_ACCESS_TOKEN/USER_ID 등록 후 활성화."
fi
echo "  수동 테스트:"
echo "    gcloud run jobs execute ${JOB_NAME} --region=${REGION} --project=${PROJECT_ID} --wait"
echo ""; echo "  완료."
