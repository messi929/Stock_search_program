"use client";

import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { useAddToWatchlist, useWatchlist } from "@/hooks/useWatchlist";

/**
 * 관심 종목 추가 — useAddToWatchlist (mutation 시점에 캐시에서 fresh list 읽음).
 * 다중 클릭/멀티 행 race 차단됨.
 */
export function AddToWatchlistButton({
  ticker,
  size = "sm",
}: {
  ticker: string;
  size?: "default" | "sm" | "lg";
}) {
  const { data, isLoading } = useWatchlist();
  const add = useAddToWatchlist();

  const list = data?.watchlist ?? [];
  const already = list.includes(ticker);

  const handle = async () => {
    try {
      const res = await add.mutateAsync(ticker);
      if (res.alreadyPresent) {
        toast.info("이미 관심 종목에 있습니다.");
      } else {
        toast.success("관심 종목에 추가됨");
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "추가 실패";
      toast.error(msg);
    }
  };

  if (already) {
    return (
      <Button type="button" disabled size={size} variant="outline">
        ⭐ 관심 종목 등록됨
      </Button>
    );
  }

  return (
    <Button
      type="button"
      onClick={handle}
      disabled={isLoading || add.isPending}
      size={size}
      variant="outline"
    >
      {add.isPending ? "추가 중..." : "⭐ 관심 종목 추가"}
    </Button>
  );
}
