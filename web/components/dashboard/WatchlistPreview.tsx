"use client";

import Link from "next/link";
import { useQueries } from "@tanstack/react-query";
import { toast } from "sonner";

import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useKisLivePrices } from "@/hooks/useKisLivePrices";
import { usePersonas } from "@/hooks/usePersonas";
import { useUpdateWatchlist, useWatchlist } from "@/hooks/useWatchlist";
import {
  entryProximity,
  useWatchlistEntryPoints,
} from "@/hooks/useWatchlistEntryPoints";
import { apiCall } from "@/lib/api";
import type { StockSearchResponse } from "@/types/api";

export function WatchlistPreview() {
  // user_plan은 personas API에 포함됨 — pro/premium은 30개, free는 5개.
  const { data: personas } = usePersonas();
  const isPaid =
    personas?.user_plan === "pro" || personas?.user_plan === "premium";
  const limit = isPaid ? 30 : 5;
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
  visibleTickers.forEach((t, i) => {
    const found = nameQueries[i]?.data?.stocks?.find(
      (s) => s.ticker.toUpperCase() === t.toUpperCase(),
    );
    nameByTicker[t] = found?.name ?? null;
  });

  // KIS WebSocket 실시간 가격 (KR 종목만 자동 활성)
  const livePrices = useKisLivePrices(visibleTickers);

  // 저장된 진입선 — 진입선 근접/도달 모니터링용
  const { data: entryData } = useWatchlistEntryPoints(visibleTickers.length > 0);
  const entryMap = entryData?.items ?? {};

  return (
    <Card>
      <CardContent className="p-4 space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold">⭐ 관심 종목</h2>
          <span className="text-xs text-muted-foreground">
            {tickers.length} / {limit}
          </span>
        </div>

        {isLoading ? (
          <p className="text-sm text-muted-foreground">불러오는 중...</p>
        ) : isError ? (
          <p className="text-sm text-muted-foreground">
            ⚠️ 관심 종목 조회 실패 (로그인 상태 확인)
          </p>
        ) : tickers.length === 0 ? (
          <div className="py-4 text-center space-y-3">
            <p className="text-sm text-muted-foreground">아직 관심 종목이 없어요.</p>
            <Link
              href="/watchlist/add"
              className={buttonVariants({ variant: "outline", size: "sm" })}
            >
              + 관심 종목 추가
            </Link>
          </div>
        ) : (
          <ul className="space-y-1">
            {visibleTickers.map((t) => {
              const name = nameByTicker[t];
              const live = livePrices[t];
              const hasLive = live?.price != null;
              const prox = entryProximity(entryMap[t]?.entry_points, live?.price);
              return (
                <li
                  key={t}
                  className="p-2 rounded-md hover:bg-muted text-sm space-y-1"
                >
                  <div className="flex items-center justify-between gap-2">
                  <span className="min-w-0 truncate">
                    {name ? (
                      <>
                        <span className="font-medium">{name}</span>
                        <span className="ml-2 font-mono text-xs text-muted-foreground">
                          {t}
                        </span>
                      </>
                    ) : (
                      <span className="font-mono">{t}</span>
                    )}
                  </span>
                  <div className="flex items-center gap-2 shrink-0">
                    {hasLive && (
                      <span
                        className="font-mono text-xs tabular-nums"
                        title={`실시간 시세 ${live.execTime ? `· ${live.execTime}` : ""}`}
                      >
                        <span className="text-foreground">
                          {live.price!.toLocaleString("ko-KR")}
                        </span>
                        {live.prdyCtrt != null && (
                          <span
                            className={`ml-1 ${
                              live.prdyCtrt > 0
                                ? "text-red-500"
                                : live.prdyCtrt < 0
                                  ? "text-blue-500"
                                  : "text-muted-foreground"
                            }`}
                          >
                            {live.prdyCtrt > 0 ? "+" : ""}
                            {live.prdyCtrt.toFixed(2)}%
                          </span>
                        )}
                      </span>
                    )}
                    <Link
                      href={`/analyze/${t}`}
                      className="text-xs text-amber-500 hover:underline px-1.5"
                    >
                      분석 →
                    </Link>
                    <button
                      type="button"
                      onClick={() => handleRemove(t, name)}
                      disabled={update.isPending}
                      aria-label={`${name ?? t} 관심 종목에서 제거`}
                      title="관심 종목에서 제거"
                      className="text-xs text-muted-foreground hover:text-destructive px-1.5 disabled:opacity-50"
                    >
                      ✕
                    </button>
                  </div>
                  </div>

                  {/* 진입선 근접/도달 모니터링 */}
                  {prox &&
                    (prox.reached > 0 ? (
                      <div className="text-[11px] font-medium text-red-500">
                        🎯 {prox.reached}차 진입 구간 도달 (진입선{" "}
                        {prox.tier1.toLocaleString("ko-KR")})
                      </div>
                    ) : prox.distPct != null ? (
                      <div className="text-[11px] text-muted-foreground">
                        1차 진입선 {prox.tier1.toLocaleString("ko-KR")} · 현재가 대비{" "}
                        <span
                          className={
                            prox.distPct > -3
                              ? "text-amber-600 font-medium"
                              : ""
                          }
                        >
                          {prox.distPct.toFixed(1)}%
                        </span>
                      </div>
                    ) : (
                      <div className="text-[11px] text-muted-foreground">
                        진입선 {prox.tier1.toLocaleString("ko-KR")} 저장됨
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
              className="text-xs text-muted-foreground hover:underline"
            >
              + 더 추가
            </Link>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
