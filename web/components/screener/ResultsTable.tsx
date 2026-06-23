"use client";

/**
 * 종목 결과 표 — 스마트 리스트(/screener/[id])와 커스텀 스크리너에서 공유.
 * 컬럼 메타(라벨·포매터·LEGAL 변환)는 columnMeta에서 일괄 관리.
 */
import Link from "next/link";

import { getColumnMeta } from "./columnMeta";

export type StockRow = Record<string, unknown> & { ticker: string; name?: string };

export function ResultsTable({
  columns,
  stocks,
  caption,
}: {
  columns: string[];
  stocks: StockRow[];
  caption: string;
}) {
  const dataColumns = columns.filter((c) => c !== "ticker" && c !== "name");

  return (
    <div className="rounded-md border overflow-x-auto">
      <table className="w-full text-sm">
        <caption className="sr-only">{caption}</caption>
        <thead className="bg-muted/50 text-xs">
          <tr>
            <th scope="col" className="px-3 py-2 text-left font-medium whitespace-nowrap">
              종목
            </th>
            {dataColumns.map((key) => {
              const meta = getColumnMeta(key);
              return (
                <th
                  key={key}
                  scope="col"
                  className={`px-3 py-2 font-medium whitespace-nowrap ${
                    meta.align === "right" ? "text-right" : "text-left"
                  }`}
                >
                  {meta.label}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {stocks.map((row) => (
            <tr
              key={row.ticker}
              className="border-t hover:bg-muted/30 transition"
            >
              <td className="px-3 py-2 whitespace-nowrap">
                <Link
                  href={
                    row.stock_type === "etf"
                      ? `/etf/${row.ticker}`
                      : `/analyze/${row.ticker}`
                  }
                  className="font-medium text-amber-500 hover:underline rounded focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500"
                >
                  {typeof row.name === "string" && row.name ? row.name : row.ticker}
                </Link>
                <span className="ml-2 text-xs text-muted-foreground">
                  {row.ticker}
                </span>
              </td>
              {dataColumns.map((key) => {
                const meta = getColumnMeta(key);
                const v = row[key];
                const text = meta.format(v);
                const color = meta.colorize?.(v) ?? "";
                return (
                  <td
                    key={key}
                    className={`px-3 py-2 whitespace-nowrap ${
                      meta.align === "right" ? "text-right tabular-nums" : "text-left"
                    } ${color}`}
                  >
                    {text}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
