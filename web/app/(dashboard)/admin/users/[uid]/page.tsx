"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { adminApi, fmtDate } from "@/lib/admin";

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-4 py-1.5 border-b last:border-0 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className="text-right">{value}</span>
    </div>
  );
}

export default function AdminUserDetailPage() {
  const params = useParams<{ uid: string }>();
  const uid = params.uid;
  const qc = useQueryClient();
  const [note, setNote] = useState("");

  const { data, isLoading, isError } = useQuery({
    queryKey: ["admin", "user", uid],
    queryFn: () => adminApi.user(uid),
  });

  const refresh = () => qc.invalidateQueries({ queryKey: ["admin", "user", uid] });

  const suspend = useMutation({
    mutationFn: () => adminApi.suspend(uid, "관리자 정지"),
    onSuccess: refresh,
  });
  const unsuspend = useMutation({
    mutationFn: () => adminApi.unsuspend(uid),
    onSuccess: refresh,
  });
  const extend = useMutation({
    mutationFn: () => adminApi.extendTrial(uid, 7),
    onSuccess: refresh,
  });
  const saveNote = useMutation({
    mutationFn: () => adminApi.setNote(uid, note),
    onSuccess: () => {
      setNote("");
      refresh();
    },
  });

  if (isLoading) return <p className="text-sm text-muted-foreground">불러오는 중...</p>;
  if (isError || !data)
    return (
      <div className="space-y-3">
        <p className="text-sm text-red-500">사용자 조회 실패</p>
        <Link href="/admin/users" className="text-sm text-primary hover:underline">
          ← 목록으로
        </Link>
      </div>
    );

  const u = data.user;

  return (
    <div className="space-y-5">
      <Link href="/admin/users" className="text-sm text-primary hover:underline">
        ← 목록으로
      </Link>

      <div className="flex items-center gap-3 flex-wrap">
        <h2 className="text-lg font-bold">{u.email || uid}</h2>
        {u.suspended && <span className="text-xs text-red-500">정지됨</span>}
        {u.suspicious && !u.suspended && (
          <span className="text-xs text-amber-500">의심 계정</span>
        )}
      </div>

      {/* 프로필/구독 */}
      <div className="rounded-xl ring-1 ring-foreground/10 p-4">
        <Row label="UID" value={<code className="text-xs">{uid}</code>} />
        <Row label="등급" value={u.tier} />
        <Row label="가입일" value={fmtDate(u.created_at)} />
        <Row label="체험 종료" value={fmtDate(u.trial_ends_at)} />
        <Row
          label="구독 상태"
          value={`${u.subscription_status || "-"}${u.subscription_plan ? ` (${u.subscription_plan})` : ""}`}
        />
        <Row label="구독 만료/갱신" value={fmtDate(u.subscription_period_end)} />
        <Row label="LS 고객 ID" value={u.lemon_customer_id || "-"} />
        <Row label="최근 30일 고유 IP" value={data.unique_ips_30d} />
        {u.admin_note && <Row label="관리자 메모" value={u.admin_note} />}
      </div>

      {/* 관리자 액션 */}
      <div className="rounded-xl ring-1 ring-foreground/10 p-4 space-y-3">
        <h3 className="text-sm font-semibold">관리자 액션</h3>
        <div className="flex flex-wrap gap-2">
          {u.suspended ? (
            <Button size="sm" variant="outline" onClick={() => unsuspend.mutate()} disabled={unsuspend.isPending}>
              정지 해제
            </Button>
          ) : (
            <Button size="sm" variant="destructive" onClick={() => suspend.mutate()} disabled={suspend.isPending}>
              계정 정지
            </Button>
          )}
          <Button size="sm" variant="outline" onClick={() => extend.mutate()} disabled={extend.isPending}>
            체험 7일 연장
          </Button>
        </div>
        <div className="flex gap-2">
          <input
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="관리자 메모 입력"
            className="flex-1 px-3 py-1.5 rounded-md bg-background ring-1 ring-foreground/15 text-sm"
          />
          <Button size="sm" onClick={() => saveNote.mutate()} disabled={!note.trim() || saveNote.isPending}>
            메모 저장
          </Button>
        </div>
      </div>

      {/* 로그인 이력 */}
      <div className="rounded-xl ring-1 ring-foreground/10 overflow-hidden">
        <div className="px-4 py-2 bg-muted/50 text-sm font-medium">최근 로그인</div>
        <table className="w-full text-sm">
          <tbody>
            {data.login_history.slice(0, 15).map((l, i) => (
              <tr key={i} className="border-t">
                <td className="px-3 py-1.5 text-muted-foreground">{fmtDate(l.timestamp)}</td>
                <td className="px-3 py-1.5">{l.ip}</td>
                <td className="px-3 py-1.5 text-muted-foreground truncate max-w-[260px] hidden md:table-cell">
                  {l.user_agent}
                </td>
              </tr>
            ))}
            {data.login_history.length === 0 && (
              <tr>
                <td className="px-3 py-4 text-center text-muted-foreground">기록 없음</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <p className="text-xs text-muted-foreground">
        활성 세션 {data.active_sessions.length}개
      </p>
    </div>
  );
}
