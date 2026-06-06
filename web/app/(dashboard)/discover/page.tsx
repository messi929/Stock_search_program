"use client";

import { Disclaimer } from "@/components/legal/Disclaimer";
import { DiscoverView } from "@/components/discover/DiscoverView";

export default function DiscoverPage() {
  return (
    <div className="space-y-6 max-w-3xl">
      <header>
        <h1 className="text-2xl font-bold">🧭 종목 발견</h1>
        <p className="text-sm text-muted-foreground mt-1">
          시장·조건을 골라 AI가 관찰 가치 종목을 찾아드립니다. 마음에 들면 관심 종목에
          추가하거나 바로 상세 분석하세요.
        </p>
      </header>

      <DiscoverView />

      <Disclaimer />
    </div>
  );
}
