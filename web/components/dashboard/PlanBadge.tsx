"use client";

import Link from "next/link";

import { useSubscription } from "@/hooks/useSubscription";

const STATUS_SHORT: Record<string, string> = {
  on_trial: "무료 체험",
  active: "구독 중",
  cancelled: "해지 예정",
  paused: "일시정지",
  past_due: "결제 실패",
};

function fmt(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return `${d.getMonth() + 1}.${d.getDate()}`;
}

/**
 * 현재 플랜(Pro/Free) 인지 배지 — 접속 직후 자기 상태를 알 수 있게 한다.
 * Pro면 설정(구독 관리)으로, Free면 요금제로 링크. compact는 모바일 상단바용(아이콘만).
 */
export function PlanBadge({ compact = false }: { compact?: boolean }) {
  const { data, isLoading } = useSubscription();
  if (isLoading) return null;

  const tier = data?.tier ?? "free";
  const sub = data?.subscription ?? null;

  if (tier === "pro") {
    const isAdmin = sub?.plan === "admin";
    const renewal = sub?.current_period_end ? fmt(sub.current_period_end) : "";
    const statusLabel = sub?.status ? STATUS_SHORT[sub.status] ?? "" : "";
    return (
      <Link
        href="/settings/profile"
        aria-label="구독 관리"
        className="inline-flex items-center gap-1 rounded-full border border-amber-500/50 bg-amber-500/15 px-2.5 py-1 text-xs font-semibold text-amber-600 hover:bg-amber-500/25"
      >
        <span>💎 Pro</span>
        {!compact && isAdmin && <span className="font-normal opacity-80">· 관리자</span>}
        {!compact && !isAdmin && sub?.cancel_at_period_end && renewal && (
          <span className="font-normal opacity-80">· {renewal} 해지</span>
        )}
        {!compact && !isAdmin && !sub?.cancel_at_period_end && renewal && (
          <span className="font-normal opacity-80">
            · {statusLabel === "무료 체험" ? "체험 " : ""}~{renewal} 갱신
          </span>
        )}
      </Link>
    );
  }

  // Free
  if (compact) {
    return (
      <Link
        href="/pricing"
        aria-label="요금제"
        className="inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-medium text-muted-foreground hover:text-foreground"
      >
        Free
      </Link>
    );
  }
  return (
    <Link
      href="/pricing"
      className="inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-medium text-muted-foreground hover:border-amber-500/50 hover:text-amber-600"
    >
      <span>Free</span>
      <span className="opacity-70">· 💎 업그레이드</span>
    </Link>
  );
}
