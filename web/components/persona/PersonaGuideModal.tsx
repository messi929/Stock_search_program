"use client";

/**
 * "각 페르소나는 어떻게 다른가요?" 도움말 모달.
 *
 * 사용자가 6 페르소나의 차이를 한 화면에서 비교할 수 있도록 카드형 그리드.
 * 모바일은 1열, 태블릿 2열, 데스크탑 3열.
 */

import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { PERSONA_META } from "@/types/persona";

const TIME_HORIZON_LABEL = {
  short: "단기 (1~3개월)",
  medium: "중기 (3개월~1년)",
  long: "장기 (1년+)",
} as const;

const GROUP_LABEL = {
  strategist: "관점 기반",
  data_driven: "데이터 기반",
} as const;

export function PersonaGuideModal() {
  const [open, setOpen] = useState(false);

  return (
    <>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        className="text-xs text-muted-foreground"
        onClick={() => setOpen(true)}
      >
        페르소나 가이드 ❓
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-3xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>6 페르소나 가이드</DialogTitle>
          <DialogDescription>
            각 페르소나는 서로 다른 데이터와 관점으로 같은 종목을 분석합니다.
            여러 페르소나를 비교해 보세요.
          </DialogDescription>
        </DialogHeader>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 pt-2">
          {PERSONA_META.map((p) => (
            <div
              key={p.id}
              className="border rounded-lg p-3 bg-muted/20 hover:bg-muted/40 transition"
            >
              <div className="flex items-start justify-between mb-2">
                <div className="text-2xl">{p.icon}</div>
                <span className="text-[10px] text-muted-foreground">
                  {GROUP_LABEL[p.group]}
                </span>
              </div>
              <div className="font-semibold">{p.name}</div>
              <div className="text-sm text-muted-foreground mt-1">{p.tagline}</div>
              <div className="text-[11px] text-muted-foreground mt-2">
                ⏱ {TIME_HORIZON_LABEL[p.time_horizon]}
              </div>
            </div>
          ))}
        </div>

        <div className="mt-4 text-xs text-muted-foreground border-t pt-3">
          <p>
            <strong>관점 기반</strong> 페르소나(블랙록/ARK/그레이엄)는 동일한 데이터를
            서로 다른 투자 철학으로 해석합니다.
          </p>
          <p className="mt-1">
            <strong>데이터 기반</strong> 페르소나(이벤트/매크로/한국 시장)는 각자
            특화된 데이터셋(이벤트 캘린더 / 매크로 사이클 / 한국 시장 구조)으로
            분석합니다.
          </p>
        </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
