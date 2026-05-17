# Week E — 검증 + 최적화 + 베타 준비

> **목표**: 6 페르소나 회귀 테스트, 비용/성능 최적화, 베타 출시 준비
> **소요**: 5일
> **선행 의존성**: Week A~D 완료
> **후속**: 베타 출시 (별도 마일스톤)

---

## 🎯 산출물

```
tests/regression/
├── test_60_cases.py                 # 6 페르소나 × 10 종목
└── results/                         # 테스트 결과 JSON

scripts/
├── legal_check.py 강화              # v2 금지 단어 추가
└── persona_consistency_check.py     # 페르소나별 캐릭터 일관성

docs/
├── v2_roadmap/PROGRESS_V2.md        # 최종 진척
└── beta_readiness_report.md         # 베타 출시 준비 보고서
```

---

## 📅 Day별 작업

### Day 1-2 — 회귀 테스트 60건

#### 테스트 매트릭스

```
6 페르소나 × 10 종목 = 60건

종목 선정 (다양성):
1. 005930 — 삼성전자 (대형 한국, 글로벌 기술)
2. 207940 — 삼성바이오로직스 (한국, 헬스케어)
3. 010060 — OCI홀딩스 (한국, 지주사)
4. 005380 — 현대차 (한국, 자동차/전기차)
5. 035720 — 카카오 (한국, 플랫폼)
6. AAPL — 애플 (미국, 대형 기술)
7. RKLB — 로켓랩 (미국, 우주, 이벤트 케이스)
8. NVDA — 엔비디아 (미국, AI 반도체)
9. JPM — JPMorgan (미국, 금융)
10. TLT — 미국 장기채 ETF (매크로 케이스)
```

#### 검증 항목

1. **차별성**: 6 페르소나가 같은 종목에 다른 결론
2. **일관성**: 같은 페르소나가 다른 종목에서도 캐릭터 유지
3. **LEGAL**: 60건 모두 금지 단어 0건
4. **데이터 정확성**: pykrx/FRED/yfinance 응답이 응답에 정확히 반영
5. **시간 시계 정합성**: 페르소나 시계 일관 (Event 1w-3m, Macro 6m-2y, Korean 3m-2y)

#### 작업
1. **`tests/regression/test_60_cases.py` 작성**
2. **자동 실행 + 결과 저장**
3. **diff 분석**: 페르소나 간 결론 차이 시각화
4. **문제 케이스 식별 + 수정**

---

### Day 3 — Reviewer Subagent 통합 검증

#### 호출 시나리오

```
1. "Review the 60 regression test results for:
   - Persona differentiation (each persona stays in lane)
   - LEGAL compliance (forbidden words count)
   - Data accuracy (collected data matches output)
   - Time horizon consistency
   "

2. "Review the strategist routing in graph.py for:
   - 6-persona branching correctness
   - Error handling when data unavailable
   - Cost tracking accuracy
   "

3. "Review the frontend PersonaSwitch.tsx for:
   - Mobile UX (6 tabs)
   - a11y (keyboard navigation)
   - Loading states per persona
   "
```

#### 발견 이슈 즉시 fix
- 베타 출시 차단 이슈: 24시간 내 fix
- minor 이슈: backlog 등록

---

### Day 4 — 비용/성능 최적화

#### 비용 측정

```python
# scripts/measure_v2_cost.py

# 60건 회귀 테스트의 비용 분석
# - 페르소나당 Strategist 비용
# - 데이터 수집 비용 (LLM 추론 등)
# - Firestore 읽기/쓰기 비용
```

#### 최적화 옵션

##### Option 1: Strategist Sonnet 다운그레이드
- 현재: Opus ~370원/페르소나
- Sonnet 4.6: ~50원/페르소나 (1/7 비용)
- **검증 필요**: 품질 저하 여부
- 회귀 테스트 60건 Sonnet으로 재실행 → diff 비교

##### Option 2: 페르소나별 프롬프트 캐싱
- 시스템 프롬프트 cache_control (1024+ tokens 자동)
- 캐시 적중 시 입력 비용 90% 절감

##### Option 3: 페르소나별 데이터 재사용
- 4 Agent (Research/Analyst/Validator) 결과는 페르소나 무관 → 1번만 호출
- Strategist만 페르소나 수만큼 호출

#### 검증
- [ ] 비용 측정 보고서
- [ ] 최적화 적용 전후 비교

---

### Day 5 — 베타 준비 + 최종 검증

#### 작업

1. **PROGRESS_V2.md 최종 업데이트**
   - Week A~E 모든 산출물 정리
   - 발견 이슈 + 해결 현황

2. **베타 출시 준비 보고서** (`docs/beta_readiness_report.md`)
   - 6 페르소나 동작 검증 결과
   - 성능 (분석 시간) 측정
   - 비용 정책 권장 (Free/Pro/Premium)
   - 알려진 한계 + 향후 계획

3. **사용자 가이드** (`docs/user_guide_v2.md`)
   - 각 페르소나가 무엇을 하는지
   - 어떤 페르소나가 본인에게 맞는지
   - LEGAL 면책 명시

4. **Cloud Run staging 배포 + 통합 테스트**
   - 6 페르소나 staging 환경 검증
   - 프론트엔드 연동 검증
   - 실제 분석 5건 시나리오 테스트

#### 베타 출시 결정 체크리스트

- [ ] 회귀 테스트 60건 100% 통과
- [ ] LEGAL strict 0건
- [ ] 비용 정책 확정 (또는 추후 결정)
- [ ] 분석 시간 90초 이내
- [ ] Cloud Run staging 안정
- [ ] 사용자 가이드 완성
- [ ] PROGRESS_V2.md 최종

---

## ✅ Week E 완료 기준

- [ ] 60건 회귀 테스트 통과
- [ ] reviewer 3회 호출 + 이슈 fix
- [ ] 비용 최적화 보고서
- [ ] 베타 준비 보고서
- [ ] 사용자 가이드
- [ ] Staging 배포 검증

---

## 🚨 베타 출시 차단 사유 (즉시 사용자 보고)

다음 발견 시 베타 출시 연기:

1. **회귀 테스트 통과율 < 95%**
2. **LEGAL 위반 발견** (1건이라도)
3. **분석 시간 > 120초** (사용성 한계)
4. **페르소나 일관성 무너짐** (같은 종목에 페르소나 결론이 무작위)
5. **Cloud Run 안정성 문제**

---

## 📊 Day별 체크리스트

| Day | 산출물 | 커밋 |
|-----|-------|-----|
| 1-2 | test_60_cases.py + results | test(v2): 60-case regression |
| 3 | reviewer issues fix | fix(v2): reviewer feedback applied |
| 4 | 비용/성능 최적화 보고서 | perf(v2): cost optimization |
| 5 | 베타 준비 보고서 + staging | docs(v2): beta readiness |

---

## 🎬 베타 출시 후 (별도)

베타 출시는 Week E 완료 후 사용자 결정으로 진행.

이후 backlog:
- Phase 2: 자체 이벤트 통계 DB 구축 (LLM 추론 대체)
- 페르소나 추가 (Japan Specialist, China Specialist)
- 사용자 매칭 로직 (어떤 페르소나가 본인에게 맞는지 자동 진단)
- 페르소나 합의 시그널 메타 분석
