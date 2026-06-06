"use client";

/**
 * 관리자 여부 게이트 — 백엔드 GET /api/admin/me (관리자면 200, 아니면 403).
 *
 * 서버가 ADMIN_EMAILS로 권한을 판정하므로 프론트는 결과만 캐싱한다. 403/에러는
 * 비관리자(false)로 처리. (useUserProfile 패턴 모방 — 전역 TanStack 캐시로 dedupe.)
 */
import { useQuery } from "@tanstack/react-query";

import { useAuth } from "@/hooks/useAuth";
import { apiCall } from "@/lib/api";

export function useIsAdmin() {
  const { user, loading: authLoading } = useAuth();
  const uid = user?.uid ?? null;

  const query = useQuery({
    queryKey: ["is-admin", uid],
    queryFn: async () => {
      try {
        await apiCall<{ is_admin: boolean }>("/api/admin/me");
        return true;
      } catch {
        return false; // 403/네트워크 → 비관리자
      }
    },
    enabled: !!uid,
    staleTime: 10 * 60_000,
    retry: false,
  });

  return {
    isAdmin: query.data ?? false,
    loading: authLoading || (!!uid && query.isLoading),
  };
}
