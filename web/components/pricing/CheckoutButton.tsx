"use client";

import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/useAuth";
import { useCheckout } from "@/hooks/useSubscription";

/** Pro 결제 버튼 — 월/연 선택 + 로그인 분기 + LS checkout. */
export function CheckoutButton() {
  const { signedIn } = useAuth();
  const checkout = useCheckout();
  const [plan, setPlan] = useState<"monthly" | "yearly">("monthly");

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
        {tab("monthly", "월 29,000원")}
        {tab("yearly", "연 319,000원")}
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
        <Link href="/login" className="block">
          <Button className="w-full">💎 14일 무료로 시작</Button>
        </Link>
      )}
      <p className="text-center text-[11px] text-muted-foreground">
        첫 14일 무료 · 언제든 해지
      </p>
    </div>
  );
}
