"use client";

import {
  BatteryCharging,
  Bot,
  Building2,
  Cpu,
  Landmark,
  Pill,
  Ship,
  UtensilsCrossed,
  Zap,
  type LucideIcon,
} from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";

const THEME_ICONS: Record<string, { icon: LucideIcon; tint: string }> = {
  ai: { icon: Cpu, tint: "bg-tint-1/15 text-tint-1" },
  battery: { icon: BatteryCharging, tint: "bg-tint-4/15 text-tint-4" },
  bio: { icon: Pill, tint: "bg-tint-6/15 text-tint-6" },
  robot: { icon: Bot, tint: "bg-tint-3/15 text-tint-3" },
  energy: { icon: Zap, tint: "bg-tint-2/15 text-tint-2" },
  defense: { icon: Ship, tint: "bg-tint-5/15 text-tint-5" },
  kfood: { icon: UtensilsCrossed, tint: "bg-tint-6/15 text-tint-6" },
  finance: { icon: Landmark, tint: "bg-tint-1/15 text-tint-1" },
  reit: { icon: Building2, tint: "bg-tint-5/15 text-tint-5" },
};

const THEMES: Array<{ id: string; label: string; query: string }> = [
  { id: "ai", label: "AI/반도체", query: "AI·반도체 메가트렌드 1차 또는 2차 수혜주" },
  { id: "battery", label: "2차전지", query: "2차전지 소재·셀 메이커 우량주" },
  { id: "bio", label: "바이오", query: "바이오 신약 파이프라인·CDMO 글로벌 수혜주" },
  { id: "robot", label: "로봇/자동화", query: "산업용 로봇·협동로봇·자동화 수혜주" },
  { id: "energy", label: "원전/에너지", query: "원자력·재생에너지 발전 인프라 종목" },
  { id: "defense", label: "조선/방산", query: "K-방산·조선 글로벌 수주 수혜주" },
  { id: "kfood", label: "K-푸드", query: "K-푸드 해외 수출·브랜드력 보유 종목" },
  { id: "finance", label: "금융", query: "은행·보험·증권 배당 + 밸류업 수혜주" },
  { id: "reit", label: "리츠/부동산", query: "리츠·부동산 임대수익 안정 배당주" },
];

interface Props {
  onSelect: (label: string, query: string) => void;
  /** 부모가 전달하는 진행 중 상태 — 다중 클릭 차단 */
  isPending?: boolean;
}

/**
 * 큐레이션 테마 그리드 — 클릭 시 부모가 종목 발견(/discover?q=)으로 런치.
 * 자체 useDiscover()를 가지지 않음. 부모에서 debounce 처리.
 */
export function ThemesTab({ onSelect, isPending = false }: Props) {
  return (
    <Card>
      <CardContent className="p-5 space-y-3">
        <h3 className="font-semibold">큐레이션 테마</h3>
        <p className="text-sm text-muted-foreground">
          클릭 시 종목 발견에서 자동으로 검색됩니다.
        </p>
        <div className="grid grid-cols-3 gap-2">
          {THEMES.map((t) => {
            const meta = THEME_ICONS[t.id];
            const Icon = meta.icon;
            return (
            <button
              key={t.id}
              type="button"
              onClick={() => onSelect(t.label, t.query)}
              disabled={isPending}
              className="p-3 rounded-md border border-border text-sm hover:bg-muted text-center disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <span className={`mx-auto mb-1.5 flex size-9 items-center justify-center rounded-lg ${meta.tint}`}>
                <Icon aria-hidden="true" className="size-5" />
              </span>
              <div>{t.label}</div>
            </button>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
