/**
 * 현재 활성 페르소나 상태 (Zustand) — 분석 페이지 전반에서 공유.
 */
import { create } from "zustand";
import { persist } from "zustand/middleware";

export type PersonaId = "blackrock" | "ark" | "graham";

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
    { name: "axis:persona" },
  ),
);
