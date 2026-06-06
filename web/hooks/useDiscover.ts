"use client";

/**
 * 자연어 종목 발견 — POST /api/ai/discover (Sonnet, ~70원/호출, 동일 query는 캐시 0원).
 */
import { useMutation } from "@tanstack/react-query";

import { apiCall } from "@/lib/api";
import type { DiscoverResponse } from "@/types/api";

interface DiscoverPayload {
  query: string;
  max_results?: number;
  exclude_tickers?: string[];
  market?: "KR" | "US" | "ALL";
  filters?: {
    market?: string[];
    min_market_cap?: number;
    max_market_cap?: number;
    sectors?: string[];
  };
}

export function useDiscover() {
  return useMutation({
    mutationFn: (payload: DiscoverPayload) =>
      apiCall<DiscoverResponse>("/api/ai/discover", {
        method: "POST",
        body: JSON.stringify({
          query: payload.query,
          max_results: payload.max_results ?? 5,
          exclude_tickers: payload.exclude_tickers ?? [],
          market: payload.market ?? "KR",
          filters: payload.filters ?? null,
        }),
      }),
  });
}
