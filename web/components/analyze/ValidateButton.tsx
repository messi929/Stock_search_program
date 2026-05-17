"use client";

/**
 * 검증 버튼 — Validator 단독 재실행. Axis의 핵심 차별점 ⭐.
 * 같은 분석에 대해 가격/PER/PBR/ROE를 실시간 재조회 (가격 부분 0원).
 */
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { useValidate } from "@/hooks/useValidate";
import type { AnalystResult, ResearchResult, ValidatorResult } from "@/types/api";

interface Props {
  ticker: string;
  research: ResearchResult | null;
  analyst: AnalystResult | null;
  onResult: (result: ValidatorResult) => void;
  size?: "default" | "sm" | "lg";
}

export function ValidateButton({ ticker, research, analyst, onResult, size = "sm" }: Props) {
  const validate = useValidate();
  const [lastValidatedAt, setLastValidatedAt] = useState<string | null>(null);

  const handle = async () => {
    if (!analyst) {
      toast.error("분석이 완료된 후에 검증할 수 있습니다.");
      return;
    }
    try {
      const res = await validate.mutateAsync({
        ticker,
        research_output: research,
        analyst_output: analyst,
      });
      onResult(res);
      setLastValidatedAt(new Date().toLocaleTimeString("ko-KR"));
      const status =
        res.overall_status === "PASS"
          ? "✅ 통과"
          : res.overall_status === "WARN"
            ? "⚠️ 일부 차이"
            : "❌ 재분석 권장";
      toast.success(`재검증 완료: ${status}`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "검증 실패";
      toast.error(msg);
    }
  };

  const disabled = !analyst || validate.isPending;
  // 라벨 — 분석 진행 중에는 비활성 + 안내, 완료 후엔 "실시간 검증"으로 통일
  // (자동 1회 실행되었더라도 사용자에겐 매번 새 검증으로 표시 — "다시"가 주는 혼란 제거)
  const label = validate.isPending
    ? "🔄 검증 중..."
    : !analyst
      ? "🔍 분석 후 검증"
      : "🔍 실시간 검증";
  return (
    <div className="inline-flex items-center gap-2">
      <Button
        type="button"
        onClick={handle}
        disabled={disabled}
        size={size}
        variant="outline"
        title={!analyst ? "분석이 완료되면 활성화됩니다" : undefined}
      >
        {label}
      </Button>
      {lastValidatedAt && !validate.isPending && (
        <span className="text-xs text-muted-foreground">
          최근 검증 {lastValidatedAt}
        </span>
      )}
    </div>
  );
}
