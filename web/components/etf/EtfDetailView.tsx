"use client";

/**
 * ETF 전용 상세 — 정보 + 상위 구성종목 + 섹터/국가/자산 비중.
 * KR 상장 ETF(국내 + 국내상장 국외). 데이터: GET /api/etf/{ticker} (네이버 etfAnalysis).
 *
 * LEGAL: 사실 데이터 표시만. 추천/매수 표현 없음. 하단 면책 문구 포함.
 */
import Link from "next/link";

import { Disclaimer } from "@/components/legal/Disclaimer";
import { Card, CardContent } from "@/components/ui/card";
import { useEtfDetail, type EtfBreakdown } from "@/hooks/useEtf";

const REGION_LABEL: Record<string, string> = {
  domestic: "🇰🇷 국내",
  foreign: "🌐 국내상장 국외",
  mixed: "🌗 혼합",
  us: "🇺🇸 미국 상장",
  unknown: "ETF",
};

// 섹터/국가/자산 코드 → 한글 라벨(네이버 detailTypeCode 매핑, 미정의는 코드 그대로).
const CODE_LABEL: Record<string, string> = {
  IT: "IT",
  FINANCIALS: "금융",
  INDUSTRIALS: "산업재",
  COMMUNICATION: "커뮤니케이션",
  CONSUMER: "소비재",
  HEALTHCARE: "헬스케어",
  MATERIALS: "소재",
  ENERGY: "에너지",
  UTILITIES: "유틸리티",
  REALESTATE: "부동산",
  EQUITY: "주식",
  CASH: "현금성",
  BOND: "채권",
  OTHERS: "기타",
  MISC: "기타",
  KR: "한국",
  US: "미국",
  CN: "중국",
  JP: "일본",
  EU: "유럽",
};

function label(code: string): string {
  return CODE_LABEL[code.toUpperCase()] ?? code;
}

function fmtPct(v: number | null | undefined, digits = 2): string {
  if (v == null) return "—";
  return `${v.toFixed(digits)}%`;
}

/** 비중 가로 막대 리스트 (섹터/국가/자산 공용). */
function BreakdownBars({
  title,
  items,
  accent,
}: {
  title: string;
  items: EtfBreakdown[];
  accent: string;
}) {
  const top = items.filter((b) => b.weight > 0).slice(0, 8);
  if (top.length === 0) return null;
  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold">{title}</h3>
      <div className="space-y-1.5">
        {top.map((b) => (
          <div key={b.code} className="space-y-0.5">
            <div className="flex justify-between text-xs">
              <span className="text-muted-foreground">{label(b.code)}</span>
              <span className="font-mono font-medium">{fmtPct(b.weight, 1)}</span>
            </div>
            <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
              <div
                className={`h-full rounded-full ${accent}`}
                style={{ width: `${Math.min(100, b.weight)}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export function EtfDetailView({ ticker }: { ticker: string }) {
  const { data, isLoading, isError } = useEtfDetail(ticker);

  if (isLoading) {
    return (
      <div className="max-w-4xl space-y-4">
        <div className="h-8 w-48 animate-pulse rounded bg-muted" />
        <div className="h-40 w-full animate-pulse rounded bg-muted" />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="max-w-4xl">
        <Card>
          <CardContent className="p-6 text-sm text-muted-foreground space-y-2">
            <p>⚠️ ETF 정보를 불러오지 못했습니다. 종목 코드를 확인하거나 잠시 후 다시 시도해주세요.</p>
            <Link href="/etf" className="text-amber-600 hover:underline">
              ETF 목록 보기 →
            </Link>
          </CardContent>
        </Card>
      </div>
    );
  }

  const metrics: Array<{ label: string; value: string }> = [
    { label: "NAV", value: data.nav != null ? data.nav.toLocaleString() : "—" },
    { label: "순자산총액", value: data.total_nav || "—" },
    { label: "총보수", value: fmtPct(data.total_fee, 3) },
    { label: "추적오차", value: fmtPct(data.chase_error_rate, 2) },
    { label: "괴리율", value: fmtPct(data.deviation_rate, 2) },
  ];

  return (
    <div className="max-w-4xl space-y-6">
      {/* 헤더 */}
      <header className="space-y-2">
        <div className="flex items-center gap-2 flex-wrap">
          <h1 className="text-2xl font-bold">{data.name || ticker}</h1>
          <span className="font-mono text-sm text-muted-foreground">{data.ticker}</span>
          <span className="text-xs px-2 py-0.5 rounded-full border bg-muted/50">
            {REGION_LABEL[data.underlying_region] ?? "ETF"}
          </span>
        </div>
        <p className="text-sm text-muted-foreground">
          {data.base_index && <>추적지수 <strong>{data.base_index}</strong></>}
          {data.issuer && <> · 운용사 {data.issuer}</>}
          {data.listed_date && <> · 상장 {data.listed_date}</>}
        </p>
      </header>

      {/* 핵심 지표 */}
      <section className="grid grid-cols-2 sm:grid-cols-5 gap-2">
        {metrics.map((m) => (
          <Card key={m.label}>
            <CardContent className="p-3">
              <p className="text-[11px] text-muted-foreground">{m.label}</p>
              <p className="text-sm font-semibold font-mono mt-0.5">{m.value}</p>
            </CardContent>
          </Card>
        ))}
      </section>

      {/* 상위 구성종목 */}
      <Card>
        <CardContent className="p-5 space-y-3">
          <div className="flex items-baseline justify-between">
            <h2 className="font-semibold">📦 상위 구성종목</h2>
            <span className="text-[11px] text-muted-foreground">상위 10개 (CU 기준)</span>
          </div>
          {data.top_holdings.length === 0 ? (
            <p className="text-sm text-muted-foreground">구성종목 정보가 없습니다.</p>
          ) : (
            <div className="space-y-1.5">
              {data.top_holdings.map((h) => (
                <div
                  key={h.seq}
                  className="flex items-center gap-3 text-sm py-1 border-b border-border/50 last:border-0"
                >
                  <span className="w-5 text-xs text-muted-foreground shrink-0">{h.seq}</span>
                  <div className="flex-1 min-w-0">
                    {h.ticker ? (
                      <Link
                        href={`/analyze/${h.ticker}`}
                        className="font-medium hover:underline truncate inline-block max-w-full"
                        title="이 종목 분석"
                      >
                        {h.name}
                      </Link>
                    ) : (
                      <span className="font-medium truncate inline-block max-w-full">
                        {h.name}
                      </span>
                    )}
                    {h.ticker && (
                      <span className="ml-1.5 font-mono text-[11px] text-muted-foreground">
                        {h.ticker}
                      </span>
                    )}
                  </div>
                  {h.weight != null ? (
                    <div className="flex items-center gap-2 shrink-0 w-32">
                      <div className="h-1.5 flex-1 rounded-full bg-muted overflow-hidden">
                        <div
                          className="h-full rounded-full bg-primary/70"
                          style={{ width: `${Math.min(100, h.weight)}%` }}
                        />
                      </div>
                      <span className="font-mono text-xs w-12 text-right">
                        {fmtPct(h.weight, 2)}
                      </span>
                    </div>
                  ) : (
                    <span className="text-[11px] text-muted-foreground shrink-0">
                      {h.shares ? `${h.shares}주` : "—"}
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}
          {data.underlying_region === "foreign" && (
            <p className="text-[11px] text-muted-foreground">
              ※ 국외 자산은 종목 비중·코드가 제공되지 않아 보유 수량으로 표시됩니다.
            </p>
          )}
        </CardContent>
      </Card>

      {/* 비중 — 섹터 / 국가 / 자산 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardContent className="p-5">
            <BreakdownBars title="🏭 섹터 비중" items={data.sector_breakdown} accent="bg-violet-500/70" />
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-5">
            <BreakdownBars title="🌐 국가 비중" items={data.country_breakdown} accent="bg-sky-500/70" />
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-5">
            <BreakdownBars title="🧱 자산 비중" items={data.asset_breakdown} accent="bg-emerald-500/70" />
          </CardContent>
        </Card>
      </div>

      <Disclaimer />
    </div>
  );
}
