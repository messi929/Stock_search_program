"use client";

/**
 * 6 페르소나 탭 — Strategist (3) + Data-driven (3) 두 그룹.
 *
 * 모바일 대응: 가로 스크롤(`overflow-x-auto`) + scroll snap.
 * 데스크탑은 6 탭 한 줄.
 *
 * 사용처: AnalyzeView 헤더 등.
 */

import { toast } from "sonner";

import { usePersonas } from "@/hooks/usePersonas";
import { usePersonaStore } from "@/store/personaStore";
import {
  ALL_PERSONAS,
  PERSONA_BY_ID,
  type PersonaId,
} from "@/types/persona";

type PersonaSwitchProps = {
  /** 현재 활성 ID (제어 컴포넌트로 사용 시). 미지정 시 store에서 읽음. */
  current?: PersonaId;
  /** 클릭 시 콜백 — 미지정 시 zustand setPersona 사용. */
  onSelect?: (id: PersonaId) => void;
  /** "Pro 전용" lock 동작 무시 (관리자 등). 기본 false. */
  skipLockCheck?: boolean;
};

export function PersonaSwitch({
  current: controlledCurrent,
  onSelect,
  skipLockCheck = false,
}: PersonaSwitchProps) {
  const storeCurrent = usePersonaStore((s) => s.current);
  const setPersona = usePersonaStore((s) => s.setPersona);
  const current = controlledCurrent ?? storeCurrent;

  const { data: personasData } = usePersonas();
  const isFree = (personasData?.user_plan ?? "free") === "free";
  const availability = new Map(
    (personasData?.personas ?? []).map((p) => [p.id, p.available_to_free]),
  );

  const handleClick = (id: PersonaId, locked: boolean, name: string) => {
    if (locked) {
      toast.info(`${name} 페르소나는 Pro 전용입니다.`, {
        description: "/pricing 에서 업그레이드 안내를 확인하세요.",
      });
      return;
    }
    if (onSelect) onSelect(id);
    else setPersona(id);
  };

  return (
    <div
      className="flex gap-1 border rounded-md p-1 bg-muted/30 overflow-x-auto scrollbar-thin snap-x snap-mandatory"
      role="tablist"
      aria-label="분석 페르소나 선택"
    >
      {ALL_PERSONAS.map((id) => {
        const meta = PERSONA_BY_ID[id];
        const availableForFree =
          availability.get(id) ?? id === "blackrock";
        const locked = !skipLockCheck && isFree && !availableForFree;
        const isActive = current === id;

        return (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={isActive}
            aria-disabled={locked}
            title={
              locked
                ? `${meta.name}: Pro 전용 — ${meta.tagline}`
                : `${meta.name}: ${meta.tagline}`
            }
            onClick={() => handleClick(id, locked, meta.name)}
            className={`
              shrink-0 snap-start whitespace-nowrap
              px-3 py-1.5 text-sm rounded transition
              ${
                isActive
                  ? "bg-background shadow-sm font-medium"
                  : "text-muted-foreground hover:text-foreground"
              }
              ${locked ? "opacity-50 cursor-not-allowed" : ""}
            `}
          >
            <span className="mr-1">{meta.icon}</span>
            {meta.name}
            {locked && <span className="ml-1 text-[10px]">🔒</span>}
          </button>
        );
      })}
    </div>
  );
}
