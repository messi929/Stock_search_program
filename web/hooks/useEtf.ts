"use client";

/**
 * ETF 상세 — GET /api/etf/{ticker} (네이버 etfAnalysis 정규화, 백엔드 1일 캐시).
 * KR 상장 ETF(국내 + 국내상장 국외) 정보 + 상위 구성종목 + 섹터/국가/자산 비중.
 */
import { useQuery } from "@tanstack/react-query";

import { apiCall } from "@/lib/api";

export interface EtfHolding {
  seq: number;
  ticker: string; // 국내 구성종목은 6자리, 국외는 ""
  name: string;
  shares?: string | null;
  weight?: number | null; // 국외 ETF는 null일 수 있음
}

export interface EtfBreakdown {
  code: string;
  weight: number;
}

export interface EtfDetail {
  ticker: string;
  name: string;
  issuer: string;
  base_index: string;
  nav: number | null;
  total_nav: string;
  total_fee: number | null;
  chase_error_rate: number | null;
  deviation_rate: number | null;
  listed_date: string;
  underlying_region: "domestic" | "foreign" | "mixed" | "us" | "unknown";
  top_holdings: EtfHolding[];
  sector_breakdown: EtfBreakdown[];
  country_breakdown: EtfBreakdown[];
  asset_breakdown: EtfBreakdown[];
  as_of: string;
  source: string;
  disclaimer: string;
}

export function useEtfDetail(ticker: string) {
  const tk = (ticker || "").trim().toUpperCase();
  return useQuery({
    queryKey: ["etf-detail", tk],
    queryFn: () => apiCall<EtfDetail>(`/api/etf/${encodeURIComponent(tk)}`),
    enabled: tk.length > 0,
    // 백엔드가 일일 캐시 — 클라이언트도 10분 신선 유지.
    staleTime: 10 * 60_000,
    retry: false, // 비ETF는 404 — 재시도 무의미
  });
}
