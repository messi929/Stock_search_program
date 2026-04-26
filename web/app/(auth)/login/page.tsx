"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/useAuth";
import { useUserProfile } from "@/hooks/useUserProfile";
import { signInWithGoogle } from "@/lib/auth-actions";

export default function LoginPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const { onboarded, loading: profileLoading } = useUserProfile();
  const [busy, setBusy] = useState(false);

  // 이미 로그인 상태 → onboarding 또는 dashboard로 자동 이동
  useEffect(() => {
    if (authLoading || profileLoading || !user) return;
    router.replace(onboarded ? "/dashboard" : "/onboarding");
  }, [user, onboarded, authLoading, profileLoading, router]);

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
          로그인하면 Axis 이용약관 및 개인정보처리방침에 동의한 것으로 간주됩니다.
        </p>
      </CardContent>
    </Card>
  );
}
