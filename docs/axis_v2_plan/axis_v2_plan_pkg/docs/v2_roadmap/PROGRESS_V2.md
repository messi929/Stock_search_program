# Axis v2 — 6 Persona Expansion 진척 기록

> **브랜치**: `feature/v2-six-personas` (axis-ai-layer에서 분기, 2026-05-02)
> **현재 위치**: Week A Day 4 진행 중

---

## 📅 Week A — 한국 시장 데이터 인프라

### Day 1 — 외국인/기관 수급 백필 ✅ (commit `47cc967`)

| 산출물 | 비고 |
|--------|------|
| `utils/data_collectors/korea_supply.py` | KoreaSupplyCollector — 방식A(일자×시장×4투자자) + 방식B(종목별 5년 외국인 보유) |
| `jobs/backfill_korea_supply.py` | CLI Job (sample/full/dry-run) — KOSPI 시총 상위 sample 자동 선정 |
| `tests/data_collectors/test_korea_supply.py` | 23 테스트 PASS — 컬럼 매핑/rate limit/Firestore batch |

**검증 보류**:
- KRX가 로컬 IP 차단 ("LOGOUT" 응답) → 실데이터 sample 미검증
- dry-run으로 코드 흐름만 21 호출 정상 발송 확인

### Day 2 — 분석 헬퍼 + 일일 증분 ✅ (commit `80cc784`)

| 산출물 | 비고 |
|--------|------|
| `KoreaSupplyAnalyzer` (korea_supply.py) | 5종 interpretation_signal 분류 + 4개 헬퍼 함수 |
| `jobs/daily_korea_collect.py` | yesterday + gap 7영업일 자동 보충 + dry-run |
| 단위 테스트 22건 추가 | analyzer 13 + daily Job 9 |

### Day 3 — 재벌 매핑 + 지주사 NAV ✅ (commit `0fd9c03`)

| 산출물 | 비고 |
|--------|------|
| `data/chaebol_groups.json` | 공정위 2024 상위 10대 그룹 (verified) |
| `utils/data_collectors/holding_company.py` | 5개 지주사 (LG/SK/GS/한화/롯데지주) NAV + 5단계 분류 |
| 단위 테스트 25건 추가 | NAV/분류/Firestore mock |

**실측 검증 결과** (Firestore 운영 시총):
- LG 26.52% (중간), SK 86.87% (매우 높음), GS -252% (프리미엄/비상장 NAV 미산입), 한화 67.39% (매우 높음), 롯데지주 21.02% (중간)

### Day 4 — 자사주 정책 (DART) 🔄 진행 중

(작업 중)

### Day 5 — 밸류업 + 거버넌스 + 공매도 ⏳ 대기

---

## 🚧 사용자/외부 작업 TODO (작업 완료 후 별도 timing)

### 🔴 KRX 외국인/기관 5년 풀 백필 (필수)

**현재 상태**: Day 1~2 코드 완성, sample 100×5일 dry-run만 검증.
**결정**: 최종 시스템 테스트는 **전체 종목 5년 실데이터**로 진행 — sample은 임시 검증용.

**실행 옵션**:
1. ⭐ **Cloud Run Job 1회 실행 (권장)** — Week A 종료 후 야간 자동 실행
   - Dockerfile에 `jobs/backfill_korea_supply.py` 진입점 추가
   - `gcloud run jobs create axis-backfill-korea-supply --command=python --args=-m,jobs.backfill_korea_supply,--mode,full`
   - 1회 실행 → ~3시간, Firestore 쓰기 ~$2.3
2. 로컬 야간 실행 — 노트북 점유 ~3시간, KRX IP 차단 풀린 후
3. (병행) 일일 증분 16:30 — `jobs/daily_korea_collect.py` (Cloud Scheduler 등록)

**예상 비용**: pykrx 무료 + Firestore 쓰기 1.25M doc × $0.18/100K = **약 $2.3 (1회)**

**선결 조건**:
- KRX IP 차단 해제 확인 (또는 Cloud Run의 별도 IP 사용)
- Firestore composite index 생성 (`historical_supply` 컬렉션의 `ticker + date`) — Firestore가 첫 쿼리 시 자동 안내

### 🔴 DART 자사주 공시 3년 백필 (Day 4 완료 후)

Day 4 코드 완성 직후 같은 Cloud Run Job 패턴으로 1회 실행. 일일 한도 10K, 3년 백필은 약 5,000~10,000건 → 1일 내 완료.

### 🟡 Cloud Run Secret Manager 등록

DART 키를 Cloud Run Job에서 사용하려면 Secret Manager 등록 필요:
```powershell
gcloud secrets create dart-api-key --data-file=- --project=all-of-asset
# (프롬프트에서 키 붙여넣기 후 Ctrl+Z)
gcloud secrets add-iam-policy-binding dart-api-key \
  --member=serviceAccount:1043976673827-compute@developer.gserviceaccount.com \
  --role=roles/secretmanager.secretAccessor --project=all-of-asset
```

---

**최종 업데이트**: 2026-05-02 (Day 4 작업 시작 시점)
