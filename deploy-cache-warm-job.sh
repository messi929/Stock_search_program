#!/bin/bash
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Axis — 인기종목 사전 캐시 워밍 Job 배포
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
# Job: axis-cache-warm  (메인 이미지, python -m jobs.cache_warm)
#   인기종목 N개를 데이터 갱신 직후 미리 분석 → L2 응답 캐시 워밍.
#   사용자 첫 분석이 cache hit → ~12s를 ~3-5s로 단축.
#
# ⚠️ 비용: 콜드 딥다이브 1건 ~175원. 스케줄러를 켜면 평일 2회 자동 과금이 발생한다.
#   그래서 기본은 Job만 배포(수동 테스트용)하고, --schedule 플래그를 줄 때만
#   Cloud Scheduler를 생성한다(자동 과금 옵트인).
#
# 사용법:
#   chmod +x deploy-cache-warm-job.sh
#   ./deploy-cache-warm-job.sh                  # 이미지 빌드 + Job 배포(스케줄러 X)
#   ./deploy-cache-warm-job.sh --skip-build     # 이미지 빌드 생략
#   ./deploy-cache-warm-job.sh --schedule       # + Cloud Scheduler 생성(자동 과금 시작)
#
# 수동 테스트(과금 없음 — 종목 선정만):
#   gcloud run jobs execute axis-cache-warm --region=asia-northeast3 --project=all-of-asset \
#     --args="-m,jobs.cache_warm,--dry-run" --wait

set -euo pipefail

PROJECT_ID="${GCP_PROJECT:-all-of-asset}"
REGION="asia-northeast3"
TIMEZONE="Asia/Seoul"
IMAGE_NAME="stock-screener"

SKIP_BUILD=false
WITH_SCHEDULE=false
for arg in "$@"; do
    case $arg in
        --skip-build) SKIP_BUILD=true ;;
        --schedule)   WITH_SCHEDULE=true ;;
    esac
done

IMAGE="gcr.io/${PROJECT_ID}/${IMAGE_NAME}:latest"
PROJECT_NUMBER=$(gcloud projects describe "${PROJECT_ID}" --format="value(projectNumber)")
SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
SCHED_SA="${PROJECT_ID}@appspot.gserviceaccount.com"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  프로젝트: ${PROJECT_ID}  리전: ${REGION}"
echo "  이미지:   ${IMAGE}"
echo "  스케줄러: $([ "$WITH_SCHEDULE" = true ] && echo '생성(자동 과금)' || echo '건너뜀(수동 테스트)')"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── Secret 확인 ───────────────────────────────
secret_exists() { gcloud secrets describe "$1" --project="${PROJECT_ID}" --quiet >/dev/null 2>&1; }

for s in firebase-key anthropic-api-key; do
    if ! secret_exists "$s"; then
        echo "ERROR: 필수 시크릿 '$s' 없음"; exit 1
    fi
    gcloud secrets add-iam-policy-binding "$s" \
        --member="serviceAccount:${SA}" --role="roles/secretmanager.secretAccessor" \
        --project="${PROJECT_ID}" --quiet >/dev/null 2>&1 || true
done

SECRETS="FIREBASE_CREDENTIALS=firebase-key:latest,ANTHROPIC_API_KEY=anthropic-api-key:latest"

# ── 이미지 빌드 ───────────────────────────────
if [ "$SKIP_BUILD" = false ]; then
    echo ""; echo "  이미지 빌드..."
    gcloud builds submit --config=cloudbuild.yaml --project="${PROJECT_ID}" --quiet .
fi

# ── Cloud Run Job ─────────────────────────────
NAME="axis-cache-warm"
echo ""; echo "  Job 배포: ${NAME}"
if gcloud run jobs describe "${NAME}" --region="${REGION}" --project="${PROJECT_ID}" --quiet >/dev/null 2>&1; then
    gcloud run jobs update "${NAME}" --image="${IMAGE}" --region="${REGION}" --project="${PROJECT_ID}" \
        --memory=2Gi --cpu=1 --task-timeout=1800 --max-retries=0 \
        --set-secrets="${SECRETS}" \
        --command="python" --args="-m,jobs.cache_warm" --quiet
    echo "    -> updated"
else
    gcloud run jobs create "${NAME}" --image="${IMAGE}" --region="${REGION}" --project="${PROJECT_ID}" \
        --memory=2Gi --cpu=1 --task-timeout=1800 --max-retries=0 \
        --set-secrets="${SECRETS}" \
        --command="python" --args="-m,jobs.cache_warm" --quiet
    echo "    -> created"
fi

# ── Cloud Scheduler (--schedule 일 때만) ───────
# 데이터 갱신(collector 08:00 / 17:30 KST) 직후 워밍 → 신선한 스냅샷 키로 적재.
create_schedule() {
    local SNAME=$1 CRON=$2
    local URI="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/${NAME}:run"
    gcloud scheduler jobs create http "${SNAME}" \
        --location="${REGION}" --project="${PROJECT_ID}" \
        --schedule="${CRON}" --time-zone="${TIMEZONE}" \
        --uri="${URI}" --http-method=POST \
        --oauth-service-account-email="${SCHED_SA}" \
        --attempt-deadline="1800s" --quiet 2>/dev/null || \
    gcloud scheduler jobs update http "${SNAME}" \
        --location="${REGION}" --project="${PROJECT_ID}" \
        --schedule="${CRON}" --time-zone="${TIMEZONE}" \
        --uri="${URI}" --http-method=POST \
        --oauth-service-account-email="${SCHED_SA}" \
        --attempt-deadline="1800s" --quiet
    echo "    ${SNAME} -> ${CRON}"
}

if [ "$WITH_SCHEDULE" = true ]; then
    echo ""; echo "  Scheduler 등록 (평일 데이터 갱신 직후)"
    create_schedule "axis-cache-warm-morning"   "30 8 * * 1-5"
    create_schedule "axis-cache-warm-afternoon" "0 18 * * 1-5"
    echo ""
    echo "  ⚠️ 자동 과금 활성화됨 — 평일 08:30 / 18:00 KST 워밍."
    echo "     중단: gcloud scheduler jobs delete axis-cache-warm-morning axis-cache-warm-afternoon --location=${REGION}"
else
    echo ""
    echo "  ℹ️ 스케줄러 건너뜀(자동 과금 비활성). 켜려면 --schedule 플래그로 재실행."
    echo "     dry-run 테스트(과금 없음):"
    echo "       gcloud run jobs execute ${NAME} --region=${REGION} --project=${PROJECT_ID} --args='-m,jobs.cache_warm,--dry-run' --wait"
fi

echo ""; echo "  완료."
