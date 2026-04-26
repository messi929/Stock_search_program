"use client";

/**
 * 4 에이전트 카드 공통 껍데기 — 헤더(아이콘/이름/상태) + body slot.
 */
import type { ReactNode } from "react";

import { Card, CardContent } from "@/components/ui/card";

export type AgentStatus = "pending" | "running" | "done" | "error";

const STATUS_LABEL: Record<AgentStatus, { text: string; className: string }> = {
  pending: { text: "대기", className: "text-muted-foreground" },
  running: { text: "분석 중...", className: "text-amber-500 animate-pulse" },
  done: { text: "완료", className: "text-emerald-500" },
  error: { text: "오류", className: "text-destructive" },
};

interface Props {
  icon: string;
  title: string;
  subtitle?: string;
  status: AgentStatus;
  children?: ReactNode;
}

export function AgentCardShell({ icon, title, subtitle, status, children }: Props) {
  const meta = STATUS_LABEL[status];
  return (
    <Card>
      <CardContent className="p-5 space-y-3">
        <header className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <span className="text-xl">{icon}</span>
            <div>
              <h3 className="font-semibold">{title}</h3>
              {subtitle ? (
                <p className="text-xs text-muted-foreground">{subtitle}</p>
              ) : null}
            </div>
          </div>
          <span className={`text-xs ${meta.className}`}>{meta.text}</span>
        </header>
        {children ? <div className="pt-1">{children}</div> : null}
      </CardContent>
    </Card>
  );
}
