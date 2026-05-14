# Axis 분석 시간 단축 재설계 (post-beta priority)

> **작성**: 2026-04-30 (라운드 3 워크스루 후)
> **참조**: [PROGRESS.md](PROGRESS.md), [NEXT_STEPS.md](NEXT_STEPS.md), [agents/graph.py](../../agents/graph.py)
> **목표**: 분석 시간 P50 84초 → 30초 이하, P90 60초 이하

---

## 1. 현재 상태 측정 (revision axis-staging-00008-mlw)

| 시점 | 측정값 | 비고 |
|------|--------|------|
| Fresh 분석 (000660) | **84.74초** | Strategist max_tokens 1500, Discoverer 40 후보 |
| 캐시 히트 (동일 티커) | **60.07초** | system prompt 캐시 + ResponseCache 부분 히트 |
| ROADMAP 추정 | 5~10초 | **8~17배 차이** |

**1쿼리 비용**: 약 450원 (Strategist Opus 80% 차지)

---

## 2. 병목 분해

```
START
  ↓
fanout
  ├─→ research (Haiku, ~5-10s)        ─┐
  └─→ analyst  (Sonnet, ~15-20s)      ─┴─→ validator (Sonnet + 라이브 데이터 fetch, ~15-25s)
                                                              ↓
                                                       strategist (Opus, ~30-40s)
                                                              ↓
                                                             END
```

**중요한 사실 (오해 정정)**:
- Research와 Analyst는 **이미 병렬 실행 중** (`agents/graph.py:161-163`)
- 시간 비례:
  - max(research, analyst) ≈ 18s
  - validator ≈ 20s  ← **여기가 핵심 병목**
  - strategist ≈ 35s ← **두 번째 병목**
  - 합계 ≈ 73s + 네트워크/SSE 오버헤드 ≈ **84초**

**왜 Validator가 직렬에 끼어 있나**:
- Strategist 입력에 Validator 결과(`confidence_score`, `contrarian_scenarios`, `blind_spots`)가 사용됨 ([strategist.py:316-325](../../agents/strategist.py))
- `requires_reanalysis=True`면 그래프가 fanout으로 재시도 라우팅 ([graph.py:134-139](../../agents/graph.py))

---

## 3. 재설계 옵션

### Option A — Validator를 critical path에서 분리 ⭐ 추천

**아이디어**: Validator는 실시간 검증의 핵심 차별점 ⭐이지만 매 분석마다 자동 실행할 필요는 없음. 사용자가 명시적으로 "🔍 실시간 검증" 버튼을 누를 때만 실행 (이미 ValidateButton 컴포넌트 존재).

**변경**:
```
START
  ↓
fanout
  ├─→ research ─┐
  └─→ analyst ──┴─→ strategist ─→ END
```

**Strategist 입력 조정**:
- `validator_output` → `Optional[ValidatorResult]`로 변경
- None일 때 시스템 프롬프트에서 "검증 미실행" 모드 안내
- `confidence_note`에 "사용자가 [실시간 검증] 버튼을 눌러 데이터 신선도를 확인하세요." 자동 삽입

**프론트 변경**:
- ValidateButton 첫 진입 시 라벨: "🔍 실시간 검증 (필수)" 강조 표시 (배지 또는 깜박임)
- 검증 후 Strategist의 `confidence_note` 영역을 Validator 결과로 교체
- 또는 Validator 결과를 별도 카드로 첨부

**예상 효과**:
- 분석 시간: **84s → ~55s** (Validator 제거 ~20s + 그래프 오버헤드 절감 ~10s)
- 비용: Validator 호출 1회 절감 (~25원/쿼리, 사용자가 검증 버튼 누를 때만 발생)

**리스크**:
- "실시간 검증"이 핵심 차별점인데 자동 실행 안 하면 가치 희석 우려
- 완화: 첫 분석 후 자동으로 ValidateButton에 시각적 강조 + "30초 후 자동 검증" 옵션 토글

**구현 작업**:
- `agents/graph.py` — validator 노드 제거, 조건부 라우팅 단순화
- `agents/strategist.py` — Optional validator 처리 + confidence_note 분기
- `web/components/analyze/AnalyzeView.tsx` — 자동 validator 흐름 제거, 첫 진입 시 검증 권장 UI
- `api/routes/ai.py` — SSE 이벤트 시퀀스에서 `validator_complete` 제외 (또는 사용자 트리거 시만 발생)

**작업량**: 2~3시간

---

### Option B — Validator를 Strategist와 병렬 (보수적)

**아이디어**: Strategist는 Validator 없이 1차 응답 생성, Validator 결과 도착하면 사후 보강(append).

**변경**:
```
fanout
  ├─→ research ─┐
  └─→ analyst ──┴─→ fanout2
                       ├─→ validator ──┐
                       └─→ strategist ─┴─→ merge → END
```

**예상 효과**:
- 분석 시간: 84s → max(validator, strategist) ≈ **~50s**
- 비용: 동일 (Validator는 여전히 자동 실행)

**리스크**:
- Strategist가 Validator 없이 작성 → 신뢰도 낮은 결론 가능
- merge 시점에 confidence_note 교체 / contrarian 추가 → UI 깜박임

**구현 작업**:
- `agents/graph.py` — fanout2 추가, merge 노드 추가
- `agents/strategist.py` — Validator None 처리 (Option A와 공유)
- `web/components/analyze/AnalyzeView.tsx` — Strategist 결과 부분 갱신 처리

**작업량**: 4~5시간

---

### Option C — Strategist 모델 다운그레이드 평가

**아이디어**: Opus 4.7 → Sonnet 4.6 비교 테스트.

**예상 효과**:
- 분석 시간: Strategist ~35s → ~15s (Sonnet은 약 2배 빠름)
- 비용: 호출당 370원 → ~50원 (약 87% 절감)
- **품질 trade-off** — 페르소나별 깊이, 사용자 원칙 부합도 평가, 한국어 자연스러움

**검증 절차**:
1. 동일 티커·페르소나·user_profile로 Opus vs Sonnet 응답 10건 생성
2. blind A/B 평가 항목:
   - 페르소나 일관성 (블랙록답게 / ARK답게 작성됐는지)
   - confidence_note 정확성
   - follow_up_questions 깊이
   - 한국어 자연스러움
3. 차이가 미미하면 Sonnet 채택, Premium tier에서만 Opus 옵션 제공

**구현 작업**:
- `agents/strategist.py` — 모델 상수 변경 + A/B 토글
- `scripts/compare_strategist_models.py` — 비교 스크립트
- 사용자 5명 베타 테스트 (눈가림)

**작업량**: 평가 1일 + 의사결정 회의

---

### Option D — Strategist 응답 스트리밍

**아이디어**: 현재 Strategist는 JSON 전체 생성 후 반환. 스트리밍으로 전환하면 토큰 단위로 UI 갱신 가능.

**예상 효과**:
- 절대 시간: 동일 (~35s)
- **체감 시간 대폭 감소** — 사용자가 5초 후부터 페르소나 분석 텍스트 보이기 시작
- "AI가 살아있다"는 인상 → 만족도 ↑

**구현 작업**:
- `agents/strategist.py` — `client.messages.stream()` 사용, JSON 점진 파싱
- `api/routes/ai.py` — SSE에 `strategist_partial` 이벤트 추가
- `web/components/analyze/StrategistCard.tsx` — 점진적 텍스트 렌더 + JSON 파싱 안정성
- json_repair 활용 (부분 JSON도 복구)

**리스크**:
- 부분 JSON 파싱 복잡 (entry_points·alert_conditions 같은 nested 구조)
- 한국어 토큰 단위 깜박임 (보기 안 좋을 수 있음 — debounce 필요)

**작업량**: 5~6시간

---

## 4. 추천 로드맵

| 단계 | 옵션 | 예상 효과 | 작업량 | 우선순위 |
|------|------|----------|--------|---------|
| **1** | A (Validator 분리) | 84s → ~55s | 2~3h | 🔥 최우선 |
| **2** | D (Strategist 스트리밍) | 체감 ~5s 시작 | 5~6h | 🔥 만족도 직결 |
| **3** | C (Sonnet 평가) | ~15s 추가 단축 + 비용 87% 절감 | 1일 평가 + 결정 | ⚠️ 품질 검증 후 |
| 보류 | B (Validator 병렬) | A보다 작은 효과, 복잡 | 4~5h | ❌ A 채택 시 불필요 |

**1+2 적용 시 예상**: 체감 5초 시작 / 절대 시간 50초 / 사용자 만족도 大폭 향상.

**1+2+3 적용 시 예상**: 체감 5초 시작 / 절대 시간 35초 / 비용 호출당 ~150원.

---

## 5. 측정 인프라 (선결)

재설계 진행 전 측정 기반 마련:

### 5.1 자동 측정 스크립트
`scripts/benchmark_analysis.py` 신규:
- Top 10 티커 × 3 페르소나 = 30 요청
- 각 요청의 P50, P90 응답 시간 + 비용 기록
- 변경 전/후 비교 표 자동 생성

### 5.2 사용자 만족도 신호
- `/analyze/[ticker]` 페이지 하단에 "이 분석이 도움됐나요?" 1~5 별점
- Firestore `analyses/{id}/feedback` 저장
- 주간 평균 점수 대시보드

### 5.3 SSE 단계별 timing
- 각 SSE 이벤트(research_complete, analyst_complete, ...)에 `elapsed_ms` 첨부
- 프론트에서 "Research 8s · Analyst 18s · Validator 22s · Strategist 36s" 디버그 표시 (개발자 모드)

---

## 6. 기타 남은 백엔드 작업

### 6.1 LEGAL — 백엔드 응답 자동 필터링
**파일**: `api/routes/ai.py`의 `_build_full_response`
**현재**: `BaseAgent.filter_forbidden()` 메서드 존재하지만 자동 호출 X
**해결**: 모든 string 필드 traversal + filter
**작업량**: 1시간 ([NEXT_STEPS.md A 항목](NEXT_STEPS.md))

### 6.2 LEGAL — `scripts/legal_check.py`
**현재**: 미구현
**해결**: CI 차단용 grep 스크립트 (agents/, personas/, api/, web/app/, web/components/)
**작업량**: 30분

### 6.3 v7.5 LEGAL 중립화 ✅ 완료 (2026-05-14)
소스에서 중립화 완료 — `screener/core/metrics.py`가 `buy_grade`를 중립 구간 라벨
("상위"/"준상위"/"중간"/"관찰")로 직접 산출하고, `screener/core/screener.py`
카테고리명도 중립화. `web/lib/legal-labels.ts`·`columnMeta.ts`는 전환기 안전망으로 유지.
v7.5 라이브 UI(index.html/pricing.html/rank_page.py)의 권유성 표현도 일괄 정리.

---

## 7. 기타 남은 프론트 작업

### 7.1 미구현 라우트 (현재 NAV에서 제외됨)
| 라우트 | 우선순위 | 작업량 | 비고 |
|--------|---------|--------|------|
| `/watchlist` (리스트 뷰) | 🟡 중 | 2h | 추가/삭제/검증 일괄 관리 |
| `/analyses` (분석 이력) | 🟢 낮 | 3h | Firestore 쿼리 + 페이지네이션 |
| `/settings/profile` | 🟢 낮 | 2h | 온보딩 4문항 재편집 |

### 7.2 페르소나 추천 강화
현재 사용자는 페르소나를 자유롭게 토글하지만, 본인 프로파일과 적합한 페르소나가 추천되면 좋음.
- 보유기간 1m → ARK
- 보유기간 3y+ → 그레이엄
- 보유기간 1-2y → 블랙록 (현재 default)
**작업량**: 30분 (디스플레이 힌트만)

### 7.3 베타 신청 폼 URL
**상태**: `NEXT_PUBLIC_BETA_FORM_URL` 비어 있음
**필요 작업**: 사용자가 Google Forms / Tally 만들고 환경변수 채우기
**임팩트**: 랜딩 → 가입 funnel 차단 중

---

## 8. 인프라 / DevOps

### 8.1 axis-staging deploy 스크립트
**문제**: `gcloud run deploy --source=.`이 Buildpacks를 골라 web/ 빌드 시도 → 실패
**해결**: `scripts/deploy-axis-staging.sh`
```bash
#!/bin/bash
set -e
TAG="$(date +%Y%m%d-%H%M%S)"
IMAGE="asia-northeast3-docker.pkg.dev/all-of-asset/cloud-run-source-deploy/axis-staging/axis-staging:${TAG}"
gcloud builds submit . --tag "$IMAGE" --region=asia-northeast3 --project=all-of-asset
gcloud run deploy axis-staging --image="$IMAGE" --region=asia-northeast3 --project=all-of-asset
```
**작업량**: 30분

### 8.2 `window.__axis_auth` dev hook 게이트
**현재**: `web/lib/firebase.ts`에서 무조건 노출
**위험**: 사실상 0 (커스텀 토큰 발급에 service account 필요), 그러나 프로덕션에서 보일 필요 없음
**개선**: `if (process.env.NEXT_PUBLIC_DEBUG_AUTH === '1')` 게이트
**작업량**: 5분 + Vercel env 추가

### 8.3 Playwright 회귀 테스트 자동화
**기반**: 이번 세션에서 검증한 시나리오 (랜딩, 로그인, 대시보드, 분석, 스크리너)
**해결**: `web/tests/e2e/*.spec.ts`로 옮기고 GitHub Actions PR 체크
**자료**: `scripts/_mint_admin_token.py` 활용
**작업량**: 4~6시간

---

## 9. 비용 최적화 (NEXT_STEPS.md 139~157 보강)

### 9.1 현재 적자 구조
- Pro 9,900원/월 × 50회 사용 가정 → 비용 22,650원/월 → **건당 -255,000원/Pro × 20명 = -255,000원/월**
- 토큰 50% 절감해도 여전히 적자

### 9.2 옵션
1. **Pro 가격 19,900원 인상** — 시장 수용성 검증 필요
2. **Premium tier(29,900원) 활성화** — 우선 분석 큐 + PDF 리포트
3. **Free tier 분석 횟수 진짜 차단** (현재 가짜 — 코드 검증 결과 미차단)
4. **위 Option C(Sonnet 다운그레이드)** 채택 시 호출당 150원 → 손익분기 가능성

---

## 10. 작업 순서 권장

```
Phase 1 (1주차)
  □ 5.1 benchmark 스크립트 작성 (측정 기반)
  □ 5.3 SSE 단계별 timing 첨부
  □ Option A 구현 (Validator 분리)
  □ 8.1 deploy 스크립트
  □ Pro/Sonnet 다운그레이드 영향 1차 측정

Phase 2 (2주차)
  □ Option D 구현 (Strategist 스트리밍)
  □ Option C 평가 (Opus vs Sonnet A/B)
  □ 6.1, 6.2 LEGAL 자동화
  □ 5.2 사용자 만족도 별점

Phase 3 (3주차)
  □ Option C 결정 + 적용 (Sonnet 채택 시)
  □ 7.1 /watchlist 리스트 뷰
  □ 7.2 페르소나 추천 힌트
  □ 8.3 Playwright E2E 자동화

Phase 4 (4주차)
  □ 7.1 나머지 라우트
  □ 9.x 가격 정책 결정 + Premium 활성화
  □ 베타 사용자 피드백 종합 → 정식 런칭 결정
```

---

## 11. 결정해야 할 것 (사용자 입력 필요)

| # | 결정 사항 | 옵션 | 권장 |
|---|---------|------|------|
| 1 | Validator 자동 실행 vs 수동 | A (수동만) / 현행 (자동+수동) | **A** — 큰 시간 절약 + 차별점 강조 가능 |
| 2 | Strategist Opus 유지 vs Sonnet | A/B 결과에 따라 | A/B 측정 후 결정 |
| 3 | 베타 신청 폼 도구 | Google Forms / Tally / Notion | Tally (이메일 자동 수집 + 한국어 친화) |
| 4 | Pro 가격 9,900 vs 19,900 | 시장 조사 필요 | 19,900 + Premium 활성화 |
| 5 | 카카오 OAuth | 베타 skip / 정식 추가 | 베타 skip |

---

**다음 액션**: 위 결정 1·2 확정 → Phase 1 착수.
