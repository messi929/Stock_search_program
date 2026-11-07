"use client";

/**
 * 분석 진행중 전역 표시기 — 대시보드 레이아웃 상단 고정.
 *
 * analysisStore는 SSE를 컴포넌트 수명과 분리해 백그라운드로 돌린다(화면 전환해도
 * 계속). 이 바는 진행 중(running)인 분석이 있으면 어느 화면에서든 노출하고,
 * 클릭하면 해당 분석 페이지로 데려간다.
 */
import Link from "next/link";

import { useAnalysisStore } from "@/store/analysisStore";

export function AnalysisProgressBar() {
  const runs = useAnalysisStore((s) => s.runs);
  const running = Object.values(runs).filter((r) => r.running);

  if (running.length === 0) return null;
  const first = running[0];

  return (
    <Link
      href={`/analyze/${first.ticker}`}
      className="flex items-center justify-center gap-2 rounded-lg border border-caution/30 bg-caution/10 text-caution dark:text-caution px-4 py-2.5 mb-4 text-sm hover:bg-caution/15 transition"
    >
      <span className="inline-block animate-spin">⏳</span>
      <span className="font-medium font-mono">{first.ticker}</span>
      <span>분석 진행 중…</span>
      {running.length > 1 && (
        <span className="text-xs text-muted-foreground">외 {running.length - 1}건</span>
      )}
      <span className="text-xs underline">보기 →</span>
    </Link>
  );
}
