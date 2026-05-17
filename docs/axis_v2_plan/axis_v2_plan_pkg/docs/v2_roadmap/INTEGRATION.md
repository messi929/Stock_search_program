# LangGraph + Frontend 통합 가이드

> **위치**: `docs/v2_roadmap/INTEGRATION.md`
> **연관**: `docs/v2_roadmap/WEEK_D.md`

---

## 🎯 목표

기존 3 페르소나 시스템을 **6 페르소나로 확장**하면서:
- 기존 시스템 안정성 유지
- 데이터 접근 권한 매트릭스 적용
- 비용 추적 통합
- Frontend 6 페르소나 UI

---

## 1. LangGraph 분기 처리

### 1.1 기존 구조 (변경 X)

```python
# graph.py (기존)

def build_graph():
    workflow = StateGraph(AnalysisState)
    
    workflow.add_node("research", research_agent)
    workflow.add_node("analyst", analyst_agent)
    workflow.add_node("validator", validator_agent)
    workflow.add_node("strategist", strategist_agent)  # ← 단일 노드
    
    workflow.add_edge(START, "research")
    workflow.add_edge("research", "analyst")
    workflow.add_edge("analyst", "validator")
    workflow.add_edge("validator", "strategist")
    workflow.add_edge("strategist", END)
    
    return workflow.compile()
```

### 1.2 v2 구조 (페르소나 분기 추가)

```python
# graph.py (v2)

PERSONA_AGENTS = {
    "blackrock": blackrock_strategist,
    "ark": ark_strategist,
    "graham": graham_strategist,
    "event": event_analyst,         # ⭐ 신규
    "macro": macro_pm,              # ⭐ 신규
    "korean": korean_specialist,    # ⭐ 신규
}

def route_to_persona(state: AnalysisState) -> str:
    """선택된 페르소나로 라우팅"""
    persona = state.get("selected_persona", "blackrock")
    if persona not in PERSONA_AGENTS:
        return "blackrock"
    return persona

def build_graph_v2():
    workflow = StateGraph(AnalysisState)
    
    # 기존 4 Agent (변경 X)
    workflow.add_node("research", research_agent)
    workflow.add_node("analyst", analyst_agent)
    workflow.add_node("validator", validator_agent)
    
    # 페르소나별 Strategist 노드
    for persona_id, agent in PERSONA_AGENTS.items():
        workflow.add_node(f"strategist_{persona_id}", agent)
    
    # Edge 구성
    workflow.add_edge(START, "research")
    workflow.add_edge("research", "analyst")
    workflow.add_edge("analyst", "validator")
    
    # 조건부 분기: validator → 선택된 페르소나
    workflow.add_conditional_edges(
        "validator",
        route_to_persona,
        {p: f"strategist_{p}" for p in PERSONA_AGENTS.keys()}
    )
    
    # 모든 페르소나 → END
    for persona_id in PERSONA_AGENTS.keys():
        workflow.add_edge(f"strategist_{persona_id}", END)
    
    return workflow.compile()
```

### 1.3 멀티 페르소나 호출 (Pro/Premium)

사용자가 여러 페르소나 선택 시 **병렬 실행**:

```python
# api/analyses_v2.py

async def run_multi_persona_analysis(
    ticker: str,
    selected_personas: List[str],
    user_id: str,
):
    """여러 페르소나 동시 실행"""
    # 4 Agent (Research/Analyst/Validator)는 1번만 실행
    base_state = await run_base_pipeline(ticker, user_id)
    
    # 페르소나별 Strategist 병렬 실행
    persona_tasks = [
        run_persona_strategist(persona_id, base_state)
        for persona_id in selected_personas
    ]
    
    persona_results = await asyncio.gather(*persona_tasks)
    
    return {
        "ticker": ticker,
        "base_analysis": base_state,
        "persona_analyses": dict(zip(selected_personas, persona_results))
    }
```

**비용 효율**:
- 4 Agent 비용 = 1번만
- 페르소나 비용 = 선택한 개수만큼

---

## 2. 데이터 접근 권한 매트릭스

페르소나별로 접근하는 데이터가 다르므로 명시적 분기 필요:

```python
# agents/persona_data_access.py

from typing import Dict, Callable

PERSONA_DATA_REQUIREMENTS = {
    "blackrock": ["fundamentals", "macro_basic"],
    "ark": ["fundamentals", "tam_data"],
    "graham": ["fundamentals", "valuation"],
    
    "event": [
        "fundamentals",
        "options_signals",        # Week C
        "credit_short",           # Week C
        "event_calendar",         # Week C
        "similar_events_llm",     # Week C
    ],
    "macro": [
        "fundamentals",
        "fred_series",            # Week B
        "ecos_series",            # Week B
        "regime_detection",       # Week B
    ],
    "korean": [
        "fundamentals",
        "korea_supply_5y",        # Week A
        "chaebol_data",           # Week A
        "valueup_data",           # Week A
        "governance_score",       # Week A
        "short_selling_korea",    # Week A
    ],
}

async def collect_persona_data(persona_id: str, ticker: str) -> dict:
    """페르소나에 필요한 데이터만 수집"""
    requirements = PERSONA_DATA_REQUIREMENTS[persona_id]
    
    data = {}
    for req in requirements:
        try:
            data[req] = await DATA_COLLECTORS[req](ticker)
        except DataUnavailableError as e:
            data[req] = {"available": False, "reason": str(e)}
    
    return data
```

---

## 3. 비용 추적

### 3.1 페르소나별 비용 메타

```python
# utils/cost_tracker.py

PERSONA_COST_META = {
    "blackrock": {"model": "opus-4-7", "estimated_cost_krw": 370},
    "ark": {"model": "opus-4-7", "estimated_cost_krw": 370},
    "graham": {"model": "opus-4-7", "estimated_cost_krw": 370},
    "event": {"model": "sonnet-4-6", "estimated_cost_krw": 50},
    "macro": {"model": "sonnet-4-6", "estimated_cost_krw": 45},
    "korean": {"model": "sonnet-4-6", "estimated_cost_krw": 48},
}

async def track_analysis_cost(
    user_id: str,
    ticker: str,
    selected_personas: List[str],
    base_pipeline_cost: float,  # 4 Agent 비용 (페르소나 무관)
):
    """분석 1건 비용 추적"""
    persona_costs = sum(
        PERSONA_COST_META[p]["estimated_cost_krw"] 
        for p in selected_personas
    )
    total = base_pipeline_cost + persona_costs
    
    await firestore.collection("cost_logs").add({
        "user_id": user_id,
        "ticker": ticker,
        "personas": selected_personas,
        "base_cost": base_pipeline_cost,
        "persona_cost": persona_costs,
        "total": total,
        "created_at": SERVER_TIMESTAMP,
    })
```

### 3.2 일일 비용 모니터링

```python
# Cloud Run Job - 매일 09:00
async def daily_cost_alert():
    yesterday = (datetime.now() - timedelta(days=1)).date()
    total = await get_daily_cost(yesterday)
    
    if total > 10000:  # 1만원 초과
        await send_alert(f"⚠️ Daily cost exceeded: {total} KRW")
```

---

## 4. Frontend 통합

### 4.1 PersonaSwitch 6 탭 확장

```tsx
// web/components/PersonaSwitch.tsx

const PERSONAS = [
  { id: "blackrock", name: "블랙록", icon: "🏛", color: "#0066cc" },
  { id: "ark", name: "ARK", icon: "🚀", color: "#ff6600" },
  { id: "graham", name: "그레이엄", icon: "📚", color: "#996633" },
  { id: "event", name: "이벤트", icon: "📅", color: "#cc0066" },
  { id: "macro", name: "매크로", icon: "🌐", color: "#006633" },
  { id: "korean", name: "한국", icon: "🇰🇷", color: "#cc3333" },
];

export function PersonaSwitch({ selected, onChange, plan }) {
  // 플랜별 활성화 페르소나 (TBD - 비용 정책 확정 후)
  const accessiblePersonas = getAccessiblePersonas(plan);
  
  return (
    <div className="persona-switch">
      {/* 모바일: 가로 스크롤 */}
      <div className="overflow-x-auto md:overflow-visible">
        <div className="flex gap-2 min-w-max md:min-w-0">
          {PERSONAS.map((p) => {
            const isAccessible = accessiblePersonas.includes(p.id);
            return (
              <button
                key={p.id}
                disabled={!isAccessible}
                onClick={() => onChange(p.id)}
                className={...}
              >
                {p.icon} {p.name}
                {!isAccessible && <LockIcon />}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
```

### 4.2 페르소나별 카드 컴포넌트

신규 페르소나는 데이터 구조가 다르므로 카드 컴포넌트도 다름:

```
web/components/persona-cards/
├── BlackrockCard.tsx          (기존, 변경 X)
├── ArkCard.tsx                (기존, 변경 X)
├── GrahamCard.tsx             (기존, 변경 X)
├── EventAnalystCard.tsx       ⭐ 신규
├── MacroPMCard.tsx            ⭐ 신규
└── KoreanSpecialistCard.tsx   ⭐ 신규
```

#### EventAnalystCard 핵심 UI

```tsx
function EventAnalystCard({ data }) {
  return (
    <Card>
      {/* 확실성 점수 배지 */}
      <CertaintyBadge score={data.event_summary.certainty_breakdown.final_score} />
      
      {/* 시나리오 분석 */}
      <ScenarioAnalysis 
        bullish={data.scenario_analysis.bullish_case}
        base={data.scenario_analysis.base_case}
        bearish={data.scenario_analysis.bearish_case}
      />
      
      {/* 참고 통계 구간 */}
      <HistoricalZones data={data.reference_observation_zones} />
      
      {/* 거래량 + 수급 신호 */}
      <VolumeSupplySignals data={data.volume_supply_analysis} />
      
      {/* 옵션/신용/공매도 */}
      <SignalGrid 
        options={data.options_signals}
        credit={data.credit_short_signals}
      />
      
      {/* 단계별 펼치기 (UX) */}
      <ExpandableSection title="비교 사례 (LLM 추정)">
        {data.historical_statistics.comparable_events.map(e => (
          <EventCase event={e} confidence={e.data_confidence} />
        ))}
      </ExpandableSection>
    </Card>
  );
}
```

#### MacroPMCard 핵심 UI

```tsx
function MacroPMCard({ data }) {
  return (
    <Card>
      {/* 6 국면 시각화 (현재 위치 표시) */}
      <RegimeMap currentRegime={data.macro_regime.current_regime} />
      
      {/* 4 사이클 게이지 */}
      <CycleGauges cycles={data.cycle_analysis} />
      
      {/* 통상 강세/약세 자산 */}
      <AssetImplications data={data.regime_implications} />
      
      {/* 전이 신호 모니터링 */}
      <TransitionSignals signals={data.transition_signals_to_monitor} />
    </Card>
  );
}
```

#### KoreanSpecialistCard 핵심 UI

```tsx
function KoreanSpecialistCard({ data }) {
  return (
    <Card>
      {/* 한국 특수 점수 5각형 차트 */}
      <PentagonChart scores={data.korea_specific_score} />
      
      {/* 외국인 수급 차트 */}
      <ForeignSupplyChart data={data.foreign_supply_analysis} />
      
      {/* 재벌 구조 (있을 시) */}
      {data.chaebol_structure_analysis.is_chaebol && (
        <ChaebolStructure data={data.chaebol_structure_analysis} />
      )}
      
      {/* 밸류업 분석 */}
      <ValueupAnalysis data={data.value_up_analysis} />
      
      {/* 테마 사이클 */}
      <ThemeCycle data={data.theme_cycle_analysis} />
      
      {/* 한국 특수 모니터링 항목 */}
      <WatchList items={data.what_to_watch_korea_specific} />
    </Card>
  );
}
```

---

## 5. 사용자 가이드 (UX)

### 5.1 첫 진입 시 모달

"각 페르소나는 어떻게 다른가요?"

| 페르소나 | 한 문장 | 적합한 경우 |
|---------|--------|----------|
| 🏛 블랙록 | 잃지 않는 게 먼저 | 보수 장기 투자자 |
| 🚀 ARK | 10년 후 시장에 5년 베팅 | 성장주 공격 투자 |
| 📚 그레이엄 | 본질가치보다 30% 싸게 | 가치주 매수 |
| 📅 이벤트 | 이벤트 패턴을 통계로 | 단기 이벤트 매매 |
| 🌐 매크로 | 사이클이 종목보다 우선 | 거시 상황 분석 |
| 🇰🇷 한국 | 한국 시장은 다르다 | 한국 종목 깊이 |

### 5.2 페르소나 매칭 가이드 (선택 사항)

사용자 프로파일 → 페르소나 매칭 안내:
- 보유 기간 짧음 + 변동성 OK → Event 페르소나 안내
- 한국 종목 비중 70%+ → Korean 페르소나 안내
- 글로벌 분산 → Macro 페르소나 안내

⚠️ 페르소나 매칭은 분석 도구 안내일 뿐, 투자 판단 권유 X.

---

## ✅ 통합 검증 체크리스트

- [ ] 6 페르소나 모두 LangGraph 라우팅 정상
- [ ] 멀티 페르소나 호출 시 4 Agent 1번만 실행
- [ ] 페르소나별 데이터 접근 권한 정확
- [ ] 비용 추적 일별 보고 동작
- [ ] Frontend 6 탭 모바일 + 데스크탑 OK
- [ ] 페르소나별 카드 UI 데이터 매핑 정확
- [ ] 데이터 부재 시 graceful degradation
- [ ] a11y (키보드 네비게이션)
