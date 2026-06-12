/**
 * 종목별 동적 OG 카드 (/stocks/[ticker]) — 카톡·Threads·카페에 링크 공유 시 뜨는 미리보기.
 *
 * 분배의 기본기: 링크만 붙여도 "종목명 + 현재가 + 핵심지표 + Axis" 브랜드 카드가 뜸.
 * 법적 원칙(CLAUDE.md): 추천/목표가 표현 0, "투자 권유 아님" 명시.
 * 색상은 한국식(상승=빨강, 하락=파랑), 미국 종목은 미국식(상승=초록).
 */
import { ImageResponse } from "next/og";

import { loadKoreanFont } from "@/lib/og-font";
import { getPublicStock, isKrMarket, type PublicStock } from "@/lib/stocks";

export const alt = "Axis 종목 분석 카드";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

const MARKET_LABEL: Record<string, string> = {
  KOSPI: "코스피",
  KOSDAQ: "코스닥",
  NASDAQ: "나스닥",
  "S&P500": "S&P500",
};

function fmtPrice(s: PublicStock): string {
  if (isKrMarket(s.market))
    return `${Math.round(s.close).toLocaleString("ko-KR")}원`;
  return `$${s.close.toLocaleString("en-US", { maximumFractionDigits: 2 })}`;
}

/** 등락 색상 — KR: 상승 빨강/하락 파랑, US: 상승 초록/하락 빨강. */
function changeColor(s: PublicStock): string {
  const up = s.change_pct > 0;
  const down = s.change_pct < 0;
  if (isKrMarket(s.market)) {
    if (up) return "#ef4444";
    if (down) return "#3b82f6";
  } else {
    if (up) return "#22c55e";
    if (down) return "#ef4444";
  }
  return "#94a3b8";
}

export default async function Image({
  params,
}: {
  params: Promise<{ ticker: string }>;
}) {
  const { ticker } = await params;
  const stock = await getPublicStock(ticker);

  // satori는 한글 글리프가 없으므로 렌더 텍스트를 서브셋해 폰트를 로드한다.
  const fontFor = async (text: string) => {
    const data = await loadKoreanFont(text);
    return data
      ? [{ name: "NotoKR", data, weight: 700 as const, style: "normal" as const }]
      : undefined;
  };
  const FONT_FAMILY = "NotoKR, system-ui, sans-serif";

  // 종목 조회 실패 → 일반 브랜드 카드로 폴백(빈 카드 방지).
  if (!stock) {
    const fallbackText = "Axis — AI 투자 분석";
    return new ImageResponse(
      (
        <div
          style={{
            width: "100%",
            height: "100%",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            background: "linear-gradient(135deg, #0b0f1a 0%, #1a2540 100%)",
            color: "#fff",
            fontSize: 72,
            fontWeight: 800,
            fontFamily: FONT_FAMILY,
          }}
        >
          {fallbackText}
        </div>
      ),
      { ...size, fonts: await fontFor(fallbackText) }
    );
  }

  const sign = stock.change_pct > 0 ? "+" : "";
  const market = MARKET_LABEL[stock.market] ?? stock.market;
  const num = (v: number, suffix = "") => (v ? `${v}${suffix}` : "-");

  const metrics: { label: string; value: string }[] = [
    { label: "PER", value: num(stock.per, "배") },
    { label: "PBR", value: num(stock.pbr, "배") },
    { label: "ROE", value: num(stock.roe, "%") },
    { label: "배당", value: num(stock.div_yield, "%") },
  ];

  const HOOK = "AI 4명이 리스크·성장·가치로 분석 — 추천은 안 합니다";
  // 카드에 렌더되는 모든 문자열 → 폰트 서브셋 텍스트.
  const subsetText =
    `Axis${stock.name}${market}${stock.ticker}${fmtPrice(stock)}${sign}${stock.change_pct}%` +
    metrics.map((m) => m.label + m.value).join("") +
    HOOK +
    "axislytics.com·";
  const fonts = await fontFor(subsetText);

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: "72px 80px",
          background:
            "linear-gradient(135deg, #0b0f1a 0%, #131a2b 50%, #1a2540 100%)",
          color: "#ffffff",
          fontFamily: FONT_FAMILY,
        }}
      >
        {/* 상단 — 브랜드 + 시장 */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
            <div
              style={{
                width: "48px",
                height: "48px",
                borderRadius: "12px",
                background: "linear-gradient(135deg, #6366f1 0%, #a855f7 100%)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: "28px",
                fontWeight: 700,
              }}
            >
              A
            </div>
            <div style={{ fontSize: "30px", fontWeight: 700 }}>Axis</div>
          </div>
          <div style={{ fontSize: "26px", color: "#94a3b8" }}>
            {`${market} · ${stock.ticker}`}
          </div>
        </div>

        {/* 중앙 — 종목명 + 가격 */}
        <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
          <div
            style={{
              fontSize: "84px",
              fontWeight: 800,
              lineHeight: 1.05,
              letterSpacing: "-0.03em",
            }}
          >
            {stock.name}
          </div>
          <div style={{ display: "flex", alignItems: "baseline", gap: "20px" }}>
            <span style={{ fontSize: "52px", fontWeight: 700 }}>
              {fmtPrice(stock)}
            </span>
            <span
              style={{
                fontSize: "40px",
                fontWeight: 700,
                color: changeColor(stock),
              }}
            >
              {`${sign}${stock.change_pct}%`}
            </span>
          </div>

          {/* 핵심 지표 4종 */}
          <div style={{ display: "flex", gap: "16px", marginTop: "12px" }}>
            {metrics.map((m) => (
              <div
                key={m.label}
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: "2px",
                  padding: "14px 22px",
                  borderRadius: "12px",
                  background: "rgba(255,255,255,0.05)",
                  border: "1px solid rgba(255,255,255,0.08)",
                }}
              >
                <span style={{ fontSize: "20px", color: "#94a3b8" }}>
                  {m.label}
                </span>
                <span style={{ fontSize: "30px", fontWeight: 700 }}>
                  {m.value}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* 하단 — 후크 + 면책 */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            fontSize: "22px",
            borderTop: "1px solid #1e293b",
            paddingTop: "24px",
          }}
        >
          <div style={{ color: "#c4b5fd", fontWeight: 600 }}>{HOOK}</div>
          <div style={{ color: "#64748b" }}>axislytics.com</div>
        </div>
      </div>
    ),
    { ...size, fonts }
  );
}
