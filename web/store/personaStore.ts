/**
 * 현재 활성 페르소나 상태 (Zustand) — 분석 페이지 전반에서 공유.
 *
 * 6 페르소나 (blackrock/ark/graham/event/macro/korean) 모두 지원.
 * 단일 source of truth는 types/persona.ts.
 */
import { create } from "zustand";
import { persist } from "zustand/middleware";
import {
  type PersonaId,
  isValidPersonaId,
} from "@/types/persona";

export type { PersonaId } from "@/types/persona";

interface PersonaState {
  current: PersonaId;
  setPersona: (id: PersonaId) => void;
}

export const usePersonaStore = create<PersonaState>()(
  persist(
    (set) => ({
      current: "blackrock",
      setPersona: (id) => set({ current: id }),
    }),
    {
      name: "axis:persona",
      // v1 (3 페르소나) → v2 (6 페르소나) 마이그레이션:
      // 저장된 값이 새 enum에 없으면 'blackrock'으로 복귀.
      version: 2,
      migrate: (persistedState: unknown, _version) => {
        const s = persistedState as { current?: string } | undefined;
        if (s && typeof s.current === "string" && !isValidPersonaId(s.current)) {
          return { current: "blackrock" } as Partial<PersonaState>;
        }
        return s as Partial<PersonaState>;
      },
    },
  ),
);
