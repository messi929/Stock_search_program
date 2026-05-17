"use client";

import Link from "next/link";

import { Disclaimer } from "@/components/legal/Disclaimer";
import { SmartListGrid } from "@/components/screener/SmartListGrid";
import { Button } from "@/components/ui/button";

export default function ScreenerPage() {
  return (
    <div className="space-y-6 max-w-5xl">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">📊 스마트 리스트</h1>
          <p className="text-sm text-muted-foreground mt-1">
            v7.5 카테고리 기반 — 그룹별 관찰 시그널, 가치, 모멘텀, 수급 종목 탐색
          </p>
        </div>
        <Link href="/screener/custom" className="shrink-0">
          <Button variant="outline" size="sm">🔧 커스텀 스크리너</Button>
        </Link>
      </header>

      <SmartListGrid />

      <Disclaimer />
    </div>
  );
}
