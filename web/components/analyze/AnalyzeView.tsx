"use client";

/**
 * 분석 페이지 클라이언트 컨테이너 — SSE 스트리밍 오케스트레이션.
 *
 * 흐름:
 *  1. mount 시 POST /api/ai/analyze stream=true 시작 (apiStream)
 *  2. start → research_complete → analyst_complete → validator_complete → strategist_complete → complete
 *  3. 각 이벤트마다 해당 에이전트 카드 채워짐
 *  4. 페르소나 변경 시 새 분석 시작 (default_cache 히트면 즉시 응답)
 */
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { AddToWatchlistButton } from "@/components/analyze/AddToWatchlistButton";
import { AnalystCard } from "@/components/analyze/AnalystCard";
import { ResearchCard } from "@/components/analyze/ResearchCard";
import { SaveEntryPointsButton } from "@/components/analyze/SaveEntryPointsButton";
import { StrategistCard } from "@/components/analyze/StrategistCard";
import { ValidateButton } from "@/components/analyze/ValidateButton";
import { ValidatorCard } from "@/components/analyze/ValidatorCard";
import { Disclaimer } from "@/components/legal/Disclaimer";
import { PersonaGuideModal } from "@/components/persona/PersonaGuideModal";
import { PersonaSwitch } from "@/components/persona/PersonaSwitch";
import { Card, CardContent } from "@/components/ui/card";
import { useStockSearch } from "@/hooks/useStockSearch";
import { useUserProfile } from "@/hooks/useUserProfile";
import { apiStream, APIError } from "@/lib/api";
import { usePersonaStore, type PersonaId } from "@/store/personaStore";
import type {
  AnalystResult,
  ResearchResult,
  StrategistResult,
  ValidatorResult,
} from "@/types/api";

type AgentKey = "research" | "analyst" | "validator" | "strategist";
type AgentStatus = "pending" | "running" | "done" | "error";

export function AnalyzeView({ ticker }: { ticker: string }) {
  const persona = usePersonaStore((s) => s.current);
  const { profile } = useUserProfile();

  // 분석이 끝나기 전(~10s)에도 종목명을 노출 — Analyst가 채워주기 전 fallback.
  // staleTime 30s로 캐싱되므로 추가 비용 없음.
  const { data: stockSearch } = useStockSearch(ticker, 1);
  const earlyName = stockSearch?.stocks?.find(
    (s) => s.ticker === ticker.toUpperCase(),
  )?.name ?? null;

  const [research, setResearch] = useState<ResearchResult | null>(null);
  const [analyst, setAnalyst] = useState<AnalystResult | null>(null);
  const [validator, setValidator] = useState<ValidatorResult | null>(null);
  const [strategist, setStrategist] = useState<StrategistResult | null>(null);

  const [status, setStatus] = useState<Record<AgentKey, AgentStatus>>({
    research: "pending",
    analyst: "pending",
    validator: "pending",
    strategist: "pending",
  });

  const [overallElapsed, setOverallElapsed] = useState<number | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    const ac = new AbortController();
    abortRef.current?.abort();
    abortRef.current = ac;

    // reset
    setResearch(null);
    setAnalyst(null);
    setValidator(null);
    setStrategist(null);
    setStatus({
      research: "running",
      analyst: "running",
      validator: "pending",
      strategist: "pending",
    });
    setOverallElapsed(null);
    setRunError(null);

    const userProfile = profile
      ? {
          investing_experience: profile.investing_experience,
          holding_period: profile.holding_period,
          volatility_tolerance: profile.volatility_tolerance,
          interested_sectors: profile.interested_sectors,
          investment_principles: profile.investment_principles,
        }
      : null;

    apiStream(
      "/api/ai/analyze",
      {
        ticker,
        query: `${ticker} 분석`,
        persona,
        stream: true,
        user_profile: userProfile,
      },
      (event, data) => {
        const payload = data as { result?: unknown; total_elapsed?: number; message?: string };

        switch (event) {
          case "start":
            // 시작 메타 — 추가 처리 필요 시 여기서
            break;
          case "research_complete":
            setResearch(payload.result as ResearchResult);
            setStatus((s) => ({ ...s, research: "done", validator: "running" }));
            break;
          case "analyst_complete":
            setAnalyst(payload.result as AnalystResult);
            setStatus((s) => ({ ...s, analyst: "done", validator: "running" }));
            break;
          case "validator_complete":
            setValidator(payload.result as ValidatorResult);
            setStatus((s) => ({ ...s, validator: "done", strategist: "running" }));
            break;
          case "strategist_complete":
            setStrategist(payload.result as StrategistResult);
            setStatus((s) => ({ ...s, strategist: "done" }));
            break;
          case "complete":
            if (typeof payload.total_elapsed === "number") {
              setOverallElapsed(payload.total_elapsed);
            }
            break;
          case "error":
            setRunError(payload.message ?? "분석 중 오류");
            toast.error(payload.message ?? "분석 중 오류");
            break;
        }
      },
      ac.signal,
    ).catch((err: unknown) => {
      if (err instanceof DOMException && err.name === "AbortError") return;
      const msg = err instanceof APIError ? err.message : err instanceof Error ? err.message : "분석 실패";
      setRunError(msg);
      toast.error(msg);
      setStatus({
        research: "error",
        analyst: "error",
        validator: "error",
        strategist: "error",
      });
    });

    return () => ac.abort();
  }, [ticker, persona, profile]);

  return (
    <div className="space-y-6 max-w-5xl">
      {/* Header */}
      <header className="space-y-4">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-2xl font-bold font-mono">{ticker}</h1>
            {analyst ? (
              <p className="text-sm text-muted-foreground mt-1">
                {analyst.name} · {analyst.technical.current_price.toLocaleString()}원
              </p>
            ) : earlyName ? (
              <p className="text-sm text-muted-foreground mt-1">
                {earlyName} · 가격 조회 중...
              </p>
            ) : null}
          </div>
          <div className="flex items-center gap-2">
            <PersonaSwitch current={persona} />
            <PersonaGuideModal />
          </div>
        </div>

        {/* Action buttons — 모바일에서 flex-wrap */}
        <div className="flex flex-wrap items-start gap-2">
          <AddToWatchlistButton ticker={ticker} />
          <ValidateButton
            ticker={ticker}
            research={research}
            analyst={analyst}
            onResult={setValidator}
          />
          <SaveEntryPointsButton ticker={ticker} strategist={strategist} />
        </div>
      </header>

      {/* Overall status */}
      {runError ? (
        <Card>
          <CardContent className="p-4 text-sm text-destructive">
            ⚠️ {runError}
          </CardContent>
        </Card>
      ) : overallElapsed !== null ? (
        <p className="text-xs text-muted-foreground">
          전체 분석 완료 ({overallElapsed}초)
        </p>
      ) : (
        <p className="text-xs text-muted-foreground">분석 진행 중...</p>
      )}

      {/* Strategist (사용자 지향 종합) — 가장 위 */}
      <StrategistCard data={strategist} status={status.strategist} />

      {/* Validator — 핵심 차별점 */}
      <ValidatorCard data={validator} status={status.validator} />

      {/* Analyst */}
      <AnalystCard data={analyst} status={status.analyst} />

      {/* Research */}
      <ResearchCard data={research} status={status.research} />

      <Disclaimer />
    </div>
  );
}

