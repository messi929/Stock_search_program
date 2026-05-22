"use client";

/**
 * 분석 페이지 클라이언트 컨테이너 — 6 페르소나 SSE 스트리밍 오케스트레이션.
 *
 * UX 흐름 (2단 구조):
 *  1. 종목 진입 → PersonaChooser로 "분석 방식 + 관점"을 의도적으로 선택 (자동 실행 X)
 *  2. "분석 시작" → 선택한 페르소나로 1회 실행 (불필요한 과금 방지)
 *  3. 결과 후 PersonaSwitch로 다른 관점 재실행 가능
 *
 * 페르소나 그룹별 흐름:
 *  - Strategist (blackrock/ark/graham):
 *      start → research/analyst → validator → strategist → complete
 *  - 데이터 페르소나 (event/macro/korean): start → {persona}_complete → complete
 */
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { AddToWatchlistButton } from "@/components/analyze/AddToWatchlistButton";
import { AnalystCard } from "@/components/analyze/AnalystCard";
import { EventAnalystCard } from "@/components/analyze/EventAnalystCard";
import { KoreanSpecialistCard } from "@/components/analyze/KoreanSpecialistCard";
import { MacroPmCard } from "@/components/analyze/MacroPmCard";
import { PersonaChooser } from "@/components/analyze/PersonaChooser";
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
  const storePersona = usePersonaStore((s) => s.current);
  const setStorePersona = usePersonaStore((s) => s.setPersona);
  const { profile } = useUserProfile();

  // runPersona: 실제로 실행할 페르소나. null이면 미선택 → 선택 화면 표시(자동 실행 X).
  const [runPersona, setRunPersona] = useState<PersonaId | null>(null);
  const isStrategist = runPersona ? isStrategistPersona(runPersona) : false;

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

  // 종목이 바뀌면 선택 화면으로 되돌림(의도적 재선택 + 자동 실행 방지).
  useEffect(() => {
    setRunPersona(null);
  }, [ticker]);

  useEffect(() => {
    // 페르소나 미선택 시 실행하지 않음(과금 방지).
    if (!runPersona) return;

    const ac = new AbortController();
    abortRef.current?.abort();
    abortRef.current = ac;
    const runStrategist = isStrategistPersona(runPersona);

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

    if (runStrategist) {
      setStrategistStatus({
        research: "running",
        analyst: "running",
        validator: "pending",
        strategist: "pending",
      });
      setDataDrivenStatus(initialDataDrivenStatus);
    } else {
      setStrategistStatus(initialStrategistStatus);
      setDataDrivenStatus({
        event: runPersona === "event" ? "running" : "pending",
        macro: runPersona === "macro" ? "running" : "pending",
        korean: runPersona === "korean" ? "running" : "pending",
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
        persona: runPersona,
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
      if (runStrategist) {
        setStrategistStatus({
          research: "error",
          analyst: "error",
          validator: "error",
          strategist: "error",
        });
      } else {
        setDataDrivenStatus({
          event: runPersona === "event" ? "error" : "pending",
          macro: runPersona === "macro" ? "error" : "pending",
          korean: runPersona === "korean" ? "error" : "pending",
        });
      }
    });

    return () => ac.abort();
  }, [ticker, runPersona, profile]);

  // 분석 시작(또는 관점 전환) — store에 기억 + 실행 트리거.
  const startAnalysis = (id: PersonaId) => {
    setStorePersona(id);
    setRunPersona(id);
  };

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
                  : runPersona && isStrategist
                    ? " · 가격 조회 중..."
                    : ""}
              </p>
            ) : null}
          </div>
          {/* 결과 단계에서만 관점 전환 노출(재실행). 선택 단계에선 chooser가 담당. */}
          {runPersona && (
            <div className="flex items-center gap-2">
              <PersonaSwitch current={runPersona} onSelect={startAnalysis} />
              <PersonaGuideModal />
            </div>
          )}
        </div>

        {/* Action buttons — 결과 단계 + Strategist 흐름에서만 */}
        {runPersona && isStrategist && (
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
        {runPersona && !isStrategist && (
          <div className="flex flex-wrap items-start gap-2">
            <AddToWatchlistButton ticker={ticker} />
          </div>
        )}
      </header>

      {/* 선택 단계 — 분석 방식/관점 선택 (자동 실행 없음) */}
      {!runPersona ? (
        <Card>
          <CardContent className="p-5">
            <PersonaChooser
              defaultPersona={storePersona}
              onStart={startAnalysis}
            />
          </CardContent>
        </Card>
      ) : (
        <>
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
          ) : runPersona === "event" ? (
            <EventAnalystCard data={dataDriven.event} status={dataDrivenStatus.event} />
          ) : runPersona === "macro" ? (
            <MacroPmCard data={dataDriven.macro} status={dataDrivenStatus.macro} />
          ) : runPersona === "korean" ? (
            <KoreanSpecialistCard
              data={dataDriven.korean}
              status={dataDrivenStatus.korean}
            />
          ) : null}
        </>
      )}

      <Disclaimer />
    </div>
  );
}
