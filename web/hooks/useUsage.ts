import { useQuery } from "@tanstack/react-query";

import { useAuth } from "@/hooks/useAuth";
import { apiCall } from "@/lib/api";
import type { HistoryResponse, UsageResponse } from "@/types/api";

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

/**
 * 분석/검증/발견 이력 조회 (최근 40, created_at desc).
 * UsageCard 항목 클릭 시 '해당 유형 종목 + 일자' 표시용.
 */
export function useHistory() {
  const { signedIn } = useAuth();
  return useQuery({
    queryKey: ["ai-history"],
    queryFn: () => apiCall<HistoryResponse>("/api/ai/history"),
    enabled: signedIn,
    staleTime: 60_000,
  });
}
