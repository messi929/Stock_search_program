"use client";

/**
 * v7.5 백엔드 상태 조회 — Axis는 분석 시 v7.5의 Firestore 데이터에 의존하므로
 * 사용자에게 데이터 신선도(last_update)를 보여주는 게 중요합니다.
 */
import { useQuery } from "@tanstack/react-query";

import { apiCall } from "@/lib/api";

export interface StatusResponse {
  status: "ready" | "loading" | string;
  total_stocks: number;
  total_etf: number;
  total_themes: number;
  last_update: string;
  loading_phase: number;
}

export function useStatus() {
  return useQuery({
    queryKey: ["status"],
    queryFn: () => apiCall<StatusResponse>("/api/status"),
    staleTime: 60_000,
    refetchInterval: 5 * 60_000, // 5분마다 갱신
  });
}
