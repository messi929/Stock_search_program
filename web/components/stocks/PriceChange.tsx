import { cn } from "@/lib/utils";

/**
 * 등락률 표시 — 한국식 상승 빨강/하락 파랑.
 * 색만으로 구분하지 않도록 화살표를 함께 쓴다.
 */
export function PriceChange({
  pct,
  className,
  digits = 2,
}: {
  pct: number | null | undefined;
  className?: string;
  digits?: number;
}) {
  if (pct == null || !Number.isFinite(pct)) return null;
  const tone = pct > 0 ? "text-up" : pct < 0 ? "text-down" : "text-muted-foreground";
  const arrow = pct > 0 ? "▲" : pct < 0 ? "▼" : "";
  return (
    <span className={cn("font-medium tabular-nums whitespace-nowrap", tone, className)}>
      {arrow && (
        <span aria-hidden="true" className="mr-0.5 text-[0.8em]">
          {arrow}
        </span>
      )}
      <span className="sr-only">{pct > 0 ? "상승" : pct < 0 ? "하락" : "보합"} </span>
      {Math.abs(pct).toFixed(digits)}%
    </span>
  );
}
