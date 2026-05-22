"use client";

/**
 * Event Analyst 결과 카드 — Week D Day 5 신규.
 *
 * 핵심 표시:
 *  1. 4차원 확실성 점수 배지 (Source/Timing/Probability/Impact + final + mode)
 *  2. 시나리오 분석 (bullish/base/bearish)
 *  3. 참고 관찰 구간 (current_position_vs_history)
 *  4. 표본 수 + sample_reliability + fabrication_warning
 *  5. summary_neutral
 *
 * LEGAL: 단정 표현 사용 금지. 백엔드가 이미 filter_forbidden 통과한 데이터.
 */

import {
  AgentCardShell,
  type AgentStatus,
} from "@/components/analyze/AgentCardShell";
import type { EventAnalystResult } from "@/types/api";

const MODE_BADGE: Record<string, { color: string; label: string }> = {
  "Full Analysis": { color: "bg-emerald-500/15 text-emerald-700", label: "Full" },
  Cautious: { color: "bg-amber-500/15 text-amber-700", label: "Cautious" },
  "Probabilistic Only": {
    color: "bg-amber-500/15 text-amber-700",
    label: "Probabilistic",
  },
  Refused: { color: "bg-red-500/15 text-red-700", label: "Refused" },
};

export function EventAnalystCard({
  data,
  status,
}: {
  data: EventAnalystResult | null;
  status: AgentStatus;
}) {
  return (
    <AgentCardShell
      icon="⚡"
      title="이벤트 통계 분석 (Event Analyst)"
      subtitle={
        data ? `${data.event_summary.event_type} — ${data.event_summary.event_target}` : "Sonnet"
      }
      status={status}
    >
      {!data ? (
        status === "running" ? (
          <p className="text-sm text-muted-foreground">
            이벤트 데이터 수집 + 4차원 확실성 점수 + 유사 사례 통계 추론 중...
          </p>
        ) : null
      ) : (
        <div className="space-y-4">
          {/* 확실성 점수 배지 */}
          <CertaintyPanel data={data} />

          {/* 영향 매핑 */}
          {data.impact_mapping?.secondary_beneficiaries?.length ? (
            <ImpactPanel data={data} />
          ) : null}

          {/* 시나리오 분석 */}
          <ScenarioPanel scenarios={data.scenario_analysis} />

          {/* 참고 관찰 구간 */}
          {data.reference_observation_zones?.current_position_vs_history && (
            <section>
              <h4 className="text-xs font-medium text-muted-foreground mb-1">
                📊 참고 관찰 구간
              </h4>
              <p className="text-sm leading-relaxed">
                {data.reference_observation_zones.current_position_vs_history}
              </p>
              {(data.reference_observation_zones.historical_volatility_lower_1sigma ||
                data.reference_observation_zones.historical_volatility_upper_1sigma) && (
                <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
                  <div className="p-2 rounded-md bg-muted/30">
                    <div className="text-muted-foreground">1σ 하단</div>
                    <div className="font-mono">
                      {data.reference_observation_zones.historical_volatility_lower_1sigma}
                    </div>
                  </div>
                  <div className="p-2 rounded-md bg-muted/30">
                    <div className="text-muted-foreground">1σ 상단</div>
                    <div className="font-mono">
                      {data.reference_observation_zones.historical_volatility_upper_1sigma}
                    </div>
                  </div>
                </div>
              )}
            </section>
          )}

          {/* 기관 보유 스냅샷 (US — 정보 제공용, 신호/점수 아님) */}
          {data.institutional_ownership?.available && (
            <InstitutionalOwnershipPanel io={data.institutional_ownership} />
          )}

          {/* 통계 신뢰도 + fabrication */}
          <section className="rounded-md border bg-muted/20 p-3 text-xs space-y-1">
            <div>
              <span className="text-muted-foreground">표본 수: </span>
              <span className="font-mono font-medium">
                {data.historical_statistics.comparable_events_count}
              </span>
              <span className="ml-2 text-muted-foreground">
                {data.historical_statistics.sample_reliability}
              </span>
            </div>
            {data.historical_statistics.fabrication_warning && (
              <div className="text-muted-foreground leading-relaxed">
                ⚠️ {data.historical_statistics.fabrication_warning}
              </div>
            )}
          </section>

          {/* 위험 + 모니터링 */}
          {(data.key_risks.length > 0 || data.what_to_watch.length > 0) && (
            <section className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {data.key_risks.length > 0 && (
                <div>
                  <h4 className="text-xs font-medium text-muted-foreground mb-1">
                    주요 위험
                  </h4>
                  <ul className="text-sm space-y-0.5">
                    {data.key_risks.slice(0, 5).map((r, i) => (
                      <li key={i}>• {r}</li>
                    ))}
                  </ul>
                </div>
              )}
              {data.what_to_watch.length > 0 && (
                <div>
                  <h4 className="text-xs font-medium text-muted-foreground mb-1">
                    모니터링 항목
                  </h4>
                  <ul className="text-sm space-y-0.5">
                    {data.what_to_watch.slice(0, 5).map((w, i) => (
                      <li key={i}>• {w}</li>
                    ))}
                  </ul>
                </div>
              )}
            </section>
          )}

          {/* 한국어 요약 */}
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

/** 4차원 확실성 점수 + 모드 배지 */
function CertaintyPanel({ data }: { data: EventAnalystResult }) {
  const cb = data.event_summary.certainty_breakdown;
  const modeMeta =
    MODE_BADGE[cb.mode] ?? { color: "bg-muted text-foreground", label: cb.mode };

  const dims: Array<{ key: string; label: string; value: number; weight: string }> = [
    { key: "source", label: "Source", value: cb.source, weight: "40%" },
    { key: "timing", label: "Timing", value: cb.timing, weight: "30%" },
    {
      key: "probability",
      label: "Probability",
      value: cb.probability,
      weight: "20%",
    },
    { key: "impact", label: "Impact", value: cb.impact, weight: "10%" },
  ];

  return (
    <section>
      <div className="flex items-center justify-between mb-2">
        <h4 className="text-xs font-medium text-muted-foreground">
          확실성 점수 (4차원 가중)
        </h4>
        <span className={`text-xs font-medium px-2 py-0.5 rounded ${modeMeta.color}`}>
          {data.event_summary.badge || modeMeta.label}
        </span>
      </div>
      <div className="grid grid-cols-4 gap-2 text-center">
        {dims.map((d) => (
          <div key={d.key} className="p-2 rounded-md bg-muted/30">
            <div className="text-[10px] text-muted-foreground">
              {d.label} ({d.weight})
            </div>
            <div className="font-mono text-sm font-medium">{d.value.toFixed(0)}/10</div>
          </div>
        ))}
      </div>
      <div className="mt-2 text-center">
        <span className="text-xs text-muted-foreground mr-1">Final:</span>
        <span className="font-mono text-base font-semibold">
          {cb.final_score.toFixed(2)}/10
        </span>
      </div>
    </section>
  );
}

function ImpactPanel({ data }: { data: EventAnalystResult }) {
  const im = data.impact_mapping;
  return (
    <section>
      <h4 className="text-xs font-medium text-muted-foreground mb-1">
        영향 매핑
      </h4>
      <div className="space-y-1 text-sm">
        {im.direct_beneficiary?.ticker && (
          <div>
            <span className="text-xs px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-700 mr-2">
              1차
            </span>
            <span className="font-mono">{im.direct_beneficiary.ticker}</span>
            {im.direct_beneficiary.rationale && (
              <span className="text-muted-foreground"> — {im.direct_beneficiary.rationale}</span>
            )}
          </div>
        )}
        {im.secondary_beneficiaries?.slice(0, 3).map((s, i) => (
          <div key={i}>
            <span className="text-xs px-1.5 py-0.5 rounded bg-sky-500/15 text-sky-700 mr-2">
              2차
            </span>
            <span className="font-mono">{s.ticker ?? "?"}</span>
            {s.rationale && (
              <span className="text-muted-foreground"> — {s.rationale}</span>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}

/** 미국 기관 보유 스냅샷 — 분기 13F 기반 정적 참고 정보 (신호 아님). */
function InstitutionalOwnershipPanel({
  io,
}: {
  io: NonNullable<EventAnalystResult["institutional_ownership"]>;
}) {
  const fmtPct = (v?: number | null) => (v == null ? "-" : `${v.toFixed(1)}%`);
  const fmtCount = (v?: number | null) =>
    v == null ? "-" : v.toLocaleString("en-US");

  return (
    <section className="rounded-md border bg-muted/20 p-3 space-y-2">
      <div className="flex items-center justify-between">
        <h4 className="text-xs font-medium text-muted-foreground">
          🏛️ 기관 보유 현황 (참고)
        </h4>
        {io.as_of && (
          <span className="text-[10px] text-muted-foreground">기준 {io.as_of}</span>
        )}
      </div>
      <div className="grid grid-cols-3 gap-2 text-center">
        <div className="p-2 rounded-md bg-muted/30">
          <div className="text-[10px] text-muted-foreground">기관 보유</div>
          <div className="font-mono text-sm font-medium">
            {fmtPct(io.institutions_pct)}
          </div>
        </div>
        <div className="p-2 rounded-md bg-muted/30">
          <div className="text-[10px] text-muted-foreground">내부자 보유</div>
          <div className="font-mono text-sm font-medium">
            {fmtPct(io.insiders_pct)}
          </div>
        </div>
        <div className="p-2 rounded-md bg-muted/30">
          <div className="text-[10px] text-muted-foreground">기관 수</div>
          <div className="font-mono text-sm font-medium">
            {fmtCount(io.institutions_count)}
          </div>
        </div>
      </div>
      {io.top_holders.length > 0 && (
        <div className="space-y-0.5">
          <div className="text-[10px] text-muted-foreground">상위 보유 기관</div>
          {io.top_holders.slice(0, 5).map((h, i) => (
            <div
              key={i}
              className="flex items-center justify-between text-xs"
            >
              <span className="truncate mr-2">{h.holder}</span>
              <span className="font-mono text-muted-foreground shrink-0">
                {fmtPct(h.pct_held)}
              </span>
            </div>
          ))}
        </div>
      )}
      {io.note && (
        <div className="text-[10px] text-muted-foreground leading-relaxed">
          ℹ️ {io.note}
        </div>
      )}
    </section>
  );
}

function ScenarioPanel({
  scenarios,
}: {
  scenarios: EventAnalystResult["scenario_analysis"];
}) {
  const cases: Array<{
    key: keyof EventAnalystResult["scenario_analysis"];
    label: string;
    color: string;
  }> = [
    { key: "bullish_case", label: "Bullish", color: "border-emerald-500/40 bg-emerald-500/5" },
    { key: "base_case", label: "Base", color: "border-slate-500/40 bg-slate-500/5" },
    { key: "bearish_case", label: "Bearish", color: "border-red-500/40 bg-red-500/5" },
  ];

  return (
    <section>
      <h4 className="text-xs font-medium text-muted-foreground mb-2">
        시나리오 분석
      </h4>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
        {cases.map((c) => {
          const sc = scenarios[c.key];
          return (
            <div key={c.key} className={`rounded-md border p-2 text-xs space-y-1 ${c.color}`}>
              <div className="flex items-center justify-between">
                <span className="font-medium">{c.label}</span>
                <span className="text-muted-foreground">{sc.probability || "-"}</span>
              </div>
              {sc.trigger && <div>트리거: {sc.trigger}</div>}
              {sc.historical_pattern && (
                <div className="text-muted-foreground leading-relaxed">
                  {sc.historical_pattern}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}
