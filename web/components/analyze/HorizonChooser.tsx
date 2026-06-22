"use client";

/**
 * 투자 시계(Horizon) 선택 — 종목 진입 후 "어느 기간 관점으로 볼지"를 의도적으로 고른 뒤 1회 실행.
 *
 * 신규 1차 축. 6 페르소나(전략 흐름 vs 데이터 특화 2단 구조)를 대체해, 단일 단계로
 * 4개 시계(단기/단중기/중기/장기) 중 하나를 고른다. 어떤 시계든 백엔드는 통합
 * strategist 파이프라인(research→analyst→validator→strategist)을 항상 실행한다.
 *
 * 자동 실행을 없애 불필요한 과금(분석 1회 ≈ ₩175~)을 방지한다. 기본 선택은 "중기"(mid).
 *
 * 잠금: Free 플랜에서 Pro 전용 시계는 🔒 Pro 배지 + /pricing 안내.
 */
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { usePersonas } from "@/hooks/usePersonas";
import {
  ALL_HORIZONS,
  DEFAULT_HORIZON,
  HORIZON_BY_ID,
  HORIZON_META,
  type HorizonId,
} from "@/types/persona";

export function HorizonChooser({
  defaultHorizon,
  onStart,
}: {
  defaultHorizon: HorizonId;
  onStart: (horizon: HorizonId) => void;
}) {
  const [selected, setSelected] = useState<HorizonId>(defaultHorizon);

  // Pro 잠금 — 사용자 플랜 + 시계별 free 허용 여부(/api/ai/personas의 horizons).
  const { data: personasData } = usePersonas();
  const isFree = (personasData?.user_plan ?? "free") === "free";
  const freeMap = new Map(
    (personasData?.horizons ?? []).map((h) => [h.id, h.available_to_free]),
  );
  const isProLocked = (id: HorizonId): boolean => {
    if (!isFree) return false;
    const free = freeMap.get(id) ?? id === DEFAULT_HORIZON;
    return !free;
  };

  const selectedProLocked = isProLocked(selected);

  return (
    <div className="space-y-3">
      {/* 헤더 */}
      <div className="flex items-baseline gap-2">
        <span className="text-xs font-bold text-primary bg-primary/10 px-2 py-0.5 rounded">
          관점
        </span>
        <h2 className="text-base font-semibold">투자 시계 선택</h2>
        <span className="text-[11px] text-muted-foreground">
          (보는 기간에 따라 분석 초점이 달라집니다)
        </span>
      </div>

      {/* 4개 시계 타일 */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2">
        {HORIZON_META.map((h) => {
          const active = selected === h.id;
          const proLocked = isProLocked(h.id);
          return (
            <button
              key={h.id}
              type="button"
              onClick={() => setSelected(h.id)}
              aria-pressed={active}
              className={`text-left rounded-md border p-3 transition bg-background ${
                active
                  ? "border-primary ring-1 ring-primary/40 bg-primary/5"
                  : "hover:bg-muted/50 hover:border-foreground/20"
              }`}
            >
              <div className="font-medium text-sm flex items-center justify-between gap-2">
                <span className="truncate">
                  <span className="mr-1">{h.icon}</span>
                  {h.name}
                </span>
                {proLocked ? (
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-700 shrink-0">
                    🔒 Pro
                  </span>
                ) : active ? (
                  <span className="text-[10px] font-bold text-primary bg-primary/10 px-1.5 py-0.5 rounded shrink-0">
                    ✓
                  </span>
                ) : null}
              </div>
              <div className="text-xs text-muted-foreground mt-1 leading-relaxed">
                {h.tagline}
              </div>
            </button>
          );
        })}
      </div>

      {/* 시작 버튼 — Pro잠금 / 정상 */}
      <div className="pt-1">
        {selectedProLocked ? (
          <div className="space-y-2">
            <Link
              href="/pricing"
              className="inline-flex items-center w-full sm:w-auto px-6 py-2.5 rounded-md bg-amber-500/90 text-white font-medium text-sm hover:bg-amber-500 transition"
            >
              🔒 {HORIZON_BY_ID[selected].name} 시계는 Pro 전용 — 업그레이드 안내
            </Link>
            <p className="text-xs text-muted-foreground">
              Free 플랜에서 사용할 수 있는 시계는 제한됩니다. 모든 시계는 Pro에서 열립니다.
            </p>
          </div>
        ) : (
          <>
            <button
              type="button"
              onClick={() => onStart(selected)}
              className="w-full sm:w-auto px-6 py-2.5 rounded-md bg-primary text-primary-foreground font-medium text-sm hover:bg-primary/90 transition"
            >
              🔍 {HORIZON_BY_ID[selected].name} 시계로 분석 시작
            </button>
            <p className="text-xs text-muted-foreground mt-2">
              분석은 선택한 시계로 1회 실행됩니다. 결과 후 다른 시계로 다시 분석할 수 있습니다.
            </p>
          </>
        )}
      </div>
    </div>
  );
}

/**
 * 결과 단계에서 다른 시계로 재실행하는 탭 — PersonaSwitch의 시계 버전.
 * 모바일은 가로 스크롤. Pro 잠금 시 토스트 안내.
 */
export function HorizonSwitch({
  current,
  onSelect,
}: {
  current: HorizonId;
  onSelect: (id: HorizonId) => void;
}) {
  const { data: personasData } = usePersonas();
  const isFree = (personasData?.user_plan ?? "free") === "free";
  const availability = new Map(
    (personasData?.horizons ?? []).map((h) => [h.id, h.available_to_free]),
  );

  const handleClick = (id: HorizonId, locked: boolean, name: string) => {
    if (locked) {
      toast.info(`${name} 시계는 Pro 전용입니다.`, {
        description: "/pricing 에서 업그레이드 안내를 확인하세요.",
      });
      return;
    }
    onSelect(id);
  };

  return (
    <div
      className="flex gap-1 border rounded-md p-1 bg-muted/30 overflow-x-auto scrollbar-thin snap-x snap-mandatory"
      role="tablist"
      aria-label="투자 시계 선택"
    >
      {ALL_HORIZONS.map((id) => {
        const meta = HORIZON_BY_ID[id];
        const availableForFree = availability.get(id) ?? id === DEFAULT_HORIZON;
        const locked = isFree && !availableForFree;
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
