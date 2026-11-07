"use client";

/**
 * 종목 결과 표 — 스마트 리스트(/screener/[id])와 커스텀 스크리너에서 공유.
 * 컬럼 메타(라벨·포매터·LEGAL 변환)는 columnMeta에서 일괄 관리.
 */
import Link from "next/link";

import { StockAvatar } from "@/components/stocks/StockAvatar";
import { Term } from "@/components/ui/term";
import { COLUMN_TERMS } from "@/lib/glossary";

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
    <div className="rounded-xl border bg-card overflow-x-auto">
      <table className="w-full text-sm">
        <caption className="sr-only">{caption}</caption>
        <thead className="bg-muted/60 text-xs text-muted-foreground">
          <tr>
            <th scope="col" className="px-3.5 py-2.5 text-left font-medium whitespace-nowrap">
              종목
            </th>
            {dataColumns.map((key) => {
              const meta = getColumnMeta(key);
              return (
                <th
                  key={key}
                  scope="col"
                  className={`px-3.5 py-2.5 font-medium whitespace-nowrap ${
                    meta.align === "right" ? "text-right" : "text-left"
                  }`}
                >
                  {COLUMN_TERMS[key] ? <Term id={COLUMN_TERMS[key]}>{meta.label}</Term> : meta.label}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {stocks.map((row) => (
            <tr
              key={row.ticker}
              className="border-t hover:bg-muted/40 transition"
            >
              <td className="px-3.5 py-2.5 whitespace-nowrap">
                <span className="flex items-center gap-2.5">
                  <StockAvatar
                    ticker={row.ticker}
                    name={typeof row.name === "string" ? row.name : null}
                    className="size-8 text-xs"
                  />
                  <span>
                    <Link
                      href={
                        row.stock_type === "etf"
                          ? `/etf/${row.ticker}`
                          : `/analyze/${row.ticker}`
                      }
                      className="block font-semibold hover:text-primary rounded focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    >
                      {typeof row.name === "string" && row.name ? row.name : row.ticker}
                    </Link>
                    <span className="block text-xs text-muted-foreground">{row.ticker}</span>
                  </span>
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
                    className={`px-3.5 py-2.5 whitespace-nowrap ${
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
