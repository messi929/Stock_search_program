"use client";

import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { usePersonas } from "@/hooks/usePersonas";
import { useWatchlist } from "@/hooks/useWatchlist";

export function WatchlistPreview() {
  // user_plan은 personas API에 포함됨 — pro/premium은 30개, free는 5개.
  const { data: personas } = usePersonas();
  const isPaid =
    personas?.user_plan === "pro" || personas?.user_plan === "premium";
  const limit = isPaid ? 30 : 5;
  const { data, isLoading, isError } = useWatchlist();
  const tickers = data?.watchlist ?? [];

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
            {tickers.slice(0, limit).map((t) => (
              <li
                key={t}
                className="flex items-center justify-between p-2 rounded-md hover:bg-muted text-sm"
              >
                <span className="font-mono">{t}</span>
                <Link
                  href={`/analyze/${t}`}
                  className="text-xs text-amber-500 hover:underline"
                >
                  분석 →
                </Link>
              </li>
            ))}
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
