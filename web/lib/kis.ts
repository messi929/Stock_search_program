/**
 * KIS (한국투자증권 OpenAPI) 클라이언트 함수.
 *
 * 백엔드 라우트: /api/kis/* (in-memory TTL 캐시 적용)
 * 백엔드 캐시 TTL과 별개로 React Query에서 refetchInterval로 폴링 시 부담 0.
 */

import { apiCall } from "./api";
import type {
  KisChartResponse,
  KisHealthResponse,
  KisInvestorResponse,
  KisOrderbookResponse,
  KisPriceResponse,
} from "../types/kis";

/** 현재가 + 등락 + 거래량 (백엔드 5초 캐시). */
export async function fetchKisPrice(ticker: string): Promise<KisPriceResponse> {
  return apiCall<KisPriceResponse>(
    `/api/kis/price/${encodeURIComponent(ticker)}`,
    { method: "GET" },
  );
}

/** 일/주/월/년봉 (백엔드 5분 캐시, 수정주가). */
export async function fetchKisDailyChart(
  ticker: string,
  period: "D" | "W" | "M" | "Y" = "D",
  adjusted = true,
): Promise<KisChartResponse> {
  const qs = new URLSearchParams({
    period,
    adjusted: adjusted ? "true" : "false",
  });
  return apiCall<KisChartResponse>(
    `/api/kis/chart/${encodeURIComponent(ticker)}/daily?${qs}`,
    { method: "GET" },
  );
}

/** 당일 1분봉 최근 30개 (백엔드 30초 캐시). */
export async function fetchKisMinuteChart(
  ticker: string,
  timeHHMMSS?: string,
): Promise<KisChartResponse> {
  const qs = new URLSearchParams();
  if (timeHHMMSS) qs.set("time_hhmmss", timeHHMMSS);
  const suffix = qs.toString() ? `?${qs}` : "";
  return apiCall<KisChartResponse>(
    `/api/kis/chart/${encodeURIComponent(ticker)}/minute${suffix}`,
    { method: "GET" },
  );
}

/** 10호가 + 예상체결 (백엔드 5초 캐시). */
export async function fetchKisOrderbook(
  ticker: string,
): Promise<KisOrderbookResponse> {
  return apiCall<KisOrderbookResponse>(
    `/api/kis/orderbook/${encodeURIComponent(ticker)}`,
    { method: "GET" },
  );
}

/** 투자자별 매매동향 최근 30일 (백엔드 5분 캐시). */
export async function fetchKisInvestor(
  ticker: string,
): Promise<KisInvestorResponse> {
  return apiCall<KisInvestorResponse>(
    `/api/kis/investor/${encodeURIComponent(ticker)}`,
    { method: "GET" },
  );
}

/** KIS 라우트 헬스. */
export async function fetchKisHealth(): Promise<KisHealthResponse> {
  return apiCall<KisHealthResponse>("/api/kis/health", { method: "GET" });
}

// ─── 표시용 유틸 ─────────────────────────────────

/** KIS 가격 문자열 → 천 단위 콤마 (예: "299000" → "299,000"). */
export function formatKisPrice(value: string | undefined): string {
  if (!value) return "—";
  const n = Number(value);
  if (!Number.isFinite(n)) return value;
  return n.toLocaleString("ko-KR");
}

/** KIS 등락률 문자열 → "+2.22%" 형태 (음수면 그대로). */
export function formatKisChangePct(value: string | undefined): string {
  if (!value) return "—";
  const n = Number(value);
  if (!Number.isFinite(n)) return value;
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(2)}%`;
}

/** prdy_vrss_sign 코드 → 색상 클래스 (Tailwind). */
export function priceSignColorClass(sign: string | undefined): string {
  // 1상한·2상승 → 빨강, 4하한·5하락 → 파랑, 3보합 → 회색
  if (sign === "1" || sign === "2") return "text-red-500";
  if (sign === "4" || sign === "5") return "text-blue-500";
  return "text-gray-500";
}
