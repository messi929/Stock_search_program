import { useQuery } from "@tanstack/react-query";

import { useAuth } from "@/hooks/useAuth";
import { apiCall } from "@/lib/api";
import type { UsageResponse } from "@/types/api";

/**
 * 현재 월 Axis AI 사용량 조회 (analyses/validations/discoveries).
 * 백엔드: GET /api/ai/usage — 로그인 필수(apiCall이 토큰 자동 첨부).
 */
export function useUsage() {
  const { signedIn } = useAuth();
  return useQuery({
    queryKey: ["ai-usage"],
    queryFn: () => apiCall<UsageResponse>("/api/ai/usage"),
    enabled: signedIn,
    staleTime: 60_000, // 1분 — 분석 직후 갱신 반영용으로 짧게
  });
}
