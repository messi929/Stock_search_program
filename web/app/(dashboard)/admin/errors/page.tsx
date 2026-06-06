"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { adminApi, fmtDate } from "@/lib/admin";

const TYPE_LABELS: Record<string, string> = {
  agent_failure: "에이전트 실패",
  ai_error: "AI 오류",
  webhook_failure: "웹훅 실패",
  unhandled_5xx: "미처리 5xx",
};

export default function AdminErrorsPage() {
  const [type, setType] = useState("");

  const summary = useQuery({
    queryKey: ["admin", "errors-summary", 7],
    queryFn: () => adminApi.errorsSummary(7),
  });
  const list = useQuery({
    queryKey: ["admin", "errors", type],
    queryFn: () => adminApi.errors(type ? `?limit=100&type=${type}` : "?limit=100"),
  });

  const byType = Object.entries(summary.data?.by_type ?? {}).sort((a, b) => b[1] - a[1]);

  return (
    <div className="space-y-5">
      {/* 요약 */}
      <div className="rounded-xl ring-1 ring-foreground/10 p-4">
        <h3 className="text-sm font-semibold mb-3">
          최근 7일 에러 요약 (총 {summary.data?.total ?? 0})
        </h3>
        {byType.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            {summary.isLoading ? "집계 중..." : "에러 없음 🎉"}
          </p>
        ) : (
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => setType("")}
              className={`px-3 py-1.5 rounded-md text-sm ${
                type === "" ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"
              }`}
            >
              전체
            </button>
            {byType.map(([t, n]) => (
              <button
                key={t}
                onClick={() => setType(t)}
                className={`px-3 py-1.5 rounded-md text-sm ${
                  type === t ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"
                }`}
              >
                {TYPE_LABELS[t] ?? t} <span className="tabular-nums">({n})</span>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* 최근 에러 목록 */}
      <div className="rounded-xl ring-1 ring-foreground/10 overflow-hidden">
        <div className="px-4 py-2 bg-muted/50 text-sm font-medium">
          최근 에러 {type ? `· ${TYPE_LABELS[type] ?? type}` : ""}
        </div>
        {list.isLoading && (
          <p className="px-4 py-6 text-sm text-muted-foreground">불러오는 중...</p>
        )}
        {list.isError && (
          <p className="px-4 py-6 text-sm text-red-500">조회 실패 (권한 확인)</p>
        )}
        {list.data && (
          <table className="w-full text-sm">
            <thead className="text-muted-foreground">
              <tr className="text-left">
                <th className="px-3 py-2 font-medium">시각</th>
                <th className="px-3 py-2 font-medium">유형</th>
                <th className="px-3 py-2 font-medium hidden md:table-cell">대상</th>
                <th className="px-3 py-2 font-medium">메시지</th>
              </tr>
            </thead>
            <tbody>
              {list.data.errors.map((e) => (
                <tr key={e.id} className="border-t align-top">
                  <td className="px-3 py-2 text-muted-foreground whitespace-nowrap">
                    {fmtDate(e.created_at)}
                  </td>
                  <td className="px-3 py-2 whitespace-nowrap">
                    {TYPE_LABELS[e.type] ?? e.type}
                    {e.agent && (
                      <span className="block text-xs text-muted-foreground">{e.agent}</span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-muted-foreground hidden md:table-cell whitespace-nowrap">
                    {e.ticker || "-"}
                    {e.uid && (
                      <span className="block text-xs truncate max-w-[120px]">{e.uid}</span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-red-500/90 break-all">{e.message}</td>
                </tr>
              ))}
              {list.data.errors.length === 0 && (
                <tr>
                  <td colSpan={4} className="px-3 py-8 text-center text-muted-foreground">
                    에러 없음
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
