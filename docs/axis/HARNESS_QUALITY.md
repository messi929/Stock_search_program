# 하네스 품질 개선 (모델 업그레이드 없이)

> 2026-06-05. 모델을 바꾸지 않고 하네스(프롬프트·컨텍스트·검증·오케스트레이션)만으로
> AI 분석 출력 품질을 올린 작업 기록. 측정 하네스(eval) + 3가지 개선 + 회귀 검증.

## 요약 결과 (Sonnet judge 기준, strategist 8건, ③②④ OFF→ON)

| 차원 | before | after | Δ |
|---|---|---|---|
| legal (권유성 단어 0건) | 0.875 | 1.000 | ▲ +0.125 |
| completeness (필수 필드) | 0.854 | 1.000 | ▲ +0.146 |
| numeric (수치 정합) | 1.000 | 0.975 | ▼ −0.025 |
| persona_diff (페르소나 차별) | 1.000 | 1.000 | = |
| judge (LLM 종합 품질) | 0.707 | 0.748 | ▲ +0.041 |
| **overall** | **0.887** | **0.945** | **▲ +0.058** |

비용: 딥다이브당 약 **+₩70** (≈175원 → ≈245원, +40%) — Extended Thinking의 추론 토큰.

## ① 측정 하네스 — `evals/`

실제 출력물을 다차원 점수화하고 회귀 비교한다. (기존 `tests/regression/test_60_cases.py`는
실행 여부만, `scripts/legal_check.py`는 코드 정적 스캔만 했음.)

- `evals/dataset.py` — 골든 케이스 (default 11 / smoke 1 / full 60). persona_diff 그룹 포함.
- `evals/scorers.py` — 결정론(legal·completeness·numeric·persona_diff, 무료) + LLM-judge.
- `evals/runner.py` — 실행→채점→스코어카드→baseline diff. 전체 출력 덤프 저장.
- `evals/README.md` — 사용법.
- `tests/test_evals.py` — 결정론 채점기 단위 테스트 (API 불필요).

### judge는 반드시 Sonnet
초기 Haiku judge는 reasoning/data를 **일괄 2점으로 포화**시키고 자기검증 문장을
환각으로 오판해 판별력이 없었다. Sonnet judge로 교체하니 정상 변별(reasoning 대부분 4).
또한 judge에 **페르소나 철학(personas/*.md)을 함께 제공**해, 그레이엄 'PER<15' 같은
표준 기준을 환각으로 오판하지 않게 했다. (`AXIS_JUDGE_MODEL=haiku`로 강제 가능)

### 표준 워크플로우
```bash
py -m evals.runner --judge --label baseline                 # 기준선 고정
#   (개선 적용)
py -m evals.runner --judge --label after --baseline evals/results/baseline.json
```

## ③ Extended Thinking — `utils/claude_client.py`

복잡한 종합·검증 노드에서 추론 품질을 높인다.
- `thinking_budget`을 base→client로 배선. SDK 0.43.0이 네이티브 미지원이라
  **`extra_body`로 주입**(버전 무관, 실호출 검증). max_tokens 가산·temperature 1.0 강제·
  캐시 키 분리(thinking 켠/끈 응답 충돌 방지).
- Strategist(budget 3200) + Validator contrarian(1600)에 적용.
- env 토글: `STRATEGIST_THINKING_BUDGET`, `VALIDATOR_THINKING_BUDGET` (0=비활성).

## ② 해석 검증 — `agents/validator.py` → `strategist.py`

Validator가 수치만 검증하던 것을, **Analyst 해석의 타당성**까지 감사하도록 확장
(기존 contrarian Claude 호출에 통합 — 추가 호출 0).
- `interpretation_audit`: "RSI 28인데 강세 해석" 같은 과신·방향 비약·톤 불일치·데이터 모순 탐지.
- Strategist가 이를 받아 종합 시 보정.
- **실측 효과**: blackrock:005930에서 후속 분석이 "'외국인 3일 연속 순매수'가 긍정으로
  서술됐으나 리서치는 상위에 없다고 명시 — 상충" / "검증가와 2.05% 괴리"를 **스스로 지적**.
  (전(前)에는 그대로 긍정 단정) judge도 "Validator 감사 지적을 실제로 반영"으로 인식.
- env 토글: `AXIS_INTERP_AUDIT=0` (비활성).

## ④ 섹터 상대 밸류에이션 — `agents/analyst.py`

"업종 평균"을 LLM이 추측(환각 위험)하지 않도록, 시장 스냅샷에서 **섹터 중앙값
PER/PBR/ROE + 백분위**를 결정론적으로 산출해 앵커로 주입.
- `valuation_judgment`·`peer_avg_per`의 근거가 데이터에 고정됨.
- env 토글: `AXIS_SECTOR_STATS=0` (비활성).

## 비용 트레이드오프

Extended Thinking이 추론 토큰을 추가해 딥다이브당 ~₩70 증가(+40%). 튜닝 옵션:
- `VALIDATOR_THINKING_BUDGET=0` — Validator thinking만 끄면 ~₩30 절감 (Strategist는 유지)
- 예산 하향 (예: STRATEGIST 3200→2000)
- Pro 티어에만 활성화 등 정책 분기

## 남은 후보 (미적용)
- self-consistency (고가치 케이스 N회 샘플) — 비용↑
- legal 필터의 부정문 false-positive (구조화 필드 미적용 포함) — 별도 개선 필요
- 데이터 페르소나(macro/korean/event)의 summary_neutral 잘림 — ②③④ 범위 밖, 별도 처리

## 산출물 위치
- 점수 리포트: `evals/results/{baseline,before_v3,after_v3}.json`
- 환경변수 일람: 위 각 절의 env 토글
