"use client";

/**
 * 진입선 저장 — PUT /api/ai/watchlist/{ticker}/entry-points.
 * Strategist가 산출한 entry_points 또는 사용자 수동값을 영속화.
 * 백엔드: users/{uid}/watchlist_meta/{ticker} (Axis 신규 서브컬렉션).
 */
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { apiCall } from "@/lib/api";

interface SavePayload {
  ticker: string;
  tier_1: number;
  tier_2: number;
  tier_3: number;
  technical_basis?: string[];
  persona_used?: string;
  source?: "manual" | "strategist";
}

export function useSaveEntryPoints() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ ticker, ...body }: SavePayload) =>
      apiCall<{ ok: boolean; ticker: string }>(
        `/api/ai/watchlist/${ticker}/entry-points`,
        {
          method: "PUT",
          body: JSON.stringify({
            tier_1: body.tier_1,
            tier_2: body.tier_2,
            tier_3: body.tier_3,
            technical_basis: body.technical_basis ?? [],
            persona_used: body.persona_used ?? "manual",
            source: body.source ?? "strategist",
          }),
        },
      ),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ["entry-points", vars.ticker] });
    },
  });
}
