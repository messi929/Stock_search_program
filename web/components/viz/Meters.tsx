/**
 * 한 값의 위치를 보여주는 막대형 시각 요소. 값은 항상 글자로도 함께 표기한다.
 */
import type { ReactNode } from "react";

const clampPct = (v: number) => Math.min(100, Math.max(0, v));

function Marker({ pct, title }: { pct: number; title: string }) {
  return (
    <span
      title={title}
      className="absolute top-1/2 size-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-card bg-foreground shadow-sm"
      style={{ left: `${clampPct(pct)}%` }}
    />
  );
}

/** KRX 호가 단위(2023-01 개편 기준)로 반올림. */
function roundToKrxTick(price: number): number {
  const tick =
    price < 2_000 ? 1
    : price < 5_000 ? 5
    : price < 20_000 ? 10
    : price < 50_000 ? 50
    : price < 200_000 ? 100
    : price < 500_000 ? 500
    : 1_000;
  return Math.round(price / tick) * tick;
}

/** 52주 최저~최고 사이에서 현재가의 위치. 등락 비율로 최저·최고가를 역산한다. */
export function Range52Week({
  close,
  vsHigh,
  vsLow,
  unit,
  label,
}: {
  close: number;
  vsHigh: number;
  vsLow: number;
  unit: string;
  label: ReactNode;
}) {
  if (!close || vsHigh <= -100 || vsLow <= -100) return null;
  const high = close / (1 + vsHigh / 100);
  const low = close / (1 + vsLow / 100);
  if (high <= low) return null;
  const pct = ((close - low) / (high - low)) * 100;
  // 등락률이 소수 둘째 자리로 반올림돼 있어 역산값에 끝자리 오차가 생긴다(353,503원 등).
  // 국내는 KRX 호가 단위, 그 외는 센트 단위로 맞춘다.
  const isKrw = unit === "원";
  const fmt = (n: number) =>
    isKrw
      ? `${roundToKrxTick(n).toLocaleString("ko-KR")}${unit}`
      : `${n.toLocaleString("ko-KR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}${unit}`;

  return (
    <div className="space-y-2">
      <div className="flex items-baseline justify-between gap-2 text-sm">
        <span className="font-medium">{label}</span>
        <span className="text-xs text-muted-foreground tabular-nums">
          1년 가격대의 {Math.round(clampPct(pct))}% 지점
        </span>
      </div>
      <div className="relative h-2 rounded-full bg-gradient-to-r from-down/35 via-muted-foreground/20 to-up/35">
        <Marker pct={pct} title={`현재가 ${fmt(close)}`} />
      </div>
      <div className="flex justify-between text-xs text-muted-foreground tabular-nums">
        <span>최저 {fmt(low)}</span>
        <span>최고 {fmt(high)}</span>
      </div>
    </div>
  );
}

/** RSI 0~100 구간 표시. 침체·중립·과열은 관습적 해석 구간이다. */
export function RsiMeter({ value, label }: { value: number; label: ReactNode }) {
  if (!value) return null;
  const zone = value >= 70 ? "과열 구간" : value <= 30 ? "침체 구간" : "중립 구간";
  return (
    <div className="space-y-2">
      <div className="flex items-baseline justify-between gap-2 text-sm">
        <span className="font-medium">{label}</span>
        <span className="text-xs text-muted-foreground tabular-nums">
          {value.toFixed(0)} · {zone}
        </span>
      </div>
      <div className="relative h-2">
        <div className="flex h-full gap-0.5 overflow-hidden rounded-full">
          <span className="w-[30%] bg-down/35" />
          <span className="flex-1 bg-muted-foreground/20" />
          <span className="w-[30%] bg-up/35" />
        </div>
        <Marker pct={value} title={`RSI ${value.toFixed(0)}`} />
      </div>
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>침체 30</span>
        <span>과열 70</span>
      </div>
    </div>
  );
}

/** AI가 계산한 저점~고점 관찰 범위 안에서 현재가 위치. */
export function ObservationRange({
  low,
  high,
  current,
  unit,
}: {
  low: number;
  high: number;
  current: number | null | undefined;
  unit: string;
}) {
  const hasCurrent = current != null && current > 0;
  const min = Math.min(low, hasCurrent ? current : low);
  const max = Math.max(high, hasCurrent ? current : high);
  const span = max - min || 1;
  const pos = (v: number) => ((v - min) / span) * 100;
  return (
    <div className="px-2 pt-2 pb-1">
      <div className="relative h-2 rounded-full bg-muted">
        <span
          className="absolute inset-y-0 rounded-full bg-gradient-to-r from-down/60 to-up/60"
          style={{ left: `${pos(low)}%`, width: `${pos(high) - pos(low)}%` }}
        />
        {hasCurrent && <Marker pct={pos(current)} title={`현재가 ${current.toLocaleString()}${unit}`} />}
      </div>
    </div>
  );
}
