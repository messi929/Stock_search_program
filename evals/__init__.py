"""Axis AI 출력 품질 eval 하네스.

모델 업그레이드 없이 하네스(프롬프트·컨텍스트·검증·오케스트레이션)를 개선할 때,
"좋아진 것 같다"가 아니라 **점수로** 회귀 비교하기 위한 측정 도구.

기존 자산과의 차이:
  - tests/regression/test_60_cases.py : 실행 여부(ok/elapsed)만 확인
  - scripts/legal_check.py            : 코드/프롬프트 정적 스캔
  - evals/ (이 패키지)                : **실제 출력물**을 다차원 점수화 + 회귀 비교

점수 차원:
  - legal           : 출력 전체 문자열에 권유성 단어 0건 (결정론적, 무료)
  - completeness    : 페르소나별 필수 콘텐츠 필드 충실도 (결정론적, 무료)
  - numeric         : 진입/청산 수치 정합성 — 순서·현재가 대비 방향 (결정론적, 무료)
  - persona_diff    : 같은 종목에서 페르소나별 진입선이 실제로 달라지는가 (결정론적, 무료)
  - judge_*         : 추론 품질·데이터 근거·페르소나 적합·환각 (LLM-judge, opt-in)

사용:
    py -m evals.runner --smoke           # 1건, 결정론 점수만
    py -m evals.runner                   # 기본 세트, 결정론 점수
    py -m evals.runner --judge           # + LLM-judge (Haiku)
    py -m evals.runner --label baseline  # 결과를 evals/results/baseline.json 저장
    py -m evals.runner --judge --baseline evals/results/baseline.json  # 회귀 diff
"""
