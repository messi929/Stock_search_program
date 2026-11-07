"use client";

/**
 * 최근 분석한 종목 리스트 — analysisStore.recents(localStorage 영속) 기반.
 * 새로고침·재방문 후에도 유지. 진행 중인 종목은 ⏳ 표시.
 */
import { ChevronRight, LoaderCircle } from "lucide-react";
import Link from "next/link";

import { HorizonIcon } from "@/components/analyze/HorizonIcon";
import { Card, CardContent } from "@/components/ui/card";
import { useAnalysisStore } from "@/store/analysisStore";
import { HORIZON_BY_ID } from "@/types/persona";

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
        <h2 className="font-semibold">최근 분석</h2>
        <div className="flex items-center gap-3">
          <Link href="/history" className="text-xs text-muted-foreground hover:text-foreground">
            전체 이력
          </Link>
          <Link href="/analyze" className="text-xs text-muted-foreground hover:text-foreground">
            새 분석
          </Link>
        </div>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {recents.map((r) => {
          // 시계 기반 분석이면 시계 메타로 라벨/아이콘. 페르소나 시대 옛 항목은 중립 라벨.
          const horizon = r.horizon ? HORIZON_BY_ID[r.horizon] : undefined;
          const label = horizon?.name ?? "분석";
          const isRunning = runs[r.ticker]?.running;
          return (
            <Link
              key={r.ticker}
              href={`/analyze/${r.ticker}`}
              className="block focus:outline-none"
            >
              <Card className="transition hover:ring-primary/40">
                <CardContent className="p-3 flex items-center gap-3">
                  {r.horizon && <HorizonIcon id={r.horizon} className="size-5 shrink-0 text-primary" />}
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1.5 min-w-0">
                      {r.name ? (
                        <span className="font-medium truncate">{r.name}</span>
                      ) : null}
                      <span className="font-mono text-xs text-muted-foreground shrink-0">
                        {r.ticker}
                      </span>
                      {isRunning && (
                        <span className="text-[11px] text-caution inline-flex items-center gap-0.5 shrink-0">
                          <LoaderCircle aria-hidden="true" className="size-3 animate-spin" />
                          진행중
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-muted-foreground truncate">
                      {label} · {timeAgo(r.at)}
                    </p>
                  </div>
                  <ChevronRight aria-hidden="true" className="size-4 shrink-0 text-muted-foreground" />
                </CardContent>
              </Card>
            </Link>
          );
        })}
      </div>
    </section>
  );
}
