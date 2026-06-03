"use client";

/**
 * Axis Smart Lists 조회 — v7.5 CATEGORIES 17개를 Axis API로 노출.
 * 실제 종목 조회는 클라이언트가 v7.5 /api/scan?category={id} 호출.
 */
import { useQuery } from "@tanstack/react-query";

import { apiCall } from "@/lib/api";
import type { SmartListsResponse } from "@/types/api";

export function useSmartLists() {
  return useQuery({
    queryKey: ["smart-lists"],
    queryFn: () => apiCall<SmartListsResponse>("/api/screener/smart-lists"),
    staleTime: 10 * 60_000, // 카테고리는 거의 변하지 않음
  });
}

interface ScanResponse {
  category: string;
  stocks: Array<Record<string, unknown>>;
  total: number;
  message?: string;
  last_update?: string;
}

/** market: "" = 전체, "KR" = 국내(KOSPI/KOSDAQ), "US" = 미국(NASDAQ/S&P500). */
export function useScan(category: string | undefined, limit = 50, market = "") {
  return useQuery({
    queryKey: ["scan", category, limit, market],
    queryFn: () =>
      apiCall<ScanResponse>(
        `/api/scan?category=${category}&limit=${limit}${market ? `&market=${market}` : ""}`,
      ),
    enabled: !!category,
    staleTime: 60_000,
  });
}
