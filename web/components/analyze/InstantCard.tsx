"use client";

/**
 * 빠른 요약 카드 — 본 분석(4에이전트, ~12s) 도착 전 즉시 노출.
 *
 * instant_snapshot(스크리너 캐시, 비용 0)로 종목 핵심 수치를 즉시 보여주고,
 * instant_summary(Haiku 1줄, ~2s)가 오면 그 자리에 채운다. Strategist가 완료되면
 * AnalyzeView가 이 카드를 숨기고 정밀 결과로 대체한다.
 *
 * 한국 시장 컬러 규칙: 상승 🔴 / 하락 🔵.
 */
import { PriceChange } from "@/components/stocks/PriceChange";
import { Card, CardContent } from "@/components/ui/card";
import { Term } from "@/components/ui/term";
import type { InstantSnapshot } from "@/store/analysisStore";

function Metric({ label, value }: { label: React.ReactNode; value: string }) {
  return (
    <div className="flex flex-col">
      <span className="text-xs text-muted-foreground">
        {label}
      </span>
      <span className="text-sm font-medium tabular-nums">{value}</span>
    </div>
  );
}

export function InstantCard({
  snapshot,
  summary,
}: {
  snapshot: InstantSnapshot;
  summary: string | null;
}) {
  const unit = snapshot.is_kr ? "원" : "달러";
  const price =
    snapshot.price != null
      ? `${snapshot.price.toLocaleString()}${unit}`
      : "—";

  return (
    <Card className="overflow-visible">
      <CardContent className="p-4 space-y-3">
        <div className="flex items-center gap-2">
          <span className="text-xs px-1.5 py-0.5 rounded bg-info/15 text-info font-medium">
            빠른 참고
          </span>
          <span className="text-[11px] text-muted-foreground">
            정밀 분석을 불러오는 동안 먼저 보는 스냅샷입니다
          </span>
        </div>

        {/* 핵심 수치 그리드 */}
        <div className="grid grid-cols-3 sm:grid-cols-4 gap-3">
          <div className="flex flex-col">
            <span className="text-xs text-muted-foreground">
              현재가
            </span>
            <span className="text-sm font-medium tabular-nums">
              {price}
              <PriceChange pct={snapshot.change_pct} className="ml-1 text-xs" />
            </span>
          </div>
          {snapshot.rsi != null && (
            <Metric label={<Term id="rsi" />} value={snapshot.rsi.toFixed(0)} />
          )}
          {snapshot.vs_high_52w != null && (
            <Metric
              label={<Term id="vs_high_52w" />}
              value={`${snapshot.vs_high_52w > 0 ? "+" : ""}${snapshot.vs_high_52w.toFixed(1)}%`}
            />
          )}
          {snapshot.per ? <Metric label={<Term id="per" />} value={snapshot.per.toFixed(1)} /> : null}
          {snapshot.pbr ? <Metric label={<Term id="pbr" />} value={snapshot.pbr.toFixed(2)} /> : null}
          {snapshot.roe ? (
            <Metric label={<Term id="roe" />} value={`${snapshot.roe.toFixed(1)}%`} />
          ) : null}
          {snapshot.foreign_consecutive > 0 && (
            <Metric label={<Term id="foreign_consecutive" />} value={`${snapshot.foreign_consecutive}일`} />
          )}
          {snapshot.sector && <Metric label="섹터" value={snapshot.sector} />}
        </div>

        {/* Haiku 1줄 요약 — 도착 전엔 shimmer */}
        <div className="pt-1 border-t border-border/50">
          {summary ? (
            <p className="text-sm leading-relaxed text-foreground/90">{summary}</p>
          ) : (
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <span className="inline-block h-3 w-3 rounded-full border-2 border-info border-t-transparent animate-spin" />
              빠른 요약 작성 중...
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
