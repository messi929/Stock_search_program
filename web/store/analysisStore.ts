"use client";

/**
 * 분석 실행 상태 (Zustand) — 종목별 SSE 스트림을 컴포넌트 수명과 분리.
 *
 * 왜: 기존 AnalyzeView는 분석 상태를 로컬 useState로 들고, 언마운트 시
 * AbortController로 SSE를 끊었다. 사용자가 분석 중(30~90초) 다른 화면으로
 * 이동하면 분석이 멈췄다. 이 store는 진행 상태와 AbortController를 전역에
 * 보관하므로, 화면을 떠나도 fetch가 계속 store를 갱신하고, 재진입 시 그대로
 * 복원된다. (탭을 닫으면 끊김 — 그건 서버 잡이 아닌 한 불가피.)
 *
 * key = ticker(대문자). 한 종목당 하나의 실행. 페르소나 전환 시 같은 key를
 * 덮어쓰며 이전 스트림은 abort.
 */
import { create } from "zustand";
import { toast } from "sonner";

import { apiStream, APIError } from "@/lib/api";
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

export type AgentStatus = "pending" | "running" | "done" | "error";

export interface StrategistFlow {
  research: ResearchResult | null;
  analyst: AnalystResult | null;
  validator: ValidatorResult | null;
  strategist: StrategistResult | null;
}

export interface StrategistStatus {
  research: AgentStatus;
  analyst: AgentStatus;
  validator: AgentStatus;
  strategist: AgentStatus;
}

export interface DataDriven {
  event: EventAnalystResult | null;
  macro: MacroPmResult | null;
  korean: KoreanSpecialistResult | null;
}

export interface DataDrivenStatus {
  event: AgentStatus;
  macro: AgentStatus;
  korean: AgentStatus;
}

export interface AnalysisRun {
  ticker: string;
  persona: PersonaId;
  isStrategist: boolean;
  running: boolean;
  strategistFlow: StrategistFlow;
  strategistStatus: StrategistStatus;
  dataDriven: DataDriven;
  dataDrivenStatus: DataDrivenStatus;
  elapsed: number | null;
  likelyCached: boolean;
  error: string | null;
  upgradeUrl: string | null;
}

const EMPTY_STRATEGIST_FLOW: StrategistFlow = {
  research: null,
  analyst: null,
  validator: null,
  strategist: null,
};

const PENDING_STRATEGIST_STATUS: StrategistStatus = {
  research: "pending",
  analyst: "pending",
  validator: "pending",
  strategist: "pending",
};

interface AnalysisStore {
  runs: Record<string, AnalysisRun>;
  /** 분석 시작(또는 페르소나 전환 재실행). 컴포넌트 언마운트와 무관하게 진행. */
  start: (ticker: string, persona: PersonaId, userProfile: unknown) => void;
  /** ValidateButton 단독 재검증 결과를 run에 반영. */
  setValidator: (ticker: string, validator: ValidatorResult) => void;
}

// AbortController는 직렬화·렌더와 무관하므로 store state 밖 모듈 레벨에 보관.
const controllers = new Map<string, AbortController>();

export const useAnalysisStore = create<AnalysisStore>((set, get) => ({
  runs: {},

  start: (ticker, persona, userProfile) => {
    const key = ticker.toUpperCase();
    // 같은 종목의 진행 중 스트림이 있으면 중단(페르소나 전환 등).
    controllers.get(key)?.abort();
    const ac = new AbortController();
    controllers.set(key, ac);

    const runStrategist = isStrategistPersona(persona);

    const initialRun: AnalysisRun = {
      ticker: key,
      persona,
      isStrategist: runStrategist,
      running: true,
      strategistFlow: { ...EMPTY_STRATEGIST_FLOW },
      strategistStatus: runStrategist
        ? { research: "running", analyst: "running", validator: "pending", strategist: "pending" }
        : { ...PENDING_STRATEGIST_STATUS },
      dataDriven: { event: null, macro: null, korean: null },
      dataDrivenStatus: {
        event: persona === "event" ? "running" : "pending",
        macro: persona === "macro" ? "running" : "pending",
        korean: persona === "korean" ? "running" : "pending",
      },
      elapsed: null,
      likelyCached: false,
      error: null,
      upgradeUrl: null,
    };
    set((s) => ({ runs: { ...s.runs, [key]: initialRun } }));

    // run을 부분 갱신 (이미 다른 종목으로 덮어써졌으면 무시).
    const patch = (fn: (r: AnalysisRun) => AnalysisRun) => {
      const cur = get().runs[key];
      if (!cur || controllers.get(key) !== ac) return; // 더 새로운 실행이 시작됨
      set((s) => ({ runs: { ...s.runs, [key]: fn(cur) } }));
    };

    apiStream(
      "/api/ai/analyze",
      { ticker, query: `${ticker} 분석`, persona, stream: true, user_profile: userProfile },
      (event, data) => {
        const payload = data as {
          result?: unknown;
          total_elapsed?: number;
          likely_cached?: boolean;
          message?: string;
        };

        switch (event) {
          case "start":
            break;

          // Strategist 흐름
          case "research_complete":
            patch((r) => ({
              ...r,
              strategistFlow: { ...r.strategistFlow, research: payload.result as ResearchResult },
              strategistStatus: { ...r.strategistStatus, research: "done", validator: "running" },
            }));
            break;
          case "analyst_complete":
            patch((r) => ({
              ...r,
              strategistFlow: { ...r.strategistFlow, analyst: payload.result as AnalystResult },
              strategistStatus: { ...r.strategistStatus, analyst: "done", validator: "running" },
            }));
            break;
          case "validator_complete":
            patch((r) => ({
              ...r,
              strategistFlow: { ...r.strategistFlow, validator: payload.result as ValidatorResult },
              strategistStatus: { ...r.strategistStatus, validator: "done", strategist: "running" },
            }));
            break;
          case "strategist_complete":
            patch((r) => ({
              ...r,
              strategistFlow: { ...r.strategistFlow, strategist: payload.result as StrategistResult },
              strategistStatus: { ...r.strategistStatus, strategist: "done" },
            }));
            break;

          // 데이터 페르소나
          case "event_complete":
            patch((r) => ({
              ...r,
              dataDriven: { ...r.dataDriven, event: payload.result as EventAnalystResult },
              dataDrivenStatus: { ...r.dataDrivenStatus, event: "done" },
            }));
            break;
          case "macro_complete":
            patch((r) => ({
              ...r,
              dataDriven: { ...r.dataDriven, macro: payload.result as MacroPmResult },
              dataDrivenStatus: { ...r.dataDrivenStatus, macro: "done" },
            }));
            break;
          case "korean_complete":
            patch((r) => ({
              ...r,
              dataDriven: { ...r.dataDriven, korean: payload.result as KoreanSpecialistResult },
              dataDrivenStatus: { ...r.dataDrivenStatus, korean: "done" },
            }));
            break;

          case "complete":
            patch((r) => ({
              ...r,
              running: false,
              elapsed: typeof payload.total_elapsed === "number" ? payload.total_elapsed : r.elapsed,
              likelyCached:
                typeof payload.likely_cached === "boolean" ? payload.likely_cached : r.likelyCached,
            }));
            break;
          case "error":
            patch((r) => ({ ...r, error: payload.message ?? "분석 중 오류", running: false }));
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
      patch((r) => ({
        ...r,
        running: false,
        error: msg,
        upgradeUrl: err instanceof APIError ? (err.upgradeUrl ?? null) : null,
        strategistStatus: r.isStrategist
          ? { research: "error", analyst: "error", validator: "error", strategist: "error" }
          : r.strategistStatus,
        dataDrivenStatus: r.isStrategist
          ? r.dataDrivenStatus
          : {
              event: r.persona === "event" ? "error" : "pending",
              macro: r.persona === "macro" ? "error" : "pending",
              korean: r.persona === "korean" ? "error" : "pending",
            },
      }));
      toast.error(msg);
    });
  },

  setValidator: (ticker, validator) => {
    const key = ticker.toUpperCase();
    const cur = get().runs[key];
    if (!cur) return;
    set((s) => ({
      runs: {
        ...s.runs,
        [key]: { ...cur, strategistFlow: { ...cur.strategistFlow, validator } },
      },
    }));
  },
}));
