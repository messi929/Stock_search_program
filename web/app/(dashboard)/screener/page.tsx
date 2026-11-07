"use client";

import { SlidersHorizontal } from "lucide-react";
import Link from "next/link";

import { Disclaimer } from "@/components/legal/Disclaimer";
import { SmartListGrid } from "@/components/screener/SmartListGrid";
import { Button } from "@/components/ui/button";

export default function ScreenerPage() {
  return (
    <div className="space-y-6">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">스마트 리스트</h1>
          <p className="text-sm text-muted-foreground mt-1">
            주제별로 미리 골라둔 종목 목록이에요. 관심 가는 주제를 눌러보세요.
          </p>
        </div>
        <Link href="/screener/custom" className="shrink-0">
          <Button variant="outline" size="sm">
            <SlidersHorizontal aria-hidden="true" />
            조건 직접 설정
          </Button>
        </Link>
      </header>

      <SmartListGrid />

      <Disclaimer />
    </div>
  );
}
