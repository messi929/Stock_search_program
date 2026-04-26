"use client";

import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { useUpdateWatchlist, useWatchlist } from "@/hooks/useWatchlist";

/**
 * 관심 종목 추가 — v7.5 /api/user/watchlist 사용 (단순 ticker 배열).
 *
 * Race: POST가 전체 목록 덮어쓰기라 다른 탭과 충돌 가능성 있음 (MVP 수용).
 * 클릭 시점의 현재 목록을 읽어 Set으로 dedupe 후 전송.
 */
export function AddToWatchlistButton({
  ticker,
  size = "sm",
}: {
  ticker: string;
  size?: "default" | "sm" | "lg";
}) {
  const { data, isLoading } = useWatchlist();
  const update = useUpdateWatchlist();

  const current = data?.watchlist ?? [];
  const already = current.includes(ticker);

  const handle = async () => {
    if (already) {
      toast.info("이미 관심 종목에 있습니다.");
      return;
    }
    const merged = Array.from(new Set([...current, ticker]));
    try {
      await update.mutateAsync(merged);
      toast.success("관심 종목에 추가됨");
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
      disabled={isLoading || update.isPending}
      size={size}
      variant="outline"
    >
      {update.isPending ? "추가 중..." : "⭐ 관심 종목 추가"}
    </Button>
  );
}
