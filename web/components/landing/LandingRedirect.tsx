"use client";

/**
 * 랜딩(/) 진입 시 로그인 상태면 대시보드로 보냄.
 *
 * 랜딩은 정적 SEO 페이지(서버 컴포넌트)라 로그인 상태를 모른다. 이 client
 * 컴포넌트를 페이지 최상단에 두어, 로그인된 사용자가 홈/로고를 누르면 마케팅
 * 랜딩 대신 /dashboard로 직행하게 한다(비로그인·로그아웃 시에만 랜딩 노출).
 */
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { useAuth } from "@/hooks/useAuth";

export function LandingRedirect() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && user) router.replace("/dashboard");
  }, [user, loading, router]);

  return null;
}
