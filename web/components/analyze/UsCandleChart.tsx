"use client";

/**
 * US 캔들 차트 — 미국 종목(알파벳 티커) 일봉.
 * lightweight-charts 5.x (TradingView).
 *
 * 데이터: 백엔드 /api/chart?ticker= (Firestore 저장 OHLCV, yfinance 수집).
 * KIS(한국투자증권)는 KR 전용이라 US는 이 컴포넌트로 분리.
 * 컬러는 앱 전체 일관성을 위해 한국식(상승🔴/하락🔵) 유지.
 */
import { useEffect, useMemo, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  CandlestickSeries,
  LineSeries,
  createChart,
  type IChartApi,
  type ISeriesApi,
} from "lightweight-charts";

import { Card, CardContent } from "@/components/ui/card";
import { apiCall } from "@/lib/api";

type ChartPoint = { time: string; open: number; high: number; low: number; close: number };
type MaPoint = { time: string; value: number };
type ChartResponse = {
  candles: ChartPoint[];
  ma5?: MaPoint[];
  ma20?: MaPoint[];
  ma60?: MaPoint[];
};

function isUs(ticker: string): boolean {
  return !/^\d{6}$/.test(ticker.trim());
}

export function UsCandleChart({ ticker }: { ticker: string }) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const ma20Ref = useRef<ISeriesApi<"Line"> | null>(null);
  const ma60Ref = useRef<ISeriesApi<"Line"> | null>(null);

  const { data, isLoading, error } = useQuery<ChartResponse>({
    queryKey: ["us-chart", ticker],
    queryFn: () =>
      apiCall<ChartResponse>(`/api/chart?ticker=${encodeURIComponent(ticker)}`, {
        method: "GET",
      }),
    enabled: isUs(ticker),
    staleTime: 300_000,
  });

  // 차트 초기화 (1회)
  useEffect(() => {
    if (!containerRef.current) return;
    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height: 360,
      layout: { background: { color: "transparent" }, textColor: "#94a3b8" },
      grid: {
        vertLines: { color: "#1e293b22" },
        horzLines: { color: "#1e293b22" },
      },
      rightPriceScale: { borderColor: "#1e293b" },
      timeScale: { borderColor: "#1e293b", timeVisible: false },
    });
    chartRef.current = chart;
    candleRef.current = chart.addSeries(CandlestickSeries, {
      upColor: "#ef4444",
      downColor: "#3b82f6",
      borderUpColor: "#ef4444",
      borderDownColor: "#3b82f6",
      wickUpColor: "#ef4444",
      wickDownColor: "#3b82f6",
    });
    ma20Ref.current = chart.addSeries(LineSeries, {
      color: "#f59e0b",
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    ma60Ref.current = chart.addSeries(LineSeries, {
      color: "#a855f7",
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
    });

    const onResize = () => {
      if (containerRef.current && chartRef.current) {
        chartRef.current.applyOptions({ width: containerRef.current.clientWidth });
      }
    };
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      chart.remove();
      chartRef.current = null;
      candleRef.current = null;
      ma20Ref.current = null;
      ma60Ref.current = null;
    };
  }, []);

  const series = useMemo(() => {
    const candles = (data?.candles ?? [])
      .map((b) => ({
        time: b.time as never,
        open: Number(b.open),
        high: Number(b.high),
        low: Number(b.low),
        close: Number(b.close),
      }))
      .sort((a, b) => (a.time < b.time ? -1 : 1));
    const toLine = (arr?: MaPoint[]) =>
      (arr ?? [])
        .map((p) => ({ time: p.time as never, value: Number(p.value) }))
        .sort((a, b) => (a.time < b.time ? -1 : 1));
    return { candles, ma20: toLine(data?.ma20), ma60: toLine(data?.ma60) };
  }, [data]);

  useEffect(() => {
    if (!candleRef.current) return;
    candleRef.current.setData(series.candles);
    ma20Ref.current?.setData(series.ma20);
    ma60Ref.current?.setData(series.ma60);
    if (series.candles.length) chartRef.current?.timeScale().fitContent();
  }, [series]);

  if (!isUs(ticker)) return null;

  return (
    <Card>
      <CardContent className="p-4 space-y-3">
        <div className="flex items-center justify-between">
          <div className="text-sm font-semibold">📊 차트 (일봉)</div>
          <div className="text-[10px] text-muted-foreground">
            <span className="text-amber-500">— MA20</span>{" "}
            <span className="text-purple-500">— MA60</span>
          </div>
        </div>

        <div className="relative">
          <div ref={containerRef} className="w-full" style={{ height: 360 }} />
          {isLoading && (
            <div className="absolute inset-0 flex items-center justify-center text-xs text-muted-foreground">
              차트 불러오는 중…
            </div>
          )}
          {error && !isLoading && (
            <div className="absolute inset-0 flex items-center justify-center text-xs text-red-500">
              차트 불러오기 실패
            </div>
          )}
          {!isLoading && !error && series.candles.length === 0 && (
            <div className="absolute inset-0 flex items-center justify-center text-xs text-muted-foreground">
              데이터 없음
            </div>
          )}
        </div>

        <p className="text-[10px] text-muted-foreground">
          데이터: yfinance · 미국 시장 · 컬러(상승🔴/하락🔵)
        </p>
      </CardContent>
    </Card>
  );
}
