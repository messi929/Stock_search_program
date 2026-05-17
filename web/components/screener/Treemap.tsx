"use client";

/**
 * 스크리너 결과 트리맵 — v7.5 흡수.
 *
 * 의존성 0 (recharts·d3 등 미사용). value 비례 박스 + change_pct 색상.
 *
 * 알고리즘: squarified treemap의 단순화 버전 (slice-and-dice).
 *   - 종목을 value 내림차순 정렬
 *   - flex column wrap + 각 박스 비율 계산 → padding-bottom 트릭 대신 grid-template-rows
 *   - 추후 진짜 squarified 필요 시 d3-hierarchy 도입 가능
 *
 * 클릭 → /analyze/[ticker] (ResultsTable과 일관).
 * LEGAL: 권유성 라벨 미사용 (단순 시각화). Disclaimer는 상위 호출자가 노출.
 */
import Link from "next/link";

import type { StockRow } from "./ResultsTable";

export interface TreemapProps {
  stocks: StockRow[];
  /** 박스 크기 결정 키 — 기본 buy_score, 없으면 market_cap. */
  sizeKey?: string;
  /** 색상 결정 키 — 기본 change_pct. */
  colorKey?: string;
  caption?: string;
}

const MIN_SIZE_RATIO = 0.05; // 너무 작은 박스 가독성 방지

function pickNumber(row: StockRow, key: string, fallback = 0): number {
  const v = row[key];
  return typeof v === "number" && Number.isFinite(v) ? v : fallback;
}

function colorClass(change: number): string {
  if (change >= 5) return "bg-emerald-500/30 hover:bg-emerald-500/40";
  if (change >= 1) return "bg-emerald-500/20 hover:bg-emerald-500/30";
  if (change > -1) return "bg-muted hover:bg-muted/80";
  if (change > -5) return "bg-red-500/20 hover:bg-red-500/30";
  return "bg-red-500/30 hover:bg-red-500/40";
}

export function Treemap({
  stocks,
  sizeKey = "buy_score",
  colorKey = "change_pct",
  caption,
}: TreemapProps) {
  if (!stocks.length) {
    return (
      <p className="text-sm text-muted-foreground">표시할 종목이 없습니다.</p>
    );
  }

  // 크기 정규화: sizeKey가 0 이거나 누락이면 1로 처리하여 동등 분할
  const sized = stocks.map((s) => ({
    row: s,
    size: Math.max(pickNumber(s, sizeKey, 0), 0),
    change: pickNumber(s, colorKey, 0),
  }));
  const totalSize = sized.reduce((sum, x) => sum + x.size, 0);
  const fallbackSize = totalSize === 0; // 모두 0 → 균등 분할
  const total = fallbackSize ? sized.length : totalSize;
  const normalized = sized
    .map((x) => ({
      ...x,
      ratio: fallbackSize ? 1 / sized.length : x.size / total,
    }))
    .sort((a, b) => b.ratio - a.ratio);

  return (
    <figure className="space-y-2">
      {caption && (
        <figcaption className="text-xs text-muted-foreground">
          {caption}
        </figcaption>
      )}
      <div
        role="grid"
        aria-label="종목 트리맵"
        className="grid gap-1 rounded-md border p-2 bg-background"
        style={{
          gridTemplateColumns: "repeat(auto-fill, minmax(96px, 1fr))",
          gridAutoRows: "minmax(72px, auto)",
        }}
      >
        {normalized.map(({ row, ratio, change }) => {
          // 비율을 grid span(1~4)으로 변환 — 큰 종목은 더 많은 셀 차지
          const span = ratio >= 0.18 ? 3 : ratio >= 0.1 ? 2 : 1;
          const display = ratio < MIN_SIZE_RATIO ? "compact" : "full";
          return (
            <Link
              key={row.ticker}
              href={`/analyze/${row.ticker}`}
              role="gridcell"
              aria-label={`${row.name ?? row.ticker} ${change >= 0 ? "+" : ""}${change.toFixed(1)}%`}
              className={`flex flex-col justify-center items-center text-center p-2 rounded transition focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500 ${colorClass(change)}`}
              style={{ gridColumn: `span ${span}`, gridRow: `span ${span}` }}
            >
              <span className="font-medium text-sm truncate max-w-full">
                {typeof row.name === "string" && row.name ? row.name : row.ticker}
              </span>
              {display === "full" && (
                <span
                  className={`text-xs tabular-nums ${
                    change >= 0 ? "text-emerald-400" : "text-red-400"
                  }`}
                >
                  {change >= 0 ? "+" : ""}
                  {change.toFixed(2)}%
                </span>
              )}
            </Link>
          );
        })}
      </div>
    </figure>
  );
}
