"use client";

import Link from "next/link";
import { useQueries } from "@tanstack/react-query";

import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { usePersonas } from "@/hooks/usePersonas";
import { useWatchlist } from "@/hooks/useWatchlist";
import { apiCall } from "@/lib/api";
import type { StockSearchResponse } from "@/types/api";

export function WatchlistPreview() {
  // user_plan은 personas API에 포함됨 — pro/premium은 30개, free는 5개.
  const { data: personas } = usePersonas();
  const isPaid =
    personas?.user_plan === "pro" || personas?.user_plan === "premium";
  const limit = isPaid ? 30 : 5;
  const { data, isLoading, isError } = useWatchlist();
  const tickers = data?.watchlist ?? [];
  const visibleTickers = tickers.slice(0, limit);

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
              return (
                <li
                  key={t}
                  className="flex items-center justify-between p-2 rounded-md hover:bg-muted text-sm gap-2"
                >
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
                  <Link
                    href={`/analyze/${t}`}
                    className="text-xs text-amber-500 hover:underline shrink-0"
                  >
                    분석 →
                  </Link>
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
