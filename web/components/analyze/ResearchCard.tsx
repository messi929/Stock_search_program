"use client";

import {
  AgentCardShell,
  type AgentStatus,
} from "@/components/analyze/AgentCardShell";
import type { ResearchResult } from "@/types/api";

const SENTIMENT_COLOR: Record<string, string> = {
  낙관적: "text-emerald-500",
  신중: "text-amber-500",
  비관적: "text-destructive",
};

const SECTOR_STATUS_COLOR: Record<string, string> = {
  강세: "text-emerald-500",
  횡보: "text-muted-foreground",
  약세: "text-destructive",
};

export function ResearchCard({
  data,
  status,
}: {
  data: ResearchResult | null;
  status: AgentStatus;
}) {
  return (
    <AgentCardShell
      icon="🔍"
      title="시황·뉴스·매크로 (Research)"
      subtitle={
        data
          ? `시장 심리: ${data.market_sentiment}`
          : "Haiku · 매크로 + 외국인·기관 수급"
      }
      status={status}
    >
      {!data ? (
        status === "running" ? (
          <p className="text-sm text-muted-foreground">
            매크로 이벤트 + 섹터 동향 정리 중...
          </p>
        ) : null
      ) : (
        <div className="space-y-4">
          {/* Sentiment */}
          <div className="text-sm">
            <span className="text-muted-foreground">시장 심리: </span>
            <span className={`font-medium ${SENTIMENT_COLOR[data.market_sentiment] ?? ""}`}>
              {data.market_sentiment}
            </span>
          </div>

          {/* Macro */}
          {(data.macro_context.fomc_next ||
            data.macro_context.key_risks.length > 0 ||
            data.macro_context.key_opportunities.length > 0) && (
            <section>
              <h4 className="text-xs font-medium text-muted-foreground mb-1">
                매크로 컨텍스트
              </h4>
              <div className="text-sm space-y-1">
                {data.macro_context.fomc_next && (
                  <p>
                    <span className="text-muted-foreground">다음 FOMC:</span>{" "}
                    {data.macro_context.fomc_next}
                  </p>
                )}
                {data.macro_context.key_risks.length > 0 && (
                  <div>
                    <span className="text-muted-foreground">주요 리스크</span>
                    <ul className="ml-3 list-disc text-xs">
                      {data.macro_context.key_risks.map((r, i) => (
                        <li key={i}>{r}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {data.macro_context.key_opportunities.length > 0 && (
                  <div>
                    <span className="text-muted-foreground">주요 기회</span>
                    <ul className="ml-3 list-disc text-xs">
                      {data.macro_context.key_opportunities.map((o, i) => (
                        <li key={i}>{o}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </section>
          )}

          {/* Sector status */}
          {data.sector_status.length > 0 && (
            <section>
              <h4 className="text-xs font-medium text-muted-foreground mb-1">
                섹터 상태
              </h4>
              <ul className="text-sm space-y-1">
                {data.sector_status.map((s, i) => (
                  <li key={i}>
                    <span className="font-medium">{s.name}:</span>{" "}
                    <span className={SECTOR_STATUS_COLOR[s.status] ?? ""}>
                      {s.status}
                    </span>
                    {s.rally_participation && (
                      <span className="text-xs text-muted-foreground">
                        {" · "}
                        {s.rally_participation}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* News */}
          {data.relevant_news.length > 0 && (
            <section>
              <h4 className="text-xs font-medium text-muted-foreground mb-1">
                관련 뉴스/이벤트
              </h4>
              <ul className="text-sm space-y-1">
                {data.relevant_news.slice(0, 5).map((n, i) => (
                  <li key={i} className="text-xs">
                    <span
                      className={`mr-1 ${
                        n.impact === "positive"
                          ? "text-emerald-500"
                          : n.impact === "negative"
                            ? "text-destructive"
                            : "text-muted-foreground"
                      }`}
                    >
                      {n.impact === "positive" ? "↑" : n.impact === "negative" ? "↓" : "·"}
                    </span>
                    <span className="font-medium">{n.headline}</span>
                    <span className="text-muted-foreground">
                      {" "}
                      ({n.source} · {n.published_at})
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* Summary */}
          <section>
            <h4 className="text-xs font-medium text-muted-foreground mb-1">
              요약
            </h4>
            <p className="text-sm leading-relaxed">{data.summary}</p>
          </section>
        </div>
      )}
    </AgentCardShell>
  );
}
