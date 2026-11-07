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
import type { ReactNode } from "react";
import Link from "next/link";
import { notFound } from "next/navigation";

import { PriceChange } from "@/components/stocks/PriceChange";
import { StockAvatar } from "@/components/stocks/StockAvatar";
import { Range52Week, RsiMeter } from "@/components/viz/Meters";
import { Sparkline } from "@/components/stocks/Sparkline";
import { Term } from "@/components/ui/term";
import { Disclaimer } from "@/components/legal/Disclaimer";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {

  fmtMarketCapEok,
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
  return `${fmtMarketCapEok(s.market_cap)}원`;
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
    `Axis가 단기부터 장기까지 4가지 기간 관점으로 분석합니다. (투자 권유 아님)`;
  const url = `${SITE_URL}/stocks/${stock.ticker}`;
  return {
    title,
    description,
    alternates: { canonical: `/stocks/${stock.ticker}` },
    openGraph: { type: "website", locale: "ko_KR", url, title, description, siteName: "Axis" },
    twitter: { card: "summary_large_image", title, description },
  };
}

function Metric({ label, value, hint }: { label: ReactNode; value: string; hint?: string }) {
  return (
    <div className="flex flex-col gap-0.5 rounded-xl border bg-card p-3">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="text-base font-semibold tabular-nums">{value}</span>
      {hint && <span className="text-xs text-muted-foreground">{hint}</span>}
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
          <StockAvatar ticker={stock.ticker} name={stock.name} className="size-10 self-center text-base" />
          <h1 className="text-2xl font-bold">{stock.name}</h1>
          <span className="text-sm text-muted-foreground">
            {stock.ticker} · {marketLabel(stock.market)}
          </span>
        </div>
        <div className="mt-2 flex items-baseline gap-3">
          <span className="text-3xl font-bold tabular-nums">{fmtPrice(stock)}</span>
          <PriceChange pct={stock.change_pct} className="text-lg font-semibold" />
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

      {/* 가격 위치 */}
      <section className="mb-6 grid gap-5 rounded-xl border bg-card p-4 md:grid-cols-2 md:gap-8">
        <Range52Week
          close={stock.close}
          vsHigh={stock.vs_high_52w}
          vsLow={stock.vs_low_52w}
          unit={isKrMarket(stock.market) ? "원" : "달러"}
          label="최근 1년 가격대"
        />
        <RsiMeter value={stock.rsi} label={<Term id="rsi">최근 힘 (RSI)</Term>} />
      </section>

      {/* 핵심 지표 */}
      <section className="mb-6">
        <h2 className="mb-3 text-lg font-semibold">핵심 지표</h2>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
          <Metric label={<Term id="per" />} value={num(stock.per, "배")} />
          <Metric label={<Term id="pbr" />} value={num(stock.pbr, "배")} />
          <Metric label={<Term id="roe" />} value={num(stock.roe, "%")} />
          <Metric label={<Term id="div_yield" />} value={num(stock.div_yield, "%")} />
          <Metric label={<Term id="market_cap" />} value={fmtCap(stock)} />
          <Metric label={<Term id="rsi" />} value={num(stock.rsi)} />
          <Metric
            label={<Term id="vs_high_52w" />}
            value={stock.vs_high_52w ? `${stock.vs_high_52w}%` : "-"}
          />
          <Metric
            label={<Term id="vs_low_52w" />}
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
              {stock.name}, 기간별로 분석해보세요
            </h2>
            <p className="text-sm text-muted-foreground">
              {stock.name}({stock.ticker})의 주가·밸류에이션·재무 지표는 위와 같습니다.
              Axis는 단기부터 장기까지 4가지 기간 관점으로 이 종목을 분석하고, 모든 수치를
              현재 시점 데이터로 재검증합니다. 어려운 용어는 쉬운 설명과 함께 보여드려요.
            </p>
            <div className="flex flex-wrap gap-2 pt-1">
              <Link
                href={`/login?next=${encodeURIComponent(`/analyze/${stock.ticker}`)}`}
                className={buttonVariants({ size: "lg" })}
              >
                심층 분석 보기
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
