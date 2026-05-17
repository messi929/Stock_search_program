/**
 * 404 — Next.js 기본 영문 페이지 대체. Axis 다크 테마 + 한국어.
 */
import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";

export default function NotFound() {
  return (
    <main className="min-h-screen flex flex-col items-center justify-center px-6 text-center">
      <p className="text-7xl font-bold text-amber-500/80">404</p>
      <h1 className="mt-4 text-2xl font-semibold">페이지를 찾을 수 없습니다</h1>
      <p className="mt-2 text-sm text-muted-foreground max-w-sm">
        주소를 다시 확인하거나, 아래 링크로 이동해주세요.
      </p>
      <div className="mt-8 flex flex-wrap justify-center gap-3">
        <Link href="/" className={buttonVariants({ size: "lg" })}>
          홈으로
        </Link>
        <Link
          href="/dashboard"
          className={buttonVariants({ size: "lg", variant: "outline" })}
        >
          대시보드
        </Link>
      </div>
    </main>
  );
}
