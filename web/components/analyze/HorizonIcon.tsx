import { Mountain, Scale, TrendingUp, Zap, type LucideIcon } from "lucide-react";

import type { HorizonId } from "@/types/persona";

const ICONS: Record<HorizonId, LucideIcon> = {
  short: Zap,
  short_mid: TrendingUp,
  mid: Scale,
  long: Mountain,
};

export function HorizonIcon({ id, className }: { id: HorizonId; className?: string }) {
  const Icon = ICONS[id];
  return <Icon aria-hidden="true" className={className} />;
}
