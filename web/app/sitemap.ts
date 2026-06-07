/**
 * sitemap.xml — 검색엔진 색인 대상 (Next 16 file convention).
 *
 * 정적 공개 페이지 + 전 종목 공개 페이지(/stocks/[ticker])를 동적으로 포함한다.
 * 종목 목록은 백엔드 공개 엔드포인트에서 가져오며, 실패 시 정적 페이지만 출력한다.
 * 로그인 뒤 개인화 페이지는 robots.ts에서 차단하므로 여기 포함하지 않는다.
 */
import type { MetadataRoute } from "next";

import { listPublicStocks } from "@/lib/stocks";

const SITE_URL = "https://axislytics.com";

// 종목 수가 많아 빌드 시 한 번 생성 후 하루 단위 재생성.
export const revalidate = 86400;

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const lastModified = new Date();

  const staticRoutes: MetadataRoute.Sitemap = [
    { url: `${SITE_URL}/`, lastModified, changeFrequency: "weekly", priority: 1 },
    { url: `${SITE_URL}/pricing`, lastModified, changeFrequency: "monthly", priority: 0.8 },
    { url: `${SITE_URL}/terms`, lastModified, changeFrequency: "yearly", priority: 0.3 },
    { url: `${SITE_URL}/privacy`, lastModified, changeFrequency: "yearly", priority: 0.3 },
    { url: `${SITE_URL}/refund`, lastModified, changeFrequency: "yearly", priority: 0.3 },
  ];

  const stocks = await listPublicStocks();
  const stockRoutes: MetadataRoute.Sitemap = stocks.map((s) => ({
    url: `${SITE_URL}/stocks/${encodeURIComponent(s.ticker)}`,
    lastModified,
    changeFrequency: "daily",
    priority: 0.6,
  }));

  return [...staticRoutes, ...stockRoutes];
}
