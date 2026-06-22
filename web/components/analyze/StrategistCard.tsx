"use client";

import {
  AgentCardShell,
  type AgentStatus,
} from "@/components/analyze/AgentCardShell";
import type { StrategistResult } from "@/types/api";

// persona_used에는 시간축 관점 id(short/short_mid/mid/long)가 담긴다.
const HORIZON_NAME: Record<string, string> = {
  short: "단기",
  short_mid: "단중기",
  mid: "중기",
  long: "장기",
};

/** 관점별 진입 철학 한 줄 — 사용자가 "왜 이 가격?"을 즉시 이해. */
const HORIZON_PHILOSOPHY: Record<string, string> = {
  short:
    "기술적 레벨 중심 — 지지·이동평균·변동성 밴드 기준의 좁은 관찰 폭. 단기 신뢰구간은 넓음.",
  short_mid:
    "실적 모멘텀 + 기술 강세 — 분기 이벤트·신고가 돌파 부근 관찰.",
  mid:
    "밸류·성장 균형(GARP) — 역사적 밸류 밴드와 실적 경로 기준의 관찰 폭.",
  long:
    "내재가치·해자 중심 — 큰 폭 할인 시 단계적 참고. 구조적 훼손 기준의 넓은 폭.",
};

function pctFromCurrent(price: number, current: number | null | undefined): string {
  if (!current || current <= 0) return "";
  const diff = ((price - current) / current) * 100;
  const sign = diff >= 0 ? "+" : "";
  return `${sign}${diff.toFixed(1)}%`;
}

function pctTone(price: number, current: number | null | undefined): string {
  if (!current || current <= 0) return "text-muted-foreground";
  const diff = price - current;
  return diff > 0 ? "text-emerald-600" : "text-rose-600";
}

export function StrategistCard({
  data,
  status,
  currentPrice = null,
  ticker = "",
}: {
  data: StrategistResult | null;
  status: AgentStatus;
  /** Analyst 결과의 현재가 — 진입/회복 관찰선 거리(%) 계산용. */
  currentPrice?: number | null;
  /** 통화 단위 판별용 (6자리=KR 원, 그 외=US 달러). */
  ticker?: string;
}) {
  const cur = /^\d{6}$/.test((ticker ?? "").trim()) ? "원" : "달러";
  return (
    <AgentCardShell
      icon="🎯"
      title="종합 분석 (Strategist)"
      subtitle={data ? `${HORIZON_NAME[data.persona_used] ?? data.persona_used} 관점` : "Opus"}
      status={status}
    >
      {!data ? (
        status === "running" ? (
          <p className="text-sm text-muted-foreground">
            관점 분석 + 진입선 산출 중...
          </p>
        ) : null
      ) : (
        <div className="space-y-4">
          {/* Perspective */}
          <section>
            <h4 className="text-xs font-medium text-muted-foreground mb-1">
              관점 분석
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

          {/* 진입 관찰 구간 — 거리 % + 관점 철학 */}
          {data.entry_points && (
            <section>
              <div className="flex items-baseline justify-between mb-1 gap-2 flex-wrap">
                <h4 className="text-xs font-medium text-muted-foreground">
                  📌 진입 관찰 구간
                </h4>
                {currentPrice != null && (
                  <span className="text-[10px] text-muted-foreground font-mono">
                    현재가 {currentPrice.toLocaleString()}{cur}
                  </span>
                )}
              </div>
              {HORIZON_PHILOSOPHY[data.persona_used] && (
                <p className="text-[11px] text-muted-foreground mb-2 italic">
                  💭 {HORIZON_PHILOSOPHY[data.persona_used]}
                </p>
              )}
              <div className="grid grid-cols-3 gap-2 text-sm">
                {(["tier_1", "tier_2", "tier_3"] as const).map((k, i) => {
                  const price = data.entry_points![k];
                  const pct = pctFromCurrent(price, currentPrice);
                  const tone = pctTone(price, currentPrice);
                  return (
                    <div key={k} className="p-2 rounded-md bg-muted/30">
                      <div className="text-xs text-muted-foreground">
                        {i + 1}차 관찰 구간
                      </div>
                      <div className="font-medium font-mono">
                        {price.toLocaleString()}{cur}
                      </div>
                      {pct && (
                        <div className={`text-[10px] font-mono ${tone}`}>
                          {pct}
                        </div>
                      )}
                    </div>
                  );
                })}
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

          {/* 회복·차익 실현 참고선 (exit_points) — LEGAL: '목표가' 단어 금지, 참고선 표현 */}
          {data.exit_points && (
            <section>
              <h4 className="text-xs font-medium text-muted-foreground mb-2">
                🎯 회복·차익 실현 참고선
                <span className="ml-2 text-[10px] text-muted-foreground font-normal">
                  (매도 권유 아닌 참고)
                </span>
              </h4>
              <div className="grid grid-cols-3 gap-2 text-sm">
                {([
                  { key: "stop_loss", label: "손실 한도 참고선", emoji: "🛑" },
                  { key: "take_profit_1", label: "1차 차익 실현 참고선", emoji: "🌱" },
                  { key: "take_profit_final", label: "최종 참고선", emoji: "🌳" },
                ] as const).map(({ key, label, emoji }) => {
                  const price = data.exit_points![key];
                  const pct = pctFromCurrent(price, currentPrice);
                  const tone = pctTone(price, currentPrice);
                  return (
                    <div key={key} className="p-2 rounded-md bg-muted/30">
                      <div className="text-xs text-muted-foreground">
                        {emoji} {label}
                      </div>
                      <div className="font-medium font-mono">
                        {price.toLocaleString()}{cur}
                      </div>
                      {pct && (
                        <div className={`text-[10px] font-mono ${tone}`}>
                          {pct}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
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
