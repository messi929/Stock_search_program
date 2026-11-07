"use client";

import { useQueries, useQuery } from "@tanstack/react-query";

import { apiCall } from "@/lib/api";
import type { PublicStock } from "@/lib/stocks";

const options = (ticker: string) => ({
  queryKey: ["public-stock", ticker.toUpperCase()],
  queryFn: () => apiCall<PublicStock>(`/api/stocks/${encodeURIComponent(ticker)}`),
  staleTime: 10 * 60_000,
  retry: false,
});

/** 공개 종목 데이터(지표·일봉) — AI 호출이 없어 비용이 들지 않는다. */
export function usePublicStock(ticker: string | undefined) {
  return useQuery({ ...options(ticker ?? ""), enabled: !!ticker });
}

export function usePublicStocks(tickers: string[]) {
  return useQueries({ queries: tickers.map(options) });
}
