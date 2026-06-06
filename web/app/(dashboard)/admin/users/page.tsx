"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { adminApi, fmtDate, type AdminUser } from "@/lib/admin";

const FILTERS = [
  { key: "", label: "전체" },
  { key: "pro", label: "Pro" },
  { key: "free", label: "Free" },
  { key: "trial", label: "체험" },
  { key: "suspicious", label: "의심" },
  { key: "suspended", label: "정지" },
];

function tierBadge(u: AdminUser) {
  if (u.suspended) return <span className="text-red-500">정지</span>;
  if (u.tier === "pro") return <span className="text-primary font-medium">Pro</span>;
  return <span className="text-muted-foreground">Free</span>;
}

function UsersInner() {
  const sp = useSearchParams();
  const [filter, setFilter] = useState(sp.get("filter") ?? "");
  const [q, setQ] = useState("");

  const { data, isLoading, isError } = useQuery({
    queryKey: ["admin", "users", filter],
    queryFn: () => adminApi.users(filter),
  });

  const rows = useMemo(() => {
    const all = data?.users ?? [];
    if (!q.trim()) return all;
    const lower = q.trim().toLowerCase();
    return all.filter((u) => u.email.toLowerCase().includes(lower));
  }, [data, q]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            className={`px-3 py-1.5 rounded-md text-sm transition ${
              filter === f.key
                ? "bg-primary text-primary-foreground"
                : "bg-muted hover:bg-muted/70 text-muted-foreground"
            }`}
          >
            {f.label}
          </button>
        ))}
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="이메일 검색"
          className="ml-auto px-3 py-1.5 rounded-md bg-background ring-1 ring-foreground/15 text-sm w-48"
        />
      </div>

      {isLoading && <p className="text-sm text-muted-foreground">불러오는 중...</p>}
      {isError && <p className="text-sm text-red-500">조회 실패 (권한 확인)</p>}

      {!isLoading && !isError && (
        <div className="rounded-xl ring-1 ring-foreground/10 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-muted/50 text-muted-foreground">
              <tr className="text-left">
                <th className="px-3 py-2 font-medium">이메일</th>
                <th className="px-3 py-2 font-medium">등급</th>
                <th className="px-3 py-2 font-medium hidden md:table-cell">구독</th>
                <th className="px-3 py-2 font-medium hidden md:table-cell">가입일</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((u) => (
                <tr key={u.uid} className="border-t hover:bg-muted/30">
                  <td className="px-3 py-2">
                    <Link href={`/admin/users/${u.uid}`} className="hover:underline">
                      {u.email || u.uid}
                    </Link>
                    {u.suspicious && !u.suspended && (
                      <span className="ml-2 text-xs text-amber-500">의심</span>
                    )}
                  </td>
                  <td className="px-3 py-2">{tierBadge(u)}</td>
                  <td className="px-3 py-2 hidden md:table-cell text-muted-foreground">
                    {u.subscription_status || "-"}
                    {u.subscription_plan ? ` (${u.subscription_plan})` : ""}
                  </td>
                  <td className="px-3 py-2 hidden md:table-cell text-muted-foreground">
                    {fmtDate(u.created_at)}
                  </td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr>
                  <td colSpan={4} className="px-3 py-8 text-center text-muted-foreground">
                    결과 없음
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
      <p className="text-xs text-muted-foreground">{rows.length}명 표시</p>
    </div>
  );
}

export default function AdminUsersPage() {
  return (
    <Suspense fallback={<p className="text-sm text-muted-foreground">불러오는 중...</p>}>
      <UsersInner />
    </Suspense>
  );
}
