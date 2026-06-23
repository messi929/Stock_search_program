"use client";

/**
 * 관리자 — 점검/이용 제한 공지 설정.
 * 켜기/끄기 + 시작·종료 시각 + 메시지 → PUT /api/admin/maintenance.
 * 전 사용자 상단 배너(MaintenanceBanner)에 즉시 반영(공개 GET /api/maintenance).
 */
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { adminApi } from "@/lib/admin";

export default function AdminMaintenancePage() {
  const { data, isLoading, refetch } = useQuery({
    queryKey: ["admin", "maintenance"],
    queryFn: adminApi.maintenance,
  });

  const [enabled, setEnabled] = useState(false);
  const [startsAt, setStartsAt] = useState("");
  const [endsAt, setEndsAt] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!data) return;
    setEnabled(!!data.enabled);
    setStartsAt(data.starts_at || "");
    setEndsAt(data.ends_at || "");
    setMessage(data.message || "");
  }, [data]);

  const save = async () => {
    setBusy(true);
    try {
      await adminApi.setMaintenance({
        enabled,
        starts_at: startsAt,
        ends_at: endsAt,
        message,
      });
      toast.success(enabled ? "점검 공지 켜짐 — 전 사용자에게 배너 노출" : "점검 공지 꺼짐");
      refetch();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "저장 실패");
    } finally {
      setBusy(false);
    }
  };

  if (isLoading) {
    return <p className="text-sm text-muted-foreground">로딩 중...</p>;
  }

  const previewWindow =
    startsAt || endsAt
      ? `점검 시간 ${startsAt ? new Date(startsAt).toLocaleString("ko-KR", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "—"} ~ ${endsAt ? new Date(endsAt).toLocaleString("ko-KR", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "—"}`
      : "";

  return (
    <div className="max-w-2xl space-y-5">
      <div>
        <h2 className="font-semibold">점검 / 이용 제한 공지</h2>
        <p className="text-sm text-muted-foreground mt-1">
          켜면 전 사용자 상단에 배너가 노출됩니다(비차단 — 서비스는 계속 동작). 종료 시각이
          지나면 자동으로 사라집니다.
        </p>
      </div>

      {/* 자동 AI 헬스(합성 핑) — 수동 공지와 독립. Claude API 장애 시 자동 배너. */}
      <div className="rounded-md border px-4 py-2.5 text-sm flex items-center gap-2">
        <span className="text-muted-foreground">AI API 자동 감지:</span>
        {data?.ai_degraded ? (
          <span className="font-medium text-red-500">
            🔴 장애 감지{data?.ai_reason ? ` — ${data.ai_reason}` : ""} (자동 배너 노출 중)
          </span>
        ) : (
          <span className="font-medium text-emerald-500">🟢 정상</span>
        )}
        <span className="ml-auto text-[11px] text-muted-foreground">
          ~4분마다 합성 핑 · 장애 시 자동 배너, 복구 시 자동 해제
        </span>
      </div>

      {/* 미리보기 */}
      {enabled && (
        <div className="rounded-md bg-amber-500/15 border border-amber-500/40 text-amber-200 px-4 py-2 text-sm text-center">
          <span className="font-semibold">🛠 점검 안내</span>
          {previewWindow && <span className="mx-1.5 font-medium">· {previewWindow}</span>}
          <span>
            {message ? ` · ${message}` : " · 점검 중 일부 기능 이용이 제한될 수 있습니다."}
          </span>
        </div>
      )}

      <div className="space-y-4 rounded-lg border p-4">
        {/* 켜기/끄기 */}
        <label className="flex items-center gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={enabled}
            onChange={(e) => setEnabled(e.target.checked)}
            className="h-4 w-4"
          />
          <span className="text-sm font-medium">
            공지 배너 표시 {enabled ? "(켜짐)" : "(꺼짐)"}
          </span>
        </label>

        {/* 시작·종료 */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-muted-foreground">시작 시각</label>
            <Input
              type="datetime-local"
              value={startsAt}
              onChange={(e) => setStartsAt(e.target.value)}
            />
          </div>
          <div>
            <label className="text-xs text-muted-foreground">종료 시각 (지나면 자동 숨김)</label>
            <Input
              type="datetime-local"
              value={endsAt}
              onChange={(e) => setEndsAt(e.target.value)}
            />
          </div>
        </div>

        {/* 메시지 */}
        <div>
          <label className="text-xs text-muted-foreground">안내 메시지 (선택)</label>
          <Input
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="예: 서버 점검으로 AI 분석 이용이 일시 제한됩니다."
            maxLength={500}
          />
        </div>

        <div className="flex justify-end">
          <Button type="button" onClick={save} disabled={busy}>
            {busy ? "저장 중..." : "💾 저장 (즉시 반영)"}
          </Button>
        </div>
      </div>
    </div>
  );
}
