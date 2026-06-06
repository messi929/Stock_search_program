"use client";

import Link from "next/link";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { adminApi, won } from "@/lib/admin";

const AGENT_LABELS: Record<string, string> = {
  strategist: "전략가",
  event_analyst: "이벤트",
  macro_pm: "매크로",
  korean_specialist: "한국",
  validator: "검증",
  discoverer: "발견",
  research: "리서치",
  analyst: "애널리스트",
};

function currentMonth() {
  return new Date().toISOString().slice(0, 7); // YYYY-MM
}

export default function AdminUsagePage() {
  const [month, setMonth] = useState(currentMonth());
  const { data, isLoading, isError } = useQuery({
    queryKey: ["admin", "usage", month],
    queryFn: () => adminApi.usage(month),
  });

  const agents = Object.entries(data?.by_agent ?? {}).sort((a, b) => b[1] - a[1]);
  const maxAgent = agents.length ? agents[0][1] : 1;

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <label className="text-sm text-muted-foreground">조회 월</label>
        <input
          type="month"
          value={month}
          onChange={(e) => setMonth(e.target.value || currentMonth())}
          className="px-3 py-1.5 rounded-md bg-background ring-1 ring-foreground/15 text-sm"
        />
      </div>

      {isLoading && <p className="text-sm text-muted-foreground">집계 중...</p>}
      {isError && <p className="text-sm text-red-500">조회 실패 (권한 확인)</p>}

      {data && (
        <>
          {/* 합계 */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="rounded-xl bg-card ring-1 ring-foreground/10 p-4">
              <p className="text-xs text-muted-foreground">총 AI 비용</p>
              <p className="text-2xl font-bold mt-1">{won(data.totals.krw)}</p>
              <p className="text-xs text-muted-foreground mt-1">${data.totals.usd}</p>
            </div>
            <div className="rounded-xl bg-card ring-1 ring-foreground/10 p-4">
              <p className="text-xs text-muted-foreground">활성 사용자</p>
              <p className="text-2xl font-bold mt-1">{data.totals.active_users}</p>
            </div>
            <div className="rounded-xl bg-card ring-1 ring-foreground/10 p-4">
              <p className="text-xs text-muted-foreground">분석</p>
              <p className="text-2xl font-bold mt-1">{data.totals.analyses}</p>
            </div>
            <div className="rounded-xl bg-card ring-1 ring-foreground/10 p-4">
              <p className="text-xs text-muted-foreground">검증 / 발견</p>
              <p className="text-2xl font-bold mt-1">
                {data.totals.validations} / {data.totals.discoveries}
              </p>
            </div>
          </div>

          {/* 에이전트별 호출 */}
          <div className="rounded-xl ring-1 ring-foreground/10 p-4">
            <h3 className="text-sm font-semibold mb-3">에이전트별 호출</h3>
            <div className="space-y-2">
              {agents.map(([name, calls]) => (
                <div key={name} className="flex items-center gap-3 text-sm">
                  <span className="w-20 text-muted-foreground">
                    {AGENT_LABELS[name] ?? name}
                  </span>
                  <div className="flex-1 h-4 bg-muted rounded overflow-hidden">
                    <div
                      className="h-full bg-primary/70"
                      style={{ width: `${Math.max(2, (calls / maxAgent) * 100)}%` }}
                    />
                  </div>
                  <span className="w-12 text-right tabular-nums">{calls}</span>
                </div>
              ))}
              {agents.length === 0 && (
                <p className="text-sm text-muted-foreground">데이터 없음</p>
              )}
            </div>
          </div>

          {/* 고객별 Top */}
          <div className="rounded-xl ring-1 ring-foreground/10 overflow-hidden">
            <div className="px-4 py-2 bg-muted/50 text-sm font-medium">
              고객별 사용량 (비용순)
            </div>
            <table className="w-full text-sm">
              <thead className="text-muted-foreground">
                <tr className="text-left">
                  <th className="px-3 py-2 font-medium">이메일</th>
                  <th className="px-3 py-2 font-medium text-right">비용</th>
                  <th className="px-3 py-2 font-medium text-right">분석</th>
                  <th className="px-3 py-2 font-medium text-right hidden md:table-cell">검증</th>
                  <th className="px-3 py-2 font-medium text-right hidden md:table-cell">발견</th>
                </tr>
              </thead>
              <tbody>
                {data.by_user.map((u) => (
                  <tr key={u.uid} className="border-t hover:bg-muted/30">
                    <td className="px-3 py-2">
                      <Link href={`/admin/users/${u.uid}`} className="hover:underline">
                        {u.email || u.uid}
                      </Link>
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums">{won(u.krw)}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{u.analyses}</td>
                    <td className="px-3 py-2 text-right tabular-nums hidden md:table-cell">{u.validations}</td>
                    <td className="px-3 py-2 text-right tabular-nums hidden md:table-cell">{u.discoveries}</td>
                  </tr>
                ))}
                {data.by_user.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-3 py-8 text-center text-muted-foreground">
                      데이터 없음
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
