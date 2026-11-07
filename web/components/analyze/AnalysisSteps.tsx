"use client";

import { Check, LoaderCircle, X } from "lucide-react";

import type { StrategistStatus } from "@/store/analysisStore";
import { cn } from "@/lib/utils";

const STEPS: { key: keyof StrategistStatus; label: string }[] = [
  { key: "research", label: "시장 조사" },
  { key: "analyst", label: "데이터 해석" },
  { key: "validator", label: "수치 검증" },
  { key: "strategist", label: "종합 정리" },
];

/** 1분 안팎의 분석 대기 중 지금 어느 단계인지 보여준다. */
export function AnalysisSteps({ status }: { status: StrategistStatus }) {
  return (
    <ol className="grid grid-cols-4 gap-1" aria-label="분석 진행 단계">
      {STEPS.map((step, i) => {
        const s = status[step.key];
        return (
          <li key={step.key} className="relative flex flex-col items-center gap-1.5 text-center">
            {i > 0 && (
              <span
                aria-hidden="true"
                className={cn(
                  "absolute top-3.5 right-[calc(50%+1.25rem)] left-[calc(-50%+1.25rem)] h-0.5 rounded-full",
                  s === "pending" ? "bg-border" : "bg-primary/50",
                )}
              />
            )}
            <span
              className={cn(
                "flex size-7 items-center justify-center rounded-full text-xs font-bold tabular-nums",
                s === "done" && "bg-primary text-primary-foreground",
                s === "running" && "bg-accent text-accent-foreground ring-2 ring-primary/40",
                s === "error" && "bg-destructive/15 text-destructive",
                s === "pending" && "bg-muted text-muted-foreground",
              )}
            >
              {s === "done" ? (
                <Check aria-label="완료" className="size-4" />
              ) : s === "running" ? (
                <LoaderCircle aria-label="진행 중" className="size-4 animate-spin" />
              ) : s === "error" ? (
                <X aria-label="오류" className="size-4" />
              ) : (
                i + 1
              )}
            </span>
            <span className={cn("text-xs", s === "pending" ? "text-muted-foreground" : "font-medium")}>
              {step.label}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
