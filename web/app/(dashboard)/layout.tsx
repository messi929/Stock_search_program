"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

import { AnalysisProgressBar } from "@/components/dashboard/AnalysisProgressBar";
import { PlanBadge } from "@/components/dashboard/PlanBadge";
import { SiteFooter } from "@/components/layout/SiteFooter";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/useAuth";
import { useIsAdmin } from "@/hooks/useIsAdmin";
import { useUserProfile } from "@/hooks/useUserProfile";
import { signOut } from "@/lib/auth-actions";

const NAV = [
  { href: "/dashboard", label: "대시보드", icon: "🏠" },
  { href: "/analyze", label: "종목 분석", icon: "🔍" },
  { href: "/discover", label: "종목 발견", icon: "🧭" },
  { href: "/screener", label: "스크리너", icon: "📊" },
  { href: "/etf", label: "ETF", icon: "🧺" },
  { href: "/settings/profile", label: "설정", icon: "⚙️" },
];

const ADMIN_NAV = { href: "/admin", label: "관리자", icon: "🛡️" };

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const { user, loading: authLoading } = useAuth();
  const { onboarded, loading: profileLoading } = useUserProfile();
  const { isAdmin } = useIsAdmin();
  // 관리자는 사이드바에 관리자 메뉴 추가 노출(모바일 하단 nav는 5개 유지).
  const sidebarNav = isAdmin ? [...NAV, ADMIN_NAV] : NAV;

  useEffect(() => {
    if (authLoading || profileLoading) return;
    if (!user) {
      const next = pathname && pathname !== "/login" ? `?next=${encodeURIComponent(pathname)}` : "";
      router.replace(`/login${next}`);
      return;
    }
    if (!onboarded) {
      router.replace("/onboarding");
    }
  }, [user, onboarded, authLoading, profileLoading, pathname, router]);

  if (authLoading || profileLoading || !user || !onboarded) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-sm text-muted-foreground">로딩 중...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col md:flex-row">
      {/* Sidebar (md+) */}
      <aside className="hidden md:flex flex-col w-56 border-r p-4 gap-1">
        <Link href="/dashboard" className="text-xl font-bold mb-6 px-2">
          Axis
        </Link>
        {sidebarNav.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className="px-3 py-2 rounded-md hover:bg-muted text-sm flex items-center gap-2"
          >
            <span>{item.icon}</span>
            <span>{item.label}</span>
          </Link>
        ))}
        <div className="mt-auto pt-4 border-t">
          <div className="px-2 pb-2">
            <PlanBadge />
          </div>
          <p className="text-xs text-muted-foreground px-2 truncate">
            {user.email}
          </p>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="mt-2 w-full justify-start"
            onClick={() => signOut().then(() => router.replace("/"))}
          >
            로그아웃
          </Button>
        </div>
      </aside>

      {/* Mobile top bar — 하단 nav는 5개 유지, 관리자 진입은 여기(관리자만 🛡️ 노출). */}
      <header className="md:hidden flex items-center justify-between px-4 py-3 border-b">
        <Link href="/dashboard" className="text-lg font-bold">
          Axis
        </Link>
        <div className="flex items-center gap-1">
          <PlanBadge compact />
          {isAdmin && (
            <Link
              href="/admin"
              aria-label="관리자"
              aria-current={pathname?.startsWith("/admin") ? "page" : undefined}
              className={`px-2 py-1 rounded-md text-lg leading-none hover:bg-muted ${
                pathname?.startsWith("/admin") ? "bg-muted" : ""
              }`}
            >
              🛡️
            </Link>
          )}
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => signOut().then(() => router.replace("/"))}
          >
            로그아웃
          </Button>
        </div>
      </header>

      {/* pb-20: 모바일 fixed bottom nav(약 60px) + safe-area 여유. md+에선 사이드바라 0. */}
      <main className="flex-1 p-4 md:p-6 pb-20 md:pb-6">
        {/* 분석 진행중 전역 표시기 (running 있을 때만 노출) */}
        <AnalysisProgressBar />
        {children}
        {/* 로그인 후에도 가격·약관·개인정보·환불 정책에 접근하도록 페이지 최하단 푸터 */}
        <SiteFooter />
      </main>

      {/* Mobile bottom nav — 항상 화면 하단 고정(긴 페이지에서도 노출). 5개 항목 + 활성 표시 + iOS safe-area. */}
      <nav
        className="md:hidden fixed bottom-0 left-0 right-0 z-40 flex justify-around py-2 pb-[max(0.5rem,env(safe-area-inset-bottom))] border-t bg-background/95 backdrop-blur"
        aria-label="모바일 주 메뉴"
      >
        {NAV.map((item) => {
          const active =
            item.href === "/dashboard"
              ? pathname === "/dashboard"
              : item.href.startsWith("/settings")
                ? pathname?.startsWith("/settings")
                : pathname?.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={active ? "page" : undefined}
              className={`flex flex-col items-center text-[11px] gap-0.5 px-2 transition ${
                active ? "text-primary font-semibold" : "text-muted-foreground"
              }`}
            >
              <span className="text-lg leading-none">{item.icon}</span>
              <span className="whitespace-nowrap">{item.label}</span>
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
