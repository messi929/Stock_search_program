import type { PublicCandle } from "@/lib/stocks";
import { cn } from "@/lib/utils";

/** 표·목록 안에 넣는 작은 추세선. 기간 수익 방향에 따라 한국식 색을 쓴다. */
export function MiniSparkline({
  candles,
  days = 30,
  className,
}: {
  candles: PublicCandle[] | undefined;
  days?: number;
  className?: string;
}) {
  const closes = (candles ?? []).slice(-days).map((c) => c.close);
  if (closes.length < 2) return <span className={cn("inline-block h-7 w-16", className)} />;

  const w = 64;
  const h = 28;
  const pad = 3;
  const min = Math.min(...closes);
  const range = Math.max(...closes) - min || 1;
  const points = closes.map((c, i) => [
    (i / (closes.length - 1)) * w,
    h - pad - ((c - min) / range) * (h - pad * 2),
  ]);
  const first = closes[0];
  const last = closes[closes.length - 1];
  const pct = ((last - first) / first) * 100;
  const line = points.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const [endX, endY] = points[points.length - 1];
  const label = `최근 ${closes.length}거래일 ${pct >= 0 ? "+" : ""}${pct.toFixed(1)}%`;

  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      role="img"
      aria-label={label}
      className={cn("h-7 w-16 shrink-0 overflow-visible", pct >= 0 ? "text-up" : "text-down", className)}
    >
      <title>{label}</title>
      <polyline
        points={line}
        fill="none"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx={endX} cy={endY} r="2.25" fill="currentColor" />
    </svg>
  );
}
