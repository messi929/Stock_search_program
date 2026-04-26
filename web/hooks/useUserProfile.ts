"use client";

/**
 * Axis 사용자 프로파일 — 백엔드 GET/PUT /api/ai/profile 경유.
 *
 * 보안: Firestore 직접 쓰기 대신 백엔드 admin SDK가 화이트리스트 검증 후 영속화
 * (코드 검증 #2 해결). 사용자 doc의 axis_profile 필드만 격리.
 *
 * 안정성: onAuthStateChanged 구독으로 uid 변경 시마다 재조회. mount 시점
 * auth.currentUser=null로 인한 race condition 제거 (코드 검증 #1 해결).
 */
import { onAuthStateChanged } from "firebase/auth";
import { useCallback, useEffect, useState } from "react";

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

export function useUserProfile() {
  const [profile, setProfile] = useState<AxisProfile | null>(null);
  const [onboarded, setOnboarded] = useState(false);
  const [loading, setLoading] = useState(true);
  const [uid, setUid] = useState<string | null>(null);

  const reload = useCallback(async (currentUid: string | null) => {
    if (!currentUid) {
      setProfile(null);
      setOnboarded(false);
      return;
    }
    try {
      const res = await apiCall<ProfileResponse>("/api/ai/profile");
      setProfile(res.profile);
      setOnboarded(res.onboarded);
    } catch (err) {
      console.warn("[useUserProfile] load failed:", err);
      setProfile(null);
      setOnboarded(false);
    }
  }, []);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, async (user) => {
      const nextUid = user?.uid ?? null;
      setUid(nextUid);
      // auth가 해결되기 전에는 loading=true 유지
      await reload(nextUid);
      setLoading(false);
    });
    return unsubscribe;
  }, [reload]);

  const save = useCallback(
    async (next: AxisProfile) => {
      if (!auth.currentUser) throw new Error("로그인 필요");
      await apiCall<{ ok: boolean }>("/api/ai/profile", {
        method: "PUT",
        body: JSON.stringify(next),
      });
      await reload(auth.currentUser.uid);
    },
    [reload],
  );

  return {
    profile,
    onboarded,
    loading,
    save,
    uid,
    reload: () => reload(auth.currentUser?.uid ?? null),
  };
}
