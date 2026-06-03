"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { toast } from "sonner";

import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/hooks/useAuth";
import { useUserProfile } from "@/hooks/useUserProfile";
import {
  kakaoConfigured,
  looksDisposable,
  resendVerification,
  sendPasswordReset,
  signInWithEmail,
  signInWithGoogle,
  signOut,
  signUpWithEmail,
  startKakaoLogin,
} from "@/lib/auth-actions";

// open-redirect 차단: 로컬 경로만 허용 (//, http:, javascript: 거부).
function safeNext(raw: string | null): string {
  if (!raw) return "/dashboard";
  if (!raw.startsWith("/") || raw.startsWith("//")) return "/dashboard";
  if (raw === "/login") return "/dashboard";
  return raw;
}

// Firebase Auth 에러코드 → 한국어 안내.
function authErrorMessage(err: unknown): string {
  const code = (err as { code?: string })?.code ?? "";
  switch (code) {
    case "auth/email-already-in-use":
      return "이미 가입된 이메일입니다. 로그인해주세요.";
    case "auth/invalid-email":
      return "이메일 형식이 올바르지 않습니다.";
    case "auth/weak-password":
      return "비밀번호는 6자 이상이어야 합니다.";
    case "auth/invalid-credential":
    case "auth/wrong-password":
    case "auth/user-not-found":
      return "이메일 또는 비밀번호가 올바르지 않습니다.";
    case "auth/too-many-requests":
      return "시도가 너무 많습니다. 잠시 후 다시 시도해주세요.";
    default:
      return err instanceof Error ? err.message : "오류가 발생했습니다.";
  }
}

type Mode = "signin" | "signup" | "reset";

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
  const kakaoOn = kakaoConfigured();

  const [mode, setMode] = useState<Mode>("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");

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
      console.warn("[login] google failed:", err);
      toast.error(authErrorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const handleEmailSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      if (mode === "reset") {
        await sendPasswordReset(email.trim());
        toast.success("비밀번호 재설정 메일을 보냈습니다. 받은 편지함을 확인해주세요.");
        setMode("signin");
        return;
      }

      if (mode === "signup") {
        if (looksDisposable(email)) {
          toast.error("일회용 이메일로는 가입할 수 없습니다.");
          return;
        }
        if (password.length < 8) {
          toast.error("비밀번호는 8자 이상으로 설정해주세요.");
          return;
        }
        if (password !== passwordConfirm) {
          toast.error("비밀번호가 일치하지 않습니다.");
          return;
        }
        await signUpWithEmail(email.trim(), password);
        // 인증 전 자동 로그인 방지 — 메일 확인 후 다시 로그인하도록 유도.
        await signOut();
        toast.success("인증 메일을 보냈습니다. 메일 확인 후 로그인해주세요.");
        setMode("signin");
        setPassword("");
        setPasswordConfirm("");
        return;
      }

      // signin
      const cred = await signInWithEmail(email.trim(), password);
      if (!cred.user.emailVerified) {
        toast.warning("이메일 인증이 필요합니다. 받은 편지함의 인증 링크를 확인해주세요.", {
          duration: 8000,
          action: {
            label: "인증 메일 재발송",
            onClick: () => {
              resendVerification()
                .then(() => toast.success("인증 메일을 다시 보냈습니다."))
                .catch(() => toast.error("재발송에 실패했습니다. 잠시 후 다시 시도해주세요."));
            },
          },
        });
      } else {
        toast.success("로그인됨");
      }
      // 이동은 위 useEffect가 처리.
    } catch (err: unknown) {
      console.warn("[login] email auth failed:", err);
      toast.error(authErrorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const titleByMode: Record<Mode, string> = {
    signin: "로그인",
    signup: "회원가입",
    reset: "비밀번호 재설정",
  };

  return (
    <Card className="w-full max-w-md">
      <CardContent className="p-8 space-y-6">
        <div className="text-center space-y-2">
          <h1 className="text-2xl font-bold">{titleByMode[mode]}</h1>
          <p className="text-sm text-muted-foreground">
            AI 투자 분석 파트너 — Axis
          </p>
        </div>

        {/* 소셜 로그인 */}
        <div className="space-y-3">
          <Button
            type="button"
            onClick={handleGoogle}
            disabled={busy || authLoading}
            className="w-full h-11"
            size="lg"
          >
            {busy ? "처리 중..." : "🔵 구글로 계속하기"}
          </Button>
          <Button
            type="button"
            onClick={() => startKakaoLogin(next)}
            disabled={!kakaoOn || busy}
            variant="outline"
            className="w-full h-11 bg-[#FEE500] text-black hover:bg-[#FEE500]/90 border-[#FEE500]"
            size="lg"
          >
            {kakaoOn ? "🟡 카카오로 계속하기" : "🟡 카카오로 로그인 (준비 중)"}
          </Button>
        </div>

        <div className="flex items-center gap-3">
          <div className="h-px flex-1 bg-border" />
          <span className="text-xs text-muted-foreground">또는 이메일로</span>
          <div className="h-px flex-1 bg-border" />
        </div>

        {/* 이메일/비밀번호 */}
        <form onSubmit={handleEmailSubmit} className="space-y-3">
          <Input
            type="email"
            inputMode="email"
            autoComplete="email"
            placeholder="이메일"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            className="h-11"
          />
          {mode !== "reset" && (
            <Input
              type="password"
              autoComplete={mode === "signup" ? "new-password" : "current-password"}
              placeholder="비밀번호"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="h-11"
            />
          )}
          {mode === "signup" && (
            <Input
              type="password"
              autoComplete="new-password"
              placeholder="비밀번호 확인"
              value={passwordConfirm}
              onChange={(e) => setPasswordConfirm(e.target.value)}
              required
              className="h-11"
            />
          )}
          {mode === "signup" && looksDisposable(email) && (
            <p className="text-xs text-destructive">
              일회용 이메일로는 가입할 수 없습니다.
            </p>
          )}
          <Button type="submit" disabled={busy} className="w-full h-11" size="lg">
            {busy
              ? "처리 중..."
              : mode === "signin"
                ? "이메일로 로그인"
                : mode === "signup"
                  ? "회원가입"
                  : "재설정 메일 받기"}
          </Button>
        </form>

        {/* 모드 전환 */}
        <div className="text-center text-sm text-muted-foreground space-y-1">
          {mode === "signin" && (
            <>
              <p>
                계정이 없으신가요?{" "}
                <button
                  type="button"
                  onClick={() => setMode("signup")}
                  className="underline hover:text-foreground"
                >
                  회원가입
                </button>
              </p>
              <p>
                <button
                  type="button"
                  onClick={() => setMode("reset")}
                  className="underline hover:text-foreground"
                >
                  비밀번호를 잊으셨나요?
                </button>
              </p>
            </>
          )}
          {mode === "signup" && (
            <p>
              이미 계정이 있으신가요?{" "}
              <button
                type="button"
                onClick={() => setMode("signin")}
                className="underline hover:text-foreground"
              >
                로그인
              </button>
            </p>
          )}
          {mode === "reset" && (
            <p>
              <button
                type="button"
                onClick={() => setMode("signin")}
                className="underline hover:text-foreground"
              >
                로그인으로 돌아가기
              </button>
            </p>
          )}
        </div>

        <p className="text-xs text-muted-foreground text-center pt-2">
          계속하면 Axis{" "}
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
