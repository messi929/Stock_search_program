"use client";

import {
  AgentCardShell,
  type AgentStatus,
} from "@/components/analyze/AgentCardShell";
import type { ValidatorResult } from "@/types/api";

const STATUS_BADGE: Record<string, { label: string; className: string }> = {
  PASS: { label: "✅ 검증 통과", className: "text-emerald-500 bg-emerald-500/10" },
  WARN: { label: "⚠️ 일부 차이", className: "text-amber-500 bg-amber-500/10" },
  FAIL: { label: "❌ 재분석 필요", className: "text-destructive bg-destructive/10" },
};

const PROBABILITY_BADGE: Record<string, string> = {
  HIGH: "text-destructive",
  MEDIUM: "text-amber-500",
  LOW: "text-muted-foreground",
};

export function ValidatorCard({
  data,
  status,
}: {
  data: ValidatorResult | null;
  status: AgentStatus;
}) {
  const badge = data ? STATUS_BADGE[data.overall_status] : null;
  return (
    <AgentCardShell
      icon="⭐"
      title="검증 + Contrarian (Validator)"
      subtitle={
        data
          ? `신뢰도 ${(data.confidence_score * 100).toFixed(0)}% · ${data.contrarian_scenarios.length} 반대 시나리오`
          : "Sonnet · 핵심 차별점"
      }
      status={status}
    >
      {!data ? (
        status === "running" ? (
          <p className="text-sm text-muted-foreground">
            가격/PER/PBR/ROE 실시간 재조회 + Contrarian 생성 중...
          </p>
        ) : null
      ) : (
        <div className="space-y-4">
          {/* Overall badge */}
          {badge && (
            <div className={`inline-block px-3 py-1 rounded text-sm ${badge.className}`}>
              {badge.label} · fresh {data.fresh_data_count} / stale {data.stale_data_count}
            </div>
          )}

          {/* Checks */}
          {data.checks.length > 0 && (
            <section>
              <h4 className="text-xs font-medium text-muted-foreground mb-2">
                코드 검증 결과
              </h4>
              <div className="space-y-1 text-sm">
                {data.checks.map((c, i) => (
                  <div
                    key={i}
                    className="grid grid-cols-12 gap-2 items-center text-xs"
                  >
                    <span className="col-span-4 font-medium">{c.item}</span>
                    <span className="col-span-3 font-mono text-muted-foreground">
                      claimed: {c.claimed.toLocaleString()}
                    </span>
                    <span className="col-span-3 font-mono text-muted-foreground">
                      verified: {c.verified !== null ? c.verified.toLocaleString() : "—"}
                    </span>
                    <span
                      className={`col-span-2 text-right font-medium ${
                        c.status === "OK"
                          ? "text-emerald-500"
                          : c.status === "WARN"
                            ? "text-amber-500"
                            : "text-destructive"
                      }`}
                    >
                      {c.diff_pct !== null ? `${c.diff_pct.toFixed(2)}%` : "—"} {c.status}
                    </span>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Contrarian scenarios */}
          {data.contrarian_scenarios.length > 0 && (
            <section>
              <h4 className="text-xs font-medium text-muted-foreground mb-2">
                🛑 Contrarian — 분석에 반대되는 시나리오
              </h4>
              <ul className="space-y-2">
                {data.contrarian_scenarios.map((s, i) => (
                  <li key={i} className="p-3 rounded-md bg-muted/30 text-sm">
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`text-xs font-medium ${PROBABILITY_BADGE[s.probability] ?? ""}`}>
                        [{s.probability}]
                      </span>
                      <span className="font-medium">{s.title}</span>
                    </div>
                    <p className="text-muted-foreground">{s.description}</p>
                    <p className="text-xs mt-1">
                      <span className="text-muted-foreground">영향:</span> {s.impact_estimate}
                    </p>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* Blind spots */}
          {data.blind_spots.length > 0 && (
            <section>
              <h4 className="text-xs font-medium text-muted-foreground mb-1">
                🔎 분석에서 누락된 관점
              </h4>
              <ul className="text-sm space-y-0.5">
                {data.blind_spots.map((b, i) => (
                  <li key={i}>• {b}</li>
                ))}
              </ul>
            </section>
          )}

          {data.requires_reanalysis && (
            <p className="text-xs text-destructive bg-destructive/10 p-2 rounded">
              ⚠️ 데이터 신선도 부족 — 재분석을 권장합니다.
            </p>
          )}
        </div>
      )}
    </AgentCardShell>
  );
}
