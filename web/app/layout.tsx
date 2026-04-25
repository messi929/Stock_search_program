import type { Metadata } from "next";
import "./globals.css";

import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "Axis — AI 투자 분석 파트너",
  description:
    "블랙록처럼 분석합니다. ARK처럼 미래를 봅니다. 그레이엄처럼 가치를 찾습니다. " +
    "투자 권유가 아닌 정보 제공 도구입니다.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ko" className="h-full antialiased">
      <body className="min-h-full flex flex-col bg-background text-foreground">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
