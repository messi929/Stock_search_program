"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/useAuth";
import { useCheckout, useSubscription } from "@/hooks/useSubscription";

/** Pro 결제 버튼 — 월/연 선택 + 로그인/구독상태 분기 + LS checkout. */
export function CheckoutButton() {
  const { signedIn } = useAuth();
  const { data: sub } = useSubscription();
  const checkout = useCheckout();
  const [plan, setPlan] = useState<"monthly" | "yearly">("monthly");
  const resumed = useRef(false);

  const isPro = sub?.tier === "pro";
  // 트라이얼(7일 무료) 자격: 비로그인 신규 방문자는 가능, 로그인 사용자는 서버 판정값.
  // 로딩 중(undefined)엔 과대약속을 피해 '구독 시작'으로 보수적 처리.
  const trialEligible = signedIn ? sub?.trial_eligible === true : true;

  // 가입→결제 흐름: 비로그인 사용자가 결제를 누르면 /login?next=/pricing?checkout=plan 으로
  // 보내고, 로그인 후 /pricing 으로 돌아오면 checkout 파라미터를 보고 결제를 자동 재개한다.
  // (effect 안에서 setState 금지 규칙 — plan은 건드리지 않고 파라미터 값으로 바로 결제)
  useEffect(() => {
    if (!signedIn || resumed.current) return;
    const q = new URLSearchParams(window.location.search).get("checkout");
    if (q !== "monthly" && q !== "yearly") return;
    resumed.current = true;
    checkout.mutate(q, {
      onError: (e) => toast.error((e as Error)?.message ?? "결제 시작에 실패했습니다."),
    });
    // 중복 재개 방지: URL에서 checkout 파라미터 제거
    const url = new URL(window.location.href);
    url.searchParams.delete("checkout");
    window.history.replaceState({}, "", url.toString());
  }, [signedIn, checkout]);

  // 이미 Pro(구독 중·체험 중·관리자) — '또 7일 무료' 오해 방지: 결제 CTA 대신 구독 관리.
  if (isPro) {
    return (
      <div className="space-y-2">
        <div className="rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-center text-sm font-medium text-amber-600">
          💎 이미 Pro를 이용 중입니다
        </div>
        <Link href="/settings/profile" className="block">
          <Button variant="outline" className="w-full">
            구독 관리
          </Button>
        </Link>
      </div>
    );
  }

  const tab = (key: "monthly" | "yearly", label: string) => (
    <button
      type="button"
      onClick={() => setPlan(key)}
      className={`flex-1 rounded-md px-2 py-1.5 text-xs font-medium transition-colors ${
        plan === key
          ? "bg-amber-500 text-black"
          : "bg-muted text-muted-foreground hover:bg-muted/70"
      }`}
    >
      {label}
    </button>
  );

  const ctaSignedIn = trialEligible ? "💎 7일 무료로 시작" : "💎 Pro 구독 시작";
  const ctaGuest = trialEligible ? "💎 가입하고 7일 무료로 시작" : "💎 가입하고 Pro 시작";

  return (
    <div className="space-y-2">
      <div className="flex gap-1">
        {tab("monthly", "월 39,000원")}
        {tab("yearly", "연 398,000원")}
      </div>
      {signedIn ? (
        <Button
          className="w-full"
          onClick={() =>
            checkout.mutate(plan, {
              onError: (e) => toast.error((e as Error)?.message ?? "결제 시작에 실패했습니다."),
            })
          }
          disabled={checkout.isPending}
        >
          {checkout.isPending ? "이동 중…" : ctaSignedIn}
        </Button>
      ) : (
        <Link
          href={`/login?next=${encodeURIComponent(`/pricing?checkout=${plan}`)}`}
          className="block"
        >
          <Button className="w-full">{ctaGuest}</Button>
        </Link>
      )}
      <p className="text-center text-[11px] text-muted-foreground">
        {trialEligible ? "첫 7일 무료 · 언제든 해지" : "언제든 해지 · 결제 후 바로 이용"}
      </p>
    </div>
  );
}
