"use client";

/**
 * 오늘 시장 분위기 — 몇 %의 종목이 올랐는지로 시장 전체를 한눈에 보여준다.
 * 지수 숫자보다 체감이 쉬운 등락 비율을 쓴다.
 */
import { Card, CardContent } from "@/components/ui/card";
import { Term } from "@/components/ui/term";
import { useMarketSentiment, type MarketBreadth } from "@/hooks/useMarketSentiment";
import { useStatus } from "@/hooks/useStatus";

function formatRelative(iso: string): string {
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return "";
  const min = Math.floor((Date.now() - t) / 60_000);
  if (min < 1) return "방금 전";
  if (min < 60) return `${min}분 전`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}시간 전`;
  return `${Math.floor(hr / 24)}일 전`;
}

function mood(up: number): string {
  if (up >= 60) return "오른 종목이 많은 날이에요";
  if (up <= 40) return "내린 종목이 많은 날이에요";
  return "오른 종목과 내린 종목이 비슷해요";
}

function Breadth({ name, data }: { name: string; data: MarketBreadth }) {
  const up = Math.round(data.advance_decline * 100);
  const ma = Math.round(data.above_ma20_ratio * 100);
  return (
    <div className="min-w-0 flex-1 space-y-2">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-sm font-medium">{name}</span>
        <span className="text-xs text-muted-foreground tabular-nums">
          {data.total_stocks.toLocaleString("ko-KR")}종목
        </span>
      </div>
      <div className="flex items-baseline gap-1.5">
        <span className="text-3xl font-bold tabular-nums">{up}%</span>
        <span className="text-xs text-muted-foreground">
          <Term id="advance_ratio">상승 종목</Term>
        </span>
      </div>
      <div
        role="img"
        aria-label={`상승 ${up}%, 나머지 ${100 - up}%`}
        className="flex h-1.5 overflow-hidden rounded-full bg-down/25"
      >
        <div className="h-full bg-up" style={{ width: `${up}%` }} />
      </div>
      <p className="text-xs text-muted-foreground">{mood(up)}</p>
      <div className="space-y-1 pt-1">
        <div className="flex justify-between text-xs text-muted-foreground">
          <Term id="above_ma20" />
          <span className="tabular-nums">{ma}%</span>
        </div>
        <div className="h-1.5 overflow-hidden rounded-full bg-muted">
          <div className="h-full rounded-full bg-primary" style={{ width: `${ma}%` }} />
        </div>
      </div>
    </div>
  );
}

export function MarketPulse() {
  const { data, isLoading, isError } = useMarketSentiment();
  const { data: status } = useStatus();

  if (isError) return null;

  return (
    <Card className="overflow-visible">
      <CardContent className="space-y-4 p-5">
        <div className="flex items-center justify-between gap-2">
          <h2 className="font-semibold">오늘의 시장 분위기</h2>
          {status?.last_update ? (
            <span className="text-xs text-muted-foreground" title={status.last_update}>
              {formatRelative(status.last_update)} 업데이트
            </span>
          ) : null}
        </div>
        {isLoading || !data ? (
          <div className="h-24 animate-pulse rounded-lg bg-muted" />
        ) : (
          <div className="flex gap-6">
            <Breadth name="국내" data={data.kr} />
            <div className="w-px bg-border" />
            <Breadth name="미국" data={data.us} />
          </div>
        )}
      </CardContent>
    </Card>
  );
}
