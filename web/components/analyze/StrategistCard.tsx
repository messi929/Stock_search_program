"use client";

import {
  AgentCardShell,
  type AgentStatus,
} from "@/components/analyze/AgentCardShell";
import type { StrategistResult } from "@/types/api";

const PERSONA_NAME: Record<string, string> = {
  blackrock: "블랙록",
  ark: "ARK",
  graham: "그레이엄",
};

export function StrategistCard({
  data,
  status,
}: {
  data: StrategistResult | null;
  status: AgentStatus;
}) {
  return (
    <AgentCardShell
      icon="🎯"
      title="종합 분석 (Strategist)"
      subtitle={data ? `${PERSONA_NAME[data.persona_used] ?? data.persona_used} 관점` : "Opus"}
      status={status}
    >
      {!data ? (
        status === "running" ? (
          <p className="text-sm text-muted-foreground">
            페르소나 분석 + 진입선 산출 중...
          </p>
        ) : null
      ) : (
        <div className="space-y-4">
          {/* Perspective */}
          <section>
            <h4 className="text-xs font-medium text-muted-foreground mb-1">
              페르소나 관점
            </h4>
            <p className="text-sm leading-relaxed">{data.persona_perspective}</p>
          </section>

          {/* Summary */}
          <section>
            <h4 className="text-xs font-medium text-muted-foreground mb-1">
              종합 분석
            </h4>
            <p className="text-sm leading-relaxed whitespace-pre-line">
              {data.summary}
            </p>
          </section>

          {/* Entry points */}
          {data.entry_points && (
            <section>
              <h4 className="text-xs font-medium text-muted-foreground mb-2">
                📌 참고 관찰 구간
              </h4>
              <div className="grid grid-cols-3 gap-2 text-sm">
                {(["tier_1", "tier_2", "tier_3"] as const).map((k, i) => (
                  <div key={k} className="p-2 rounded-md bg-muted/30">
                    <div className="text-xs text-muted-foreground">
                      {i + 1}차 관찰 구간
                    </div>
                    <div className="font-medium font-mono">
                      {data.entry_points![k].toLocaleString()}원
                    </div>
                  </div>
                ))}
              </div>
              {data.entry_points.technical_basis.length > 0 && (
                <ul className="mt-2 space-y-0.5 text-xs text-muted-foreground">
                  {data.entry_points.technical_basis.map((b, i) => (
                    <li key={i}>• {b}</li>
                  ))}
                </ul>
              )}
            </section>
          )}

          {/* User principles alignment */}
          {Object.keys(data.user_principles_alignment).length > 0 && (
            <section>
              <h4 className="text-xs font-medium text-muted-foreground mb-1">
                내 투자 원칙 부합도
              </h4>
              <ul className="space-y-1 text-sm">
                {Object.entries(data.user_principles_alignment).map(([k, v]) => (
                  <li key={k}>
                    <span className="font-medium">• {k}:</span>{" "}
                    <span className="text-muted-foreground">{String(v)}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* Follow-up questions */}
          {data.follow_up_questions.length > 0 && (
            <section>
              <h4 className="text-xs font-medium text-muted-foreground mb-1">
                💡 추가 검토할 질문
              </h4>
              <ol className="list-decimal list-inside space-y-1 text-sm">
                {data.follow_up_questions.map((q, i) => (
                  <li key={i}>{q}</li>
                ))}
              </ol>
            </section>
          )}

          {data.confidence_note && (
            <p className="text-xs text-amber-500 bg-amber-500/10 p-2 rounded">
              {data.confidence_note}
            </p>
          )}
        </div>
      )}
    </AgentCardShell>
  );
}
