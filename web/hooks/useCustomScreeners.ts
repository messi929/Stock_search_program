"use client";

/**
 * 커스텀 스크리너 CRUD 훅 — Pro 전용 백엔드 라우트 호출.
 *
 * 백엔드: GET/POST/DELETE /api/ai/screeners/custom
 *        Free 플랜은 402 PRO_REQUIRED 응답.
 *
 * 실행은 v7.5 /api/scan?category=custom + 사용자 필터 query string으로.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiCall } from "@/lib/api";
import type {
  CustomScreener,
  CustomScreenerFilters,
  CustomScreenersResponse,
} from "@/types/api";

const QK = ["custom-screeners"] as const;

export function useCustomScreeners(enabled = true) {
  return useQuery({
    queryKey: QK,
    queryFn: () => apiCall<CustomScreenersResponse>("/api/ai/screeners/custom"),
    enabled,
    staleTime: 30_000,
  });
}

export interface CustomScreenerInput {
  name: string;
  filters: CustomScreenerFilters;
  sort_by: string;
  sort_asc: boolean;
}

export function useSaveCustomScreener() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: CustomScreenerInput) =>
      apiCall<{ ok: boolean; id: string }>("/api/ai/screeners/custom", {
        method: "POST",
        body: JSON.stringify(input),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: QK }),
  });
}

export function useDeleteCustomScreener() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiCall<{ ok: boolean }>(`/api/ai/screeners/custom/${encodeURIComponent(id)}`, {
        method: "DELETE",
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: QK }),
  });
}

/**
 * 사용자 필터 객체 → /api/scan query string. category=custom 고정.
 * undefined/null/빈 문자열은 제외, market="ALL"은 명시적으로 보냄.
 */
export function filtersToQueryString(
  filters: CustomScreenerFilters,
  sortBy: string,
  sortAsc: boolean,
  limit = 50,
): string {
  const params = new URLSearchParams();
  params.set("category", "custom");
  params.set("limit", String(limit));
  params.set("sort_by", sortBy);
  params.set("sort_asc", String(sortAsc));

  for (const [key, value] of Object.entries(filters)) {
    if (value === undefined || value === null || value === "") continue;
    if (typeof value === "boolean") {
      // 백엔드는 None 기본 → true일 때만 보냄. false는 omit.
      if (value) params.set(key, "true");
      continue;
    }
    params.set(key, String(value));
  }
  return params.toString();
}

export function useRunCustomScreener(
  filters: CustomScreenerFilters | null,
  sortBy: string,
  sortAsc: boolean,
) {
  return useQuery({
    queryKey: ["scan-custom", filters, sortBy, sortAsc],
    queryFn: () => {
      if (!filters) throw new Error("filters required");
      const qs = filtersToQueryString(filters, sortBy, sortAsc, 50);
      return apiCall<{
        category: string;
        stocks: Array<Record<string, unknown>>;
        total: number;
        message?: string;
      }>(`/api/scan?${qs}`);
    },
    enabled: !!filters,
    staleTime: 60_000,
  });
}

export type SavedScreenerSummary = Pick<
  CustomScreener,
  "id" | "name" | "filters" | "sort_by" | "sort_asc" | "updated_at"
>;
