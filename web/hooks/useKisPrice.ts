"use client";

/**
 * KIS 실시간 현재가 / 일봉 / 호가 / 투자자별 매매동향 React Query 훅.
 *
 * - KR 종목(6자리 숫자)만 활성화. US 종목은 enabled=false.
 * - staleTime은 백엔드 캐시 TTL과 일치 (서버 부담 최소화).
 * - 장중 자동 갱신은 refetchInterval 옵션으로 사용처에서 제어.
 */
import { useQuery, type UseQueryOptions } from "@tanstack/react-query";

import {
  fetchKisDailyChart,
  fetchKisInvestor,
  fetchKisMinuteChart,
  fetchKisOrderbook,
  fetchKisPrice,
} from "@/lib/kis";
import type {
  KisChartResponse,
  KisInvestorResponse,
  KisOrderbookResponse,
  KisPriceResponse,
} from "@/types/kis";

function isKrTicker(ticker: string): boolean {
  return /^\d{6}$/.test(ticker.trim());
}

type ExtraOpts<T> = Pick<
  UseQueryOptions<T>,
  "enabled" | "refetchInterval" | "staleTime"
>;

/** 현재가. 백엔드 5초 캐시. KR만. */
export function useKisPrice(
  ticker: string,
  opts: ExtraOpts<KisPriceResponse> = {},
) {
  const enabled = (opts.enabled ?? true) && isKrTicker(ticker);
  return useQuery<KisPriceResponse>({
    queryKey: ["kis-price", ticker],
    queryFn: () => fetchKisPrice(ticker),
    enabled,
    staleTime: opts.staleTime ?? 5_000,
    refetchInterval: opts.refetchInterval,
  });
}

/** 일/주/월/년봉. 백엔드 5분 캐시. */
export function useKisDailyChart(
  ticker: string,
  period: "D" | "W" | "M" | "Y" = "D",
  opts: ExtraOpts<KisChartResponse> = {},
) {
  const enabled = (opts.enabled ?? true) && isKrTicker(ticker);
  return useQuery<KisChartResponse>({
    queryKey: ["kis-chart-daily", ticker, period],
    queryFn: () => fetchKisDailyChart(ticker, period),
    enabled,
    staleTime: opts.staleTime ?? 300_000,
    refetchInterval: opts.refetchInterval,
  });
}

/** 분봉. 백엔드 30초 캐시. */
export function useKisMinuteChart(
  ticker: string,
  opts: ExtraOpts<KisChartResponse> = {},
) {
  const enabled = (opts.enabled ?? true) && isKrTicker(ticker);
  return useQuery<KisChartResponse>({
    queryKey: ["kis-chart-minute", ticker],
    queryFn: () => fetchKisMinuteChart(ticker),
    enabled,
    staleTime: opts.staleTime ?? 30_000,
    refetchInterval: opts.refetchInterval,
  });
}

/** 10호가. 백엔드 5초 캐시. */
export function useKisOrderbook(
  ticker: string,
  opts: ExtraOpts<KisOrderbookResponse> = {},
) {
  const enabled = (opts.enabled ?? true) && isKrTicker(ticker);
  return useQuery<KisOrderbookResponse>({
    queryKey: ["kis-orderbook", ticker],
    queryFn: () => fetchKisOrderbook(ticker),
    enabled,
    staleTime: opts.staleTime ?? 5_000,
    refetchInterval: opts.refetchInterval,
  });
}

/** 투자자별 매매동향 최근 30일. 백엔드 5분 캐시. */
export function useKisInvestor(
  ticker: string,
  opts: ExtraOpts<KisInvestorResponse> = {},
) {
  const enabled = (opts.enabled ?? true) && isKrTicker(ticker);
  return useQuery<KisInvestorResponse>({
    queryKey: ["kis-investor", ticker],
    queryFn: () => fetchKisInvestor(ticker),
    enabled,
    staleTime: opts.staleTime ?? 300_000,
    refetchInterval: opts.refetchInterval,
  });
}
