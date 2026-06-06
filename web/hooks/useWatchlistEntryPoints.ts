"use client";

/**
 * 관심종목 전체의 저장된 진입선 맵 — 대시보드 모니터링(진입선 근접/도달)용.
 * GET /api/ai/watchlist/entry-points → { items: { [ticker]: {entry_points, ...} } }
 */
import { useQuery } from "@tanstack/react-query";

import { apiCall } from "@/lib/api";

export type WatchlistEntryMeta = {
  entry_points: {
    tier_1: number;
    tier_2: number;
    tier_3: number;
    technical_basis?: string[];
  };
  persona_used: string;
  source: string;
};

export function useWatchlistEntryPoints(enabled = true) {
  return useQuery<{ items: Record<string, WatchlistEntryMeta> }>({
    queryKey: ["watchlist-entry-points"],
    queryFn: () => apiCall("/api/ai/watchlist/entry-points"),
    enabled,
    staleTime: 60_000,
  });
}

/** 진입선 대비 현재가 상태 — 도달 차수(0=미도달) + 1차까지 거리%(음수=하락 필요). */
export function entryProximity(
  ep: WatchlistEntryMeta["entry_points"] | undefined,
  price: number | null | undefined,
): { reached: number; tier1: number; distPct: number | null } | null {
  if (!ep) return null;
  const tiers = [ep.tier_1, ep.tier_2, ep.tier_3].filter((v) => v > 0);
  if (tiers.length === 0) return null;
  const tier1 = Math.max(...tiers);
  if (price == null || price <= 0) {
    return { reached: 0, tier1, distPct: null };
  }
  const reached = tiers.filter((t) => price <= t).length; // 가격이 진입선 이하로 떨어진 차수
  const distPct = ((tier1 - price) / price) * 100; // 1차 진입선까지 (음수 = 더 떨어져야)
  return { reached, tier1, distPct };
}
