"use client";

/**
 * 관심 종목 — v7.5 /api/user/watchlist (단순 ticker 배열)와
 * Axis /api/ai/watchlist/{ticker}/entry-points (진입선 메타) 조합.
 */
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import { apiCall } from "@/lib/api";

interface WatchlistResponse {
  watchlist: string[];
}

interface EntryPointsResponse {
  ticker: string;
  entry_points: {
    tier_1: number;
    tier_2: number;
    tier_3: number;
    technical_basis: string[];
  } | null;
  persona_used?: string;
  source?: string;
  saved_at?: string | null;
}

const KEY = ["watchlist"] as const;

export function useWatchlist() {
  return useQuery({
    queryKey: KEY,
    queryFn: () => apiCall<WatchlistResponse>("/api/user/watchlist"),
    staleTime: 30_000,
  });
}

export function useUpdateWatchlist() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (next: string[]) =>
      apiCall<{ ok: boolean; count: number }>("/api/user/watchlist", {
        method: "POST",
        body: JSON.stringify({ watchlist: next }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEY });
    },
  });
}

export function useEntryPoints(ticker: string | undefined) {
  return useQuery({
    queryKey: ["entry-points", ticker],
    queryFn: () =>
      apiCall<EntryPointsResponse>(`/api/ai/watchlist/${ticker}/entry-points`),
    enabled: !!ticker,
    staleTime: 60_000,
  });
}
