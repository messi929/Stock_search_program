"use client";

/**
 * Validator 단독 재실행 — Axis 핵심 차별점.
 * 가격은 결정론적 코드(0원), Contrarian만 Sonnet (~40원, 동일 입력은 캐시 0원).
 */
import { useMutation } from "@tanstack/react-query";

import { apiCall } from "@/lib/api";
import type { AnalystResult, ResearchResult, ValidatorResult } from "@/types/api";

interface ValidatePayload {
  ticker: string;
  research_output: ResearchResult | null;
  analyst_output: AnalystResult;
}

interface ValidateResponse extends ValidatorResult {
  ticker: string;
  validated_at: string;
  elapsed_seconds: number;
}

export function useValidate() {
  return useMutation({
    mutationFn: (input: ValidatePayload) =>
      apiCall<ValidateResponse>(`/api/ai/validate/${input.ticker}`, {
        method: "POST",
        body: JSON.stringify({
          ticker: input.ticker,
          research_output: input.research_output,
          analyst_output: input.analyst_output,
        }),
      }),
  });
}
