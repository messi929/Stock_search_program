"use client";

/**
 * Axis 사용자 프로파일 — 백엔드 GET/PUT /api/ai/profile 경유.
 *
 * 보안: Firestore 직접 쓰기 대신 백엔드 admin SDK가 화이트리스트 검증 후 영속화
 * (코드 검증 #2 해결). 사용자 doc의 axis_profile 필드만 격리.
 *
 * 성능: TanStack Query 전역 캐시(queryKey=["user-profile", uid])로 통합.
 * login → dashboard layout → 내부 컴포넌트가 같은 훅을 호출해도 캐시를 공유하므로
 * /api/ai/profile 네트워크 호출은 1회로 dedupe(이전엔 컴포넌트마다 onAuthStateChanged
 * 구독 + 독립 fetch → 로그인 직후 "로딩 중"이 2~N회 반복되던 문제 해결).
 */
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { useCallback } from "react";

import { useAuth } from "@/hooks/useAuth";
import { apiCall } from "@/lib/api";
import { auth } from "@/lib/firebase";

export type InvestingExperience = "beginner" | "1-5y" | "5y+";
export type HoldingPeriod = "1m" | "6m" | "1-2y" | "3y+";
export type PersonaId = "blackrock" | "ark" | "graham";

export interface AxisProfile {
  investing_experience?: InvestingExperience;
  holding_period?: HoldingPeriod;
  volatility_tolerance?: "10" | "20" | "30";
  interested_sectors?: string[];
  investment_principles?: string[];
  preferred_persona?: PersonaId;
  onboarded_at?: { _seconds?: number } | string | null;
}

interface ProfileResponse {
  profile: AxisProfile | null;
  onboarded: boolean;
}

const profileKey = (uid: string | null) => ["user-profile", uid] as const;

export function useUserProfile() {
  const qc = useQueryClient();
  const { user, loading: authLoading } = useAuth();
  const uid = user?.uid ?? null;

  const query = useQuery({
    queryKey: profileKey(uid),
    queryFn: () => apiCall<ProfileResponse>("/api/ai/profile"),
    // uid 확정 전에는 실행하지 않음 (auth 미해결 시 idle).
    enabled: !!uid,
    // 프로필은 자주 바뀌지 않음 — 5분 신선 유지로 페이지 전환 시 재요청 차단.
    staleTime: 5 * 60_000,
  });

  const saveMutation = useMutation({
    mutationFn: (next: AxisProfile) => {
      if (!auth.currentUser) throw new Error("로그인 필요");
      return apiCall<{ ok: boolean }>("/api/ai/profile", {
        method: "PUT",
        body: JSON.stringify(next),
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({
        queryKey: profileKey(auth.currentUser?.uid ?? null),
      });
    },
  });

  // 기존 호출부 호환: save(next) 형태 유지 (Promise 반환).
  const save = useCallback(
    (next: AxisProfile) => saveMutation.mutateAsync(next),
    [saveMutation],
  );

  const reload = useCallback(() => {
    qc.invalidateQueries({
      queryKey: profileKey(auth.currentUser?.uid ?? null),
    });
  }, [qc]);

  // auth 미해결이거나, 로그인되어 프로필 첫 조회 중일 때만 loading.
  // (비로그인 확정 시 authLoading=false·uid=null → loading=false)
  const loading = authLoading || (!!uid && query.isLoading);

  return {
    profile: query.data?.profile ?? null,
    onboarded: query.data?.onboarded ?? false,
    loading,
    save,
    uid,
    reload,
  };
}
