"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/useAuth";
import { useUserProfile } from "@/hooks/useUserProfile";
import { signOut } from "@/lib/auth-actions";

const NAV = [
  { href: "/dashboard", label: "대시보드", icon: "🏠" },
  { href: "/analyze", label: "종목 분석", icon: "🔍" },
  { href: "/watchlist/add", label: "관심 종목", icon: "⭐" },
  { href: "/screener", label: "스크리너", icon: "📊" },
  { href: "/settings/notifications", label: "알림 설정", icon: "🔔" },
];

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const { user, loading: authLoading } = useAuth();
  const { onboarded, loading: profileLoading } = useUserProfile();

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
        <Link href="/" className="text-xl font-bold mb-6 px-2">
          Axis
        </Link>
        {NAV.map((item) => (
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

      {/* Mobile top bar */}
      <header className="md:hidden flex items-center justify-between px-4 py-3 border-b">
        <Link href="/" className="text-lg font-bold">
          Axis
        </Link>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={() => signOut().then(() => router.replace("/"))}
        >
          로그아웃
        </Button>
      </header>

      <main className="flex-1 p-4 md:p-6">{children}</main>

      {/* Mobile bottom nav */}
      <nav className="md:hidden flex justify-around py-2 border-t bg-background">
        {NAV.slice(0, 4).map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className="flex flex-col items-center text-xs"
          >
            <span className="text-lg">{item.icon}</span>
            <span>{item.label}</span>
          </Link>
        ))}
      </nav>
    </div>
  );
}
