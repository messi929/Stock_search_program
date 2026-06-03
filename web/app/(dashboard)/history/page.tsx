"use client";

/**
 * /history — AI 분석/검증/발견 이력 전용 페이지.
 *
 * AI 사용량 카드 항목 클릭 시 이동(?kind=). 월 최대 100회까지 분석 가능하므로
 * 카드 인라인 확장 대신 전용 화면에서 유형 탭 + 일자별 전체 목록을 본다.
 */
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { Disclaimer } from "@/components/legal/Disclaimer";
import { Card, CardContent } from "@/components/ui/card";
import { useHistory } from "@/hooks/useUsage";
import type { HistoryItem } from "@/types/api";
import { PERSONA_BY_ID, type PersonaId } from "@/types/persona";

type TabKey = "all" | "analysis" | "validation" | "discovery";

const TABS: { key: TabKey; label: string; icon: string }[] = [
  { key: "all", label: "전체", icon: "🗂" },
  { key: "analysis", label: "종목 분석", icon: "🔍" },
  { key: "validation", label: "실시간 검증", icon: "✅" },
  { key: "discovery", label: "종목 발견", icon: "🧭" },
];

function isTab(v: string | null): v is TabKey {
  return v === "all" || v === "analysis" || v === "validation" || v === "discovery";
}

function fmtDateTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString("ko-KR", {
    year: "numeric",
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function HistoryItemRow({ it }: { it: HistoryItem }) {
  const at = fmtDateTime(it.at);
  const persona = it.persona ? PERSONA_BY_ID[it.persona as PersonaId]?.name : "";

  if (it.kind === "discovery") {
    return (
      <div className="flex items-center justify-between gap-3 py-3 px-1">
        <span className="truncate text-sm">🧭 “{it.query || "발견"}”</span>
        <span className="text-xs text-muted-foreground shrink-0 tabular-nums">{at}</span>
      </div>
    );
  }

  const kindIcon = it.kind === "validation" ? "✅" : "🔍";
  return (
    <Link
      href={`/analyze/${it.ticker}`}
      className="flex items-center justify-between gap-3 py-3 px-1 hover:bg-muted/50 rounded-md transition"
    >
      <span className="flex items-center gap-2 min-w-0">
        <span className="shrink-0">{kindIcon}</span>
        {it.name ? <span className="font-medium truncate">{it.name}</span> : null}
        <span className="font-mono text-sm text-muted-foreground shrink-0">{it.ticker}</span>
        {persona ? <span className="text-xs text-muted-foreground truncate hidden sm:inline">· {persona}</span> : null}
      </span>
      <span className="text-xs text-muted-foreground shrink-0 tabular-nums">{at}</span>
    </Link>
  );
}

export default function HistoryPage() {
  return (
    <Suspense fallback={<div className="p-2 text-sm text-muted-foreground">불러오는 중...</div>}>
      <HistoryInner />
    </Suspense>
  );
}

function HistoryInner() {
  const sp = useSearchParams();
  const initial = sp.get("kind");
  const [tab, setTab] = useState<TabKey>(isTab(initial) ? initial : "all");

  const { data, isLoading } = useHistory(100);
  const items = data?.items ?? [];
  const filtered = tab === "all" ? items : items.filter((i) => i.kind === tab);

  return (
    <div className="space-y-5 max-w-3xl">
      <header className="space-y-1">
        <div className="flex items-center gap-2">
          <Link href="/dashboard" className="text-sm text-muted-foreground hover:text-foreground">
            ← 대시보드
          </Link>
        </div>
        <h1 className="text-2xl font-bold">🕘 분석 이력</h1>
        <p className="text-sm text-muted-foreground">
          분석 시점마다 판단이 달라질 수 있어요. 종목과 분석 일자를 함께 확인하세요.
        </p>
      </header>

      {/* 유형 탭 */}
      <div className="flex flex-wrap gap-1.5">
        {TABS.map((t) => {
          const active = tab === t.key;
          const count = t.key === "all" ? items.length : items.filter((i) => i.kind === t.key).length;
          return (
            <button
              key={t.key}
              type="button"
              onClick={() => setTab(t.key)}
              aria-pressed={active}
              className={`px-3 py-1.5 text-sm rounded-md border transition ${
                active
                  ? "bg-foreground text-background border-foreground"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted"
              }`}
            >
              {t.icon} {t.label}
              <span className="ml-1 text-xs opacity-70">{count}</span>
            </button>
          );
        })}
      </div>

      {/* 리스트 */}
      <Card>
        <CardContent className="p-3">
          {isLoading ? (
            <div className="space-y-2 py-2">
              {[0, 1, 2].map((i) => (
                <div key={i} className="h-9 animate-pulse rounded bg-muted" />
              ))}
            </div>
          ) : filtered.length === 0 ? (
            <p className="text-sm text-muted-foreground py-6 text-center leading-relaxed">
              표시할 이력이 없습니다.
              <br />
              <span className="text-xs">
                이 기능 도입(6/3) 이전 분석은 표시되지 않아요. 이후 분석부터 기록됩니다.
              </span>
            </p>
          ) : (
            <div className="divide-y divide-border/60">
              {filtered.map((it, i) => (
                <HistoryItemRow key={`${it.kind}-${it.ticker}-${it.at}-${i}`} it={it} />
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Disclaimer />
    </div>
  );
}
