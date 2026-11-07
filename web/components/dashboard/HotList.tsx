"use client";

import { Flame } from "lucide-react";
import Link from "next/link";

import { PriceChange } from "@/components/stocks/PriceChange";
import { StockAvatar } from "@/components/stocks/StockAvatar";
import { Card, CardContent } from "@/components/ui/card";
import { MiniSparkline } from "@/components/viz/MiniSparkline";
import { usePublicStocks } from "@/hooks/usePublicStock";
import { useScan } from "@/hooks/useSmartLists";

/** 홈의 관찰 목록 미리보기 — 스마트 리스트 '급등 관찰'의 상위 4종목. */
export function HotList() {
  const { data } = useScan("surge", 4, "KR");
  const stocks = (data?.stocks ?? []).slice(0, 4) as Array<{
    ticker: string;
    name?: string;
    change_pct?: number;
  }>;
  const details = usePublicStocks(stocks.map((s) => s.ticker));

  if (stocks.length === 0) return null;

  return (
    <section aria-labelledby="hot-list" className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <h2 id="hot-list" className="flex items-center gap-1.5 font-semibold">
          <Flame aria-hidden="true" className="size-[18px] text-tint-2" />
          거래가 몰리는 종목
        </h2>
        <Link href="/screener/surge" className="text-xs font-medium text-primary hover:underline">
          전체 보기
        </Link>
      </div>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {stocks.map((s, i) => (
          <Link key={s.ticker} href={`/analyze/${s.ticker}`} className="block rounded-xl focus-visible:ring-2 focus-visible:ring-ring">
            <Card className="h-full transition hover:ring-primary/40">
              <CardContent className="space-y-2.5 p-3.5">
                <div className="flex items-center gap-2">
                  <StockAvatar ticker={s.ticker} name={s.name} className="size-8 text-xs" />
                  <span className="min-w-0 truncate font-semibold">{s.name ?? s.ticker}</span>
                </div>
                <div className="flex items-end justify-between gap-2">
                  <PriceChange pct={s.change_pct} />
                  <MiniSparkline candles={details[i]?.data?.chart} />
                </div>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>
    </section>
  );
}
