"use client";

/**
 * 종목 한눈에 보기 — 공개 데이터만 써서 AI 분석 전에도 바로 보여준다(비용 0).
 */
import { Card, CardContent } from "@/components/ui/card";
import { Term } from "@/components/ui/term";
import { Range52Week, RsiMeter } from "@/components/viz/Meters";
import { usePublicStock } from "@/hooks/usePublicStock";
import type { GlossaryId } from "@/lib/glossary";

function Tile({ id, value }: { id: GlossaryId; value: string }) {
  return (
    <div className="rounded-lg bg-muted px-3 py-2.5">
      <p className="text-xs text-muted-foreground">
        <Term id={id} />
      </p>
      <p className="mt-0.5 text-lg font-bold tabular-nums">{value}</p>
    </div>
  );
}

export function StockSnapshot({ ticker, isKR }: { ticker: string; isKR: boolean }) {
  const { data, isLoading, isError } = usePublicStock(ticker);

  if (isError) return null;
  if (isLoading || !data) {
    return <div className="h-48 animate-pulse rounded-xl bg-muted" aria-label="종목 지표 불러오는 중" />;
  }

  const show = (v: number, suffix: string) => (v ? `${v.toFixed(v >= 100 ? 0 : 2)}${suffix}` : "—");

  return (
    <Card className="overflow-visible">
      <CardContent className="space-y-5 p-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-semibold">한눈에 보기</h2>
          {data.sector && (
            <span className="rounded-md bg-accent px-2 py-0.5 text-xs font-medium text-accent-foreground">
              {data.sector}
            </span>
          )}
        </div>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <Tile id="per" value={show(data.per, "배")} />
          <Tile id="pbr" value={show(data.pbr, "배")} />
          <Tile id="roe" value={show(data.roe, "%")} />
          <Tile id="div_yield" value={show(data.div_yield, "%")} />
        </div>
        <div className="grid gap-5 md:grid-cols-2 md:gap-8">
          <Range52Week
            close={data.close}
            vsHigh={data.vs_high_52w}
            vsLow={data.vs_low_52w}
            unit={isKR ? "원" : "달러"}
            label="최근 1년 가격대"
          />
          <RsiMeter value={data.rsi} label={<Term id="rsi">최근 힘 (RSI)</Term>} />
        </div>
      </CardContent>
    </Card>
  );
}
