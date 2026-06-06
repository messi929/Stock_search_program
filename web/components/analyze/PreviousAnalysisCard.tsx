"use client";

/**
 * 이전 분석 카드 — 종목 진입 시 차트 하단에 표시.
 *
 * "지난번 이 종목 분석 때 1차 진입/손절이 이랬다"를 한눈에 보여주고, 당시가 대비
 * 현재가 변화를 함께 표기. 아래에서 새 분석을 진행하기 전 참고용.
 * 직전 strategist 분석이 없으면 아무것도 렌더하지 않음(첫 분석 화면을 깔끔히 유지).
 */
import { usePreviousAnalysis } from "@/hooks/usePreviousAnalysis";
import { PERSONA_BY_ID, type PersonaId } from "@/types/persona";

function fmtPrice(v: number | null | undefined, isKR: boolean): string {
  if (v == null) return "-";
  return isKR ? `${v.toLocaleString()}원` : `$${v.toLocaleString()}`;
}

/** 당시가 대비 변화율 (KR 컬러: 상승 빨강 / 하락 파랑) */
function MovePct({ from, to }: { from: number | null; to: number | null }) {
  if (from == null || to == null || from <= 0) return null;
  const pct = ((to - from) / from) * 100;
  const cls =
    pct > 0 ? "text-red-500" : pct < 0 ? "text-blue-500" : "text-muted-foreground";
  return (
    <span className={`font-medium ${cls}`}>
      {pct > 0 ? "+" : ""}
      {pct.toFixed(1)}%
    </span>
  );
}

export function PreviousAnalysisCard({
  ticker,
  currentPrice,
  isKR,
}: {
  ticker: string;
  currentPrice: number | null;
  isKR: boolean;
}) {
  const { data } = usePreviousAnalysis(ticker);
  const prev = data?.item;
  if (!prev || !prev.entry_points) return null;

  const ep = prev.entry_points;
  const xp = prev.exit_points;
  const then = prev.price ?? null;
  const personaName =
    PERSONA_BY_ID[prev.persona as PersonaId]?.name ?? prev.persona ?? "분석";
  const dateLabel = prev.at
    ? new Date(prev.at).toLocaleDateString("ko-KR", {
        year: "numeric",
        month: "long",
        day: "numeric",
      })
    : "";

  const tiers: Array<{ label: string; value: number | undefined }> = [
    { label: "1차", value: ep.tier_1 },
    { label: "2차", value: ep.tier_2 },
    { label: "3차", value: ep.tier_3 },
  ];

  return (
    <section className="rounded-lg border border-amber-500/30 bg-amber-500/[0.04] p-4 space-y-3">
      {/* 헤더 */}
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold">📌 이전 분석</span>
          <span className="text-xs px-2 py-0.5 rounded-full bg-muted text-muted-foreground">
            {personaName}
          </span>
        </div>
        {dateLabel && (
          <span className="text-xs text-muted-foreground">{dateLabel}</span>
        )}
      </div>

      {/* 당시가 → 현재가 */}
      <div className="flex items-baseline gap-2 text-sm">
        <span className="text-muted-foreground">분석 당시</span>
        <span className="font-mono font-medium">{fmtPrice(then, isKR)}</span>
        {currentPrice != null && then != null && (
          <>
            <span className="text-muted-foreground">→ 현재</span>
            <span className="font-mono font-medium">
              {fmtPrice(currentPrice, isKR)}
            </span>
            <MovePct from={then} to={currentPrice} />
          </>
        )}
      </div>

      {/* 진입 관찰 구간 (1/2/3차) */}
      <div>
        <div className="text-xs text-muted-foreground mb-1">관찰 구간 (당시 제시)</div>
        <div className="grid grid-cols-3 gap-2">
          {tiers.map((t) => (
            <div key={t.label} className="rounded-md bg-muted/40 p-2 text-center">
              <div className="text-[10px] text-muted-foreground">{t.label} 진입</div>
              <div className="font-mono text-sm font-medium">
                {fmtPrice(t.value, isKR)}
              </div>
              {then != null && t.value != null && then > 0 && (
                <div className="text-[10px] text-muted-foreground">
                  당시 대비 {(((t.value - then) / then) * 100).toFixed(0)}%
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* 손절 / 익절 참고선 */}
      {xp && (
        <div className="grid grid-cols-3 gap-2">
          <div className="rounded-md bg-blue-500/10 p-2 text-center">
            <div className="text-[10px] text-muted-foreground">손실 한도</div>
            <div className="font-mono text-sm font-medium">
              {fmtPrice(xp.stop_loss, isKR)}
            </div>
          </div>
          <div className="rounded-md bg-red-500/10 p-2 text-center">
            <div className="text-[10px] text-muted-foreground">1차 익절</div>
            <div className="font-mono text-sm font-medium">
              {fmtPrice(xp.take_profit_1, isKR)}
            </div>
          </div>
          <div className="rounded-md bg-red-500/10 p-2 text-center">
            <div className="text-[10px] text-muted-foreground">최종 익절</div>
            <div className="font-mono text-sm font-medium">
              {fmtPrice(xp.take_profit_final, isKR)}
            </div>
          </div>
        </div>
      )}

      {/* 당시 요약 (2줄) */}
      {prev.summary && (
        <p className="text-xs text-muted-foreground leading-relaxed line-clamp-2">
          {prev.summary}
        </p>
      )}

      <p className="text-[10px] text-muted-foreground">
        지난 분석 시점의 참고치입니다. 아래에서 현재 시점으로 새로 분석하세요.
      </p>
    </section>
  );
}
