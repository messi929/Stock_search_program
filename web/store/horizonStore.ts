/**
 * 현재 선택된 투자 시계(Horizon) 상태 (Zustand) — 분석 페이지 전반에서 공유.
 *
 * 신규 1차 축. personaStore와 동일한 패턴(persist + 마이그레이션 가드).
 * 단일 source of truth는 types/persona.ts.
 */
import { create } from "zustand";
import { persist } from "zustand/middleware";

import {
  DEFAULT_HORIZON,
  isValidHorizonId,
  type HorizonId,
} from "@/types/persona";

export type { HorizonId } from "@/types/persona";

interface HorizonState {
  current: HorizonId;
  setHorizon: (id: HorizonId) => void;
}

export const useHorizonStore = create<HorizonState>()(
  persist(
    (set) => ({
      current: DEFAULT_HORIZON,
      setHorizon: (id) => set({ current: id }),
    }),
    {
      name: "axis:horizon",
      version: 1,
      // 저장된 값이 enum에 없으면 기본 시계로 복귀.
      migrate: (persistedState: unknown) => {
        const s = persistedState as { current?: string } | undefined;
        if (s && typeof s.current === "string" && !isValidHorizonId(s.current)) {
          return { current: DEFAULT_HORIZON } as Partial<HorizonState>;
        }
        return s as Partial<HorizonState>;
      },
    },
  ),
);
