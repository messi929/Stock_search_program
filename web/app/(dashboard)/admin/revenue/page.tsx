"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";

import { adminApi, fmtDate, won } from "@/lib/admin";

export default function AdminRevenuePage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["admin", "revenue"],
    queryFn: adminApi.revenue,
  });

  return (
    <div className="space-y-5">
      {isLoading && <p className="text-sm text-muted-foreground">불러오는 중...</p>}
      {isError && <p className="text-sm text-red-500">조회 실패 (권한 확인)</p>}

      {data && (
        <>
          <p className="text-xs text-muted-foreground">
            ※ 수입은 코드 상수 가격(월 {won(data.prices.monthly)} · 연 {won(data.prices.yearly)})
            기준 <strong>추정치</strong>입니다. 환불·프로모·세금 등으로 실제 정산과 차이가 있을 수 있습니다.
          </p>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="rounded-xl bg-card ring-1 ring-foreground/10 p-4">
              <p className="text-xs text-muted-foreground">MRR (월 환산)</p>
              <p className="text-2xl font-bold mt-1">{won(data.mrr_krw)}</p>
            </div>
            <div className="rounded-xl bg-card ring-1 ring-foreground/10 p-4">
              <p className="text-xs text-muted-foreground">ARR (연 환산)</p>
              <p className="text-2xl font-bold mt-1">{won(data.arr_krw)}</p>
            </div>
            <div className="rounded-xl bg-card ring-1 ring-foreground/10 p-4">
              <p className="text-xs text-muted-foreground">활성 구독</p>
              <p className="text-2xl font-bold mt-1">{data.active_subscriptions}</p>
              <p className="text-xs text-muted-foreground mt-1">
                월 {data.by_plan.monthly} · 연 {data.by_plan.yearly}
              </p>
            </div>
            <div className="rounded-xl bg-card ring-1 ring-foreground/10 p-4">
              <p className="text-xs text-muted-foreground">체험 중 / 해지 예정</p>
              <p className="text-2xl font-bold mt-1">
                {data.trial_active} / {data.cancel_scheduled}
              </p>
            </div>
          </div>

          {/* 갱신/만료 예정 */}
          <div className="rounded-xl ring-1 ring-foreground/10 overflow-hidden">
            <div className="px-4 py-2 bg-muted/50 text-sm font-medium">
              향후 30일 갱신·만료 예정 ({data.upcoming_renewals.length})
            </div>
            <table className="w-full text-sm">
              <thead className="text-muted-foreground">
                <tr className="text-left">
                  <th className="px-3 py-2 font-medium">이메일</th>
                  <th className="px-3 py-2 font-medium">플랜</th>
                  <th className="px-3 py-2 font-medium">예정일</th>
                  <th className="px-3 py-2 font-medium">상태</th>
                </tr>
              </thead>
              <tbody>
                {data.upcoming_renewals.map((r) => (
                  <tr key={r.uid} className="border-t hover:bg-muted/30">
                    <td className="px-3 py-2">
                      <Link href={`/admin/users/${r.uid}`} className="hover:underline">
                        {r.email || r.uid}
                      </Link>
                    </td>
                    <td className="px-3 py-2">{r.plan || "-"}</td>
                    <td className="px-3 py-2 text-muted-foreground">{fmtDate(r.period_end)}</td>
                    <td className="px-3 py-2">
                      {r.cancel_at_period_end ? (
                        <span className="text-red-500">해지 예정</span>
                      ) : (
                        <span className="text-muted-foreground">갱신 예정</span>
                      )}
                    </td>
                  </tr>
                ))}
                {data.upcoming_renewals.length === 0 && (
                  <tr>
                    <td colSpan={4} className="px-3 py-8 text-center text-muted-foreground">
                      30일 내 예정 없음
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
