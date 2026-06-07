/**
 * 공개 종목 페이지(/stocks/[ticker]) 데이터 — 서버 전용 fetch 헬퍼.
 *
 * lib/api.ts(클라이언트, Firebase 토큰)와 분리: 공개 페이지는 무인증 SSR이라
 * Firebase에 의존하지 않고 백엔드 공개 엔드포인트를 직접 호출한다.
 * 크롤러 친화 + CDN 캐싱을 위해 ISR(revalidate)을 사용한다.
 */
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

// 데이터 갱신 주기(초). 종목 스냅샷은 일 단위라 1시간 ISR이면 충분.
const REVALIDATE = 3600;

export interface PublicCandle {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
}

export interface PublicStock {
  ticker: string;
  name: string;
  market: string;
  stock_type: string;
  close: number;
  change_pct: number;
  volume: number;
  trading_value: number;
  market_cap: number;
  per: number;
  pbr: number;
  roe: number;
  div_yield: number;
  vs_high_52w: number;
  vs_low_52w: number;
  rsi: number;
  sector: string;
  industry: string;
  themes: string;
  chart: PublicCandle[];
  updated_at: string;
}

export interface PublicStockListItem {
  ticker: string;
  name: string;
  market: string;
}

/** 단일 공개 종목 조회. 없으면 null(404). */
export async function getPublicStock(ticker: string): Promise<PublicStock | null> {
  try {
    const res = await fetch(`${API_BASE}/api/stocks/${encodeURIComponent(ticker)}`, {
      next: { revalidate: REVALIDATE },
    });
    if (!res.ok) return null;
    return (await res.json()) as PublicStock;
  } catch {
    return null;
  }
}

/** sitemap용 전체 종목 경량 목록. 실패 시 빈 배열. */
export async function listPublicStocks(): Promise<PublicStockListItem[]> {
  try {
    const res = await fetch(`${API_BASE}/api/stocks`, {
      next: { revalidate: REVALIDATE },
    });
    if (!res.ok) return [];
    const data = (await res.json()) as { stocks?: PublicStockListItem[] };
    return data.stocks ?? [];
  } catch {
    return [];
  }
}

// ── 표시 포맷 (screener/columnMeta.ts와 동일 규칙) ──

/** 시총·거래대금 등 큰 수 → 조/억/만 (원 단위 입력). */
export function fmtCompactKR(v: number): string {
  const n = Number(v);
  if (!Number.isFinite(n) || n === 0) return "-";
  if (n >= 1e12) return `${(n / 1e12).toFixed(2)}조`;
  if (n >= 1e8) return `${(n / 1e8).toFixed(0)}억`;
  if (n >= 1e4) return `${(n / 1e4).toFixed(0)}만`;
  return n.toLocaleString("ko-KR");
}

/** KR 시장 여부(원화 표기 판단). */
export function isKrMarket(market: string): boolean {
  return market === "KOSPI" || market === "KOSDAQ";
}

/** 등락률 색상 — 한국식(상승 빨강 / 하락 파랑). */
export function changeColorClass(pct: number): string {
  if (pct > 0) return "text-red-500";
  if (pct < 0) return "text-blue-500";
  return "text-muted-foreground";
}
