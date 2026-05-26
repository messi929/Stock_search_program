import type { Metadata } from "next";
import "./globals.css";

import { Providers } from "./providers";

const SITE_URL = "https://axislytics.com";
const SITE_TITLE = "Axis — AI 투자 분석 파트너";
const SITE_DESC =
  "리스크·성장·가치 3가지 원칙으로 같은 종목을 다르게 분석합니다. " +
  "투자 권유가 아닌 정보 제공 도구입니다.";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: SITE_TITLE,
  description: SITE_DESC,
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    locale: "ko_KR",
    url: SITE_URL,
    siteName: "Axis",
    title: SITE_TITLE,
    description: SITE_DESC,
    // og:image는 app/opengraph-image.tsx에서 자동 생성 (Next 동적 OG).
  },
  twitter: {
    card: "summary_large_image",
    title: SITE_TITLE,
    description: SITE_DESC,
  },
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ko" className="dark h-full antialiased">
      <body className="min-h-full flex flex-col bg-background text-foreground">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
