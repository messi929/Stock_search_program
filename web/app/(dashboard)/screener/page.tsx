"use client";

import { Disclaimer } from "@/components/legal/Disclaimer";
import { SmartListGrid } from "@/components/screener/SmartListGrid";

export default function ScreenerPage() {
  return (
    <div className="space-y-6 max-w-5xl">
      <header>
        <h1 className="text-2xl font-bold">📊 스마트 리스트</h1>
        <p className="text-sm text-muted-foreground mt-1">
          v7.5 카테고리 기반 — 그룹별 관찰 시그널, 가치, 모멘텀, 수급 종목 탐색
        </p>
      </header>

      <SmartListGrid />

      <Disclaimer />
    </div>
  );
}
