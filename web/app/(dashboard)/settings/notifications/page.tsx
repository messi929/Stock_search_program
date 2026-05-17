"use client";

/**
 * /settings/notifications — 알림 설정.
 *
 * MVP: opt-in 토글 + 이메일 override만 수집. 실제 발송은 v1.1 (Mailgun + Cloud
 * Scheduler 잡 도입 후). UI 상단에 "준비 중" 배너로 명시.
 */
import { useEffect, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";

import { Disclaimer } from "@/components/legal/Disclaimer";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  useNotificationPreferences,
  useSaveNotificationPreferences,
} from "@/hooks/useNotificationPreferences";

export default function NotificationsSettingsPage() {
  const { data, isLoading, isError } = useNotificationPreferences();
  const save = useSaveNotificationPreferences();

  const [daily, setDaily] = useState(false);
  const [entry, setEntry] = useState(false);
  const [emailOverride, setEmailOverride] = useState("");
  const [dirty, setDirty] = useState(false);

  // 서버 값 도착 시 폼에 반영 (한 번만)
  useEffect(() => {
    if (!data) return;
    setDaily(!!data.preferences.daily_briefing_enabled);
    setEntry(!!data.preferences.entry_point_alerts_enabled);
    setEmailOverride(data.preferences.email_override ?? "");
    setDirty(false);
  }, [data]);

  const markDirty = () => setDirty(true);

  const handleSave = async () => {
    const trimmed = emailOverride.trim();
    if (trimmed && (!trimmed.includes("@") || !trimmed.split("@").pop()?.includes("."))) {
      toast.error("이메일 형식이 올바르지 않습니다.");
      return;
    }
    try {
      await save.mutateAsync({
        daily_briefing_enabled: daily,
        entry_point_alerts_enabled: entry,
        email_override: trimmed || null,
      });
      toast.success("저장되었습니다.");
      setDirty(false);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "저장 실패";
      toast.error(msg);
    }
  };

  if (isLoading) {
    return <p className="text-sm text-muted-foreground">설정 로딩 중...</p>;
  }
  if (isError || !data) {
    return (
      <Card>
        <CardContent className="p-6 text-center">
          <p className="text-sm text-muted-foreground">설정을 불러오지 못했습니다.</p>
        </CardContent>
      </Card>
    );
  }

  const recipient = emailOverride.trim() || data.user_email || "(이메일 미등록)";

  return (
    <div className="max-w-2xl space-y-6">
      <header className="space-y-1">
        <Link
          href="/dashboard"
          className="text-sm text-muted-foreground hover:text-foreground"
        >
          ← 대시보드
        </Link>
        <h1 className="text-2xl font-bold">🔔 알림 설정</h1>
        <p className="text-sm text-muted-foreground">
          관심 종목 진입선 도달, 일일 시황 등을 이메일로 받아봅니다.
        </p>
      </header>

      <Card className="border-amber-500/30 bg-amber-500/5">
        <CardContent className="p-4 text-sm space-y-1">
          <p className="font-medium">⏳ 알림 발송은 v1.1 도입 예정입니다</p>
          <p className="text-xs text-muted-foreground">
            지금은 받을 항목을 미리 선택해두시면, 발송 시스템이 켜지는 즉시 자동으로 수신됩니다.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-6 space-y-5">
          <ToggleRow
            title="📰 일일 시황 브리핑"
            desc="매일 오전 7시(KST), 시장 분위기·주요 뉴스·관심 종목 요약."
            value={daily}
            onChange={(v) => {
              setDaily(v);
              markDirty();
            }}
          />
          <ToggleRow
            title="🎯 진입선 도달 알림"
            desc="관심 종목에 저장한 1차/2차/3차 관찰 구간에 가격이 도달하면 즉시 발송."
            value={entry}
            onChange={(v) => {
              setEntry(v);
              markDirty();
            }}
          />

          <div className="space-y-2 pt-3 border-t">
            <label htmlFor="email-override" className="text-sm font-medium">
              수신 이메일 (선택)
            </label>
            <p className="text-xs text-muted-foreground">
              비우면 로그인 이메일로 발송됩니다.
            </p>
            <Input
              id="email-override"
              type="email"
              value={emailOverride}
              onChange={(e) => {
                setEmailOverride(e.target.value);
                markDirty();
              }}
              placeholder={data.user_email ?? "you@example.com"}
              maxLength={200}
            />
            <p className="text-xs text-muted-foreground">
              현재 수신 주소: <span className="font-medium">{recipient}</span>
            </p>
          </div>

          <div className="flex gap-2 pt-3 border-t">
            <Button onClick={handleSave} disabled={!dirty || save.isPending}>
              {save.isPending ? "저장 중..." : "저장"}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Disclaimer />
    </div>
  );
}

function ToggleRow({
  title,
  desc,
  value,
  onChange,
}: {
  title: string;
  desc: string;
  value: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <div className="flex items-start justify-between gap-4">
      <div className="flex-1 space-y-0.5">
        <p className="font-medium text-sm">{title}</p>
        <p className="text-xs text-muted-foreground">{desc}</p>
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={value}
        aria-label={title}
        onClick={() => onChange(!value)}
        className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500 ${
          value ? "bg-amber-500" : "bg-muted"
        }`}
      >
        <span
          className={`inline-block h-5 w-5 transform rounded-full bg-white transition ${
            value ? "translate-x-5" : "translate-x-0.5"
          }`}
        />
      </button>
    </div>
  );
}
