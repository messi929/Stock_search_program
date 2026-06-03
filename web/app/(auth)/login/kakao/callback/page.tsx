"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { completeKakaoLogin } from "@/lib/auth-actions";

// open-redirect 차단: 로컬 경로만 허용 (login 페이지와 동일 규칙).
function safeNext(raw: string | null): string {
  if (!raw) return "/dashboard";
  if (!raw.startsWith("/") || raw.startsWith("//")) return "/dashboard";
  if (raw === "/login") return "/dashboard";
  return raw;
}

export default function KakaoCallbackPage() {
  return (
    <Suspense fallback={<Shell>로그인 처리 중...</Shell>}>
      <KakaoCallbackInner />
    </Suspense>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <Card className="w-full max-w-md">
      <CardContent className="p-8 space-y-4 text-center">{children}</CardContent>
    </Card>
  );
}

function KakaoCallbackInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const ran = useRef(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // StrictMode/리렌더로 인한 중복 교환 방지 (인가코드는 1회용).
    if (ran.current) return;
    ran.current = true;

    const code = searchParams.get("code");
    const oauthError = searchParams.get("error");
    const next = safeNext(searchParams.get("state"));

    // async 경계 안에서 setState — effect 본문 동기 setState(react-hooks 규칙) 회피.
    void (async () => {
      if (oauthError || !code) {
        setError("카카오 로그인이 취소되었거나 실패했습니다.");
        return;
      }
      try {
        await completeKakaoLogin(code);
        toast.success("로그인됨");
        // onboarded 판정은 목적지(dashboard) 레이아웃이 처리 — 신규 사용자는 자동으로 온보딩.
        router.replace(next);
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : "카카오 로그인 실패";
        console.warn("[kakao callback] failed:", err);
        setError(msg);
      }
    })();
  }, [searchParams, router]);

  if (error) {
    return (
      <Shell>
        <p className="text-sm text-destructive">{error}</p>
        <Link
          href="/login"
          className={buttonVariants({ variant: "outline", className: "w-full" })}
        >
          다시 로그인
        </Link>
      </Shell>
    );
  }

  return <Shell>로그인 처리 중...</Shell>;
}
