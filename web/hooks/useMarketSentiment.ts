"use client";

import { useQuery } from "@tanstack/react-query";

import { apiCall } from "@/lib/api";

export interface MarketBreadth {
  advance_decline: number;
  above_ma20_ratio: number;
  total_stocks: number;
}

export interface MarketSentimentResponse {
  kr: MarketBreadth;
  us: MarketBreadth;
}

export function useMarketSentiment() {
  return useQuery({
    queryKey: ["market-sentiment"],
    queryFn: () => apiCall<MarketSentimentResponse>("/api/market-sentiment"),
    staleTime: 5 * 60_000,
  });
}
