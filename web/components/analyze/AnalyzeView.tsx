"use client";

/**
 * 분석 페이지 클라이언트 컨테이너 — 6 페르소나 SSE 스트리밍 오케스트레이션.
 *
 * 페르소나 그룹별 흐름:
 *  - **Strategist 흐름** (blackrock/ark/graham):
 *      start → research_complete → analyst_complete → validator_complete → strategist_complete → complete
 *  - **데이터 페르소나** (event/macro/korean):
 *      start → {persona}_complete → complete   (단일 노드)
 *
 * persona 변경 시 새 분석 시작 (default_cache 히트면 즉시 응답).
 */
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { AddToWatchlistButton } from "@/components/analyze/AddToWatchlistButton";
import { AnalystCard } from "@/components/analyze/AnalystCard";
import { EventAnalystCard } from "@/components/analyze/EventAnalystCard";
import { KoreanSpecialistCard } from "@/components/analyze/KoreanSpecialistCard";
import { MacroPmCard } from "@/components/analyze/MacroPmCard";
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
import { usePersonaStore } from "@/store/personaStore";
import type {
  AnalystResult,
  EventAnalystResult,
  KoreanSpecialistResult,
  MacroPmResult,
  ResearchResult,
  StrategistResult,
  ValidatorResult,
} from "@/types/api";
import { isStrategistPersona, type PersonaId } from "@/types/persona";

type AgentStatus = "pending" | "running" | "done" | "error";

type StrategistFlowState = {
  research: ResearchResult | null;
  analyst: AnalystResult | null;
  validator: ValidatorResult | null;
  strategist: StrategistResult | null;
};

type StrategistFlowStatus = {
  research: AgentStatus;
  analyst: AgentStatus;
  validator: AgentStatus;
  strategist: AgentStatus;
};

type DataDrivenState = {
  event: EventAnalystResult | null;
  macro: MacroPmResult | null;
  korean: KoreanSpecialistResult | null;
};

type DataDrivenStatus = {
  event: AgentStatus;
  macro: AgentStatus;
  korean: AgentStatus;
};

const initialStrategistStatus: StrategistFlowStatus = {
  research: "pending",
  analyst: "pending",
  validator: "pending",
  strategist: "pending",
};

const initialDataDrivenStatus: DataDrivenStatus = {
  event: "pending",
  macro: "pending",
  korean: "pending",
};

export function AnalyzeView({ ticker }: { ticker: string }) {
  const persona = usePersonaStore((s) => s.current);
  const { profile } = useUserProfile();
  const isStrategist = isStrategistPersona(persona);

  // 분석이 끝나기 전(~10s)에도 종목명을 노출 — Analyst가 채워주기 전 fallback.
  const { data: stockSearch } = useStockSearch(ticker, 1);
  const earlyName = stockSearch?.stocks?.find(
    (s) => s.ticker === ticker.toUpperCase(),
  )?.name ?? null;

  // Strategist 흐름 상태
  const [strategistFlow, setStrategistFlow] = useState<StrategistFlowState>({
    research: null,
    analyst: null,
    validator: null,
    strategist: null,
  });
  const [strategistStatus, setStrategistStatus] = useState<StrategistFlowStatus>(
    initialStrategistStatus,
  );

  // 데이터 페르소나 상태
  const [dataDriven, setDataDriven] = useState<DataDrivenState>({
    event: null,
    macro: null,
    korean: null,
  });
  const [dataDrivenStatus, setDataDrivenStatus] = useState<DataDrivenStatus>(
    initialDataDrivenStatus,
  );

  const [overallElapsed, setOverallElapsed] = useState<number | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    const ac = new AbortController();
    abortRef.current?.abort();
    abortRef.current = ac;

    // reset
    setStrategistFlow({
      research: null,
      analyst: null,
      validator: null,
      strategist: null,
    });
    setDataDriven({ event: null, macro: null, korean: null });
    setOverallElapsed(null);
    setRunError(null);

    if (isStrategist) {
      setStrategistStatus({
        research: "running",
        analyst: "running",
        validator: "pending",
        strategist: "pending",
      });
      setDataDrivenStatus(initialDataDrivenStatus);
    } else {
      setStrategistStatus(initialStrategistStatus);
      // 데이터 페르소나는 현재 persona만 running, 나머지 pending
      setDataDrivenStatus({
        event: persona === "event" ? "running" : "pending",
        macro: persona === "macro" ? "running" : "pending",
        korean: persona === "korean" ? "running" : "pending",
      });
    }

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
        const payload = data as {
          result?: unknown;
          total_elapsed?: number;
          message?: string;
        };

        switch (event) {
          case "start":
            break;

          // Strategist 흐름
          case "research_complete":
            setStrategistFlow((s) => ({
              ...s,
              research: payload.result as ResearchResult,
            }));
            setStrategistStatus((s) => ({
              ...s,
              research: "done",
              validator: "running",
            }));
            break;
          case "analyst_complete":
            setStrategistFlow((s) => ({
              ...s,
              analyst: payload.result as AnalystResult,
            }));
            setStrategistStatus((s) => ({
              ...s,
              analyst: "done",
              validator: "running",
            }));
            break;
          case "validator_complete":
            setStrategistFlow((s) => ({
              ...s,
              validator: payload.result as ValidatorResult,
            }));
            setStrategistStatus((s) => ({
              ...s,
              validator: "done",
              strategist: "running",
            }));
            break;
          case "strategist_complete":
            setStrategistFlow((s) => ({
              ...s,
              strategist: payload.result as StrategistResult,
            }));
            setStrategistStatus((s) => ({ ...s, strategist: "done" }));
            break;

          // 데이터 페르소나
          case "event_complete":
            setDataDriven((s) => ({
              ...s,
              event: payload.result as EventAnalystResult,
            }));
            setDataDrivenStatus((s) => ({ ...s, event: "done" }));
            break;
          case "macro_complete":
            setDataDriven((s) => ({
              ...s,
              macro: payload.result as MacroPmResult,
            }));
            setDataDrivenStatus((s) => ({ ...s, macro: "done" }));
            break;
          case "korean_complete":
            setDataDriven((s) => ({
              ...s,
              korean: payload.result as KoreanSpecialistResult,
            }));
            setDataDrivenStatus((s) => ({ ...s, korean: "done" }));
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
      const msg =
        err instanceof APIError
          ? err.message
          : err instanceof Error
            ? err.message
            : "분석 실패";
      setRunError(msg);
      toast.error(msg);
      if (isStrategist) {
        setStrategistStatus({
          research: "error",
          analyst: "error",
          validator: "error",
          strategist: "error",
        });
      } else {
        setDataDrivenStatus({
          event: persona === "event" ? "error" : "pending",
          macro: persona === "macro" ? "error" : "pending",
          korean: persona === "korean" ? "error" : "pending",
        });
      }
    });

    return () => ac.abort();
  }, [ticker, persona, profile, isStrategist]);

  // 종목명 표시 — Strategist 흐름은 analyst가 채워줌, 데이터 페르소나는 earlyName fallback
  const displayName = strategistFlow.analyst?.name ?? earlyName;
  const displayPrice = strategistFlow.analyst?.technical.current_price;

  return (
    <div className="space-y-6 max-w-5xl">
      {/* Header */}
      <header className="space-y-4">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-2xl font-bold font-mono">{ticker}</h1>
            {displayName ? (
              <p className="text-sm text-muted-foreground mt-1">
                {displayName}
                {displayPrice != null
                  ? ` · ${displayPrice.toLocaleString()}원`
                  : !isStrategist
                    ? ""
                    : " · 가격 조회 중..."}
              </p>
            ) : null}
          </div>
          <div className="flex items-center gap-2">
            <PersonaSwitch current={persona} />
            <PersonaGuideModal />
          </div>
        </div>

        {/* Action buttons — Strategist 흐름 결과 의존이라 데이터 페르소나에선 숨김 */}
        {isStrategist && (
          <div className="flex flex-wrap items-start gap-2">
            <AddToWatchlistButton ticker={ticker} />
            <ValidateButton
              ticker={ticker}
              research={strategistFlow.research}
              analyst={strategistFlow.analyst}
              onResult={(v) =>
                setStrategistFlow((s) => ({ ...s, validator: v }))
              }
            />
            <SaveEntryPointsButton
              ticker={ticker}
              strategist={strategistFlow.strategist}
            />
          </div>
        )}
        {!isStrategist && (
          <div className="flex flex-wrap items-start gap-2">
            <AddToWatchlistButton ticker={ticker} />
          </div>
        )}
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

      {/* 페르소나 그룹별 카드 분기 */}
      {isStrategist ? (
        <>
          <StrategistCard
            data={strategistFlow.strategist}
            status={strategistStatus.strategist}
          />
          <ValidatorCard
            data={strategistFlow.validator}
            status={strategistStatus.validator}
          />
          <AnalystCard
            data={strategistFlow.analyst}
            status={strategistStatus.analyst}
          />
          <ResearchCard
            data={strategistFlow.research}
            status={strategistStatus.research}
          />
        </>
      ) : persona === "event" ? (
        <EventAnalystCard data={dataDriven.event} status={dataDrivenStatus.event} />
      ) : persona === "macro" ? (
        <MacroPmCard data={dataDriven.macro} status={dataDrivenStatus.macro} />
      ) : persona === "korean" ? (
        <KoreanSpecialistCard
          data={dataDriven.korean}
          status={dataDrivenStatus.korean}
        />
      ) : null}

      <Disclaimer />
    </div>
  );
}
