#!/bin/bash
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Axis — 밸류에이션 밴드 백필 Job 배포 (1b/1c)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
# Job (메인 이미지, python -m jobs.backfill_fundamental_band):
#   axis-fundamental-band   토요일 15:00 KST — KR 시총 상위 300 PER/PBR 역사 밴드 + EPS
#                           사이클을 pykrx에서 당겨 Firestore fundamental_band/{ticker} 적재
#
# ⚠️ KRX 펀더멘탈(PER/PBR/EPS)은 **로그인 인증 필수**(KRX가 변경) → pykrx>=1.2.8 +
#    KRX_ID/KRX_PW 시크릿 주입 없으면 빈 응답 → 가드 조기중단(데이터 0건).
# ⚠️ 야간점검 시에도 빈 응답 → 낮 시간 스케줄(토 15:00 KST). 초반 연속 빈 응답이면 조기 중단.
#
# 이미지는 daily 잡과 동일(stock-screener)이므로, 이미지가 최신이면 --skip-build 권장.
#
# 사용법:
#   chmod +x deploy-fundamental-band-job.sh
#   ./deploy-fundamental-band-job.sh                # 이미지 빌드 + Job + Scheduler
#   ./deploy-fundamental-band-job.sh --skip-build   # 이미지 빌드 생략(권장)

set -euo pipefail

PROJECT_ID="${GCP_PROJECT:-all-of-asset}"
REGION="asia-northeast3"
TIMEZONE="Asia/Seoul"
IMAGE_NAME="stock-screener"
JOB_NAME="axis-fundamental-band"
SCHED_CRON="0 15 * * 6"   # 토요일 15:00 KST (KRX 운영시간·야간점검 회피)

# --years 3 --sleep 0.5: 인증 KRX 펀더멘탈 fetch가 종목당 ~12초(5년)로 무거워 5년·300종목이면
# 30분 초과. 3년 히스토리(밴드 분위수엔 740거래일로 충분)+sleep 단축 → ~40분 내 완주(타임아웃 60분).
JOB_ARGS="-m,jobs.backfill_fundamental_band,--years,3,--sleep,0.5"

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

secret_exists() { gcloud secrets describe "$1" --project="${PROJECT_ID}" --quiet >/dev/null 2>&1; }

# krx-id/krx-pw = pykrx 1.2.8 KRX 로그인(펀더멘탈 데이터 인증 필수).
for s in firebase-key anthropic-api-key krx-id krx-pw; do
    secret_exists "$s" || { echo "ERROR: 필수 시크릿 '$s' 없음"; exit 1; }
done
SECRETS="FIREBASE_CREDENTIALS=firebase-key:latest,ANTHROPIC_API_KEY=anthropic-api-key:latest,KRX_ID=krx-id:latest,KRX_PW=krx-pw:latest"

for s in firebase-key anthropic-api-key krx-id krx-pw; do
    gcloud secrets add-iam-policy-binding "$s" \
        --member="serviceAccount:${SA}" --role="roles/secretmanager.secretAccessor" \
        --project="${PROJECT_ID}" --quiet >/dev/null 2>&1 || true
done

if [ "$SKIP_BUILD" = false ]; then
    echo ""; echo "  이미지 빌드..."
    gcloud builds submit --config=cloudbuild.yaml --project="${PROJECT_ID}" --quiet .
fi

# ── Cloud Run Job ─────────────────────────────
# 인증 KRX 펀더멘탈 fetch ~12초/종목(5년) → 3년·300종목 ≈ 40분. 타임아웃 60분, 재시도 0
# (끝에서 일괄 저장 구조라 중도 타임아웃 시 손실 → 넉넉히).
TASK_TIMEOUT=3600
MAX_RETRIES=0
echo ""; echo "  Job 배포: ${JOB_NAME}  (args: ${JOB_ARGS})"
if gcloud run jobs describe "${JOB_NAME}" --region="${REGION}" --project="${PROJECT_ID}" --quiet >/dev/null 2>&1; then
    gcloud run jobs update "${JOB_NAME}" --image="${IMAGE}" --region="${REGION}" --project="${PROJECT_ID}" \
        --memory=1Gi --cpu=1 --task-timeout="${TASK_TIMEOUT}" --max-retries="${MAX_RETRIES}" \
        --set-secrets="${SECRETS}" --command="python" --args="${JOB_ARGS}" --quiet
    echo "    -> updated"
else
    gcloud run jobs create "${JOB_NAME}" --image="${IMAGE}" --region="${REGION}" --project="${PROJECT_ID}" \
        --memory=1Gi --cpu=1 --task-timeout="${TASK_TIMEOUT}" --max-retries="${MAX_RETRIES}" \
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
    --attempt-deadline="1800s" --quiet 2>/dev/null || \
gcloud scheduler jobs update http "${JOB_NAME}-sched" \
    --location="${REGION}" --project="${PROJECT_ID}" \
    --schedule="${SCHED_CRON}" --time-zone="${TIMEZONE}" \
    --uri="${URI}" --http-method=POST \
    --oauth-service-account-email="${SCHED_SA}" \
    --attempt-deadline="1800s" --quiet

echo ""
echo "  최초 백필(낮 시간 수동 1회 권장):"
echo "    gcloud run jobs execute ${JOB_NAME} --region=${REGION} --project=${PROJECT_ID} --wait"
echo ""; echo "  완료."
