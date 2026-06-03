"use client";

/**
 * 최근 분석한 종목 리스트 — analysisStore.recents(localStorage 영속) 기반.
 * 새로고침·재방문 후에도 유지. 진행 중인 종목은 ⏳ 표시.
 */
import Link from "next/link";

import { Card, CardContent } from "@/components/ui/card";
import { useAnalysisStore } from "@/store/analysisStore";
import { PERSONA_BY_ID } from "@/types/persona";

function timeAgo(at: number): string {
  const s = Math.floor((Date.now() - at) / 1000);
  if (s < 60) return "방금";
  if (s < 3600) return `${Math.floor(s / 60)}분 전`;
  if (s < 86400) return `${Math.floor(s / 3600)}시간 전`;
  return `${Math.floor(s / 86400)}일 전`;
}

export function RecentAnalyses() {
  const recents = useAnalysisStore((s) => s.recents);
  const runs = useAnalysisStore((s) => s.runs);

  if (recents.length === 0) return null;

  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold">🕘 최근 분석</h2>
        <div className="flex items-center gap-3">
          <Link href="/history" className="text-xs text-muted-foreground hover:text-foreground">
            전체 이력
          </Link>
          <Link href="/analyze" className="text-xs text-muted-foreground hover:text-foreground">
            새 분석 →
          </Link>
        </div>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {recents.map((r) => {
          const persona = PERSONA_BY_ID[r.persona];
          const isRunning = runs[r.ticker]?.running;
          return (
            <Link
              key={r.ticker}
              href={`/analyze/${r.ticker}`}
              className="block focus:outline-none"
            >
              <Card className="hover:bg-muted transition">
                <CardContent className="p-3 flex items-center gap-3">
                  <span className="text-lg shrink-0">{persona?.icon ?? "📊"}</span>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1.5 min-w-0">
                      {r.name ? (
                        <span className="font-medium truncate">{r.name}</span>
                      ) : null}
                      <span className="font-mono text-xs text-muted-foreground shrink-0">
                        {r.ticker}
                      </span>
                      {isRunning && (
                        <span className="text-[10px] text-amber-600 inline-flex items-center gap-0.5 shrink-0">
                          <span className="inline-block animate-spin">⏳</span>진행중
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-muted-foreground truncate">
                      {persona?.name ?? r.persona} · {timeAgo(r.at)}
                    </p>
                  </div>
                  <span className="text-muted-foreground text-sm shrink-0">→</span>
                </CardContent>
              </Card>
            </Link>
          );
        })}
      </div>
    </section>
  );
}
