import type { Metadata } from "next";
import "./globals.css";

import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "Axis — AI 투자 분석 파트너",
  description:
    "리스크·성장·가치 3가지 원칙으로 같은 종목을 다르게 분석합니다. " +
    "투자 권유가 아닌 정보 제공 도구입니다.",
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
