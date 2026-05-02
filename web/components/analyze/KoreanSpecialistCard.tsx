"use client";

/**
 * Korean Specialist 결과 카드 — Week D Day 5 신규.
 *
 * 핵심 표시:
 *  1. 5각형 점수 차트 (외국인/거버넌스/밸류업/테마/정책)
 *  2. weighted_total + interpretation
 *  3. governance_disclaimer 강조
 *  4. summary_neutral
 *
 * SVG 5각형은 외부 차트 라이브러리 없이 polygon으로 직접 렌더 (의존성 최소).
 */

import {
  AgentCardShell,
  type AgentStatus,
} from "@/components/analyze/AgentCardShell";
import type { KoreaSpecificScore, KoreanSpecialistResult } from "@/types/api";

const SCORE_LABELS: Array<{ key: keyof Omit<KoreaSpecificScore, "weighted_total" | "interpretation">; label: string }> = [
  { key: "foreign_supply", label: "외국인 수급" },
  { key: "governance", label: "거버넌스" },
  { key: "valueup_alignment", label: "밸류업" },
  { key: "theme_position", label: "테마 위치" },
  { key: "policy_friendliness", label: "정책 친화" },
];

export function KoreanSpecialistCard({
  data,
  status,
}: {
  data: KoreanSpecialistResult | null;
  status: AgentStatus;
}) {
  return (
    <AgentCardShell
      icon="🇰🇷"
      title="한국 시장 특수성 (Korean Specialist)"
      subtitle={
        data
          ? `종합 ${data.korea_specific_score.weighted_total.toFixed(1)}/10`
          : "Sonnet"
      }
      status={status}
    >
      {!data ? (
        status === "running" ? (
          <p className="text-sm text-muted-foreground">
            외국인 수급 + 재벌 구조 + 밸류업 + 거버넌스 + 공매도 데이터 통합 중...
          </p>
        ) : null
      ) : (
        <div className="space-y-4">
          {/* 5각형 점수 차트 */}
          <section className="grid grid-cols-1 md:grid-cols-2 gap-3 items-center">
            <PentagonChart scores={data.korea_specific_score} />
            <ScoreList scores={data.korea_specific_score} />
          </section>

          {/* 종합 점수 + 해석 */}
          {data.korea_specific_score.interpretation && (
            <p className="text-sm leading-relaxed">
              {data.korea_specific_score.interpretation}
            </p>
          )}

          {/* 거버넌스 disclaimer (강조) */}
          {data.chaebol_structure_analysis?.governance_disclaimer ? (
            <div className="rounded-md border border-amber-500/40 bg-amber-500/5 p-2 text-xs text-muted-foreground leading-relaxed">
              ⚠️ {String(data.chaebol_structure_analysis.governance_disclaimer)}
            </div>
          ) : null}

          {/* 모니터링 항목 */}
          {data.what_to_watch_korea_specific.length > 0 && (
            <section>
              <h4 className="text-xs font-medium text-muted-foreground mb-1">
                한국 특수 모니터링 항목
              </h4>
              <ul className="text-sm space-y-0.5">
                {data.what_to_watch_korea_specific.slice(0, 5).map((w, i) => (
                  <li key={i}>• {w}</li>
                ))}
              </ul>
            </section>
          )}

          {/* 종합 자연어 */}
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

/** 5각형 (펜타곤) 점수 차트 — 의존성 없이 SVG polygon 사용. */
function PentagonChart({ scores }: { scores: KoreaSpecificScore }) {
  const SIZE = 200;
  const CENTER = SIZE / 2;
  const RADIUS = 80;

  // 5 축 각도 (12시 방향부터 시계방향, -90° 시작)
  const angleFor = (i: number) => -Math.PI / 2 + (i * 2 * Math.PI) / SCORE_LABELS.length;

  const axisPoint = (i: number, ratio: number) => {
    const r = RADIUS * ratio;
    return {
      x: CENTER + r * Math.cos(angleFor(i)),
      y: CENTER + r * Math.sin(angleFor(i)),
    };
  };

  // 그리드 (4 단계: 0.25 / 0.5 / 0.75 / 1.0)
  const gridLevels = [0.25, 0.5, 0.75, 1];

  // 데이터 polygon
  const dataPoints = SCORE_LABELS.map((s, i) => {
    const v = (scores[s.key] ?? 0) / 10;
    return axisPoint(i, Math.max(0, Math.min(1, v)));
  });
  const dataPolygon = dataPoints.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ");

  return (
    <div className="flex justify-center">
      <svg width={SIZE} height={SIZE} viewBox={`0 0 ${SIZE} ${SIZE}`} role="img" aria-label="5축 한국 시장 점수">
        {/* 배경 그리드 */}
        {gridLevels.map((lvl) => {
          const pts = SCORE_LABELS.map((_, i) => axisPoint(i, lvl));
          return (
            <polygon
              key={lvl}
              points={pts.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ")}
              fill="none"
              stroke="currentColor"
              strokeOpacity={0.12}
              strokeWidth={1}
            />
          );
        })}

        {/* 축 선 */}
        {SCORE_LABELS.map((_, i) => {
          const p = axisPoint(i, 1);
          return (
            <line
              key={i}
              x1={CENTER}
              y1={CENTER}
              x2={p.x}
              y2={p.y}
              stroke="currentColor"
              strokeOpacity={0.18}
              strokeWidth={1}
            />
          );
        })}

        {/* 데이터 polygon */}
        <polygon
          points={dataPolygon}
          fill="rgb(244 63 94 / 0.25)"
          stroke="rgb(244 63 94)"
          strokeWidth={2}
        />
        {/* 데이터 점 */}
        {dataPoints.map((p, i) => (
          <circle
            key={i}
            cx={p.x}
            cy={p.y}
            r={3}
            fill="rgb(244 63 94)"
          />
        ))}

        {/* 라벨 */}
        {SCORE_LABELS.map((s, i) => {
          const p = axisPoint(i, 1.2);
          // 텍스트 정렬 (각도 기반)
          const a = angleFor(i);
          const anchor =
            Math.abs(Math.cos(a)) < 0.1
              ? "middle"
              : Math.cos(a) > 0
                ? "start"
                : "end";
          const baseline = Math.sin(a) > 0.1 ? "hanging" : Math.sin(a) < -0.1 ? "auto" : "central";
          return (
            <text
              key={s.key}
              x={p.x}
              y={p.y}
              textAnchor={anchor}
              dominantBaseline={baseline as never}
              className="text-[10px] fill-muted-foreground"
            >
              {s.label}
            </text>
          );
        })}
      </svg>
    </div>
  );
}

function ScoreList({ scores }: { scores: KoreaSpecificScore }) {
  return (
    <div className="space-y-1.5 text-sm">
      {SCORE_LABELS.map((s) => {
        const v = scores[s.key] ?? 0;
        const pct = Math.max(0, Math.min(100, v * 10));
        return (
          <div key={s.key}>
            <div className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground">{s.label}</span>
              <span className="font-mono">{v.toFixed(1)}/10</span>
            </div>
            <div className="h-1 rounded bg-muted overflow-hidden">
              <div
                className="h-full bg-rose-500/70"
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>
        );
      })}
      <div className="pt-2 border-t mt-2">
        <div className="flex items-center justify-between text-sm">
          <span className="font-medium">종합 점수</span>
          <span className="font-mono font-semibold">
            {scores.weighted_total.toFixed(2)}/10
          </span>
        </div>
      </div>
    </div>
  );
}
