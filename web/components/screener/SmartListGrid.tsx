"use client";

import {
  Activity,
  Award,
  Building2,
  ChevronRight,
  Coins,
  Flame,
  Gem,
  Layers,
  LineChart,
  PackagePlus,
  Rocket,
  Shapes,
  Sprout,
  Star,
  Tags,
  TrendingDown,
  TrendingUp,
  Trophy,
  Undo2,
  Wallet,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";

import { Card, CardContent } from "@/components/ui/card";
import { useSmartLists } from "@/hooks/useSmartLists";
import { toSafeCategory } from "@/lib/legal-labels";
import type { SmartListCategory } from "@/types/api";

const CATEGORY_ICONS: Record<string, LucideIcon> = {
  surge: Flame,
  turnaround: Undo2,
  dividend: Wallet,
  growth: Sprout,
  value: Gem,
  recommend: Trophy,
  momentum: TrendingUp,
  quality: Award,
  etf: Layers,
  watchlist: Star,
  bluechip: Building2,
  smallcap: Shapes,
  theme: Tags,
  oversold: TrendingDown,
  breakout: Rocket,
  accumulation: PackagePlus,
  foreign_inst: Coins,
};

const GROUPS: Record<string, { label: string; desc: string; icon: LucideIcon; tint: string }> = {
  strategy: { label: "투자 전략별", desc: "여러 지표를 묶은 대표 전략", icon: LineChart, tint: "bg-tint-1/15 text-tint-1" },
  market: { label: "시장·종목 유형별", desc: "회사 규모나 상품 유형으로 나눈 목록", icon: Building2, tint: "bg-tint-3/15 text-tint-3" },
  signal: { label: "주가·수급 신호", desc: "차트와 큰손의 매매 흐름으로 고른 종목", icon: Activity, tint: "bg-tint-2/15 text-tint-2" },
  etc: { label: "기타", desc: "", icon: Shapes, tint: "bg-muted text-muted-foreground" },
};

function groupBy(items: SmartListCategory[]): Record<string, SmartListCategory[]> {
  const out: Record<string, SmartListCategory[]> = {};
  for (const it of items) {
    const g = it.group || "etc";
    (out[g] ??= []).push(it);
  }
  return out;
}

export function SmartListGrid() {
  const { data, isLoading, isError } = useSmartLists();

  if (isLoading) {
    return <p className="text-sm text-muted-foreground">목록을 불러오는 중...</p>;
  }
  if (isError || !data) {
    return <p className="text-sm text-muted-foreground">목록을 불러오지 못했어요. 잠시 후 다시 시도해 주세요.</p>;
  }

  // LEGAL: 권유성 카테고리 라벨을 Axis 정책에 맞게 변환 후 표시
  const safeCategories = data.categories.map(toSafeCategory);
  const groups = groupBy(safeCategories);
  const order = ["strategy", "market", "signal", "etc"];

  return (
    <div className="space-y-6">
      {order
        .filter((g) => groups[g])
        .map((g) => {
          const meta = GROUPS[g];
          const Icon = meta.icon;
          return (
          <section key={g}>
            <div className="mb-3 flex flex-wrap items-center gap-x-2">
              <h2 className="flex items-center gap-1.5 font-semibold">
                {meta.label}
              </h2>
              <p className="text-xs text-muted-foreground">{meta.desc}</p>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {groups[g].map((c) => {
                const CatIcon = CATEGORY_ICONS[c.id] ?? Icon;
                return (
                <Link
                  key={c.id}
                  href={`/screener/${c.id}`}
                  className="block rounded-xl focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <Card className="h-full transition hover:ring-primary/40">
                    <CardContent className="p-4 space-y-2">
                      <span className={`flex size-10 items-center justify-center rounded-xl ${meta.tint}`}>
                        <CatIcon aria-hidden="true" className="size-5" />
                      </span>
                      <div className="flex items-center justify-between">
                        <h3 className="font-semibold">{c.name}</h3>
                        {!c.available_to_free && (
                          <span className="text-xs px-1.5 py-0.5 rounded bg-accent text-accent-foreground font-medium">
                            Pro
                          </span>
                        )}
                      </div>
                      <div className="flex items-end justify-between gap-2">
                        <p className="text-xs leading-relaxed text-muted-foreground line-clamp-2">
                          {c.desc || c.id}
                        </p>
                        <ChevronRight aria-hidden="true" className="size-4 shrink-0 text-muted-foreground" />
                      </div>
                    </CardContent>
                  </Card>
                </Link>
                );
              })}
            </div>
          </section>
          );
        })}
    </div>
  );
}
