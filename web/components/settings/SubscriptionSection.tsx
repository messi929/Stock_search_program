"use client";

import Link from "next/link";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  useBillingPortal,
  useCancelSubscription,
  useSubscription,
} from "@/hooks/useSubscription";

const STATUS_LABEL: Record<string, string> = {
  on_trial: "무료 체험 중",
  active: "구독 중",
  cancelled: "해지 예정",
  expired: "만료됨",
  paused: "일시정지",
  past_due: "결제 실패",
};

const PLAN_LABEL: Record<string, string> = {
  monthly: "Pro 월간",
  yearly: "Pro 연간",
  admin: "Pro (관리자)",
};

function formatDate(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return `${d.getFullYear()}.${d.getMonth() + 1}.${d.getDate()}`;
}

export function SubscriptionSection() {
  const { data, isLoading } = useSubscription();
  const cancel = useCancelSubscription();
  const portal = useBillingPortal();

  const tier = data?.tier ?? "free";
  const sub = data?.subscription ?? null;
  const isAdmin = sub?.plan === "admin";

  return (
    <Card>
      <CardContent className="space-y-3 p-6">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold">구독</h2>
          {!isLoading && (
            <span className="text-xs text-muted-foreground">
              {tier === "free" ? "Free 플랜" : PLAN_LABEL[sub?.plan ?? ""] ?? "Pro"}
            </span>
          )}
        </div>

        {isLoading ? (
          <div className="h-16 animate-pulse rounded bg-muted" />
        ) : tier === "free" || !sub ? (
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">
              현재 무료 플랜입니다. Pro로 업그레이드하면 월 100회 분석·관심 종목
              30개·커스텀 스크리너를 이용할 수 있습니다. 첫 14일 무료.
            </p>
            <Link href="/pricing" className="block">
              <Button className="w-full sm:w-auto">💎 Pro 업그레이드</Button>
            </Link>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <span className="rounded-full bg-amber-500/15 px-2 py-0.5 text-xs font-medium text-amber-600">
                {STATUS_LABEL[sub.status] ?? sub.status}
              </span>
              {sub.current_period_end && (
                <span className="text-muted-foreground">
                  {sub.cancel_at_period_end
                    ? `${formatDate(sub.current_period_end)}에 해지`
                    : `다음 갱신 ${formatDate(sub.current_period_end)}`}
                </span>
              )}
            </div>

            {isAdmin ? (
              <p className="text-xs text-muted-foreground">
                관리자 계정으로 Pro 기능이 활성화돼 있습니다.
              </p>
            ) : (
              <div className="flex flex-wrap gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() =>
                    portal.mutate(undefined, {
                      onError: (e) =>
                        toast.error((e as Error)?.message ?? "포털 연결 실패"),
                    })
                  }
                  disabled={portal.isPending}
                >
                  결제수단·영수증
                </Button>
                {!sub.cancel_at_period_end && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-destructive hover:text-destructive"
                    onClick={() => {
                      if (!confirm("정말 구독을 해지하시겠어요? 기간 종료까지는 계속 이용할 수 있습니다.")) return;
                      cancel.mutate(undefined, {
                        onSuccess: () => toast.success("기간 종료 후 해지됩니다."),
                        onError: (e) =>
                          toast.error((e as Error)?.message ?? "해지 요청 실패"),
                      });
                    }}
                    disabled={cancel.isPending}
                  >
                    구독 해지
                  </Button>
                )}
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
