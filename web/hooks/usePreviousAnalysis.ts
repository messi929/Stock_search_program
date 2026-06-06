"use client";

/**
 * 특정 종목의 직전 분석(진입/청산 참고치 포함) 조회 — 차트 하단 '이전 분석' 카드용.
 *
 * 백엔드 GET /api/ai/history/latest?ticker= 는 strategist 흐름(진입선 보유)의 가장
 * 최근 1건만 반환. 없으면 item=null.
 */
import { useQuery } from "@tanstack/react-query";

import { apiCall } from "@/lib/api";
import type { EntryPoints, ExitPoints } from "@/types/api";

export type PreviousAnalysis = {
  ticker: string;
  persona: string;
  at: string;
  price: number | null;
  summary: string;
  entry_points: EntryPoints | null;
  exit_points: ExitPoints | null;
};

export function usePreviousAnalysis(ticker: string, enabled = true) {
  const tk = ticker.trim().toUpperCase();
  return useQuery<{ item: PreviousAnalysis | null }>({
    queryKey: ["prev-analysis", tk],
    queryFn: () =>
      apiCall(`/api/ai/history/latest?ticker=${encodeURIComponent(tk)}`),
    enabled: enabled && tk.length > 0,
    staleTime: 60_000,
  });
}
