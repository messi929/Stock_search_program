# Stock Screener Pro — 배포 가이드

> v6.1 (2026-04-10) | Cloud Run + Cloud Scheduler

---

## 1. 웹 서비스 배포 (Cloud Run)

### 빌드 + 배포 (한 줄)

```bash
gcloud builds submit --config=cloudbuild.yaml
```

### 수동 배포 (이미지 빌드 후)

```bash
# 이미지 빌드
docker build -t gcr.io/stock-search-program/stock-screener .

# 푸시
docker push gcr.io/stock-search-program/stock-screener

# 배포
gcloud run deploy stock-screener \
  --image=gcr.io/stock-search-program/stock-screener \
  --region=asia-northeast3 \
  --memory=1Gi --cpu=1 \
  --min-instances=1 --max-instances=3 \
  --timeout=3600 \
  --allow-unauthenticated \
  --set-env-vars="RUN_MODE=server,COLLECT_MODE=readonly" \
  --set-secrets="FIREBASE_CREDENTIALS=firebase-key:latest,ADMIN_KEY=admin-key:latest"
```

### 배포 확인

```bash
gcloud run services describe stock-screener --region=asia-northeast3 --format='value(status.url)'
# → https://stock-screener-119320994983.asia-northeast3.run.app
```

---

## 2. 수집기 배포 (Cloud Run Jobs)

### 전체 배포 (스크립트)

```bash
chmod +x deploy-cloud-jobs.sh
./deploy-cloud-jobs.sh
```

### 개별 Job 업데이트

```bash
# 이미지 빌드
gcloud builds submit --config=cloudbuild-collector.yaml

# Heavy Job 업데이트
gcloud run jobs update collector-heavy \
  --region=asia-northeast3 \
  --image=gcr.io/stock-search-program/stock-collector \
  --memory=2Gi --cpu=1 --task-timeout=900

# Light-KR Job 업데이트
gcloud run jobs update collector-light-kr \
  --region=asia-northeast3 \
  --image=gcr.io/stock-search-program/stock-collector \
  --memory=1Gi --cpu=1 --task-timeout=300
```

### 수동 실행 테스트

```bash
gcloud run jobs execute collector-heavy --region=asia-northeast3 --wait
```

---

## 3. 커스텀 도메인 + HTTPS

### 방법 A: Cloud Run 도메인 매핑 (권장)

```bash
# 1) 도메인 소유권 확인 (GCP 콘솔에서 TXT 레코드 추가)
# https://console.cloud.google.com/run/domains

# 2) 도메인 매핑
gcloud beta run domain-mappings create \
  --service=stock-screener \
  --domain=screener.yourdomain.com \
  --region=asia-northeast3

# 3) DNS 설정
# CNAME: screener.yourdomain.com → ghs.googlehosted.com.
# 또는 A 레코드: Google이 제공하는 IP 주소
```

HTTPS는 Cloud Run이 자동 제공 (Let's Encrypt).

### 방법 B: Cloudflare Proxy (빠른 설정)

1. Cloudflare에 도메인 추가
2. DNS에 CNAME 레코드 추가: `screener` → `stock-screener-119320994983.asia-northeast3.run.app`
3. Proxy 활성화 (주황색 구름)
4. SSL/TLS → Full (strict)

장점: CDN 캐싱, DDoS 보호, 무료 SSL, 한국 PoP

### 방법 C: Firebase Hosting (리다이렉트)

```json
// firebase.json
{
  "hosting": {
    "public": "public",
    "rewrites": [{
      "source": "**",
      "run": {
        "serviceId": "stock-screener",
        "region": "asia-northeast3"
      }
    }]
  }
}
```

```bash
firebase deploy --only hosting
```

---

## 4. 환경변수

| 변수 | 값 | 설명 |
|------|-----|------|
| `RUN_MODE` | `server` | 서버 모드 |
| `COLLECT_MODE` | `readonly` | Cloud Run에서 크롤링 비활성화 |
| `PORT` | `8501` | 서버 포트 |
| `ADMIN_KEY` | Secret Manager | 관리자 키 |
| `FIREBASE_CREDENTIALS` | Secret Manager | Firebase 서비스 계정 JSON |
| `AUTH_ENABLED` | `false` | 인증 비활성화 (상용화 전) |
| `CLOUD_RUN_URL` | `https://stock-screener-...` | Collector가 reload 호출할 URL |

---

## 5. Cloud Scheduler (20개 cron)

| 유형 | 시간 (KST) | 간격 | Job |
|------|-----------|------|-----|
| Heavy | 06:30, 09:30, 16:00, 22:30 | 4회/일 | collector-heavy |
| Light KR | 10:00~15:00 | 30분 | collector-light-kr |
| Light US | 00:00~05:00 | 60분 | collector-light-us |

---

## 6. v6.1 변경사항 배포 체크리스트

```
[ ] gcloud builds submit --config=cloudbuild.yaml         # 웹 서비스
[ ] gcloud builds submit --config=cloudbuild-collector.yaml # 수집기
[ ] gcloud run jobs update collector-heavy ...             # Heavy Job (히스토리 확대)
[ ] gcloud run jobs update collector-light-kr ...          # Light-KR
[ ] gcloud run jobs execute collector-heavy --wait         # 테스트 실행
[ ] 브라우저에서 UI 확인
```
