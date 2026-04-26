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

/**
 * 단일 ticker 추가 — closure stale 방지를 위해 mutation 시점에 캐시에서 최신
 * 목록을 읽어 dedupe 후 전송. 동일 ticker 또는 빠른 멀티 클릭의 race 차단.
 */
export function useAddToWatchlist() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (ticker: string) => {
      // 캐시 신선화 (다른 탭/뷰의 변경 반영)
      const fresh = await qc.fetchQuery<WatchlistResponse>({
        queryKey: KEY,
        queryFn: () => apiCall<WatchlistResponse>("/api/user/watchlist"),
        staleTime: 5_000,
      });
      const current = fresh?.watchlist ?? [];
      if (current.includes(ticker)) {
        return { ok: true, count: current.length, alreadyPresent: true as const };
      }
      const next = Array.from(new Set([...current, ticker]));
      const res = await apiCall<{ ok: boolean; count: number }>(
        "/api/user/watchlist",
        { method: "POST", body: JSON.stringify({ watchlist: next }) },
      );
      return { ...res, alreadyPresent: false as const };
    },
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
