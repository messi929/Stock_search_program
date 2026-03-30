#!/bin/bash
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Stock Screener Pro — 클라우드 수집기 통합 배포
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
# 이 스크립트 하나로 전체 클라우드 수집 인프라를 배포합니다:
#   Phase 1: 사전 검증 (gcloud 인증, 프로젝트, API, 시크릿)
#   Phase 2: collector 이미지 빌드 + 푸시
#   Phase 3: Cloud Run Job 3개 생성/업데이트
#   Phase 4: Cloud Scheduler 20개 cron 등록
#   Phase 5: 테스트 실행 (선택)
#
# 사용법:
#   chmod +x deploy-cloud-jobs.sh
#   ./deploy-cloud-jobs.sh              # 전체 배포
#   ./deploy-cloud-jobs.sh --skip-build # 이미지 빌드 생략 (Job+Scheduler만)
#   ./deploy-cloud-jobs.sh --test-only  # 테스트 실행만
#
# 사전 준비 (최초 1회):
#   gcloud auth login
#   gcloud config set project YOUR_PROJECT_ID
#
#   # Secret Manager 시크릿 등록
#   gcloud secrets create firebase-key --data-file=YOUR_FIREBASE_KEY.json
#   echo -n "YOUR_ADMIN_KEY" | gcloud secrets create admin-key --data-file=-
#   # (선택) 텔레그램 알림
#   echo -n "YOUR_BOT_TOKEN" | gcloud secrets create telegram-bot-token --data-file=-
#   echo -n "YOUR_CHAT_ID"   | gcloud secrets create telegram-chat-id --data-file=-

set -euo pipefail

# ──────────────────────────────────────────────
# 설정
# ──────────────────────────────────────────────
REGION="asia-northeast3"
TIMEZONE="Asia/Seoul"
IMAGE_NAME="stock-collector"

# 인자 파싱
SKIP_BUILD=false
TEST_ONLY=false
for arg in "$@"; do
    case $arg in
        --skip-build) SKIP_BUILD=true ;;
        --test-only)  TEST_ONLY=true ;;
    esac
done

# ──────────────────────────────────────────────
# Phase 1: 사전 검증
# ──────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Phase 1: 사전 검증"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# gcloud 인증 확인
ACCOUNT=$(gcloud config get-value account 2>/dev/null)
if [ -z "$ACCOUNT" ] || [ "$ACCOUNT" = "(unset)" ]; then
    echo "ERROR: gcloud 인증 필요 → gcloud auth login"
    exit 1
fi
echo "  계정: ${ACCOUNT}"

# 프로젝트 확인
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
if [ -z "$PROJECT_ID" ] || [ "$PROJECT_ID" = "(unset)" ]; then
    echo "ERROR: 프로젝트 미설정 → gcloud config set project YOUR_PROJECT_ID"
    exit 1
fi
echo "  프로젝트: ${PROJECT_ID}"
echo "  리전: ${REGION}"

IMAGE="gcr.io/${PROJECT_ID}/${IMAGE_NAME}"

# Cloud Run URL (프로젝트 번호 기반)
PROJECT_NUMBER=$(gcloud projects describe "${PROJECT_ID}" --format="value(projectNumber)" 2>/dev/null)
CLOUD_RUN_URL="https://stock-screener-${PROJECT_NUMBER}.${REGION}.run.app"
echo "  Cloud Run URL: ${CLOUD_RUN_URL}"

# 필수 API 활성화 확인
echo ""
echo "  API 활성화 확인 중..."
REQUIRED_APIS=("run.googleapis.com" "cloudscheduler.googleapis.com" "cloudbuild.googleapis.com" "secretmanager.googleapis.com")
for api in "${REQUIRED_APIS[@]}"; do
    if gcloud services list --enabled --format="value(config.name)" 2>/dev/null | grep -q "$api"; then
        echo "    $api"
    else
        echo "    $api 활성화 중..."
        gcloud services enable "$api" --quiet
        echo "    $api (활성화 완료)"
    fi
done

# 시크릿 확인
echo ""
echo "  Secret Manager 시크릿 확인..."
REQUIRED_SECRETS=("firebase-key" "admin-key")
OPTIONAL_SECRETS=("telegram-bot-token" "telegram-chat-id")
MISSING_REQUIRED=()

for secret in "${REQUIRED_SECRETS[@]}"; do
    if gcloud secrets describe "$secret" --quiet 2>/dev/null; then
        echo "    $secret"
    else
        MISSING_REQUIRED+=("$secret")
        echo "    $secret (미등록!)"
    fi
done

for secret in "${OPTIONAL_SECRETS[@]}"; do
    if gcloud secrets describe "$secret" --quiet 2>/dev/null; then
        echo "    $secret"
    else
        echo "    $secret (선택 — 미등록, 텔레그램 알림 비활성)"
    fi
done

if [ ${#MISSING_REQUIRED[@]} -gt 0 ]; then
    echo ""
    echo "ERROR: 필수 시크릿이 없습니다: ${MISSING_REQUIRED[*]}"
    echo "  등록 방법:"
    echo "    gcloud secrets create firebase-key --data-file=YOUR_KEY.json"
    echo "    echo -n 'YOUR_KEY' | gcloud secrets create admin-key --data-file=-"
    exit 1
fi

# 텔레그램 시크릿 존재 여부에 따라 SECRETS 문자열 결정
SECRETS_HEAVY="FIREBASE_CREDENTIALS=firebase-key:latest,ADMIN_KEY=admin-key:latest"
if gcloud secrets describe "telegram-bot-token" --quiet 2>/dev/null && \
   gcloud secrets describe "telegram-chat-id" --quiet 2>/dev/null; then
    SECRETS_HEAVY="${SECRETS_HEAVY},TELEGRAM_BOT_TOKEN=telegram-bot-token:latest,TELEGRAM_CHAT_ID=telegram-chat-id:latest"
fi
SECRETS_LIGHT="FIREBASE_CREDENTIALS=firebase-key:latest,ADMIN_KEY=admin-key:latest"

# 서비스 계정에 Secret 접근 권한 부여
SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
echo ""
echo "  서비스 계정 권한 확인: ${SA}"
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${SA}" \
    --role="roles/secretmanager.secretAccessor" \
    --condition=None --quiet 2>/dev/null || true

echo ""
echo "  Phase 1 완료"

if [ "$TEST_ONLY" = true ]; then
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  테스트 실행: collector-heavy"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    gcloud run jobs execute collector-heavy --region="${REGION}" --wait --quiet
    echo "  테스트 완료! Firestore 데이터 확인하세요."
    exit 0
fi

# ──────────────────────────────────────────────
# Phase 2: collector 이미지 빌드
# ──────────────────────────────────────────────
if [ "$SKIP_BUILD" = false ]; then
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  Phase 2: collector 이미지 빌드"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  이미지: ${IMAGE}"
    echo ""
    gcloud builds submit --config=cloudbuild-collector.yaml --quiet
    echo ""
    echo "  Phase 2 완료"
else
    echo ""
    echo "  Phase 2 스킵 (--skip-build)"
fi

# ──────────────────────────────────────────────
# Phase 3: Cloud Run Job 생성/업데이트
# ──────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Phase 3: Cloud Run Job 배포"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

deploy_job() {
    local NAME=$1 MEM=$2 TIMEOUT=$3 SEC=$4; shift 4
    local JOB_ARGS="$*"

    echo "  [job] ${NAME} (mem=${MEM}, timeout=${TIMEOUT}s, args=${JOB_ARGS})"

    if gcloud run jobs describe "${NAME}" --region="${REGION}" --quiet 2>/dev/null; then
        gcloud run jobs update "${NAME}" \
            --region="${REGION}" --image="${IMAGE}" \
            --memory="${MEM}" --cpu=1 \
            --task-timeout="${TIMEOUT}" --max-retries=1 \
            --set-env-vars="CLOUD_RUN_URL=${CLOUD_RUN_URL}" \
            --set-secrets="${SEC}" \
            --args="${JOB_ARGS}" --quiet
        echo "    -> updated"
    else
        gcloud run jobs create "${NAME}" \
            --region="${REGION}" --image="${IMAGE}" \
            --memory="${MEM}" --cpu=1 \
            --task-timeout="${TIMEOUT}" --max-retries=1 \
            --set-env-vars="CLOUD_RUN_URL=${CLOUD_RUN_URL}" \
            --set-secrets="${SEC}" \
            --args="${JOB_ARGS}" --quiet
        echo "    -> created"
    fi
}

deploy_job "collector-heavy"    "2Gi" "900" "${SECRETS_HEAVY}" "--all"
deploy_job "collector-light-kr"  "1Gi" "300" "${SECRETS_LIGHT}" "--kr-snapshot,--etf"
deploy_job "collector-light-us"  "1Gi" "300" "${SECRETS_LIGHT}" "--us-snapshot"

echo ""
echo "  Phase 3 완료 — Job 3개 배포됨"

# ──────────────────────────────────────────────
# Phase 4: Cloud Scheduler 등록
# ──────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Phase 4: Cloud Scheduler 등록"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

SA_EMAIL="${PROJECT_ID}@appspot.gserviceaccount.com"

create_schedule() {
    local NAME=$1 CRON=$2 JOB=$3 TIMEOUT=$4

    local URI="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/${JOB}:run"

    gcloud scheduler jobs create http "${NAME}" \
        --location="${REGION}" \
        --schedule="${CRON}" \
        --time-zone="${TIMEZONE}" \
        --uri="${URI}" \
        --http-method=POST \
        --oauth-service-account-email="${SA_EMAIL}" \
        --attempt-deadline="${TIMEOUT}s" \
        --quiet 2>/dev/null || \
    gcloud scheduler jobs update http "${NAME}" \
        --location="${REGION}" \
        --schedule="${CRON}" \
        --time-zone="${TIMEZONE}" \
        --uri="${URI}" \
        --http-method=POST \
        --oauth-service-account-email="${SA_EMAIL}" \
        --attempt-deadline="${TIMEOUT}s" \
        --quiet

    echo "    ${NAME} -> ${CRON}"
}

# Heavy 스케줄 (4회/일, 평일만)
echo ""
echo "  [Heavy] 전체 수집 — 평일 4회"
HEAVY_CRONS=("30 6 * * 1-5" "30 9 * * 1-5" "0 16 * * 1-5" "30 22 * * 1-5")
HEAVY_NAMES=("0630-us-close" "0930-kr-open" "1600-kr-close" "2230-us-open")
for i in "${!HEAVY_CRONS[@]}"; do
    create_schedule "collector-heavy-${HEAVY_NAMES[$i]}" "${HEAVY_CRONS[$i]}" "collector-heavy" "900"
done

# Light KR 스케줄 (10회/일, 장중 스냅샷)
echo ""
echo "  [Light KR] 장중 30분 간격 — 평일 10:00~15:00"
LIGHT_KR_TIMES=("0 10" "30 10" "0 11" "30 11" "0 12" "0 13" "30 13" "0 14" "30 14" "0 15")
LIGHT_KR_NAMES=("1000" "1030" "1100" "1130" "1200" "1300" "1330" "1400" "1430" "1500")
for i in "${!LIGHT_KR_TIMES[@]}"; do
    create_schedule "collector-light-kr-${LIGHT_KR_NAMES[$i]}" "${LIGHT_KR_TIMES[$i]} * * 1-5" "collector-light-kr" "300"
done

# Light US 스케줄 (6회/일, US 장중)
echo ""
echo "  [Light US] 60분 간격 — 월~토 00:00~05:00"
LIGHT_US_TIMES=("0 0" "0 1" "0 2" "0 3" "0 4" "0 5")
LIGHT_US_NAMES=("0000" "0100" "0200" "0300" "0400" "0500")
for i in "${!LIGHT_US_TIMES[@]}"; do
    create_schedule "collector-light-us-${LIGHT_US_NAMES[$i]}" "${LIGHT_US_TIMES[$i]} * * 1-6" "collector-light-us" "300"
done

TOTAL=$((${#HEAVY_CRONS[@]} + ${#LIGHT_KR_TIMES[@]} + ${#LIGHT_US_TIMES[@]}))
echo ""
echo "  Phase 4 완료 — Scheduler ${TOTAL}개 등록됨"

# ──────────────────────────────────────────────
# Phase 5: 테스트 실행 (heavy 1회)
# ──────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Phase 5: 테스트 실행"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
read -p "  collector-heavy Job을 지금 테스트 실행할까요? (y/N) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "  실행 중... (최대 15분 소요)"
    gcloud run jobs execute collector-heavy --region="${REGION}" --wait --quiet
    echo "  테스트 완료!"
else
    echo "  테스트 건너뜀. 수동 실행:"
    echo "    gcloud run jobs execute collector-heavy --region=${REGION} --wait"
fi

# ──────────────────────────────────────────────
# 완료 요약
# ──────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  배포 완료!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  Cloud Run Job:  3개 (heavy, light-kr, light-us)"
echo "  Scheduler:      ${TOTAL}개 (heavy 4 + light-kr 10 + light-us 6)"
echo "  Cloud Run URL:  ${CLOUD_RUN_URL}"
echo ""
echo "  확인 명령어:"
echo "    gcloud run jobs list --region=${REGION}"
echo "    gcloud scheduler jobs list --location=${REGION}"
echo "    gcloud run jobs executions list --job=collector-heavy --region=${REGION}"
echo ""
echo "  이제 로컬 PC 없이도 자동으로 데이터가 수집됩니다!"
echo ""
