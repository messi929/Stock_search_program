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
  const abs = Math.abs(n);
  const sign = n < 0 ? "-" : "";
  if (abs >= 1e12) return `${sign}${(abs / 1e12).toFixed(2)}조`;
  if (abs >= 1e8) return `${sign}${(abs / 1e8).toFixed(0)}억`;
  if (abs >= 1e4) return `${sign}${(abs / 1e4).toFixed(0)}만`;
  return n.toLocaleString("ko-KR");
}

/** 시가총액 표기. 백엔드 market_cap은 국내·미국 모두 억원 단위다. */
export function fmtMarketCapEok(v: unknown): string {
  const n = Number(v);
  if (!Number.isFinite(n) || n <= 0) return "-";
  if (n >= 1e4) return `${(n / 1e4).toLocaleString("ko-KR", { maximumFractionDigits: n >= 1e6 ? 0 : 1 })}조`;
  return `${Math.round(n).toLocaleString("ko-KR")}억`;
}

/**
 * 저장된 국내 시세가 직전 정규장 종가로 확정됐는지 판단한다.
 * KIS 현재가는 마감 뒤에도 시간외 거래로 움직이므로, 장외 시간에는 이 값을 공식 종가로 쓴다.
 * updatedAt은 백엔드 형식("YYYY-MM-DD HH:mm:ss", KST). 공휴일은 구분하지 않는다.
 */
export function isKrxCloseFinal(updatedAt: string | undefined, now = new Date()): boolean {
  if (!updatedAt) return false;
  const kst = new Date(now.getTime() + 9 * 3_600_000);
  const isWeekday = (d: Date) => d.getUTCDay() >= 1 && d.getUTCDay() <= 5;
  const minutes = kst.getUTCHours() * 60 + kst.getUTCMinutes();
  const closeMinutes = 15 * 60 + 30;
  if (isWeekday(kst) && minutes >= 9 * 60 && minutes < closeMinutes) return false;

  const lastClose = new Date(
    Date.UTC(kst.getUTCFullYear(), kst.getUTCMonth(), kst.getUTCDate(), 15, 30),
  );
  if (!isWeekday(kst) || minutes < closeMinutes) {
    do {
      lastClose.setUTCDate(lastClose.getUTCDate() - 1);
    } while (!isWeekday(lastClose));
  }
  return Date.parse(`${updatedAt.replace(" ", "T")}Z`) >= lastClose.getTime();
}

/** KR 시장 여부(원화 표기 판단). */
export function isKrMarket(market: string): boolean {
  return market === "KOSPI" || market === "KOSDAQ";
}

/** 등락률 색상 — 한국식(상승 빨강 / 하락 파랑). */
export function changeColorClass(pct: number): string {
  if (pct > 0) return "text-up";
  if (pct < 0) return "text-down";
  return "text-muted-foreground";
}
