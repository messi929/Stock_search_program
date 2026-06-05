# Axis AI 출력 품질 Eval 하네스

모델을 바꾸지 않고 **하네스(프롬프트·컨텍스트·검증·오케스트레이션)**를 개선할 때,
변경이 실제로 품질을 올렸는지 **점수로 회귀 비교**하기 위한 도구.

## 왜 필요한가

| 기존 자산 | 측정 대상 |
|---|---|
| `tests/regression/test_60_cases.py` | 실행 여부(ok/elapsed)만 |
| `scripts/legal_check.py` | 코드/프롬프트 정적 스캔 |
| **`evals/` (이 패키지)** | **실제 출력물의 품질 다차원 점수** |

`②해석검증 / ③Extended Thinking / ④컨텍스트 큐레이션` 같은 개선이
정말 효과 있는지 숫자로 판정하는 토대.

## 점수 차원

| 차원 | 방식 | 비용 | 의미 |
|---|---|---|---|
| `legal` | 결정론 | 무료 | 출력 **전 필드**에 권유성 단어 0건 (런타임 필터는 free-text만 검사) |
| `completeness` | 결정론 | 무료 | 페르소나별 필수 콘텐츠 필드 충실도 |
| `numeric` | 결정론 | 무료 | 진입/청산 수치의 순서·현재가 대비 방향 정합 |
| `persona_diff` | 결정론 | 무료 | 같은 종목에서 페르소나별 진입선이 실제로 달라지는가 |
| `judge` | LLM(Haiku) | ~₩3/건 | 추론 품질·데이터 근거·페르소나 적합·환각 |

각 점수는 0.0~1.0. `overall`은 차원 평균의 평균.

## 사용법

```bash
# 결정론 점수만 (judge 없이)
py -m evals.runner --smoke              # 1건 (~₩200)
py -m evals.runner                      # 기본 세트 11건 (~₩2,000)

# LLM-judge 포함
py -m evals.runner --judge

# baseline 저장 → 개선 후 회귀 비교
py -m evals.runner --judge --label baseline
#   (… ②③④ 개선 적용 …)
py -m evals.runner --judge --label after --baseline evals/results/baseline.json

# 전체 60건 매트릭스 (비용 큼)
py -m evals.runner --full --label full_run
```

결과 JSON(`evals/results/<label>.json`)에는 **전체 출력 덤프**가 포함되어,
채점 로직만 고쳐 오프라인 재채점도 가능.

## 결정론 채점기 단위 테스트

```bash
py -m pytest tests/test_evals.py -q     # API 불필요, 무료
```

## 표준 워크플로우 (개선 작업 시)

1. `--judge --label baseline` 으로 현재 품질 고정
2. 하네스 개선 1건 적용 (예: Extended Thinking)
3. `--judge --label <change> --baseline evals/results/baseline.json`
4. 스코어카드 diff 확인 — `🚨 회귀`(−0.05↓) 없으면 채택, 있으면 원인 분석
