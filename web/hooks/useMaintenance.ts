"use client";

/**
 * 점검 공지 설정 — 공개 GET /api/maintenance (인증 불필요).
 * 관리자가 /admin/maintenance에서 설정, 전 사용자 배너로 노출.
 */
import { useQuery } from "@tanstack/react-query";

import { apiCall } from "@/lib/api";

export interface MaintenanceConfig {
  enabled: boolean;
  starts_at: string; // "YYYY-MM-DDTHH:MM" (로컬) 또는 빈값
  ends_at: string;
  message: string;
}

export function useMaintenance() {
  return useQuery({
    queryKey: ["maintenance"],
    queryFn: () => apiCall<MaintenanceConfig>("/api/maintenance"),
    staleTime: 60_000,
    refetchInterval: 120_000, // 2분마다 갱신(공지 켜고/끄면 곧 반영)
    refetchOnWindowFocus: true,
  });
}
