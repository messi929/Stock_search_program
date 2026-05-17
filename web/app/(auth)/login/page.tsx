"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { toast } from "sonner";

import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/useAuth";
import { useUserProfile } from "@/hooks/useUserProfile";
import { signInWithGoogle } from "@/lib/auth-actions";

// open-redirect 차단: 로컬 경로만 허용 (//, http:, javascript: 거부).
function safeNext(raw: string | null): string {
  if (!raw) return "/dashboard";
  if (!raw.startsWith("/") || raw.startsWith("//")) return "/dashboard";
  if (raw === "/login") return "/dashboard";
  return raw;
}

export default function LoginPage() {
  // Next.js 16 — useSearchParams는 Suspense 경계 필수
  return (
    <Suspense fallback={<LoginCardShell />}>
      <LoginPageInner />
    </Suspense>
  );
}

function LoginCardShell() {
  return (
    <Card className="w-full max-w-md">
      <CardContent className="p-8 space-y-6">
        <p className="text-sm text-muted-foreground text-center">로딩 중...</p>
      </CardContent>
    </Card>
  );
}

function LoginPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const next = safeNext(searchParams.get("next"));
  const { user, loading: authLoading } = useAuth();
  const { onboarded, loading: profileLoading } = useUserProfile();
  const [busy, setBusy] = useState(false);

  // 이미 로그인 상태 → onboarding 또는 next(또는 dashboard)로 이동
  useEffect(() => {
    if (authLoading || profileLoading || !user) return;
    router.replace(onboarded ? next : "/onboarding");
  }, [user, onboarded, authLoading, profileLoading, next, router]);

  const handleGoogle = async () => {
    setBusy(true);
    try {
      await signInWithGoogle();
      toast.success("로그인됨");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "로그인 실패";
      console.warn("[login] google failed:", err);
      toast.error(msg);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card className="w-full max-w-md">
      <CardContent className="p-8 space-y-6">
        <div className="text-center space-y-2">
          <h1 className="text-2xl font-bold">로그인</h1>
          <p className="text-sm text-muted-foreground">
            AI 투자 분석 파트너 — Axis
          </p>
        </div>

        <div className="space-y-3">
          <Button
            type="button"
            onClick={handleGoogle}
            disabled={busy || authLoading}
            className="w-full h-11"
            size="lg"
          >
            {busy ? "처리 중..." : "🔵 구글로 로그인"}
          </Button>
          <Button
            type="button"
            disabled
            variant="outline"
            className="w-full h-11"
            size="lg"
          >
            🟡 카카오로 로그인 (준비 중)
          </Button>
        </div>

        <p className="text-xs text-muted-foreground text-center pt-2">
          로그인하면 Axis{" "}
          <Link href="/terms" className="underline hover:text-foreground">
            이용약관
          </Link>{" "}
          및{" "}
          <Link href="/privacy" className="underline hover:text-foreground">
            개인정보처리방침
          </Link>
          에 동의한 것으로 간주됩니다.
        </p>
      </CardContent>
    </Card>
  );
}
