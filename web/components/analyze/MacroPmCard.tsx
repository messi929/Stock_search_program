"use client";

/**
 * Macro PM 결과 카드 — Week D Day 5 신규.
 *
 * 핵심 표시:
 *  1. 6 매크로 국면 (current_regime + transition_to + confidence bar)
 *  2. 4 사이클 (interest_rate / business_cycle / currency / inflation) 게이지
 *  3. 동적 가중치 (US/KR weighting)
 *  4. 종목별 macro alignment (있을 때)
 *  5. summary_neutral
 */

import {
  AgentCardShell,
  type AgentStatus,
} from "@/components/analyze/AgentCardShell";
import type { CycleStage, MacroPmResult } from "@/types/api";

const REGIME_NAMES_KR: Record<string, string> = {
  Goldilocks: "골디락스",
  Reflation: "리플레이션",
  Stagflation: "스태그플레이션",
  "Risk-Off": "리스크 오프",
  Recovery: "리커버리",
  "Late Cycle": "레이트 사이클",
  Transition: "전환기",
};

const CYCLE_LABELS: Array<{ key: keyof MacroPmResult["cycle_analysis"]; label: string; emoji: string }> = [
  { key: "interest_rate", label: "금리", emoji: "💹" },
  { key: "business_cycle", label: "경기", emoji: "🏭" },
  { key: "currency_cycle", label: "통화", emoji: "💱" },
  { key: "inflation_cycle", label: "인플레", emoji: "📈" },
];

export function MacroPmCard({
  data,
  status,
}: {
  data: MacroPmResult | null;
  status: AgentStatus;
}) {
  return (
    <AgentCardShell
      icon="🌐"
      title="매크로 사이클 분석 (Macro PM)"
      subtitle={data ? `${data.macro_regime.current_regime} 국면` : "Sonnet"}
      status={status}
    >
      {!data ? (
        status === "running" ? (
          <p className="text-sm text-muted-foreground">
            FRED + ECOS 데이터 로드 → 4 사이클 판정 → 6 국면 매핑 중...
          </p>
        ) : null
      ) : (
        <div className="space-y-4">
          {/* 6 국면 + 신뢰도 */}
          <RegimePanel data={data} />

          {/* 4 사이클 게이지 */}
          <section>
            <h4 className="text-xs font-medium text-muted-foreground mb-2">
              4 사이클 (정량 판정)
            </h4>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {CYCLE_LABELS.map((c) => (
                <CycleRow
                  key={c.key}
                  emoji={c.emoji}
                  label={c.label}
                  stage={data.cycle_analysis[c.key]}
                />
              ))}
            </div>
          </section>

          {/* 동적 가중치 */}
          <WeightingPanel weighting={data.weighting_used} />

          {/* 종목별 macro alignment */}
          {data.stock_specific_analysis && (
            <section className="rounded-md border p-3 bg-muted/20 text-sm space-y-1">
              <div className="flex items-center justify-between">
                <span className="text-xs text-muted-foreground">
                  종목 매크로 정합도 ({data.stock_specific_analysis.ticker})
                </span>
                <span className="font-mono">
                  {data.stock_specific_analysis.alignment_score?.toFixed?.(1) ?? "-"}/10
                </span>
              </div>
              <div className="text-sm">{data.stock_specific_analysis.macro_alignment}</div>
              {data.stock_specific_analysis.interpretation && (
                <p className="text-xs leading-relaxed text-muted-foreground">
                  {data.stock_specific_analysis.interpretation}
                </p>
              )}
            </section>
          )}

          {/* 전환 신호 */}
          {data.transition_signals_to_monitor.length > 0 && (
            <section>
              <h4 className="text-xs font-medium text-muted-foreground mb-1">
                모니터링 신호
              </h4>
              <ul className="text-xs space-y-1">
                {data.transition_signals_to_monitor.slice(0, 4).map((s, i) => (
                  <li key={i}>
                    • <span className="font-medium">{s.signal}</span>
                    {s.current && <span className="ml-1 text-muted-foreground">현재 {s.current}</span>}
                    {s.trigger_level && (
                      <span className="ml-1 text-muted-foreground">
                        → 트리거 {s.trigger_level}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          )}

          <section>
            <h4 className="text-xs font-medium text-muted-foreground mb-1">
              종합 (자연어)
            </h4>
            <p className="text-sm leading-relaxed">{data.summary_neutral}</p>
          </section>
        </div>
      )}
    </AgentCardShell>
  );
}

function RegimePanel({ data }: { data: MacroPmResult }) {
  const r = data.macro_regime;
  const regimeKr = REGIME_NAMES_KR[r.current_regime] ?? r.current_regime;
  const conf = Math.max(0, Math.min(1, r.regime_confidence ?? 0));
  const confPct = Math.round(conf * 100);

  return (
    <section className="rounded-md border bg-muted/20 p-3">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-xs text-muted-foreground">현재 국면</div>
          <div className="font-semibold text-base">
            {r.current_regime} <span className="text-sm text-muted-foreground">({regimeKr})</span>
          </div>
        </div>
        {r.transition_to && (
          <div className="text-right">
            <div className="text-xs text-muted-foreground">전환 가능</div>
            <div className="text-sm">{r.transition_to}</div>
          </div>
        )}
      </div>
      <div className="mt-2">
        <div className="flex items-center justify-between text-[10px] text-muted-foreground mb-0.5">
          <span>국면 신뢰도</span>
          <span className="font-mono">{confPct}%</span>
        </div>
        <div className="h-1.5 rounded bg-muted overflow-hidden">
          <div
            className="h-full bg-sky-500 transition-all"
            style={{ width: `${confPct}%` }}
          />
        </div>
      </div>
    </section>
  );
}

function CycleRow({
  emoji,
  label,
  stage,
}: {
  emoji: string;
  label: string;
  stage: CycleStage;
}) {
  return (
    <div className="rounded-md border p-2.5">
      <div className="flex items-center justify-between mb-0.5">
        <span className="text-xs text-muted-foreground">
          {emoji} {label} 사이클
        </span>
      </div>
      <div className="text-sm font-medium">{stage.stage || "—"}</div>
      {stage.rationale && (
        <p className="mt-1 text-xs text-muted-foreground leading-relaxed line-clamp-2">
          {stage.rationale}
        </p>
      )}
    </div>
  );
}

function WeightingPanel({
  weighting,
}: {
  weighting: MacroPmResult["weighting_used"];
}) {
  const us = Math.max(0, Math.min(1, weighting.us_weight));
  const kr = Math.max(0, Math.min(1, weighting.kr_weight));
  const total = us + kr || 1;
  const usPct = Math.round((us / total) * 100);
  const krPct = 100 - usPct;

  return (
    <section>
      <h4 className="text-xs font-medium text-muted-foreground mb-1">
        동적 매크로 가중치
      </h4>
      <div className="flex h-6 rounded-md overflow-hidden border text-[10px]">
        <div
          className="bg-sky-500/20 text-sky-800 flex items-center justify-center font-mono"
          style={{ width: `${usPct}%` }}
        >
          🇺🇸 {usPct}%
        </div>
        <div
          className="bg-rose-500/20 text-rose-800 flex items-center justify-center font-mono"
          style={{ width: `${krPct}%` }}
        >
          🇰🇷 {krPct}%
        </div>
      </div>
      {weighting.rationale && (
        <p className="mt-1 text-xs text-muted-foreground">{weighting.rationale}</p>
      )}
    </section>
  );
}
