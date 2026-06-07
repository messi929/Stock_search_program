/**
 * 공개 종목 페이지용 SVG 스파크라인 — 순수 서버 렌더(JS 불필요, 크롤러 친화).
 *
 * 인터랙티브 차트(lightweight-charts)는 클라이언트 전용이라 로그인 뒤 분석
 * 페이지에서만 제공하고, 공개 페이지는 정적 SVG로 색인 가능하게 한다.
 */
import type { PublicCandle } from "@/lib/stocks";

interface SparklineProps {
  candles: PublicCandle[];
  /** 한국식: 상승 빨강 / 하락 파랑 */
  up: boolean;
  width?: number;
  height?: number;
}

export function Sparkline({ candles, up, width = 640, height = 160 }: SparklineProps) {
  if (!candles || candles.length < 2) {
    return (
      <div
        className="flex items-center justify-center text-xs text-muted-foreground border rounded-md"
        style={{ height }}
      >
        차트 데이터가 아직 없습니다
      </div>
    );
  }

  const closes = candles.map((c) => c.close);
  const min = Math.min(...closes);
  const max = Math.max(...closes);
  const range = max - min || 1;
  const pad = 4;
  const w = width;
  const h = height;

  const points = closes.map((c, i) => {
    const x = (i / (closes.length - 1)) * (w - pad * 2) + pad;
    const y = h - pad - ((c - min) / range) * (h - pad * 2);
    return [x, y] as const;
  });

  const linePath = points
    .map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`)
    .join(" ");
  const areaPath = `${linePath} L${points[points.length - 1][0].toFixed(1)},${h - pad} L${points[0][0].toFixed(1)},${h - pad} Z`;

  const stroke = up ? "#ef4444" : "#3b82f6"; // red-500 / blue-500
  const fillId = up ? "spark-up" : "spark-down";

  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      width="100%"
      height={h}
      role="img"
      aria-label="종가 추이 차트"
      className="overflow-visible"
    >
      <defs>
        <linearGradient id={fillId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={stroke} stopOpacity="0.22" />
          <stop offset="100%" stopColor={stroke} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={areaPath} fill={`url(#${fillId})`} stroke="none" />
      <path d={linePath} fill="none" stroke={stroke} strokeWidth="1.8" strokeLinejoin="round" />
    </svg>
  );
}
