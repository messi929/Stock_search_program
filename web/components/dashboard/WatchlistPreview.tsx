"use client";

import { Plus, Star, X } from "lucide-react";
import Link from "next/link";
import { useQueries } from "@tanstack/react-query";
import { toast } from "sonner";

import { PriceChange } from "@/components/stocks/PriceChange";
import { StockAvatar } from "@/components/stocks/StockAvatar";
import { MiniSparkline } from "@/components/viz/MiniSparkline";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useKisLivePrices } from "@/hooks/useKisLivePrices";
import { usePublicStocks } from "@/hooks/usePublicStock";
import { useUpdateWatchlist, useWatchlist } from "@/hooks/useWatchlist";
import {
  entryProximity,
  useWatchlistEntryPoints,
} from "@/hooks/useWatchlistEntryPoints";
import { apiCall } from "@/lib/api";
import type { StockSearchResponse } from "@/types/api";

export function WatchlistPreview() {
  // 관심종목은 티어 무관(등록은 AI 비용 0). 대시보드 미리보기는 티어 상관없이 동일 캡.
  const limit = 30;
  const { data, isLoading, isError } = useWatchlist();
  const update = useUpdateWatchlist();
  const tickers = data?.watchlist ?? [];
  const visibleTickers = tickers.slice(0, limit);

  const handleRemove = (ticker: string, name?: string | null) => {
    const label = name ? `${name} (${ticker})` : ticker;
    if (!window.confirm(`'${label}'을(를) 관심 종목에서 제거할까요?`)) return;
    const next = tickers.filter((t) => t !== ticker);
    update.mutate(next, {
      onSuccess: () => toast.success(`'${label}' 제거됨`),
      onError: (err: unknown) => {
        const msg = err instanceof Error ? err.message : "제거 실패";
        toast.error(msg);
      },
    });
  };

  // 티커별 종목명 병렬 조회(react-query 캐시 공유 — staleTime 1h, 종목명은 거의 안 변함).
  const nameQueries = useQueries({
    queries: visibleTickers.map((t) => ({
      queryKey: ["stock-search", t, 1],
      queryFn: () =>
        apiCall<StockSearchResponse>(
          `/api/all-stocks?q=${encodeURIComponent(t)}&limit=1`,
        ),
      enabled: t.length > 0,
      staleTime: 60 * 60_000,
    })),
  });
  const nameByTicker: Record<string, string | null> = {};
  const closeByTicker: Record<string, number | null> = {};
  visibleTickers.forEach((t, i) => {
    const found = nameQueries[i]?.data?.stocks?.find(
      (s) => s.ticker.toUpperCase() === t.toUpperCase(),
    );
    nameByTicker[t] = found?.name ?? null;
    closeByTicker[t] = found?.close || null;
  });

  // 미니 차트와 전일 등락 — 공개 API라 AI 비용이 없다.
  const details = usePublicStocks(visibleTickers);

  // KIS WebSocket 실시간 가격 (KR 종목만 자동 활성)
  const livePrices = useKisLivePrices(visibleTickers);

  // 저장된 진입선 — 진입선 근접/도달 모니터링용
  const { data: entryData } = useWatchlistEntryPoints(visibleTickers.length > 0);
  const entryMap = entryData?.items ?? {};

  return (
    <Card>
      <CardContent className="p-4 space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="flex items-center gap-1.5 font-semibold">
            <Star aria-hidden="true" className="size-[18px] text-primary" />
            관심 종목
          </h2>
          <span className="text-xs text-muted-foreground">
            {tickers.length} / {limit}
          </span>
        </div>

        {isLoading ? (
          <p className="text-sm text-muted-foreground">불러오는 중...</p>
        ) : isError ? (
          <p className="text-sm text-muted-foreground">
            관심 종목을 불러오지 못했어요. 잠시 후 다시 시도해 주세요.
          </p>
        ) : tickers.length === 0 ? (
          <div className="py-4 text-center space-y-3">
            <p className="text-sm text-muted-foreground">
              아직 관심 종목이 없어요. 추가해 두면 여기서 가격을 바로 볼 수 있어요.
            </p>
            <Link
              href="/watchlist/add"
              className={buttonVariants({ variant: "outline", size: "sm" })}
            >
              <Plus aria-hidden="true" />
              관심 종목 추가
            </Link>
          </div>
        ) : (
          <ul className="-mx-2 space-y-0.5">
            {visibleTickers.map((t, i) => {
              const name = nameByTicker[t];
              const detail = details[i]?.data;
              const live = livePrices[t];
              const hasLive = live?.price != null;
              const prox = entryProximity(entryMap[t]?.entry_points, live?.price);
              return (
                <li
                  key={t}
                  className="p-2 rounded-md hover:bg-muted text-sm space-y-1"
                >
                  <div className="flex items-center justify-between gap-2">
                  <Link href={`/analyze/${t}`} className="flex min-w-0 flex-1 items-center gap-2.5">
                    <StockAvatar ticker={t} name={name} />
                    <span className="min-w-0">
                      <span className="block truncate font-semibold">{name ?? t}</span>
                      <span className="block text-xs text-muted-foreground tabular-nums">{t}</span>
                    </span>
                  </Link>
                  <MiniSparkline candles={detail?.chart} className="hidden sm:block" />
                  <div className="flex items-center gap-1 shrink-0">
                    {!hasLive && closeByTicker[t] != null && (
                      <span className="flex flex-col items-end text-sm tabular-nums" title="최근 수집 시점의 종가">
                        {closeByTicker[t]!.toLocaleString("ko-KR")}
                        <PriceChange pct={detail?.change_pct} className="text-xs" />
                      </span>
                    )}
                    {hasLive && (
                      <span
                        className="text-sm tabular-nums"
                        title={`실시간 시세 ${live.execTime ? `· ${live.execTime}` : ""}`}
                      >
                        <span className="text-foreground">
                          {live.price!.toLocaleString("ko-KR")}
                        </span>
                        <PriceChange pct={live.prdyCtrt} className="ml-1.5" />
                      </span>
                    )}
                    <button
                      type="button"
                      onClick={() => handleRemove(t, name)}
                      disabled={update.isPending}
                      aria-label={`${name ?? t} 관심 종목에서 제거`}
                      title="관심 종목에서 제거"
                      className="rounded p-1 text-muted-foreground hover:text-destructive disabled:opacity-50"
                    >
                      <X aria-hidden="true" className="size-3.5" />
                    </button>
                  </div>
                  </div>

                  {/* 진입선 근접/도달 모니터링 */}
                  {prox &&
                    (prox.reached > 0 ? (
                      <div className="text-[11px] font-medium text-up">
                        {prox.reached}차 관찰 구간 도달 (기준가{" "}
                        {prox.tier1.toLocaleString("ko-KR")})
                      </div>
                    ) : prox.distPct != null ? (
                      <div className="text-[11px] text-muted-foreground">
                        1차 관찰 구간 {prox.tier1.toLocaleString("ko-KR")} · 현재가 대비{" "}
                        <span
                          className={
                            prox.distPct > -3
                              ? "text-caution font-medium"
                              : ""
                          }
                        >
                          {prox.distPct.toFixed(1)}%
                        </span>
                      </div>
                    ) : (
                      <div className="text-[11px] text-muted-foreground">
                        관찰 구간 {prox.tier1.toLocaleString("ko-KR")} 저장됨
                      </div>
                    ))}
                </li>
              );
            })}
          </ul>
        )}

        {tickers.length > limit && (
          <p className="text-xs text-muted-foreground">
            … {tickers.length - limit}개 더 있음
          </p>
        )}

        {tickers.length > 0 && (
          <div className="pt-2">
            <Link
              href="/watchlist/add"
              className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
            >
              <Plus aria-hidden="true" className="size-3.5" />
              더 추가
            </Link>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
