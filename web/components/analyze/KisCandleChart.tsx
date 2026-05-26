"use client";

/**
 * KIS 캔들 차트 — 일봉 / 주봉 / 월봉 / 분봉 토글.
 * lightweight-charts 5.x (TradingView).
 *
 * KR 종목(6자리)에서만 렌더. 그 외는 null.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import {
  CandlestickSeries,
  HistogramSeries,
  createChart,
  type IChartApi,
  type ISeriesApi,
} from "lightweight-charts";

import { Card, CardContent } from "@/components/ui/card";
import { useKisDailyChart, useKisMinuteChart } from "@/hooks/useKisPrice";
import type { KisDailyBar, KisMinuteBar } from "@/types/kis";

type Period = "D" | "W" | "M" | "MIN";

const PERIODS: { id: Period; label: string }[] = [
  { id: "D", label: "일봉" },
  { id: "W", label: "주봉" },
  { id: "M", label: "월봉" },
  { id: "MIN", label: "분봉" },
];

function isKr(ticker: string): boolean {
  return /^\d{6}$/.test(ticker.trim());
}

/** KIS 날짜/시각 → lightweight-charts time. 일봉=epoch sec(자정), 분봉=epoch sec(체결시각). */
function dailyTime(date: string): number {
  // YYYYMMDD → epoch sec (KST 자정)
  const y = Number(date.slice(0, 4));
  const m = Number(date.slice(4, 6)) - 1;
  const d = Number(date.slice(6, 8));
  return Math.floor(new Date(Date.UTC(y, m, d, -9, 0, 0)).getTime() / 1000);
}

function minuteTime(date: string, time: string): number {
  const y = Number(date.slice(0, 4));
  const mo = Number(date.slice(4, 6)) - 1;
  const d = Number(date.slice(6, 8));
  const h = Number(time.slice(0, 2));
  const mi = Number(time.slice(2, 4));
  const s = Number(time.slice(4, 6) || 0);
  // KST → UTC: -9h
  return Math.floor(new Date(Date.UTC(y, mo, d, h - 9, mi, s)).getTime() / 1000);
}

export function KisCandleChart({ ticker }: { ticker: string }) {
  const [period, setPeriod] = useState<Period>("D");
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeRef = useRef<ISeriesApi<"Histogram"> | null>(null);

  const dailyQ = useKisDailyChart(ticker, period === "MIN" ? "D" : period, {
    enabled: isKr(ticker) && period !== "MIN",
  });
  const minuteQ = useKisMinuteChart(ticker, {
    enabled: isKr(ticker) && period === "MIN",
  });

  const isMinute = period === "MIN";
  const loading = isMinute ? minuteQ.isLoading : dailyQ.isLoading;
  const error = isMinute ? minuteQ.error : dailyQ.error;
  const bars = isMinute ? minuteQ.data?.bars : dailyQ.data?.bars;

  // 차트 초기화 (1회만)
  useEffect(() => {
    if (!containerRef.current) return;
    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height: 360,
      layout: {
        background: { color: "transparent" },
        textColor: "#94a3b8",
      },
      grid: {
        vertLines: { color: "#1e293b22" },
        horzLines: { color: "#1e293b22" },
      },
      rightPriceScale: { borderColor: "#1e293b" },
      timeScale: { borderColor: "#1e293b", timeVisible: true },
    });
    chartRef.current = chart;
    candleRef.current = chart.addSeries(CandlestickSeries, {
      upColor: "#ef4444",      // 한국식: 상승 빨강
      downColor: "#3b82f6",    // 하락 파랑
      borderUpColor: "#ef4444",
      borderDownColor: "#3b82f6",
      wickUpColor: "#ef4444",
      wickDownColor: "#3b82f6",
    });
    volumeRef.current = chart.addSeries(HistogramSeries, {
      color: "#64748b",
      priceFormat: { type: "volume" },
      priceScaleId: "",
    });
    chart
      .priceScale("")
      .applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });

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
      volumeRef.current = null;
    };
  }, []);

  // 데이터 → series
  const { candles, volumes } = useMemo(() => {
    if (!bars || bars.length === 0) return { candles: [], volumes: [] };

    if (isMinute) {
      const mb = (bars as KisMinuteBar[])
        .map((b) => ({
          time: minuteTime(b.stck_bsop_date, b.stck_cntg_hour),
          open: Number(b.stck_oprc),
          high: Number(b.stck_hgpr),
          low: Number(b.stck_lwpr),
          close: Number(b.stck_prpr),
          volume: Number(b.cntg_vol || 0),
        }))
        .sort((a, b) => a.time - b.time);
      return {
        candles: mb.map(({ time, open, high, low, close }) => ({
          time: time as never,
          open,
          high,
          low,
          close,
        })),
        volumes: mb.map(({ time, volume, close, open }) => ({
          time: time as never,
          value: volume,
          color: close >= open ? "#ef444466" : "#3b82f666",
        })),
      };
    }

    const db = (bars as KisDailyBar[])
      .map((b) => ({
        time: dailyTime(b.stck_bsop_date),
        open: Number(b.stck_oprc),
        high: Number(b.stck_hgpr),
        low: Number(b.stck_lwpr),
        close: Number(b.stck_clpr),
        volume: Number(b.acml_vol || 0),
      }))
      .sort((a, b) => a.time - b.time);
    return {
      candles: db.map(({ time, open, high, low, close }) => ({
        time: time as never,
        open,
        high,
        low,
        close,
      })),
      volumes: db.map(({ time, volume, close, open }) => ({
        time: time as never,
        value: volume,
        color: close >= open ? "#ef444466" : "#3b82f666",
      })),
    };
  }, [bars, isMinute]);

  useEffect(() => {
    if (!candleRef.current || !volumeRef.current) return;
    if (candles.length === 0) {
      candleRef.current.setData([]);
      volumeRef.current.setData([]);
      return;
    }
    candleRef.current.setData(candles);
    volumeRef.current.setData(volumes);
    chartRef.current?.timeScale().fitContent();
  }, [candles, volumes]);

  if (!isKr(ticker)) return null;

  return (
    <Card>
      <CardContent className="p-4 space-y-3">
        <div className="flex items-center justify-between">
          <div className="text-sm font-semibold">📊 차트</div>
          <div className="flex gap-1">
            {PERIODS.map((p) => (
              <button
                key={p.id}
                type="button"
                onClick={() => setPeriod(p.id)}
                className={`text-xs px-2 py-1 rounded-md border transition ${
                  period === p.id
                    ? "bg-primary text-primary-foreground border-primary"
                    : "bg-transparent border-border hover:bg-muted"
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>

        <div className="relative">
          <div ref={containerRef} className="w-full" style={{ height: 360 }} />
          {loading && (
            <div className="absolute inset-0 flex items-center justify-center text-xs text-muted-foreground">
              차트 불러오는 중…
            </div>
          )}
          {error && !loading && (
            <div className="absolute inset-0 flex items-center justify-center text-xs text-red-500">
              차트 불러오기 실패
            </div>
          )}
          {!loading && !error && candles.length === 0 && (
            <div className="absolute inset-0 flex items-center justify-center text-xs text-muted-foreground">
              데이터 없음
            </div>
          )}
        </div>

        <p className="text-[10px] text-muted-foreground">
          데이터: 한국투자증권 OpenAPI · 수정주가 · 한국식 컬러(상승🔴/하락🔵)
        </p>
      </CardContent>
    </Card>
  );
}
