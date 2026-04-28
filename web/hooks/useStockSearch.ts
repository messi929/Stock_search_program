"use client";

/**
 * 종목명·티커 LIKE 검색 — v7.5 /api/all-stocks 호출.
 *
 * 인증 불필요. 캐시 30초, 빈 쿼리는 비활성.
 */
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { apiCall } from "@/lib/api";
import type { StockSearchResponse } from "@/types/api";

const DEFAULT_LIMIT = 10;

export function useDebounced<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(id);
  }, [value, delayMs]);
  return debounced;
}

export function useStockSearch(query: string, limit = DEFAULT_LIMIT) {
  const q = query.trim();
  return useQuery({
    queryKey: ["stock-search", q, limit],
    queryFn: () =>
      apiCall<StockSearchResponse>(
        `/api/all-stocks?q=${encodeURIComponent(q)}&limit=${limit}`,
      ),
    enabled: q.length > 0,
    staleTime: 30_000,
  });
}
