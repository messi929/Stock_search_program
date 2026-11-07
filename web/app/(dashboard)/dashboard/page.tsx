"use client";

import { ChartCandlestick, Compass, Layers, ListFilter, type LucideIcon } from "lucide-react";
import Link from "next/link";
import { useEffect } from "react";
import { toast } from "sonner";
import { useQueryClient } from "@tanstack/react-query";

import { GettingStarted } from "@/components/dashboard/GettingStarted";
import { HotList } from "@/components/dashboard/HotList";
import { MarketPulse } from "@/components/dashboard/MarketPulse";
import { RecentAnalyses } from "@/components/dashboard/RecentAnalyses";
import { UsageCard } from "@/components/dashboard/UsageCard";
import { WatchlistPreview } from "@/components/dashboard/WatchlistPreview";
import { Disclaimer } from "@/components/legal/Disclaimer";
import { StockSearch } from "@/components/stocks/StockSearch";
import { Card, CardContent } from "@/components/ui/card";
import { useAuth } from "@/hooks/useAuth";
import { useWatchlist } from "@/hooks/useWatchlist";
import { useAnalysisStore } from "@/store/analysisStore";

const SHORTCUTS: { href: string; icon: LucideIcon; tint: string; title: string; desc: string }[] = [
  { href: "/analyze", icon: ChartCandlestick, tint: "bg-tint-1/15 text-tint-1", title: "종목 분석", desc: "AI가 한 종목을 깊이 있게 분석해요" },
  { href: "/discover", icon: Compass, tint: "bg-tint-3/15 text-tint-3", title: "종목 발견", desc: "주제나 조건을 말하면 AI가 찾아드려요" },
  { href: "/screener", icon: ListFilter, tint: "bg-tint-2/15 text-tint-2", title: "스마트 리스트", desc: "주제별로 정리된 종목 목록을 봐요" },
  { href: "/etf", icon: Layers, tint: "bg-tint-5/15 text-tint-5", title: "ETF 탐색", desc: "ETF의 구성 종목과 비중을 확인해요" },
];

export default function DashboardHome() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const { data: watchlist, isLoading: watchlistLoading } = useWatchlist();
  const hasRecents = useAnalysisStore((s) => s.recents.length > 0);
  const isNewUser = !watchlistLoading && (watchlist?.watchlist.length ?? 0) === 0 && !hasRecents;

  // 결제 성공 콜백 (?payment=success) — LS 결제 후 리다이렉트
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (new URLSearchParams(window.location.search).get("payment") !== "success") return;
    toast.success("결제가 완료되었습니다! Pro 기능이 활성화됩니다.", { duration: 6000 });
    // 구독/사용량 캐시 갱신 (웹훅 반영까지 약간 지연될 수 있어 재조회)
    qc.invalidateQueries({ queryKey: ["subscription"] });
    qc.invalidateQueries({ queryKey: ["ai-usage"] });
    window.history.replaceState({}, "", "/dashboard");
  }, [qc]);

  return (
    <div className="space-y-6">
      {/* 첫 화면의 주 행동은 종목 검색 하나로 모은다. */}
      <header className="bg-hero relative rounded-2xl p-6 md:p-8">
        {/* 장식용 상승 곡선 — 데이터가 아니므로 스크린리더에서 숨긴다. */}
        <svg
          aria-hidden="true"
          viewBox="0 0 400 120"
          preserveAspectRatio="none"
          className="pointer-events-none absolute inset-x-0 bottom-0 h-2/3 w-full rounded-b-2xl opacity-20"
        >
          <path d="M0 100 L60 84 L110 92 L170 60 L220 70 L280 38 L330 46 L400 12" fill="none" stroke="#fff" strokeWidth="2" vectorEffect="non-scaling-stroke" />
          <path d="M0 100 L60 84 L110 92 L170 60 L220 70 L280 38 L330 46 L400 12 L400 120 L0 120 Z" fill="#fff" fillOpacity="0.12" />
        </svg>
        <div className="relative space-y-4">
          <div>
            <h1 className="text-2xl font-bold md:text-3xl">
              {user?.displayName ? `${user.displayName}님, ` : ""}어떤 종목이 궁금하세요?
            </h1>
            <p className="mt-1 text-white/80">회사 이름만 입력하면 분석을 시작할 수 있어요.</p>
          </div>
          <div className="text-foreground">
            <StockSearch size="lg" placeholder="예: 삼성전자, 현대차, AAPL" className="max-w-2xl" />
          </div>
        </div>
      </header>

      {isNewUser && <GettingStarted />}

      <HotList />

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="min-w-0 space-y-6">
          <MarketPulse />
          <WatchlistPreview />
          <RecentAnalyses />
        </div>
        <div className="min-w-0 space-y-6">
          <section aria-labelledby="shortcuts" className="space-y-3">
            <h2 id="shortcuts" className="font-semibold">
              바로 가기
            </h2>
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-1">
              {SHORTCUTS.map((s) => {
                const Icon = s.icon;
                return (
                  <Link key={s.href} href={s.href} className="block rounded-xl focus-visible:ring-2 focus-visible:ring-ring">
                    <Card className="h-full transition hover:ring-primary/40">
                      <CardContent className="flex items-start gap-3 p-3.5">
                        <span className={`flex size-9 shrink-0 items-center justify-center rounded-lg ${s.tint}`}>
                          <Icon aria-hidden="true" className="size-5" />
                        </span>
                        <span className="min-w-0">
                          <span className="block font-semibold">{s.title}</span>
                          <span className="mt-0.5 block text-xs leading-relaxed text-muted-foreground">{s.desc}</span>
                        </span>
                      </CardContent>
                    </Card>
                  </Link>
                );
              })}
            </div>
          </section>
          <UsageCard />
        </div>
      </div>

      <Disclaimer />
    </div>
  );
}
