# 시간축 관점(Horizon Lens) 재설계

> **결정 (2026-06-22)**: 페르소나 6종(블랙록/ARK/그레이엄/event/macro/korean)을 폐기하고,
> **4개 시간축 "관점(lens)"** 으로 종목분석을 단순화한다. 페르소나는 *투자 철학* 축이라
> 1~3년차 타깃에게 직관적이지 않음 — "얼마나 들고 볼 것인가"가 실제 사용자 멘탈모델.

---

## 1. 4개 관점 (확정)

| 관점 | 시간축 | 정의 |
|------|--------|------|
| **단기** | 수일~1개월 | 가격·수급·임박 이벤트 중심 |
| **단중기** | 1~3개월 | 기술적 + 실적 이벤트(어닝) |
| **중기** | 3개월~1년 | 실적 모멘텀·밸류에이션·국면 |
| **장기** | 1년+ | 펀더멘털·해자·재무건전성·매크로 사이클 |

경계 무(無)갭(원안의 3~6개월 갭 제거). "스윙" 등 트레이딩 용어 사용 안 함.

### 관점별 방법론 앵커 (결정 2026-06-22)
검증된 방법론을 분석 스탠스 앵커로 차용. **사용자 표기는 "방법론 라벨"만**, 실무자명은
**프롬프트 내부 앵커로만**(실명 브랜딩 금지 — 상표·추천 함의·비직관성 회피). = 옵션 (A).

| 관점 | 방법론(노출) | 내부 앵커 | 핵심 판단 기준 |
|------|------|------|------|
| 단기 | 모멘텀·추세 | 미너비니 SEPA | 가격추세·거래량급증·상대강도(RS)·수급·임박이벤트 |
| 단중기 | 어닝 모멘텀 | 오닐 CANSLIM | 분기 서프라이즈·EPS성장·신고가 돌파·기관 매집 |
| 중기 | GARP(합리가격성장) | 피터 린치 | PEG·실적 지속성·밸류 vs 성장·섹터국면·정책 |
| 장기 | 가치·해자 | 그레이엄/버핏 | 내재가치 할인·해자·재무건전성·구조적성장·매크로사이클 |

**자산 재활용**: 폐기 페르소나 .md가 앵커로 녹음 — graham.md→장기, ark.md→중기/장기 성장요소,
blackrock.md→전 관점 리스크 오버레이. 신규 작성이 아닌 재배치.

### 법적 프레이밍 (Hard Rule 유지)
- ❌ "보유 기간 권유", "스윙", "매수가/목표가"
- ✅ **"이 종목을 [단기] 관점에서 보면 어떤 데이터가 중요한가"** — 보유기간을 권하는 게
  아니라 사용자가 고른 *분석 시간축*에 맞춰 무엇을 봐야 하는지 보여주는 렌즈.
- 모든 응답 하단 면책 문구 유지. entry/exit는 "관찰 구간(참고 수치)"로만.

---

## 2. 관점별 분석 엔진 매핑 (핵심)

기존 6 페르소나는 사라지지만, **데이터 자산은 내부 입력 제공자로 재활용**한다.
사용자는 더 이상 event/macro/korean을 직접 고르지 않고, 관점에 따라 자동으로 적절한
데이터 모듈이 합성에 투입된다.

| 관점 | 기술/수급 | 이벤트(event) | 매크로(macro) | 한국특수(korean) | 펀더/밸류 |
|------|:--:|:--:|:--:|:--:|:--:|
| 단기 | ●●● | ●● (임박) | ○ | ●(수급) | ○ |
| 단중기 | ●● | ●●●(어닝) | ● | ● | ● |
| 중기 | ● | ● | ●●(국면) | ●●(정책/밸류업) | ●● |
| 장기 | ○ | ○ | ●●(사이클) | ●●(거버넌스) | ●●● |

(●●●=핵심 / ●●=중요 / ●=배경 / ○=제외)

- **macro는 단기에서 제외**: 지표가 월~분기 시차라 단기엔 무용 (이번에 확인된 사실).
- korean 모듈은 KR 종목에만, US 종목은 자동 스킵.

---

## 3. 아키텍처 변경

### 통합 파이프라인 (페르소나 분기 제거)
```
START → route_by_horizon → fanout
   ├── research (뉴스/수급, 관점별 timeframe)
   ├── analyst  (기술 vs 펀더 강조를 관점이 결정)
   └── [관점별 조건부] event / macro / korean  ← 사용자 선택 아님, 자동 투입
        → validator → strategist(관점 emphasis .md) → END
```

- `route_by_persona` → `route_by_horizon`. 4 관점 모두 **단일 통합 파이프라인** 사용.
- 기존 `STRATEGIST_PERSONAS` 3종 흐름과 `DATA_DRIVEN_PERSONAS` 단일노드 흐름을 **하나로 통합**.
- event/macro/korean 노드는 *user-facing persona*에서 *internal data provider*로 강등.

### 페르소나 .md → 관점 emphasis .md
`personas/blackrock|ark|graham.md` 삭제 → `personas/horizons/{short|short_mid|mid|long}.md` 신설.
strategist의 `_load_personas`/`_build_full_system(persona)` → `_load_horizons`/`_build_full_system(horizon)`.
event/macro/korean.md는 **유지**(내부 데이터 제공자 프롬프트로 계속 사용).

---

## 4. 변경 파일

### Backend
- `agents/graph.py` — route_by_horizon, 통합 파이프라인, 조건부 specialist 투입
- `agents/strategist.py` — persona→horizon emphasis 로딩
- `agents/analyst.py`, `agents/research.py` — horizon 입력으로 강조점 조정 (timeframe 필드 이미 존재)
- `api/routes/ai.py` — `_PERSONAS`→`_HORIZONS` 레지스트리, `AnalyzeRequest.persona`→`horizon`
  (구버전 호환: persona도 잠시 수용 후 매핑), **quota 카운팅 수정**(아래 5-③)
- `personas/horizons/*.md` 신설, `personas/blackrock|ark|graham.md` 삭제

### Frontend
- `web/types/persona.ts` → horizon 타입 (이미 `time_horizon` 필드 있음 — 재활용)
- `web/store/personaStore.ts` → horizonStore (+ persist 마이그레이션)
- `web/components/analyze/PersonaChooser.tsx`, `web/components/persona/PersonaSwitch.tsx` → Horizon 선택 4타일
- `web/components/analyze/AnalyzeView.tsx` 연동

---

## 5. 통합 수정 — 이전에 발견한 버그 (이 작업에 포함)

① **CPI 지수↔YoY 오매핑 → 하이퍼인플레이션 오판** *(심각)*
   `jobs/monthly_regime_calc.build_cycle_inputs`가 `cpi_yoy`에 지수 원값(KR 119.9/US 332)을
   넣어 cycle_detector가 "하이퍼인플레이션"으로 오판. 모든 매크로 국면 판정 오염.
   → 지수 현재값÷12개월전−1로 YoY 산출(또는 YoY 시리즈 직접 수집). macro는 중기/장기에서
   계속 쓰므로 in-scope.

② **`summary_neutral` 빈 값(빈 카드)**
   macro_pm completeness/단정어 필터 후처리에서 summary가 비는 경우. 항상 채워지도록 보강.

③ **quota 과다 카운팅 (신규 — 통합 파이프라인 부작용)**
   `_count_month_usage`가 `agents.{strategist,event_analyst,macro_pm,korean_specialist}.calls`를
   합산. 통합 후 한 분석이 analyst+macro+strategist를 내부 호출하면 1회 분석이 2~3회로
   잘못 카운트됨. → **종착 synthesis(strategist) 1회 또는 analysis_history 기준**으로 카운트.

④ **KIS 접근토큰 403 rate limit (EGW00133)**
   최초 에러. 1분 1회 제한 락 시 분석 전체가 5xx로 죽음. → 캐시 토큰 폴백·백오프, KIS
   위젯만 degrade(분석 본문은 진행). `utils/data_collectors/kis_client.py`.

⑤ **수치 신선도 as-of 표기** — 환율(일별) vs 기준금리(월별) 시차 다름. "as-of 날짜" 노출.

---

## 6. 단계별 실행 (가역성 우선)

- **Phase 1 (백엔드, 비파괴)**: horizon emphasis .md 신설 + graph route_by_horizon 추가
  (persona 경로 병존). strategist/analyst/research horizon 수용. → 기존 동작 안 깨고 신규 경로 검증.
- **Phase 2 (버그 수정)**: ①CPI/하이퍼인플레이션 ②빈 summary ④KIS 토큰 ⑤신선도.
- **Phase 3 (API 전환)**: `_HORIZONS` 레지스트리, horizon 요청 수용, ③quota 카운팅 수정.
- **Phase 4 (프론트)**: Horizon 선택 UI + store 마이그레이션.
- **Phase 5 (정리)** ✅ **완료(2026-06-22, feature/horizons)**: blackrock/ark/graham 페르소나
  전면 폐지. 결정 = **노드 보존, UI만 제거** — event/macro/korean 노드·에이전트 코드는 graph에
  내부 데이터 제공자로 잔존(UI 미노출), 사용자 1차 축은 horizon만.
  - Backend: `personas/{blackrock,ark,graham}.md` 삭제 / strategist.py horizon 전용
    (`_load_personas`·`VALID_PERSONAS` 제거, `_build_full_system(horizon)`, 빈 값→mid) /
    graph.py `route_by_persona`→`route_by_horizon`(STRATEGIST_PERSONAS 제거) /
    ai.py `_PERSONAS`에서 3종 제거(event/macro/korean만)·analyze 핸들러 비데이터노드→mid 기본·
    profile `preferred_persona`→`preferred_horizon`.
  - Frontend: PersonaChooser·PersonaSwitch·PersonaGuideModal·personaStore 삭제 /
    AnalyzeView horizon 전용(데이터 노드 카드는 휴면 폴백) / onboarding·settings·dashboard의
    "선호 페르소나"→"선호 시계(horizon)". types/persona.ts는 캐리어/데이터노드 메타로 잔존.
  - 검증: pytest 743 pass(신규 실패 0, 잔존 14건은 전부 사전 존재=ECOS/korea_supply/legal
    baseline/auth) + web tsc --noEmit 클린.
  - 남은 것: **라이브 스모크(horizon analyze E2E)** → main 머지 → 백엔드 재배포 + Vercel 배포
    (프론트 배포=즉시 사용자 노출, 피처플래그 없음). 잔존 dev 스크립트(measure_v2_cost·
    persona_consistency_check·strategist_ab)는 폐지 페르소나 참조하나 앱/CI 무관·미수정.

각 Phase 끝에 테스트·검증. Phase 1~3은 prod 영향 없음(병존), Phase 4~5에서 사용자 노출 전환.
