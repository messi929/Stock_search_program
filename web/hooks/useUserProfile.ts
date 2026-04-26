"use client";

/**
 * Axis 사용자 프로파일 — Firestore users/{uid}.axis_profile 필드.
 * v7.5의 user 문서를 공유하되 Axis 전용 필드만 기록 (충돌 방지).
 */
import {
  doc,
  getDoc,
  serverTimestamp,
  setDoc,
  Timestamp,
} from "firebase/firestore";
import { useEffect, useState, useCallback } from "react";

import { auth, db } from "@/lib/firebase";

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
  onboarded_at?: Timestamp | null;
}

const PROFILE_FIELD = "axis_profile";

export function useUserProfile() {
  const [profile, setProfile] = useState<AxisProfile | null>(null);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(async () => {
    const uid = auth.currentUser?.uid;
    if (!uid) {
      setProfile(null);
      setLoading(false);
      return;
    }
    try {
      const snap = await getDoc(doc(db, "users", uid));
      const data = snap.exists() ? snap.data() : null;
      setProfile((data?.[PROFILE_FIELD] as AxisProfile) ?? null);
    } catch (err) {
      console.warn("[useUserProfile] load failed:", err);
      setProfile(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  const save = useCallback(
    async (next: AxisProfile) => {
      const uid = auth.currentUser?.uid;
      if (!uid) throw new Error("로그인 필요");

      await setDoc(
        doc(db, "users", uid),
        {
          [PROFILE_FIELD]: {
            ...next,
            onboarded_at: next.onboarded_at ?? serverTimestamp(),
          },
        },
        { merge: true },
      );
      await reload();
    },
    [reload],
  );

  return {
    profile,
    loading,
    onboarded: !!profile?.onboarded_at,
    save,
    reload,
  };
}
