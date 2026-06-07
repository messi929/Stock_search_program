/**
 * robots.txt — 검색엔진 크롤러 접근 규칙 (Next 16 file convention).
 *
 * 공개 페이지(/, /pricing, /terms, /privacy, /refund)는 허용,
 * 로그인 뒤 개인화 영역(대시보드/분석/관리자 등)은 색인 차단(크롤 예산 낭비·로그인 월 노출 방지).
 */
import type { MetadataRoute } from "next";

const SITE_URL = "https://axislytics.com";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      disallow: [
        "/dashboard",
        "/analyze",
        "/discover",
        "/screener",
        "/history",
        "/portfolio",
        "/watchlist",
        "/settings",
        "/onboarding",
        "/admin",
        "/login",
        "/api/",
      ],
    },
    sitemap: `${SITE_URL}/sitemap.xml`,
    host: SITE_URL,
  };
}
