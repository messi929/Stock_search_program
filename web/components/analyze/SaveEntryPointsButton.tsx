"use client";

import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { useSaveEntryPoints } from "@/hooks/useSaveEntryPoints";
import type { StrategistResult } from "@/types/api";

interface Props {
  ticker: string;
  strategist: StrategistResult | null;
  size?: "default" | "sm" | "lg";
}

export function SaveEntryPointsButton({ ticker, strategist, size = "sm" }: Props) {
  const save = useSaveEntryPoints();
  const ep = strategist?.entry_points;
  // canonical persona = backend가 실제 사용한 값 (캐시 히트 시 요청과 다를 수 있음)
  const personaUsed = strategist?.persona_used ?? "manual";
  const disabled = !ep || save.isPending;

  const handle = async () => {
    if (!ep) {
      toast.error("진입선이 없는 분석입니다.");
      return;
    }
    try {
      await save.mutateAsync({
        ticker,
        tier_1: ep.tier_1,
        tier_2: ep.tier_2,
        tier_3: ep.tier_3,
        technical_basis: ep.technical_basis,
        persona_used: personaUsed,
        source: "strategist",
      });
      toast.success(`관찰 구간 저장됨 (${personaUsed})`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "저장 실패";
      toast.error(msg);
    }
  };

  return (
    <div className="inline-flex flex-col items-start gap-1">
      <Button
        type="button"
        onClick={handle}
        disabled={disabled}
        size={size}
        variant="outline"
      >
        {save.isPending ? "💾 저장 중..." : "💾 관찰 구간 저장"}
      </Button>
      <p className="text-[10px] text-muted-foreground leading-tight">
        참고 수치이며 투자 판단은 사용자 본인의 책임입니다.
      </p>
    </div>
  );
}
