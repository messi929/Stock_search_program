"use client";

/**
 * KIS 투자자별 매매동향 — 최근 14일 외인/기관/개인 누적 막대.
 * Korean Specialist 데이터를 보완. KR 종목만.
 */
import { Card, CardContent } from "@/components/ui/card";
import { useKisInvestor } from "@/hooks/useKisPrice";

function isKr(ticker: string): boolean {
  return /^\d{6}$/.test(ticker.trim());
}

function num(v: string | undefined): number {
  if (!v) return 0;
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
}

function fmtKshares(qty: number): string {
  if (Math.abs(qty) >= 1_000_000) return `${(qty / 1_000_000).toFixed(1)}M`;
  if (Math.abs(qty) >= 1_000) return `${(qty / 1_000).toFixed(0)}K`;
  return qty.toLocaleString("ko-KR");
}

function fmtDate(d: string): string {
  // YYYYMMDD → MM/DD
  if (d.length !== 8) return d;
  return `${Number(d.slice(4, 6))}/${Number(d.slice(6, 8))}`;
}

export function KisInvestorFlow({ ticker }: { ticker: string }) {
  const { data, isLoading, error } = useKisInvestor(ticker);

  if (!isKr(ticker)) return null;

  if (isLoading) {
    return (
      <Card>
        <CardContent className="p-4 text-xs text-muted-foreground">투자자 흐름 불러오는 중…</CardContent>
      </Card>
    );
  }
  if (error || !data || data.trend.length === 0) {
    return (
      <Card>
        <CardContent className="p-4 text-xs text-muted-foreground">투자자 흐름 데이터 없음</CardContent>
      </Card>
    );
  }

  // 최근 14일 (응답은 최신 → 과거, 차트는 좌→우 = 과거 → 최근)
  const rows = data.trend.slice(0, 14).reverse().map((r) => ({
    date: r.stck_bsop_date,
    foreign: num(r.frgn_ntby_qty),
    inst: num(r.orgn_ntby_qty),
    person: num(r.prsn_ntby_qty),
  }));

  // 절대값 max — 막대 스케일
  const maxAbs = Math.max(
    1,
    ...rows.flatMap((r) => [Math.abs(r.foreign), Math.abs(r.inst), Math.abs(r.person)]),
  );

  // 누적 (14일 합계)
  const sumForeign = rows.reduce((s, r) => s + r.foreign, 0);
  const sumInst = rows.reduce((s, r) => s + r.inst, 0);
  const sumPerson = rows.reduce((s, r) => s + r.person, 0);

  return (
    <Card>
      <CardContent className="p-4 space-y-3">
        <div className="flex items-center justify-between">
          <div className="text-sm font-semibold">🌊 투자자 매매 흐름 (14일)</div>
          <div className="text-[10px] text-muted-foreground">단위: 주</div>
        </div>

        {/* 14일 누적 요약 */}
        <div className="grid grid-cols-3 gap-2 text-xs">
          <SummaryCell label="외국인" qty={sumForeign} accent="text-amber-500" />
          <SummaryCell label="기관" qty={sumInst} accent="text-emerald-500" />
          <SummaryCell label="개인" qty={sumPerson} accent="text-slate-400" />
        </div>

        {/* 일자별 막대 */}
        <div className="space-y-1.5">
          {rows.map((r) => (
            <div key={r.date} className="space-y-0.5">
              <div className="flex items-center gap-1.5">
                <div className="w-10 text-[10px] text-muted-foreground tabular-nums">
                  {fmtDate(r.date)}
                </div>
                <FlowBar value={r.foreign} max={maxAbs} color="bg-amber-500" />
              </div>
              <div className="flex items-center gap-1.5">
                <div className="w-10 text-[10px] text-muted-foreground tabular-nums" />
                <FlowBar value={r.inst} max={maxAbs} color="bg-emerald-500" />
              </div>
            </div>
          ))}
        </div>

        <div className="flex items-center gap-3 text-[10px] text-muted-foreground border-t border-border pt-2">
          <span className="flex items-center gap-1">
            <span className="inline-block w-2 h-2 rounded-sm bg-amber-500" /> 외인
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block w-2 h-2 rounded-sm bg-emerald-500" /> 기관
          </span>
          <span className="ml-auto">우=순매수 · 좌=순매도</span>
        </div>
      </CardContent>
    </Card>
  );
}

function SummaryCell({
  label,
  qty,
  accent,
}: {
  label: string;
  qty: number;
  accent: string;
}) {
  const sign = qty > 0 ? "+" : "";
  return (
    <div className="border border-border rounded-md p-2">
      <div className="text-[10px] text-muted-foreground">{label}</div>
      <div className={`font-mono text-sm font-semibold ${accent}`}>
        {sign}
        {fmtKshares(qty)}
      </div>
    </div>
  );
}

function FlowBar({ value, max, color }: { value: number; max: number; color: string }) {
  const pct = Math.min(100, (Math.abs(value) / max) * 100);
  const positive = value >= 0;
  return (
    <div className="flex-1 relative h-2 bg-muted/30 rounded-sm overflow-hidden">
      {/* 중앙선 */}
      <div className="absolute left-1/2 top-0 bottom-0 w-px bg-border" />
      <div
        className={`absolute top-0 bottom-0 ${color}`}
        style={{
          left: positive ? "50%" : `${50 - pct / 2}%`,
          width: `${pct / 2}%`,
        }}
      />
    </div>
  );
}
