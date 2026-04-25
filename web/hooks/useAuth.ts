"use client";

/**
 * Firebase Auth 상태 훅 — onAuthStateChanged 구독.
 * (auth) 그룹 페이지에서 인증 상태 체크에 사용.
 */
import { onAuthStateChanged, type User } from "firebase/auth";
import { useEffect, useState } from "react";

import { auth } from "@/lib/firebase";

export function useAuth() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (next) => {
      setUser(next);
      setLoading(false);
    });
    return unsubscribe;
  }, []);

  return { user, loading, signedIn: !!user };
}
