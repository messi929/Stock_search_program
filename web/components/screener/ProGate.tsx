"use client";

/**
 * Pro 전용 카테고리 접근 시 노출되는 안내 카드.
 * 사용자가 free 플랜인데 available_to_free=false 인 카테고리에 진입하면
 * 결과는 숨기고 업그레이드 CTA만 표시.
 */
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

export function ProGate({ categoryName }: { categoryName: string }) {
  return (
    <Card className="border-amber-500/40 bg-amber-500/5">
      <CardContent className="p-8 space-y-4 text-center">
        <div className="text-4xl">🔒</div>
        <h2 className="text-lg font-semibold">{categoryName}는 Pro 전용입니다</h2>
        <p className="text-sm text-muted-foreground">
          Pro 플랜은 무제한 분석·검증과 모든 스마트 리스트 카테고리를 제공합니다.
        </p>
        <div className="flex justify-center gap-2 pt-2">
          <Link href="/pricing">
            <Button>플랜 보기</Button>
          </Link>
          <Link href="/screener">
            <Button variant="outline">다른 카테고리</Button>
          </Link>
        </div>
      </CardContent>
    </Card>
  );
}
