"use client";

/**
 * KIS 10호가 + 잔량 막대 시각화.
 * KR 종목만. 백엔드 5초 캐시.
 */
import { Card, CardContent } from "@/components/ui/card";
import { useKisOrderbook } from "@/hooks/useKisPrice";
import { formatKisPrice } from "@/lib/kis";

function isKr(ticker: string): boolean {
  return /^\d{6}$/.test(ticker.trim());
}

function num(v: string | undefined): number {
  if (!v) return 0;
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
}

export function KisOrderbook({ ticker }: { ticker: string }) {
  const { data, isLoading, error } = useKisOrderbook(ticker);

  if (!isKr(ticker)) return null;

  if (isLoading) {
    return (
      <Card>
        <CardContent className="p-4 text-xs text-muted-foreground">호가 불러오는 중…</CardContent>
      </Card>
    );
  }
  if (error || !data) {
    return (
      <Card>
        <CardContent className="p-4 text-xs text-red-500">호가 불러오기 실패</CardContent>
      </Card>
    );
  }

  const ob = data.orderbook;
  const expected = data.expected;

  // 1~10호가 추출 + 잔량 최대값 (막대 비율)
  type Row = { idx: number; price: number; qty: number };
  const asks: Row[] = [];
  const bids: Row[] = [];
  for (let i = 1; i <= 10; i++) {
    asks.push({ idx: i, price: num(ob[`askp${i}`]), qty: num(ob[`askp_rsqn${i}`]) });
    bids.push({ idx: i, price: num(ob[`bidp${i}`]), qty: num(ob[`bidp_rsqn${i}`]) });
  }
  const maxQty = Math.max(...asks.map((r) => r.qty), ...bids.map((r) => r.qty), 1);

  // 매도는 위에서 아래 = 10호가 → 1호가 (높은 가격이 위)
  const asksDesc = [...asks].reverse();
  // 매수는 1호가 → 10호가 (높은 가격이 위)
  const bidsAsc = bids;

  const totalAsk = num(ob.total_askp_rsqn);
  const totalBid = num(ob.total_bidp_rsqn);
  const total = totalAsk + totalBid || 1;
  const askPct = (totalAsk / total) * 100;
  const bidPct = (totalBid / total) * 100;

  return (
    <Card>
      <CardContent className="p-4 space-y-3">
        <div className="flex items-center justify-between">
          <div className="text-sm font-semibold">📋 호가 (10단계)</div>
          {expected?.antc_cnpr && expected.antc_cnpr !== "0" && (
            <div className="text-[10px] text-muted-foreground">
              예상체결 {formatKisPrice(expected.antc_cnpr)}원 ·{" "}
              {expected.antc_cntg_vrss}
            </div>
          )}
        </div>

        {/* 호가표 */}
        <div className="font-mono text-xs">
          {/* 매도 (높은 가격이 위) */}
          {asksDesc.map((r) => (
            <OrderbookRow key={`ask-${r.idx}`} side="ask" row={r} maxQty={maxQty} />
          ))}
          {/* 구분 */}
          <div className="border-t border-border my-1" />
          {/* 매수 (높은 가격이 위) */}
          {bidsAsc.map((r) => (
            <OrderbookRow key={`bid-${r.idx}`} side="bid" row={r} maxQty={maxQty} />
          ))}
        </div>

        {/* 총잔량 비율 막대 */}
        <div className="space-y-1">
          <div className="flex justify-between text-[11px] text-muted-foreground">
            <span>매도 총 {totalAsk.toLocaleString("ko-KR")}</span>
            <span>매수 총 {totalBid.toLocaleString("ko-KR")}</span>
          </div>
          <div className="flex h-2 rounded-full overflow-hidden bg-muted">
            <div className="bg-blue-500" style={{ width: `${askPct}%` }} />
            <div className="bg-red-500" style={{ width: `${bidPct}%` }} />
          </div>
          <div className="text-[10px] text-center text-muted-foreground">
            {bidPct > askPct
              ? `매수 우세 ${(bidPct - askPct).toFixed(1)}%p`
              : askPct > bidPct
                ? `매도 우세 ${(askPct - bidPct).toFixed(1)}%p`
                : "균형"}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function OrderbookRow({
  side,
  row,
  maxQty,
}: {
  side: "ask" | "bid";
  row: { idx: number; price: number; qty: number };
  maxQty: number;
}) {
  const pct = (row.qty / maxQty) * 100;
  // 한국식: 매도=파랑, 매수=빨강
  const isAsk = side === "ask";
  const color = isAsk ? "bg-blue-500/15" : "bg-red-500/15";
  const text = isAsk ? "text-blue-500" : "text-red-500";
  return (
    <div className="grid grid-cols-[1fr_1fr] gap-2 py-0.5">
      {isAsk ? (
        <>
          <div className="relative flex items-center justify-end pr-2">
            <div
              className={`absolute right-0 top-0 bottom-0 ${color}`}
              style={{ width: `${pct}%` }}
            />
            <span className="relative text-muted-foreground">
              {row.qty.toLocaleString("ko-KR")}
            </span>
          </div>
          <div className={`pl-2 ${text} font-semibold`}>{row.price.toLocaleString("ko-KR")}</div>
        </>
      ) : (
        <>
          <div className={`pr-2 text-right ${text} font-semibold`}>
            {row.price.toLocaleString("ko-KR")}
          </div>
          <div className="relative flex items-center pl-2">
            <div
              className={`absolute left-0 top-0 bottom-0 ${color}`}
              style={{ width: `${pct}%` }}
            />
            <span className="relative text-muted-foreground">
              {row.qty.toLocaleString("ko-KR")}
            </span>
          </div>
        </>
      )}
    </div>
  );
}
