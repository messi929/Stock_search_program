"use client";

/**
 * GET /api/ai/personas — 페르소나 목록 + 현재 사용자 플랜.
 * AnalyzeView의 PersonaTabs가 Pro 전용을 비활성화할 때 사용.
 */
import { useQuery } from "@tanstack/react-query";

import { apiCall } from "@/lib/api";
import type { PersonasResponse } from "@/types/api";

export function usePersonas() {
  return useQuery({
    queryKey: ["personas"],
    queryFn: () => apiCall<PersonasResponse>("/api/ai/personas"),
    staleTime: 5 * 60_000,
  });
}
