"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

import { useIsAdmin } from "@/hooks/useIsAdmin";

const TABS = [
  { href: "/admin", label: "개요" },
  { href: "/admin/funnel", label: "퍼널" },
  { href: "/admin/users", label: "사용자" },
  { href: "/admin/usage", label: "사용량" },
  { href: "/admin/revenue", label: "수입" },
  { href: "/admin/errors", label: "에러" },
  { href: "/admin/maintenance", label: "점검 공지" },
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { isAdmin, loading } = useIsAdmin();

  // 서버도 403으로 막지만, 비관리자는 화면 진입 자체를 차단(이중 방어).
  useEffect(() => {
    if (!loading && !isAdmin) router.replace("/dashboard");
  }, [loading, isAdmin, router]);

  if (loading) {
    return (
      <div className="py-20 text-center text-sm text-muted-foreground">
        권한 확인 중...
      </div>
    );
  }
  if (!isAdmin) return null;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">관리자 콘솔</h1>
        <p className="text-sm text-muted-foreground mt-1">
          고객·사용량·수입·에러 모니터링
        </p>
      </div>

      {/* 서브 탭 */}
      <nav className="flex gap-1 border-b overflow-x-auto">
        {TABS.map((t) => {
          const active =
            t.href === "/admin"
              ? pathname === "/admin"
              : pathname?.startsWith(t.href);
          return (
            <Link
              key={t.href}
              href={t.href}
              className={`px-4 py-2 text-sm whitespace-nowrap border-b-2 -mb-px transition ${
                active
                  ? "border-primary text-primary font-semibold"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              {t.label}
            </Link>
          );
        })}
      </nav>

      <div>{children}</div>
    </div>
  );
}
