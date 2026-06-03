"use client";

import Link from "next/link";
import { useState } from "react";

import { Card, CardContent } from "@/components/ui/card";
import { useHistory, useUsage } from "@/hooks/useUsage";
import type { HistoryItem, HistoryKind, UsageMetric } from "@/types/api";
import { PERSONA_BY_ID, type PersonaId } from "@/types/persona";

const PLAN_LABEL: Record<string, string> = {
  free: "무료",
  pro: "Pro",
  premium: "Premium",
};

type MetricKey = "analyses" | "validations" | "discoveries";

const METRICS: { key: MetricKey; label: string; icon: string; kind: HistoryKind }[] = [
  { key: "analyses", label: "종목 분석", icon: "🔍", kind: "analysis" },
  { key: "validations", label: "실시간 검증", icon: "✅", kind: "validation" },
  { key: "discoveries", label: "종목 발견", icon: "🧭", kind: "discovery" },
];

function fmtAt(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString("ko-KR", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function MetricRow({
  label,
  icon,
  metric,
  open,
}: {
  label: string;
  icon: string;
  metric: UsageMetric;
  open: boolean;
}) {
  const unlimited = metric.limit < 0;
  const pct =
    unlimited || metric.limit === 0 ? 0 : Math.min(100, (metric.used / metric.limit) * 100);
  const barColor = pct >= 90 ? "bg-red-500" : pct >= 70 ? "bg-amber-500" : "bg-sky-500";

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-sm">
        <span className="flex items-center gap-1">
          <span
            className={`text-muted-foreground text-xs transition-transform ${open ? "rotate-90" : ""}`}
            aria-hidden="true"
          >
            ▸
          </span>
          {icon} {label}
        </span>
        <span className="text-xs text-muted-foreground tabular-nums">
          {unlimited ? `${metric.used} (무제한)` : `${metric.used} / ${metric.limit}`}
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

function HistoryRow({ it }: { it: HistoryItem }) {
  const at = fmtAt(it.at);
  const persona = it.persona ? PERSONA_BY_ID[it.persona as PersonaId]?.name : "";

  // 발견(discovery)은 종목이 아닌 쿼리 기준 — 링크 없이 텍스트.
  if (it.kind === "discovery") {
    return (
      <div className="flex items-center justify-between gap-2 text-xs py-1">
        <span className="truncate text-muted-foreground">🧭 “{it.query || "발견"}”</span>
        <span className="text-muted-foreground shrink-0 tabular-nums">{at}</span>
      </div>
    );
  }

  return (
    <Link
      href={`/analyze/${it.ticker}`}
      className="flex items-center justify-between gap-2 text-xs py-1 hover:text-foreground"
    >
      <span className="truncate">
        <span className="font-mono font-medium">{it.ticker}</span>
        {persona ? <span className="text-muted-foreground"> · {persona}</span> : null}
      </span>
      <span className="text-muted-foreground shrink-0 tabular-nums">{at}</span>
    </Link>
  );
}

export function UsageCard() {
  const { data, isLoading, isError } = useUsage();
  const { data: history } = useHistory();
  const [expanded, setExpanded] = useState<MetricKey | null>(null);

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
            {METRICS.map((m) => {
              const isOpen = expanded === m.key;
              const items = (history?.items ?? []).filter((it) => it.kind === m.kind);
              return (
                <div key={m.key} className="rounded-lg border">
                  <button
                    type="button"
                    onClick={() => setExpanded(isOpen ? null : m.key)}
                    aria-expanded={isOpen}
                    className="w-full text-left p-2.5 hover:bg-muted/50 transition rounded-lg"
                  >
                    <MetricRow label={m.label} icon={m.icon} metric={data.usage[m.key]} open={isOpen} />
                  </button>
                  {isOpen && (
                    <div className="border-t px-3 py-2">
                      {items.length === 0 ? (
                        <p className="text-xs text-muted-foreground py-1.5 leading-relaxed">
                          {data.usage[m.key].used > 0 ? (
                            <>
                              이 기능 도입(6/3) 이전 분석은 내역에 표시되지 않아요.
                              <br />
                              이후 분석부터 종목·일자가 기록됩니다.
                            </>
                          ) : (
                            "아직 분석 내역이 없습니다."
                          )}
                        </p>
                      ) : (
                        <div className="divide-y divide-border/50">
                          {items.map((it, i) => (
                            <HistoryRow key={`${it.ticker}-${it.at}-${i}`} it={it} />
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
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
