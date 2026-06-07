/**
 * 공개 종목 페이지 (/stocks/[ticker]) — 비로그인·SSR·색인 대상.
 *
 * 목적: 검색 유입 착지점 → 로그인 게이트 → AI 딥다이브(/analyze) 전환 깔때기.
 * 공개 영역은 사실 데이터(시세·밸류에이션·재무지표·차트)만 노출하고,
 * 4-에이전트 분석/실시간 검증/페르소나는 로그인 뒤에서만 제공한다.
 *
 * 법적 원칙(CLAUDE.md): 추천/목표가 표현 0, 면책 문구 필수, 기준 시점 명시.
 */
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { Sparkline } from "@/components/stocks/Sparkline";
import { Disclaimer } from "@/components/legal/Disclaimer";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  changeColorClass,
  fmtCompactKR,
  getPublicStock,
  isKrMarket,
  type PublicStock,
} from "@/lib/stocks";

const SITE_URL = "https://axislytics.com";

// 동적 라우트지만 ISR로 캐싱 — 첫 크롤 시 렌더 후 재사용.
export const revalidate = 3600;

type Params = { params: Promise<{ ticker: string }> };

function marketLabel(market: string): string {
  const map: Record<string, string> = {
    KOSPI: "코스피",
    KOSDAQ: "코스닥",
    NASDAQ: "나스닥",
    "S&P500": "S&P500",
  };
  return map[market] ?? market;
}

function fmtPrice(s: PublicStock): string {
  if (isKrMarket(s.market)) return `${Math.round(s.close).toLocaleString("ko-KR")}원`;
  return `$${s.close.toLocaleString("en-US", { maximumFractionDigits: 2 })}`;
}

function fmtCap(s: PublicStock): string {
  if (s.market_cap <= 0) return "-";
  if (isKrMarket(s.market)) return `${fmtCompactKR(s.market_cap)}원`;
  return `$${fmtCompactKR(s.market_cap)}`;
}

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { ticker } = await params;
  const stock = await getPublicStock(ticker);
  if (!stock) {
    return { title: "종목을 찾을 수 없습니다 | Axis", robots: { index: false } };
  }
  const title = `${stock.name}(${stock.ticker}) 주가·PER·재무 분석 | Axis`;
  const description =
    `${stock.name} ${marketLabel(stock.market)} 현재가 ${fmtPrice(stock)}, ` +
    `PER ${stock.per || "-"}·PBR ${stock.pbr || "-"}·ROE ${stock.roe || "-"}%·배당수익률 ${stock.div_yield || "-"}%. ` +
    `Axis가 리스크·성장·가치 등 6가지 관점으로 분석합니다. (투자 권유 아님)`;
  const url = `${SITE_URL}/stocks/${stock.ticker}`;
  return {
    title,
    description,
    alternates: { canonical: `/stocks/${stock.ticker}` },
    openGraph: { type: "website", locale: "ko_KR", url, title, description, siteName: "Axis" },
    twitter: { card: "summary_large_image", title, description },
  };
}

function Metric({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="flex flex-col gap-0.5 rounded-md border p-3">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="text-base font-semibold tabular-nums">{value}</span>
      {hint && <span className="text-[11px] text-muted-foreground">{hint}</span>}
    </div>
  );
}

export default async function PublicStockPage({ params }: Params) {
  const { ticker } = await params;
  const stock = await getPublicStock(ticker);
  if (!stock) notFound();

  const up = stock.change_pct > 0;
  const num = (v: number, suffix = "") => (v ? `${v}${suffix}` : "-");

  // 구조화 데이터(JSON-LD) — 검색 리치 결과용. 사실 데이터만.
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "FinancialProduct",
    name: `${stock.name} (${stock.ticker})`,
    category: "Stock",
    url: `${SITE_URL}/stocks/${stock.ticker}`,
    provider: { "@type": "Organization", name: "Axis", url: SITE_URL },
  };

  return (
    <div className="mx-auto max-w-3xl px-4 py-8 md:py-12">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />

      {/* 헤더 */}
      <nav className="mb-4 text-sm text-muted-foreground">
        <Link href="/" className="hover:underline">
          Axis
        </Link>{" "}
        / 종목 / {stock.name}
      </nav>

      <header className="mb-6">
        <div className="flex items-baseline gap-2">
          <h1 className="text-2xl font-bold">{stock.name}</h1>
          <span className="text-sm text-muted-foreground">
            {stock.ticker} · {marketLabel(stock.market)}
          </span>
        </div>
        <div className="mt-2 flex items-baseline gap-3">
          <span className="text-3xl font-bold tabular-nums">{fmtPrice(stock)}</span>
          <span className={`text-lg font-semibold tabular-nums ${changeColorClass(stock.change_pct)}`}>
            {stock.change_pct > 0 ? "+" : ""}
            {stock.change_pct}%
          </span>
        </div>
        {stock.updated_at && (
          <p className="mt-1 text-xs text-muted-foreground">
            기준 시점: {stock.updated_at} · 실시간 시세는 로그인 후 제공
          </p>
        )}
      </header>

      {/* 차트 */}
      <section className="mb-6">
        <Sparkline candles={stock.chart} up={up} />
      </section>

      {/* 핵심 지표 */}
      <section className="mb-6">
        <h2 className="mb-3 text-lg font-semibold">핵심 지표</h2>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
          <Metric label="PER" value={num(stock.per, "배")} />
          <Metric label="PBR" value={num(stock.pbr, "배")} />
          <Metric label="ROE" value={num(stock.roe, "%")} />
          <Metric label="배당수익률" value={num(stock.div_yield, "%")} />
          <Metric label="시가총액" value={fmtCap(stock)} />
          <Metric label="RSI" value={num(stock.rsi)} />
          <Metric
            label="52주 고점 대비"
            value={stock.vs_high_52w ? `${stock.vs_high_52w}%` : "-"}
          />
          <Metric
            label="52주 저점 대비"
            value={stock.vs_low_52w ? `+${stock.vs_low_52w}%` : "-"}
          />
          {stock.sector && <Metric label="섹터" value={stock.sector} />}
        </div>
      </section>

      {/* SEO 텍스트 + 전환 CTA */}
      <section className="mb-6">
        <Card>
          <CardContent className="space-y-3 p-5">
            <h2 className="text-lg font-semibold">
              {stock.name}, 6가지 관점으로 분석해보세요
            </h2>
            <p className="text-sm text-muted-foreground">
              {stock.name}({stock.ticker})의 주가·밸류에이션·재무 지표는 위와 같습니다.
              Axis는 4개의 AI 에이전트가 이 종목을 리스크 관리·성장·가치 등 6가지 투자
              관점으로 다층 분석하고, 모든 수치를 현재 시점 데이터로 재검증합니다. 추천이
              아니라, 당신의 판단을 돕는 정보 제공 도구입니다.
            </p>
            <div className="flex flex-wrap gap-2 pt-1">
              <Link
                href={`/login?next=${encodeURIComponent(`/analyze/${stock.ticker}`)}`}
                className={buttonVariants({ size: "lg" })}
              >
                심층 분석 보기 →
              </Link>
              <Link href="/pricing" className={buttonVariants({ variant: "outline", size: "lg" })}>
                요금제 보기
              </Link>
            </div>
          </CardContent>
        </Card>
      </section>

      <Disclaimer />
    </div>
  );
}
