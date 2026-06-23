"use client";

/**
 * ETF 발견 (/etf) — 국내 ETF(스크리너 데이터) + 해외 인기 ETF(큐레이션).
 * 카드 클릭 → /etf/{ticker} 전용 상세(정보 + 구성종목 + 비중).
 */
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";

import { Card, CardContent } from "@/components/ui/card";
import { apiCall } from "@/lib/api";

// 한국 투자자에게 친숙한 해외(US 상장) 대표 ETF — /etf/{ticker}는 yfinance로 동작.
const US_ETFS: { ticker: string; label: string }[] = [
  { ticker: "SPY", label: "S&P500" },
  { ticker: "QQQ", label: "나스닥100" },
  { ticker: "VOO", label: "S&P500(뱅가드)" },
  { ticker: "SCHD", label: "배당성장" },
  { ticker: "JEPI", label: "커버드콜 인컴" },
  { ticker: "VTI", label: "미국 전체" },
  { ticker: "SOXX", label: "반도체" },
  { ticker: "TLT", label: "美 장기국채" },
  { ticker: "GLD", label: "금" },
  { ticker: "DIA", label: "다우30" },
];

type EtfRow = {
  ticker: string;
  name?: string;
  etf_category?: string;
  change_pct?: number;
};

function changeTone(v: number | undefined): string {
  if (v == null) return "text-muted-foreground";
  // KR 컬러: 상승 빨강 / 하락 파랑
  return v > 0 ? "text-red-500" : v < 0 ? "text-blue-500" : "text-muted-foreground";
}

export function EtfDiscoverView() {
  const { data, isLoading } = useQuery({
    queryKey: ["etf-list-kr"],
    queryFn: () =>
      apiCall<{ stocks: EtfRow[] }>("/api/scan?category=etf&limit=24&sort_by=volume"),
    staleTime: 5 * 60_000,
  });
  const krEtfs = data?.stocks ?? [];

  return (
    <div className="space-y-8 max-w-5xl">
      <header>
        <h1 className="text-2xl font-bold">🧺 ETF 탐색</h1>
        <p className="text-sm text-muted-foreground mt-1">
          국내·국내상장 국외·해외 ETF의 정보와 구성종목·비중을 확인하세요.
        </p>
      </header>

      {/* 해외 인기 ETF (US 상장) */}
      <section className="space-y-3">
        <div className="flex items-baseline gap-2">
          <h2 className="font-semibold">🇺🇸 해외 인기 ETF</h2>
          <span className="text-[11px] text-muted-foreground">미국 상장</span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2">
          {US_ETFS.map((e) => (
            <Link key={e.ticker} href={`/etf/${e.ticker}`} className="block">
              <Card className="hover:bg-muted/50 transition cursor-pointer h-full">
                <CardContent className="p-3">
                  <p className="font-mono font-semibold text-sm">{e.ticker}</p>
                  <p className="text-xs text-muted-foreground mt-0.5 truncate">{e.label}</p>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      </section>

      {/* 국내 상장 ETF (국내 + 국내상장 국외) */}
      <section className="space-y-3">
        <div className="flex items-baseline justify-between">
          <div className="flex items-baseline gap-2">
            <h2 className="font-semibold">🇰🇷 국내 상장 ETF</h2>
            <span className="text-[11px] text-muted-foreground">거래량 상위</span>
          </div>
          <Link href="/screener/etf" className="text-xs text-amber-600 hover:underline">
            전체 목록 →
          </Link>
        </div>
        {isLoading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="h-16 animate-pulse rounded bg-muted" />
            ))}
          </div>
        ) : krEtfs.length === 0 ? (
          <p className="text-sm text-muted-foreground">ETF 데이터를 불러오지 못했습니다.</p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
            {krEtfs.map((e) => (
              <Link key={e.ticker} href={`/etf/${e.ticker}`} className="block">
                <Card className="hover:bg-muted/50 transition cursor-pointer">
                  <CardContent className="p-3 flex items-center justify-between gap-2">
                    <div className="min-w-0">
                      <p className="font-medium text-sm truncate">{e.name ?? e.ticker}</p>
                      <p className="text-xs text-muted-foreground">
                        <span className="font-mono">{e.ticker}</span>
                        {e.etf_category ? ` · ${e.etf_category}` : ""}
                      </p>
                    </div>
                    {e.change_pct != null && (
                      <span className={`text-sm font-medium shrink-0 ${changeTone(e.change_pct)}`}>
                        {e.change_pct > 0 ? "+" : ""}
                        {e.change_pct.toFixed(2)}%
                      </span>
                    )}
                  </CardContent>
                </Card>
              </Link>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
