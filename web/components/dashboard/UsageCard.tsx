"use client";

import Link from "next/link";

import { Card, CardContent } from "@/components/ui/card";
import { useUsage } from "@/hooks/useUsage";
import type { UsageMetric } from "@/types/api";

const PLAN_LABEL: Record<string, string> = {
  free: "무료",
  pro: "Pro",
  premium: "Premium",
};

// kind: /history?kind= 로 전달 (analysis|validation|discovery)
const METRICS: { key: "analyses" | "validations" | "discoveries"; label: string; icon: string; kind: string }[] = [
  { key: "analyses", label: "종목 분석", icon: "🔍", kind: "analysis" },
  { key: "validations", label: "실시간 검증", icon: "✅", kind: "validation" },
  { key: "discoveries", label: "종목 발견", icon: "🧭", kind: "discovery" },
];

function MetricRow({ label, icon, metric }: { label: string; icon: string; metric: UsageMetric }) {
  const unlimited = metric.limit < 0;
  const pct =
    unlimited || metric.limit === 0 ? 0 : Math.min(100, (metric.used / metric.limit) * 100);
  const barColor = pct >= 90 ? "bg-red-500" : pct >= 70 ? "bg-amber-500" : "bg-sky-500";

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-sm">
        <span>
          {icon} {label}
        </span>
        <span className="flex items-center gap-1.5 text-xs text-muted-foreground tabular-nums">
          {unlimited ? `${metric.used} (무제한)` : `${metric.used} / ${metric.limit}`}
          <span aria-hidden="true">›</span>
        </span>
      </div>
      {!unlimited && (
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
          <div className={`h-full ${barColor} transition-all`} style={{ width: `${pct}%` }} />
        </div>
      )}
    </div>
  );
}

export function UsageCard() {
  const { data, isLoading, isError } = useUsage();

  // 조용히 숨김 — 대시보드 다른 영역에 영향 없게
  if (isError || (!isLoading && !data)) return null;

  const plan = data?.plan ?? "free";
  const planLabel = PLAN_LABEL[plan] ?? plan;

  let resetLabel = "";
  if (data?.reset_at) {
    const d = new Date(data.reset_at);
    if (!Number.isNaN(d.getTime())) {
      resetLabel = `${d.getMonth() + 1}월 ${d.getDate()}일 초기화`;
    }
  }

  return (
    <Card>
      <CardContent className="space-y-3 p-4">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold">🔥 이번 달 AI 사용량</h2>
          <span className="text-xs text-muted-foreground">
            {data?.month}
            {" · "}
            {planLabel}
          </span>
        </div>

        {isLoading || !data ? (
          <div className="space-y-3">
            {METRICS.map((m) => (
              <div key={m.key} className="h-6 animate-pulse rounded bg-muted" />
            ))}
          </div>
        ) : (
          <div className="space-y-2">
            {METRICS.map((m) => (
              <Link
                key={m.key}
                href={`/history?kind=${m.kind}`}
                className="block rounded-lg border p-2.5 hover:bg-muted/50 transition"
                title={`${m.label} 이력 보기`}
              >
                <MetricRow label={m.label} icon={m.icon} metric={data.usage[m.key]} />
              </Link>
            ))}
          </div>
        )}

        <div className="flex items-center justify-between pt-1">
          {resetLabel && <span className="text-xs text-muted-foreground">{resetLabel}</span>}
          {plan === "free" && (
            <Link href="/pricing" className="text-xs font-medium text-primary hover:underline">
              Pro로 업그레이드 →
            </Link>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
