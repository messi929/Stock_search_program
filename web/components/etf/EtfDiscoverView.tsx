"use client";

/**
 * ETF 발견 (/etf) — 칩(세그먼트) 필터로 3분류:
 *   ① 국내 ETF (국내 지수·섹터 추종)
 *   ② 국내상장 해외 ETF (국내 상장이나 해외 자산 추종, 예 KODEX 미국S&P500)
 *   ③ 해외 ETF (미국 상장, 예 SPY/QQQ — 큐레이션)
 * 카드 클릭 → /etf/{ticker} 전용 상세.
 *
 * ①②는 /api/scan?category=etf 결과를 etf_category + 종목명 키워드로 분류.
 */
import Link from "next/link";
import { useState } from "react";
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

// 종목명에 들어가면 '해외 자산 추종'으로 보는 키워드 (레버리지·섹터형 해외물 보정용).
const FOREIGN_KW = [
  "미국", "나스닥", "S&P", "SP500", "차이나", "중국", "항셍", "홍콩", "일본", "닛케이",
  "유럽", "유로", "글로벌", "선진", "신흥", "인도", "베트남", "브라질", "대만",
  "필라델피아", "달러", "미국채",
];

type EtfRow = {
  ticker: string;
  name?: string;
  etf_category?: string;
  change_pct?: number;
};

type Chip = "domestic" | "krForeign" | "overseas";

/** 국내 상장 ETF가 '해외 자산 추종(국내상장 해외)'인지 — 분류(해외*) + 종목명 키워드. */
function isKrForeign(cat?: string, name?: string): boolean {
  if (cat && cat.startsWith("해외")) return true;
  if (name && FOREIGN_KW.some((k) => name.includes(k))) return true;
  return false;
}

function changeTone(v: number | undefined): string {
  if (v == null) return "text-muted-foreground";
  // KR 컬러: 상승 빨강 / 하락 파랑
  return v > 0 ? "text-red-500" : v < 0 ? "text-blue-500" : "text-muted-foreground";
}

function KrEtfCard({ e }: { e: EtfRow }) {
  return (
    <Link href={`/etf/${e.ticker}`} className="block">
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
  );
}

export function EtfDiscoverView() {
  const [chip, setChip] = useState<Chip>("domestic");

  const { data, isLoading } = useQuery({
    queryKey: ["etf-list-kr"],
    queryFn: () =>
      apiCall<{ stocks: EtfRow[] }>("/api/scan?category=etf&limit=200&sort_by=volume"),
    staleTime: 5 * 60_000,
  });
  const krEtfs = data?.stocks ?? [];
  const domestic = krEtfs.filter((e) => !isKrForeign(e.etf_category, e.name));
  const krForeign = krEtfs.filter((e) => isKrForeign(e.etf_category, e.name));

  const chips: { id: Chip; label: string; count: number | null; desc: string }[] = [
    { id: "domestic", label: "국내 ETF", count: domestic.length, desc: "국내 지수·섹터 추종" },
    { id: "krForeign", label: "국내상장 해외", count: krForeign.length, desc: "국내 상장 · 해외 자산 추종" },
    { id: "overseas", label: "해외 ETF", count: US_ETFS.length, desc: "미국 상장 (SPY·QQQ 등)" },
  ];
  const activeDesc = chips.find((c) => c.id === chip)?.desc ?? "";

  return (
    <div className="space-y-5 max-w-5xl">
      <header>
        <h1 className="text-2xl font-bold">🧺 ETF 탐색</h1>
        <p className="text-sm text-muted-foreground mt-1">
          분류를 선택해 ETF 정보·구성종목·비중을 확인하세요.
        </p>
      </header>

      {/* 분류 칩 (세그먼트) */}
      <div className="flex flex-wrap gap-2">
        {chips.map((c) => {
          const active = chip === c.id;
          return (
            <button
              key={c.id}
              type="button"
              onClick={() => setChip(c.id)}
              aria-pressed={active}
              className={`px-3.5 py-2 rounded-full border text-sm font-medium transition ${
                active
                  ? "bg-primary text-primary-foreground border-primary"
                  : "bg-background hover:bg-muted/60 border-border text-foreground"
              }`}
            >
              {c.label}
              <span
                className={`ml-1.5 text-xs ${
                  active ? "text-primary-foreground/80" : "text-muted-foreground"
                }`}
              >
                {c.count != null ? c.count : ""}
              </span>
            </button>
          );
        })}
      </div>
      <p className="text-xs text-muted-foreground -mt-2">{activeDesc}</p>

      {/* 활성 분류 그리드 */}
      {chip === "overseas" ? (
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
      ) : isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
          {Array.from({ length: 9 }).map((_, i) => (
            <div key={i} className="h-16 animate-pulse rounded bg-muted" />
          ))}
        </div>
      ) : (
        (() => {
          const list = chip === "domestic" ? domestic : krForeign;
          if (list.length === 0) {
            return (
              <p className="text-sm text-muted-foreground">
                해당 분류의 ETF를 불러오지 못했습니다.
              </p>
            );
          }
          return (
            <>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                {list.map((e) => (
                  <KrEtfCard key={e.ticker} e={e} />
                ))}
              </div>
              <p className="text-[11px] text-muted-foreground">
                거래량 상위 기준. 전체 목록은{" "}
                <Link href="/screener/etf" className="text-amber-600 hover:underline">
                  스크리너 ETF
                </Link>
                에서.
              </p>
            </>
          );
        })()
      )}
    </div>
  );
}
