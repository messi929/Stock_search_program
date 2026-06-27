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
import { persist } from "zustand/middleware";
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
import {
  isStrategistPersona,
  type HorizonId,
  type PersonaId,
} from "@/types/persona";

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

/** 빠른 요약 스냅샷 — 본 분석 전 즉시 표시(스크리너 캐시, 비용 0). */
export interface InstantSnapshot {
  ticker: string;
  name: string;
  market: string;
  is_kr: boolean;
  price: number | null;
  change_pct: number | null;
  rsi: number | null;
  buy_score: number | null;
  buy_grade: string;
  per: number | null;
  pbr: number | null;
  roe: number | null;
  sector: string;
  vs_high_52w: number | null;
  foreign_consecutive: number;
  volume_ratio: number | null;
}

export interface AnalysisRun {
  ticker: string;
  persona: PersonaId;
  /** 선택된 투자 시계. 지정 시 페르소나와 무관하게 strategist 흐름으로 실행. */
  horizon?: HorizonId;
  isStrategist: boolean;
  running: boolean;
  strategistFlow: StrategistFlow;
  strategistStatus: StrategistStatus;
  dataDriven: DataDriven;
  dataDrivenStatus: DataDrivenStatus;
  /** 빠른 요약 — 즉시 스냅샷(비용 0) + Haiku 1줄 요약(~2s). 본 분석 도착 전 노출. */
  instantSnapshot: InstantSnapshot | null;
  instantSummary: string | null;
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

/**
 * GET /api/ai/result 페이로드 — 서버에 저장된 **전체** 분석 결과(복원용).
 * 모바일 백그라운드/새로고침/앱전환 후 메모리 run이 사라졌을 때 카드를 되살린다.
 * 필드는 _build_full_response(백엔드)와 동일 직렬화 → SSE result와 구조 동일.
 */
export interface SavedAnalysisResult {
  ticker: string;
  persona?: PersonaId;
  horizon?: HorizonId;
  research?: ResearchResult | null;
  analyst?: AnalystResult | null;
  validator?: ValidatorResult | null;
  strategist?: StrategistResult | null;
  event?: EventAnalystResult | null;
  macro?: MacroPmResult | null;
  korean?: KoreanSpecialistResult | null;
  metadata?: { total_elapsed?: number } | null;
  saved_at?: string | null;
}

/** 최근 분석 이력 항목 — localStorage 영속(가벼운 메타만). */
export interface RecentAnalysis {
  ticker: string;
  name?: string; // 종목명 (분석 시작 시점에 알면 저장)
  persona: PersonaId;
  /** 시계 기반 분석이면 저장(있으면 카드 라벨을 시계명으로 표시). */
  horizon?: HorizonId;
  at: number; // epoch ms
}

interface AnalysisStore {
  runs: Record<string, AnalysisRun>;
  /** 최근 분석한 종목(최신순, 최대 8). 새로고침 후에도 유지(persist). */
  recents: RecentAnalysis[];
  /**
   * 분석 시작(또는 관점/시계 전환 재실행). 컴포넌트 언마운트와 무관하게 진행.
   * horizon 지정 시: 페르소나와 무관하게 strategist 흐름으로 실행하고, 요청 본문에
   * horizon을 포함한다. horizon이 없으면 기존 페르소나 경로 그대로 동작.
   */
  start: (
    ticker: string,
    persona: PersonaId,
    userProfile: unknown,
    name?: string,
    horizon?: HorizonId,
  ) => void;
  /** ValidateButton 단독 재검증 결과를 run에 반영. */
  setValidator: (ticker: string, validator: ValidatorResult) => void;
  /**
   * 서버에 저장된 전체 결과로 run을 복원(완료 상태). 모바일 백그라운드/새로고침/앱전환
   * 후 메모리 run이 사라진 경우 카드 전체를 되살린다. 라이브 스트림과 충돌하지 않는다
   * (live patch는 자신의 controller만 갱신, restore는 controller를 만들지 않음).
   */
  restore: (ticker: string, result: SavedAnalysisResult) => void;
}

// AbortController는 직렬화·렌더와 무관하므로 store state 밖 모듈 레벨에 보관.
const controllers = new Map<string, AbortController>();

export const useAnalysisStore = create<AnalysisStore>()(
  persist(
    (set, get) => ({
  runs: {},
  recents: [],

  start: (ticker, persona, userProfile, name = "", horizon) => {
    const key = ticker.toUpperCase();
    // 같은 종목의 진행 중 스트림이 있으면 중단(페르소나/시계 전환 등).
    controllers.get(key)?.abort();
    const ac = new AbortController();
    controllers.set(key, ac);

    // 시계가 지정되면 항상 strategist 흐름(4노드). 없으면 페르소나로 판별.
    const runStrategist = horizon ? true : isStrategistPersona(persona);

    const initialRun: AnalysisRun = {
      ticker: key,
      persona,
      horizon,
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
      instantSnapshot: null,
      instantSummary: null,
      elapsed: null,
      likelyCached: false,
      error: null,
      upgradeUrl: null,
    };
    set((s) => ({
      runs: { ...s.runs, [key]: initialRun },
      // 최근 분석 이력 갱신(같은 종목은 최신으로 끌어올림, 최대 8).
      recents: [
        { ticker: key, name: name || undefined, persona, horizon, at: Date.now() },
        ...s.recents.filter((r) => r.ticker !== key),
      ].slice(0, 8),
    }));

    // run을 부분 갱신 (이미 다른 종목으로 덮어써졌으면 무시).
    const patch = (fn: (r: AnalysisRun) => AnalysisRun) => {
      const cur = get().runs[key];
      if (!cur || controllers.get(key) !== ac) return; // 더 새로운 실행이 시작됨
      set((s) => ({ runs: { ...s.runs, [key]: fn(cur) } }));
    };

    apiStream(
      "/api/ai/analyze",
      {
        ticker,
        query: `${ticker} 분석`,
        persona,
        // 시계 기반 분석이면 horizon을 포함(백엔드는 horizon 우선, persona 무시).
        ...(horizon ? { horizon } : {}),
        stream: true,
        user_profile: userProfile,
      },
      (event, data) => {
        const payload = data as {
          result?: unknown;
          total_elapsed?: number;
          likely_cached?: boolean;
          message?: string;
          snapshot?: InstantSnapshot;
          summary?: string;
        };

        switch (event) {
          case "start":
            break;

          // 빠른 요약 — 본 분석 전 즉시 노출
          case "instant_snapshot":
            patch((r) => ({ ...r, instantSnapshot: payload.snapshot ?? r.instantSnapshot }));
            break;
          case "instant_summary":
            patch((r) => ({ ...r, instantSummary: payload.summary ?? r.instantSummary }));
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

  restore: (ticker, result) => {
    const key = ticker.toUpperCase();
    const st = (v: unknown): AgentStatus => (v ? "done" : "pending");
    const hasStrategist = !!(
      result.horizon ||
      result.research ||
      result.analyst ||
      result.validator ||
      result.strategist
    );
    const restored: AnalysisRun = {
      ticker: key,
      persona: result.persona ?? "blackrock",
      horizon: result.horizon,
      isStrategist: hasStrategist,
      running: false,
      strategistFlow: {
        research: result.research ?? null,
        analyst: result.analyst ?? null,
        validator: result.validator ?? null,
        strategist: result.strategist ?? null,
      },
      strategistStatus: {
        research: st(result.research),
        analyst: st(result.analyst),
        validator: st(result.validator),
        strategist: st(result.strategist),
      },
      dataDriven: {
        event: result.event ?? null,
        macro: result.macro ?? null,
        korean: result.korean ?? null,
      },
      dataDrivenStatus: {
        event: st(result.event),
        macro: st(result.macro),
        korean: st(result.korean),
      },
      instantSnapshot: null,
      instantSummary: null,
      elapsed: result.metadata?.total_elapsed ?? null,
      likelyCached: false,
      error: null,
      upgradeUrl: null,
    };
    set((s) => ({ runs: { ...s.runs, [key]: restored } }));
  },
    }),
    {
      name: "axis:analysis",
      version: 1,
      // runs/AbortController는 직렬화 불가·새로고침 시 좀비 → recents만 영속.
      partialize: (s) => ({ recents: s.recents }),
    },
  ),
);
