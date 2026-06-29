#!/bin/bash
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Axis — 매일 스레드 콘텐츠 생성 Job 배포
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
# Job (메인 이미지, python -m jobs.daily_threads_content):
#   axis-threads-daily    화~토 07:30 KST — 새벽 미국장 브리핑만 생성(검수 큐)
#
# 스케줄=화~토(2-6): 간밤 미국 세션이 있는 아침만. 미국은 주말 휴장이라 KST 월·일 아침엔
#   직전 세션이 없음(월요일 국내장 길잡이는 일요일밤 주말 브리핑이 담당). 브리핑 코드에도
#   신선도 가드가 있어 미 공휴일 직후엔 자동 생략.
# 종목글(--stocks)은 자동 생성에서 제외(JEON 수동 운영) — 코드는 남아 있어 수동 실행 시
#   `--stocks N`으로 생성 가능. 검수 큐 모드(생성만)라 무해. 자동발행은 끝에 ,--publish.
#
# 사용법:
#   chmod +x deploy-threads-job.sh
#   ./deploy-threads-job.sh                # 이미지 빌드 + Job + Scheduler 배포
#   ./deploy-threads-job.sh --skip-build   # 이미지 빌드 생략
#
# Threads 시크릿 등록(자동발행 쓸 때만, 최초 1회):
#   printf '%s' "<장기토큰>"  | gcloud secrets create THREADS_ACCESS_TOKEN --data-file=- --project all-of-asset
#   printf '%s' "<user_id숫자>" | gcloud secrets create THREADS_USER_ID    --data-file=- --project all-of-asset
#   (값/절차: API_KEYS.local.txt 11번 · docs/axis/THREADS_PUBLISHING.md)

set -euo pipefail

PROJECT_ID="${GCP_PROJECT:-all-of-asset}"
REGION="asia-northeast3"
TIMEZONE="Asia/Seoul"
IMAGE_NAME="stock-screener"
JOB_NAME="axis-threads-daily"
SCHED_CRON="30 7 * * 2-6"   # 화~토 07:30 KST (간밤 미국 세션이 있는 아침만)

# 브리핑 전용(--stocks 0). 종목글은 수동 운영. 검수 큐 모드(생성만), 자동발행은 끝에 ,--publish.
JOB_ARGS="-m,jobs.daily_threads_content,--stocks,0"

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
