"use client";

import {
  AgentCardShell,
  type AgentStatus,
} from "@/components/analyze/AgentCardShell";
import type { AnalystResult } from "@/types/api";

const TIER_COLOR: Record<string, string> = {
  상위: "text-emerald-500",
  준상위: "text-amber-500",
  중간: "text-muted-foreground",
  관찰: "text-muted-foreground",
};

const SIGNAL_COLOR: Record<string, string> = {
  강세: "text-emerald-500",
  중립: "text-muted-foreground",
  약세: "text-destructive",
};

/** 6자리 숫자=KR(원), 그 외=US(달러). */
function curUnit(ticker: string): string {
  return /^\d{6}$/.test((ticker ?? "").trim()) ? "원" : "달러";
}

export function AnalystCard({
  data,
  status,
}: {
  data: AnalystResult | null;
  status: AgentStatus;
}) {
  return (
    <AgentCardShell
      icon="📊"
      title="기술/펀더멘털 (Analyst)"
      subtitle="Sonnet · 정량 데이터 해석"
      status={status}
    >
      {!data ? (
        status === "running" ? (
          <p className="text-sm text-muted-foreground">
            v7.5 buy_score + 이평/RSI/PER/PBR 해석 중...
          </p>
        ) : null
      ) : (
        <div className="space-y-4">
          {/* Headline metrics grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
            <Metric label="현재가" value={`${data.technical.current_price.toLocaleString()}${curUnit(data.ticker)}`} />
            <Metric
              label="시그널"
              value={data.technical.signal}
              valueClass={SIGNAL_COLOR[data.technical.signal] ?? ""}
            />
            <Metric
              label="Buy Score"
              value={`${data.buy_score.buy_score.toFixed(1)} (${data.buy_score.score_tier})`}
              valueClass={TIER_COLOR[data.buy_score.score_tier] ?? ""}
            />
            <Metric label="이평 정렬" value={data.technical.ma_status} />
            <Metric
              label="RSI"
              value={`${data.technical.rsi.toFixed(1)} (${data.technical.rsi_status})`}
            />
            <Metric label="52w 고가 대비" value={`${data.technical.vs_high_52w.toFixed(1)}%`} />
            <Metric label="PER" value={data.fundamental.per.toFixed(1)} />
            <Metric label="PBR" value={data.fundamental.pbr.toFixed(2)} />
            <Metric label="ROE" value={`${data.fundamental.roe.toFixed(1)}%`} />
            <Metric label="배당수익률" value={`${data.fundamental.div_yield.toFixed(2)}%`} />
            <Metric label="MA20" value={data.technical.ma20.toLocaleString()} />
            <Metric label="MA60" value={data.technical.ma60.toLocaleString()} />
          </div>

          {/* Buy score interpretation */}
          {data.buy_score.interpretation && (
            <section>
              <h4 className="text-xs font-medium text-muted-foreground mb-1">
                Buy Score 해석
              </h4>
              <p className="text-sm">{data.buy_score.interpretation}</p>
              {data.buy_score.contributing_factors.length > 0 && (
                <ul className="mt-1 space-y-0.5 text-xs text-muted-foreground">
                  {data.buy_score.contributing_factors.map((f, i) => (
                    <li key={i}>• {f}</li>
                  ))}
                </ul>
              )}
            </section>
          )}

          {/* Fundamental judgment */}
          {data.fundamental.valuation_judgment && (
            <section>
              <h4 className="text-xs font-medium text-muted-foreground mb-1">
                펀더멘털 판단
              </h4>
              <p className="text-sm">{data.fundamental.valuation_judgment}</p>
            </section>
          )}

          {/* Summary */}
          <section>
            <h4 className="text-xs font-medium text-muted-foreground mb-1">
              종합 요약
            </h4>
            <p className="text-sm leading-relaxed">{data.summary}</p>
          </section>
        </div>
      )}
    </AgentCardShell>
  );
}

function Metric({
  label,
  value,
  valueClass,
}: {
  label: string;
  value: string;
  valueClass?: string;
}) {
  return (
    <div className="p-2 rounded-md bg-muted/30">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className={`font-medium font-mono text-sm ${valueClass ?? ""}`}>{value}</div>
    </div>
  );
}
