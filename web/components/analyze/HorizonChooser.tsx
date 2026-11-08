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
import { Check, Lock } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { HorizonIcon } from "@/components/analyze/HorizonIcon";
import { Button, buttonVariants } from "@/components/ui/button";
import { usePersonas } from "@/hooks/usePersonas";
import {
  ALL_HORIZONS,
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
  // 사용자가 직접 고른 관점 (null이면 아직 기본값 사용 중)
  const [picked, setSelected] = useState<HorizonId | null>(null);

  // Pro 잠금 — 사용자 플랜 + 시계별 free 허용 여부(/api/ai/personas의 horizons).
  const { data: personasData } = usePersonas();
  const isFree = (personasData?.user_plan ?? "free") === "free";
  const freeMap = new Map(
    (personasData?.horizons ?? []).map((h) => [h.id, h.available_to_free]),
  );
  const isProLocked = (id: HorizonId): boolean => {
    if (!isFree) return false;
    const free = freeMap.get(id) ?? id === "short";
    return !free;
  };

  // 기본 시계가 Pro 잠금이면 무료로 열린 첫 시계(단기)로 보정. 직접 고른 잠긴 시계는 그대로
  // 두어 업그레이드 안내를 보여준다.
  const selected: HorizonId =
    picked ??
    (isProLocked(defaultHorizon)
      ? (ALL_HORIZONS.find((id) => !isProLocked(id)) ?? defaultHorizon)
      : defaultHorizon);

  const selectedProLocked = isProLocked(selected);

  return (
    <div className="space-y-3">
      {/* 헤더 */}
      <div>
        <h2 className="text-lg font-semibold">어느 기간으로 볼까요?</h2>
        <p className="mt-0.5 text-muted-foreground">
          기간에 따라 AI가 중점적으로 살펴보는 데이터가 달라져요.
        </p>
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
              title={h.tagline}
              className={`flex flex-col text-left rounded-xl border p-3.5 transition bg-card ${
                active
                  ? "border-primary ring-1 ring-primary bg-accent"
                  : "hover:bg-muted/50 hover:border-foreground/20"
              }`}
            >
              <div className="w-full font-semibold flex items-center justify-between gap-2">
                <span className="flex items-center gap-1.5 truncate">
                  <HorizonIcon id={h.id} className="size-4 shrink-0 text-primary" />
                  {h.name}
                </span>
                {proLocked ? (
                  <span className="inline-flex items-center gap-0.5 text-[11px] px-1.5 py-0.5 rounded bg-caution/15 text-caution shrink-0">
                    <Lock aria-hidden="true" className="size-3" /> Pro
                  </span>
                ) : active ? (
                  <Check aria-label="선택됨" className="size-4 shrink-0 text-primary" />
                ) : null}
              </div>
              <div className="mt-1 text-xs leading-relaxed text-muted-foreground">{h.plain}</div>
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
              className={`${buttonVariants({ size: "lg" })} w-full sm:w-auto`}
            >
              <Lock aria-hidden="true" />
              {HORIZON_BY_ID[selected].name} 관점은 Pro에서 볼 수 있어요
            </Link>
            <p className="text-xs text-muted-foreground">
              Free 플랜에서는 일부 기간만 분석할 수 있어요.
            </p>
          </div>
        ) : (
          <>
            <Button type="button" size="lg" onClick={() => onStart(selected)} className="w-full sm:w-auto">
              {HORIZON_BY_ID[selected].name} 관점으로 분석 시작
            </Button>
            <p className="text-xs text-muted-foreground mt-2">
              보통 1분 안팎 걸려요. 결과를 본 뒤 다른 기간으로 다시 분석할 수 있습니다.
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
      toast.info(`${name} 관점은 Pro에서 볼 수 있어요.`, {
        description: "요금제 페이지에서 자세히 확인하세요.",
      });
      return;
    }
    onSelect(id);
  };

  // 무료 기본 가용 시계는 단기.
  const freeFallback = "short";

  return (
    <div
      className="flex gap-1 border rounded-md p-1 bg-muted/30 overflow-x-auto scrollbar-thin snap-x snap-mandatory"
      role="tablist"
      aria-label="분석 기간 선택"
    >
      {ALL_HORIZONS.map((id) => {
        const meta = HORIZON_BY_ID[id];
        const availableForFree = availability.get(id) ?? id === freeFallback;
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
                ? `${meta.name}: Pro 전용 — ${meta.plain}`
                : `${meta.name}: ${meta.plain}`
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
            <span className="inline-flex items-center gap-1">
              <HorizonIcon id={id} className="size-3.5" />
              {meta.name}
              {locked && <Lock aria-label="Pro 전용" className="size-3" />}
            </span>
          </button>
        );
      })}
    </div>
  );
}
