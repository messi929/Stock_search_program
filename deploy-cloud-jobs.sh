#!/bin/bash
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Stock Screener Pro — Cloud Scheduler + Cloud Run Job 배포
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
# 사전 준비:
#   1. gcloud auth login
#   2. gcloud config set project YOUR_PROJECT_ID
#   3. Secret Manager에 시크릿 등록:
#      gcloud secrets create firebase-credentials --data-file=YOUR_KEY.json
#      gcloud secrets create admin-key --data-file=-  (echo "YOUR_KEY")
#      gcloud secrets create telegram-bot-token --data-file=-
#      gcloud secrets create telegram-chat-id --data-file=-
#   4. collector 이미지 빌드:
#      gcloud builds submit --config=cloudbuild-collector.yaml
#
# 사용법:
#   chmod +x deploy-cloud-jobs.sh
#   ./deploy-cloud-jobs.sh

set -e

PROJECT_ID=$(gcloud config get-value project)
REGION="asia-northeast3"
TIMEZONE="Asia/Seoul"

echo "=== Cloud Scheduler 배포 시작 ==="
echo "프로젝트: ${PROJECT_ID}"
echo "리전: ${REGION}"
echo ""

# ──────────────────────────────────────────────
# Heavy 스케줄 (4회/일) — 전체 수집
# ──────────────────────────────────────────────

HEAVY_TIMES=("30 6" "30 9" "0 16" "30 22")
HEAVY_NAMES=("0630-us-close" "0930-kr-open" "1600-kr-close" "2230-us-open")

for i in "${!HEAVY_TIMES[@]}"; do
    CRON="${HEAVY_TIMES[$i]} * * 1-5"  # 평일만
    NAME="collector-heavy-${HEAVY_NAMES[$i]}"

    echo "  [heavy] ${NAME} → cron: ${CRON}"
    gcloud scheduler jobs create http "${NAME}" \
        --location="${REGION}" \
        --schedule="${CRON}" \
        --time-zone="${TIMEZONE}" \
        --uri="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/collector-heavy:run" \
        --http-method=POST \
        --oauth-service-account-email="${PROJECT_ID}@appspot.gserviceaccount.com" \
        --attempt-deadline=900s \
        --quiet 2>/dev/null || \
    gcloud scheduler jobs update http "${NAME}" \
        --location="${REGION}" \
        --schedule="${CRON}" \
        --time-zone="${TIMEZONE}" \
        --uri="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/collector-heavy:run" \
        --http-method=POST \
        --oauth-service-account-email="${PROJECT_ID}@appspot.gserviceaccount.com" \
        --attempt-deadline=900s \
        --quiet
done

# ──────────────────────────────────────────────
# Light KR 스케줄 (10회/일) — KR 장중 스냅샷
# ──────────────────────────────────────────────

LIGHT_KR_TIMES=("0 10" "30 10" "0 11" "30 11" "0 12" "0 13" "30 13" "0 14" "30 14" "0 15")
LIGHT_KR_NAMES=("1000" "1030" "1100" "1130" "1200" "1300" "1330" "1400" "1430" "1500")

for i in "${!LIGHT_KR_TIMES[@]}"; do
    CRON="${LIGHT_KR_TIMES[$i]} * * 1-5"
    NAME="collector-light-kr-${LIGHT_KR_NAMES[$i]}"

    echo "  [light_kr] ${NAME} → cron: ${CRON}"
    gcloud scheduler jobs create http "${NAME}" \
        --location="${REGION}" \
        --schedule="${CRON}" \
        --time-zone="${TIMEZONE}" \
        --uri="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/collector-light-kr:run" \
        --http-method=POST \
        --oauth-service-account-email="${PROJECT_ID}@appspot.gserviceaccount.com" \
        --attempt-deadline=300s \
        --quiet 2>/dev/null || \
    gcloud scheduler jobs update http "${NAME}" \
        --location="${REGION}" \
        --schedule="${CRON}" \
        --time-zone="${TIMEZONE}" \
        --uri="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/collector-light-kr:run" \
        --http-method=POST \
        --oauth-service-account-email="${PROJECT_ID}@appspot.gserviceaccount.com" \
        --attempt-deadline=300s \
        --quiet
done

# ──────────────────────────────────────────────
# Light US 스케줄 (6회/일) — US 장중 스냅샷
# ──────────────────────────────────────────────

LIGHT_US_TIMES=("0 0" "0 1" "0 2" "0 3" "0 4" "0 5")
LIGHT_US_NAMES=("0000" "0100" "0200" "0300" "0400" "0500")

for i in "${!LIGHT_US_TIMES[@]}"; do
    CRON="${LIGHT_US_TIMES[$i]} * * 1-6"  # 월~토 (US 장은 KST 기준 화~토 새벽)
    NAME="collector-light-us-${LIGHT_US_NAMES[$i]}"

    echo "  [light_us] ${NAME} → cron: ${CRON}"
    gcloud scheduler jobs create http "${NAME}" \
        --location="${REGION}" \
        --schedule="${CRON}" \
        --time-zone="${TIMEZONE}" \
        --uri="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/collector-light-us:run" \
        --http-method=POST \
        --oauth-service-account-email="${PROJECT_ID}@appspot.gserviceaccount.com" \
        --attempt-deadline=300s \
        --quiet 2>/dev/null || \
    gcloud scheduler jobs update http "${NAME}" \
        --location="${REGION}" \
        --schedule="${CRON}" \
        --time-zone="${TIMEZONE}" \
        --uri="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/collector-light-us:run" \
        --http-method=POST \
        --oauth-service-account-email="${PROJECT_ID}@appspot.gserviceaccount.com" \
        --attempt-deadline=300s \
        --quiet
done

echo ""
echo "=== 배포 완료 ==="
echo "Heavy 스케줄: ${#HEAVY_TIMES[@]}개"
echo "Light KR: ${#LIGHT_KR_TIMES[@]}개"
echo "Light US: ${#LIGHT_US_TIMES[@]}개"
echo "합계: $((${#HEAVY_TIMES[@]} + ${#LIGHT_KR_TIMES[@]} + ${#LIGHT_US_TIMES[@]}))개"
echo ""
echo "확인: gcloud scheduler jobs list --location=${REGION}"
