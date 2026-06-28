"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/useAuth";
import { useCheckout } from "@/hooks/useSubscription";

/** Pro 결제 버튼 — 월/연 선택 + 로그인 분기 + LS checkout. */
export function CheckoutButton() {
  const { signedIn } = useAuth();
  const checkout = useCheckout();
  const [plan, setPlan] = useState<"monthly" | "yearly">("monthly");
  const resumed = useRef(false);

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
          {checkout.isPending ? "이동 중…" : "💎 14일 무료로 시작"}
        </Button>
      ) : (
        <Link
          href={`/login?next=${encodeURIComponent(`/pricing?checkout=${plan}`)}`}
          className="block"
        >
          <Button className="w-full">💎 가입하고 14일 무료로 시작</Button>
        </Link>
      )}
      <p className="text-center text-[11px] text-muted-foreground">
        첫 14일 무료 · 언제든 해지
      </p>
    </div>
  );
}
