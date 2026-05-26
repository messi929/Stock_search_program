import { ImageResponse } from "next/og";

export const runtime = "edge";
export const alt = "Axis — AI 투자 분석 파트너";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function Image() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: "80px",
          background:
            "linear-gradient(135deg, #0b0f1a 0%, #131a2b 50%, #1a2540 100%)",
          color: "#ffffff",
          fontFamily: "system-ui, sans-serif",
        }}
      >
        {/* 상단 — 브랜드 */}
        <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
          <div
            style={{
              width: "56px",
              height: "56px",
              borderRadius: "14px",
              background:
                "linear-gradient(135deg, #6366f1 0%, #a855f7 100%)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: "32px",
              fontWeight: 700,
            }}
          >
            A
          </div>
          <div style={{ fontSize: "36px", fontWeight: 700, letterSpacing: "-0.02em" }}>
            Axis
          </div>
        </div>

        {/* 중앙 — 메인 카피 */}
        <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
          <div
            style={{
              fontSize: "72px",
              fontWeight: 800,
              lineHeight: 1.1,
              letterSpacing: "-0.03em",
            }}
          >
            AI 투자 분석 파트너
          </div>
          <div
            style={{
              fontSize: "32px",
              color: "#94a3b8",
              lineHeight: 1.4,
              maxWidth: "900px",
            }}
          >
            리스크·성장·가치 — 같은 종목을 3가지 관점으로 분석
          </div>
        </div>

        {/* 하단 — 면책 + URL */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            fontSize: "20px",
            color: "#64748b",
            borderTop: "1px solid #1e293b",
            paddingTop: "24px",
          }}
        >
          <div>📌 투자 권유가 아닌 정보 제공 도구입니다</div>
          <div style={{ fontWeight: 600, color: "#a855f7" }}>axislytics.com</div>
        </div>
      </div>
    ),
    { ...size }
  );
}
