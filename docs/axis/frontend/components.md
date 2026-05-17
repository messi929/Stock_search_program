# Frontend 핵심 컴포넌트

> **목적**: Axis만의 차별화된 UX를 만드는 핵심 컴포넌트들

---

## 🔥 핵심 3대 컴포넌트

1. **ValidateButton** ⭐ - 검증 버튼 (핵심 차별점)
2. **PersonaSwitch** - 페르소나 전환
3. **AnalysisStream** - SSE 스트리밍 분석 표시

---

## 1. ValidateButton ⭐

### 용도
모든 AI 분석 결과 옆에 노출. 클릭 시 모든 수치를 실시간 재검증.

### 위치
- `/analyze/[ticker]` 페이지 상단 + 각 에이전트 카드
- `/analyses/[id]` 과거 분석 페이지

### 구현

```typescript
// components/analyze/ValidateButton.tsx
"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { 
  Check, AlertTriangle, X, Loader2 
} from "lucide-react";
import { apiCall } from "@/lib/api";
import { ValidationResult } from "@/types/api";

interface ValidateButtonProps {
  analysisId: string;
  onValidated?: (result: ValidationResult) => void;
  size?: "sm" | "default" | "lg";
}

export function ValidateButton({
  analysisId,
  onValidated,
  size = "default",
}: ValidateButtonProps) {
  const [result, setResult] = useState<ValidationResult | null>(null);
  
  const { mutate, isPending } = useMutation({
    mutationFn: () => apiCall<ValidationResult>(
      `/api/ai/validate/${analysisId}`,
      { method: "POST" }
    ),
    onSuccess: (data) => {
      setResult(data);
      onValidated?.(data);
    },
  });
  
  const getStatusIcon = () => {
    if (isPending) return <Loader2 className="animate-spin" />;
    if (!result) return <span>🔍</span>;
    
    switch (result.overall_status) {
      case "PASS": return <Check className="text-green-500" />;
      case "WARN": return <AlertTriangle className="text-yellow-500" />;
      case "FAIL": return <X className="text-red-500" />;
    }
  };
  
  const getButtonText = () => {
    if (isPending) return "검증 중...";
    if (!result) return "검증하기";
    
    switch (result.overall_status) {
      case "PASS": return `검증 OK (${result.elapsed_minutes}분 전)`;
      case "WARN": return `주의 - 일부 stale`;
      case "FAIL": return `재분석 필요`;
    }
  };
  
  return (
    <div className="flex flex-col gap-2">
      <Button
        size={size}
        variant={
          result?.overall_status === "FAIL" ? "destructive" :
          result?.overall_status === "WARN" ? "outline" :
          "default"
        }
        onClick={() => mutate()}
        disabled={isPending}
      >
        {getStatusIcon()}
        <span className="ml-2">{getButtonText()}</span>
      </Button>
      
      {result && (
        <ValidationDetails result={result} />
      )}
    </div>
  );
}

function ValidationDetails({ result }: { result: ValidationResult }) {
  return (
    <div className="text-xs space-y-1 p-2 bg-muted rounded">
      <div className="flex items-center gap-2">
        <Badge variant="outline">신뢰도 {Math.round(result.confidence_score * 100)}%</Badge>
        <span>
          신선 {result.fresh_data_count} / Stale {result.stale_data_count}
        </span>
      </div>
      
      {result.checks.slice(0, 3).map((check) => (
        <div key={check.item} className="flex justify-between">
          <span>{check.item}</span>
          <span className={
            check.status === "OK" ? "text-green-500" :
            check.status === "WARN" ? "text-yellow-500" :
            "text-red-500"
          }>
            {check.diff_pct >= 0 ? "+" : ""}{check.diff_pct.toFixed(1)}%
          </span>
        </div>
      ))}
      
      {result.requires_reanalysis && (
        <Button size="sm" variant="link" className="text-xs">
          → 재분석 요청
        </Button>
      )}
    </div>
  );
}
```

### UX 노트

- **시각적 신호 강화**: 색상 + 아이콘 + 텍스트 3중
- **자동 재분석 버튼**: FAIL일 때만 노출
- **검증 상세 펼치기**: 어떤 수치가 stale인지 명시
- **부담 없는 버튼**: 작은 사이즈 옵션, 어디든 배치 가능

---

## 2. PersonaSwitch 🎭

### 용도
같은 종목을 블랙록/ARK/그레이엄 관점으로 즉시 전환

### 구현

```typescript
// components/analyze/PersonaSwitch.tsx
"use client";

import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAuth } from "@/hooks/useAuth";
import { Lock } from "lucide-react";
import { Tooltip } from "@/components/ui/tooltip";

interface Persona {
  id: "blackrock" | "ark" | "graham";
  name: string;
  icon: string;
  description: string;
  proOnly?: boolean;
}

const PERSONAS: Persona[] = [
  {
    id: "blackrock",
    name: "블랙록",
    icon: "🏛",
    description: "리스크 우선, 장기 가치"
  },
  {
    id: "ark",
    name: "ARK",
    icon: "🚀",
    description: "파괴적 혁신, 5년 시계",
    proOnly: true,
  },
  {
    id: "graham",
    name: "그레이엄",
    icon: "📚",
    description: "안전마진, 저평가",
    proOnly: true,
  },
];

interface PersonaSwitchProps {
  current: string;
  onChange: (persona: string) => void;
}

export function PersonaSwitch({ current, onChange }: PersonaSwitchProps) {
  const { userPlan } = useAuth();
  const isPro = userPlan === "pro" || userPlan === "premium";
  
  return (
    <Tabs value={current} onValueChange={onChange}>
      <TabsList className="grid grid-cols-3 w-full">
        {PERSONAS.map((persona) => {
          const locked = persona.proOnly && !isPro;
          
          return (
            <Tooltip
              key={persona.id}
              content={
                locked
                  ? "Pro 플랜에서 사용 가능"
                  : persona.description
              }
            >
              <TabsTrigger
                value={persona.id}
                disabled={locked}
                className="relative"
              >
                <span className="mr-2">{persona.icon}</span>
                <span>{persona.name}</span>
                {locked && (
                  <Lock className="ml-1 h-3 w-3 absolute top-1 right-1" />
                )}
              </TabsTrigger>
            </Tooltip>
          );
        })}
      </TabsList>
    </Tabs>
  );
}
```

### UX 노트

- **3개 탭 명시적**: 무엇이 있는지 한눈에
- **Lock 아이콘**: Pro 잠금 시각화
- **즉각 전환**: 클릭 시 바로 재분석 (캐시 활용)

### Free 유저 잠금 처리

```typescript
// app/(dashboard)/analyze/[ticker]/page.tsx
function AnalyzePage() {
  const [persona, setPersona] = useState("blackrock");
  const { userPlan } = useAuth();
  
  const handlePersonaChange = (newPersona: string) => {
    if (newPersona !== "blackrock" && userPlan === "free") {
      // 업그레이드 모달 표시
      showUpgradeDialog();
      return;
    }
    setPersona(newPersona);
  };
  
  // ...
}
```

---

## 3. AnalysisStream 📡

### 용도
SSE로 4개 에이전트 결과를 점진적으로 표시

### 구현

```typescript
// components/analyze/AnalysisStream.tsx
"use client";

import { useEffect, useState } from "react";
import { auth } from "@/lib/firebase";

interface AgentResult {
  agent: "research" | "analyst" | "validator" | "strategist";
  result: any;
  elapsed: number;
}

interface AnalysisStreamProps {
  ticker: string;
  persona: string;
  onComplete?: (analysisId: string) => void;
}

export function AnalysisStream({
  ticker,
  persona,
  onComplete,
}: AnalysisStreamProps) {
  const [results, setResults] = useState<{
    research?: any;
    analyst?: any;
    validator?: any;
    strategist?: any;
  }>({});
  
  const [currentAgent, setCurrentAgent] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  
  useEffect(() => {
    let eventSource: EventSource;
    
    const startStream = async () => {
      const token = await auth.currentUser?.getIdToken();
      
      // EventSource는 헤더 못 넣어서 URL에 토큰
      // 실제로는 fetch + ReadableStream 사용 권장
      const url = `${process.env.NEXT_PUBLIC_API_BASE_URL}/api/ai/analyze?` +
        `ticker=${ticker}&persona=${persona}&token=${token}`;
      
      eventSource = new EventSource(url);
      
      eventSource.addEventListener("research_start", () => {
        setCurrentAgent("research");
      });
      
      eventSource.addEventListener("research_complete", (e) => {
        const data = JSON.parse(e.data);
        setResults((prev) => ({ ...prev, research: data.result }));
      });
      
      eventSource.addEventListener("analyst_start", () => {
        setCurrentAgent("analyst");
      });
      
      eventSource.addEventListener("analyst_complete", (e) => {
        const data = JSON.parse(e.data);
        setResults((prev) => ({ ...prev, analyst: data.result }));
      });
      
      eventSource.addEventListener("validator_complete", (e) => {
        const data = JSON.parse(e.data);
        setResults((prev) => ({ ...prev, validator: data.result }));
      });
      
      eventSource.addEventListener("strategist_complete", (e) => {
        const data = JSON.parse(e.data);
        setResults((prev) => ({ ...prev, strategist: data.result }));
        setCurrentAgent(null);
      });
      
      eventSource.addEventListener("complete", (e) => {
        const data = JSON.parse(e.data);
        eventSource.close();
        onComplete?.(data.analysis_id);
      });
      
      eventSource.addEventListener("error", (e) => {
        eventSource.close();
        setError("분석 중 오류가 발생했습니다");
      });
    };
    
    startStream();
    
    return () => {
      eventSource?.close();
    };
  }, [ticker, persona]);
  
  return (
    <div className="space-y-4">
      {/* Strategist - 최상단 표시 */}
      {results.strategist ? (
        <StrategistCard result={results.strategist} />
      ) : (
        <SkeletonCard title="🎯 종합 분석" loading={currentAgent === "strategist"} />
      )}
      
      {/* 펼치기 가능한 상세 */}
      <Accordion type="multiple">
        <AccordionItem value="research">
          <AccordionTrigger>
            🔍 시황/뉴스 (Research)
            {currentAgent === "research" && <Loader2 className="ml-2 animate-spin h-4 w-4" />}
            {results.research && <Check className="ml-2 text-green-500 h-4 w-4" />}
          </AccordionTrigger>
          <AccordionContent>
            {results.research ? (
              <ResearchCard result={results.research} />
            ) : (
              <Skeleton className="h-32" />
            )}
          </AccordionContent>
        </AccordionItem>
        
        <AccordionItem value="analyst">
          <AccordionTrigger>📊 기술/펀더멘털 (Analyst)</AccordionTrigger>
          <AccordionContent>
            {results.analyst && <AnalystCard result={results.analyst} />}
          </AccordionContent>
        </AccordionItem>
        
        <AccordionItem value="validator">
          <AccordionTrigger>⭐ 검증/Contrarian</AccordionTrigger>
          <AccordionContent>
            {results.validator && <ValidatorCard result={results.validator} />}
          </AccordionContent>
        </AccordionItem>
      </Accordion>
      
      {error && <ErrorAlert message={error} />}
    </div>
  );
}
```

### UX 노트

- **점진적 표시**: 사용자가 기다리는 느낌 적게
- **Strategist 최상단**: 가장 중요한 결과 먼저
- **상세 펼침/접기**: 깊이 보고 싶은 사람만
- **로딩 애니메이션**: 어떤 에이전트가 작동 중인지 표시

---

## 🎴 결과 카드 컴포넌트

### StrategistCard

```typescript
// components/analyze/StrategistCard.tsx
import { Card } from "@/components/ui/card";
import { Disclaimer } from "@/components/legal/Disclaimer";
import { ValidateButton } from "./ValidateButton";

export function StrategistCard({ result, analysisId }) {
  return (
    <Card className="p-6 space-y-4">
      <div className="flex justify-between items-start">
        <h2 className="text-xl font-bold">
          🎯 {result.persona_used === "blackrock" && "블랙록"} 관점 종합 분석
        </h2>
        {analysisId && <ValidateButton analysisId={analysisId} size="sm" />}
      </div>
      
      <div className="prose prose-sm dark:prose-invert">
        <p>{result.persona_perspective}</p>
        <p>{result.summary}</p>
      </div>
      
      {result.entry_points && (
        <div className="bg-muted p-4 rounded-lg space-y-2">
          <h3 className="font-semibold">📌 참고 진입 구간</h3>
          <ul className="space-y-1 text-sm">
            <li>• 1차: {formatPrice(result.entry_points.tier_1)}원 (-10%)</li>
            <li>• 2차: {formatPrice(result.entry_points.tier_2)}원 (-15%)</li>
            <li>• 3차: {formatPrice(result.entry_points.tier_3)}원 (-20%)</li>
          </ul>
          <div className="text-xs text-muted-foreground">
            기준: {result.entry_points.technical_basis.join(", ")}
          </div>
        </div>
      )}
      
      {result.alert_conditions?.length > 0 && (
        <div className="space-y-2">
          <h3 className="font-semibold">🔔 알림 설정 (참고)</h3>
          {result.alert_conditions.map((cond, i) => (
            <div key={i} className="flex items-center gap-2">
              <Checkbox id={`alert-${i}`} />
              <label htmlFor={`alert-${i}`}>{cond.description}</label>
            </div>
          ))}
        </div>
      )}
      
      {result.follow_up_questions?.length > 0 && (
        <div className="space-y-2">
          <h3 className="font-semibold">💡 추가 검토 질문</h3>
          <ol className="list-decimal list-inside text-sm">
            {result.follow_up_questions.map((q, i) => (
              <li key={i}>{q}</li>
            ))}
          </ol>
        </div>
      )}
      
      <Disclaimer />
    </Card>
  );
}
```

---

### ValidatorCard

```typescript
// components/analyze/ValidatorCard.tsx
export function ValidatorCard({ result }) {
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <Badge variant={
          result.overall_status === "PASS" ? "default" :
          result.overall_status === "WARN" ? "outline" :
          "destructive"
        }>
          {result.overall_status}
        </Badge>
        <span>신뢰도 {Math.round(result.confidence_score * 100)}%</span>
      </div>
      
      {/* Contrarian 시나리오 강조 */}
      <div className="space-y-3">
        <h4 className="font-semibold">🔄 분석이 틀릴 수 있는 이유</h4>
        {result.contrarian_scenarios.map((s, i) => (
          <div key={i} className="border-l-4 border-orange-500 pl-3 py-1">
            <div className="font-medium">{s.title}</div>
            <p className="text-sm text-muted-foreground">{s.description}</p>
            <div className="text-xs mt-1">
              영향: {s.impact_estimate} • 확률: {s.probability}
            </div>
          </div>
        ))}
      </div>
      
      {/* Blind Spots */}
      {result.blind_spots?.length > 0 && (
        <div>
          <h4 className="font-semibold">👁 분석에서 빠진 관점</h4>
          <ul className="list-disc list-inside text-sm">
            {result.blind_spots.map((b, i) => (
              <li key={i}>{b}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
```

---

## 4. EntryPointEditor

### 용도
관심 종목의 진입선/손절선 수정

```typescript
// components/watchlist/EntryPointEditor.tsx
"use client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Sparkles } from "lucide-react";

export function EntryPointEditor({ ticker, currentPrice, initial, onChange }) {
  const [tier1, setTier1] = useState(initial?.tier_1 || Math.floor(currentPrice * 0.9));
  const [tier2, setTier2] = useState(initial?.tier_2 || Math.floor(currentPrice * 0.85));
  const [tier3, setTier3] = useState(initial?.tier_3 || Math.floor(currentPrice * 0.8));
  
  const { mutate: getAISuggestion, isPending } = useMutation({
    mutationFn: () => apiCall(`/api/ai/entry-suggest`, {
      method: "POST",
      body: JSON.stringify({ ticker })
    }),
    onSuccess: (data) => {
      setTier1(data.tiers[0].price);
      setTier2(data.tiers[1].price);
      setTier3(data.tiers[2].price);
    }
  });
  
  return (
    <div className="space-y-4">
      <div className="flex justify-between">
        <h3 className="font-semibold">진입선 설정</h3>
        <Button 
          size="sm" 
          variant="outline"
          onClick={() => getAISuggestion()}
          disabled={isPending}
        >
          <Sparkles className="mr-2 h-4 w-4" />
          AI 참고 수치 (Pro)
        </Button>
      </div>
      
      <div className="space-y-2">
        <Label>1차 진입선 (-10%)</Label>
        <Input 
          type="number" 
          value={tier1} 
          onChange={(e) => setTier1(+e.target.value)} 
        />
        
        <Label>2차 진입선 (-15%)</Label>
        <Input 
          type="number" 
          value={tier2}
          onChange={(e) => setTier2(+e.target.value)}
        />
        
        <Label>3차 진입선 (-20%)</Label>
        <Input 
          type="number"
          value={tier3}
          onChange={(e) => setTier3(+e.target.value)}
        />
      </div>
      
      <div className="text-xs text-muted-foreground">
        💡 진입선은 참고 수치이며, 실제 매매는 본인의 판단입니다.
      </div>
    </div>
  );
}
```

---

## 5. Disclaimer (필수)

```typescript
// components/legal/Disclaimer.tsx
export function Disclaimer() {
  return (
    <div className="text-xs text-muted-foreground border-t pt-3 mt-4 space-y-1">
      <p>📌 본 분석은 투자 권유가 아닌 정보 제공입니다.</p>
      <p>최종 투자 판단은 사용자 본인의 책임입니다.</p>
      <p>Axis는 자본시장법상 투자자문업 면허가 없습니다.</p>
    </div>
  );
}
```

**모든 분석 결과에 필수 포함**

---

## 6. SkeletonCard (로딩)

```typescript
// components/ui/SkeletonCard.tsx
export function SkeletonCard({ title, loading }) {
  return (
    <Card className="p-6">
      <div className="flex justify-between items-center mb-4">
        <h3 className="font-semibold">{title}</h3>
        {loading && <Loader2 className="animate-spin h-4 w-4" />}
      </div>
      <div className="space-y-2">
        <div className="h-4 bg-muted rounded animate-pulse" />
        <div className="h-4 bg-muted rounded animate-pulse w-3/4" />
        <div className="h-4 bg-muted rounded animate-pulse w-1/2" />
      </div>
    </Card>
  );
}
```

---

## 🛠 상태 관리

### Zustand (클라이언트 상태)

```typescript
// store/personaStore.ts
import { create } from "zustand";
import { persist } from "zustand/middleware";

interface PersonaState {
  selected: "blackrock" | "ark" | "graham";
  setSelected: (persona: string) => void;
}

export const usePersonaStore = create<PersonaState>()(
  persist(
    (set) => ({
      selected: "blackrock",
      setSelected: (selected) => set({ selected }),
    }),
    { name: "axis-persona" }
  )
);
```

### TanStack Query (서버 상태)

```typescript
// hooks/useWatchlist.ts
export function useWatchlist() {
  return useQuery({
    queryKey: ["watchlist"],
    queryFn: () => apiCall("/api/watchlist"),
    staleTime: 30 * 1000, // 30초
  });
}

export function useAddWatchlist() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (data) => apiCall("/api/watchlist", {
      method: "POST",
      body: JSON.stringify(data),
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["watchlist"] });
    },
  });
}
```

---

## 📦 shadcn/ui 컴포넌트 설치 목록

```bash
npx shadcn-ui@latest add button card dialog input label
npx shadcn-ui@latest add badge tabs accordion dropdown-menu
npx shadcn-ui@latest add toast tooltip skeleton checkbox
npx shadcn-ui@latest add select textarea form sheet
```

---

**완료**: 모든 Frontend 핵심 컴포넌트 명세
