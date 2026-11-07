"use client";

import {
  ChartCandlestick,
  Compass,
  House,
  Layers,
  ListFilter,
  Settings,
  Shield,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

import { AnalysisProgressBar } from "@/components/dashboard/AnalysisProgressBar";
import { PlanBadge } from "@/components/dashboard/PlanBadge";
import { SiteFooter } from "@/components/layout/SiteFooter";
import { UserMenu } from "@/components/layout/UserMenu";
import { StockSearch } from "@/components/stocks/StockSearch";
import { Logo } from "@/components/ui/logo";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import { useAuth } from "@/hooks/useAuth";
import { useIsAdmin } from "@/hooks/useIsAdmin";
import { useUserProfile } from "@/hooks/useUserProfile";
import { cn } from "@/lib/utils";

interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

// 모바일 하단 nav도 이 5개를 쓴다. 설정은 상단 계정 메뉴로 이동.
const NAV: NavItem[] = [
  { href: "/dashboard", label: "홈", icon: House },
  { href: "/analyze", label: "종목 분석", icon: ChartCandlestick },
  { href: "/discover", label: "종목 발견", icon: Compass },
  { href: "/screener", label: "스마트 리스트", icon: ListFilter },
  { href: "/etf", label: "ETF", icon: Layers },
];

const SETTINGS_NAV: NavItem = { href: "/settings/profile", label: "설정", icon: Settings };
const ADMIN_NAV: NavItem = { href: "/admin", label: "관리자", icon: Shield };

function isActive(href: string, pathname: string | null): boolean {
  if (!pathname) return false;
  if (href === "/dashboard") return pathname === href;
  if (href.startsWith("/settings")) return pathname.startsWith("/settings");
  return pathname.startsWith(href);
}

function SidebarLink({ item, pathname }: { item: NavItem; pathname: string | null }) {
  const active = isActive(item.href, pathname);
  const Icon = item.icon;
  return (
    <Link
      href={item.href}
      aria-current={active ? "page" : undefined}
      className={cn(
        "flex items-center gap-2.5 rounded-lg px-3 py-2.5 text-sm transition",
        active
          ? "bg-sidebar-accent font-semibold text-sidebar-accent-foreground"
          : "text-muted-foreground hover:bg-muted hover:text-foreground",
      )}
    >
      <Icon aria-hidden="true" className="size-[18px] shrink-0" />
      {item.label}
    </Link>
  );
}

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
    <div className="min-h-screen flex">
      {/* Sidebar (md+) */}
      <aside className="hidden md:flex sticky top-0 h-screen w-60 shrink-0 flex-col border-r bg-sidebar p-3">
        <Link href="/dashboard" className="mb-5 px-2.5 py-2 text-lg">
          <Logo />
        </Link>
        <nav aria-label="주 메뉴" className="flex flex-col gap-0.5">
          {NAV.map((item) => (
            <SidebarLink key={item.href} item={item} pathname={pathname} />
          ))}
        </nav>
        <div className="mt-auto flex flex-col gap-0.5 border-t pt-3">
          {isAdmin && <SidebarLink item={ADMIN_NAV} pathname={pathname} />}
          <SidebarLink item={SETTINGS_NAV} pathname={pathname} />
          <div className="px-3 pt-2">
            <PlanBadge />
          </div>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        {/* 상단바 — 어느 화면에서든 종목을 바로 찾을 수 있게 검색을 고정한다. */}
        <header className="sticky top-0 z-30 flex items-center gap-2 border-b bg-background/90 px-4 py-2 backdrop-blur md:px-6">
          <Link href="/dashboard" className="shrink-0 md:hidden" aria-label="홈">
            <Logo showName={false} />
          </Link>
          {/* 홈은 본문에 큰 검색창이 있으므로 상단에서는 뺀다. */}
          {pathname !== "/dashboard" && <StockSearch shortcut className="min-w-0 flex-1 md:max-w-md" />}
          <div className="ml-auto flex shrink-0 items-center">
            <span className="md:hidden">
              <PlanBadge compact />
            </span>
            <ThemeToggle />
            <UserMenu email={user.email} isAdmin={isAdmin} />
          </div>
        </header>

        {/* pb-24: 모바일 fixed bottom nav + safe-area 여유. md+에선 사이드바라 불필요. */}
        <main className="flex-1 p-4 pb-24 md:p-6 md:pb-6">
          <div className="mx-auto w-full max-w-5xl">
            {/* 분석 진행중 전역 표시기 (running 있을 때만 노출) */}
            <AnalysisProgressBar />
            {children}
            {/* 로그인 후에도 가격·약관·개인정보·환불 정책에 접근하도록 페이지 최하단 푸터 */}
            <SiteFooter />
          </div>
        </main>
      </div>

      {/* Mobile bottom nav — 항상 화면 하단 고정. 활성 표시 + iOS safe-area. */}
      <nav
        className="md:hidden fixed bottom-0 left-0 right-0 z-40 grid grid-cols-5 border-t bg-card/95 pt-1.5 pb-[max(0.375rem,env(safe-area-inset-bottom))] backdrop-blur"
        aria-label="모바일 주 메뉴"
      >
        {NAV.map((item) => {
          const active = isActive(item.href, pathname);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={active ? "page" : undefined}
              className={cn(
                "flex min-h-11 flex-col items-center justify-center gap-0.5 text-[11px] transition",
                active ? "font-semibold text-primary" : "text-muted-foreground",
              )}
            >
              <Icon aria-hidden="true" className="size-5" />
              <span className="whitespace-nowrap">{item.label}</span>
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
