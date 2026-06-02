import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/hooks/useAuth";
import { apiCall } from "@/lib/api";
import type { CheckoutResponse, SubscriptionResponse } from "@/types/api";

/** 현재 사용자의 구독 상태 (Lemon Squeezy). */
export function useSubscription() {
  const { signedIn } = useAuth();
  return useQuery({
    queryKey: ["subscription"],
    queryFn: () => apiCall<SubscriptionResponse>("/api/subscription"),
    enabled: signedIn,
    staleTime: 60_000,
  });
}

/** Checkout 세션 생성 → LS 결제 페이지로 이동. plan: "monthly" | "yearly". */
export function useCheckout() {
  return useMutation({
    mutationFn: (plan: "monthly" | "yearly") =>
      apiCall<CheckoutResponse>("/api/checkout", {
        method: "POST",
        body: JSON.stringify({ plan }),
      }),
    onSuccess: (data) => {
      if (data?.url) window.location.href = data.url;
    },
  });
}

/** 구독 해지 (기간 종료 예약). */
export function useCancelSubscription() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiCall<{ message: string }>("/api/subscription/cancel", { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["subscription"] }),
  });
}

/** 고객 포털(결제수단 변경·영수증) URL → 이동. */
export function useBillingPortal() {
  return useMutation({
    mutationFn: () => apiCall<{ url: string }>("/api/billing-portal", { method: "POST" }),
    onSuccess: (data) => {
      if (data?.url) window.location.href = data.url;
    },
  });
}
