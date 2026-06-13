# Axis — 제품 백로그 (보류/검토 대기)

> 즉시 착수하지 않고 의사결정/검토가 필요한 후보. 착수 시 항목을 옮기고 커밋 메시지에 근거 기록.

---

## 📌 마케팅 직전 로드맵 후보

### ✅ 진행 중 / 완료
- [x] **첫 분석 체감속도 개선** (2026-06-13)
  - **A. 인기종목 사전캐시** — `jobs/cache_warm.py` + `deploy-cache-warm-job.sh`.
    데이터 갱신 직후 인기 N종목 미리 분석 → L2 응답캐시 워밍 → 첫 분석 cache hit(~12s→~3-5s).
    ⚠️ 스케줄러는 `--schedule` 플래그로만 생성(자동 과금 옵트인). 콜드 1건 ~175원.
  - **B. 빠른요약(instant)** — `agents/instant.py` + `/api/ai/analyze` SSE
    `instant_snapshot`(즉시·비용0) + `instant_summary`(Haiku ~5원·~2s). 프론트 `InstantCard`.

### 🤔 검토 대기 (JEON 고민 중 — 2026-06-13 보류)
- [ ] **Free/Pro 차별 메시지 날카롭게**
  - 현재 Pro 락은 페르소나/커스텀스크리너 위주. "왜 Pro인가"를 분석 흐름 안에서
    체감시키는 카피·게이트 위치 재설계 필요. 전환율 직결.
  - 관련: `web/components/persona`, 402 PERSONA_LOCKED CTA, `/pricing`.
- [ ] **Premium 재도입 (월 99,000)**
  - 관심 100 / 월 300회 / 주간 PDF 리포트 / 우선 분석 큐.
  - 단가/손익분기 근거: `docs/axis/UNIT_ECONOMICS.md`. PLAN_LIMITS에 premium 정의는 이미 있음.

---

## 🟡 기술 부채 (보안 감사에서 의도적 연기 — [[project_prelaunch_security_audit]])
- [ ] **quota race condition** — "조회 후 실행"이라 동시요청 소폭 초과 가능.
  유료화 후 Firestore transaction `reserve_usage` 선점+실패 rollback으로 전환.
- [ ] **관리자 지표 풀스캔** — `admin_routes.py` funnel/usage가 collection_group/users 전량 스캔.
  유저 증가 시 일별 집계 컬렉션 필요.

---

## ⏳ 운영 대기 (외부 셋업 후 활성화)
- [ ] **알림 발송 활성화** — 코드/인프라 완성, Mailgun만 대기.
  JEON: mailgun 시크릿 3종(api-key/domain/from) + 도메인 DNS 인증 후 `deploy-notify-job.sh` 재실행.
- [ ] **캐시 워밍 자동화** — `deploy-cache-warm-job.sh --schedule`로 평일 08:30/18:00 KST 스케줄러 생성.
  비용(평일 2회 × N×175원) 감안해 종목수 `WARM_TICKER_COUNT` 조정 후 켜기.
