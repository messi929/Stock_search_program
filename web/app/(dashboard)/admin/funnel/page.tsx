"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { adminApi, type FunnelCohort } from "@/lib/admin";

const RANGES = [
  { days: 7, label: "7일" },
  { days: 30, label: "30일" },
  { days: 90, label: "90일" },
];

/** 퍼널 단계 막대 — 가입 대비 비율로 폭 표현. */
function FunnelBar({
  label,
  value,
  base,
  rate,
  hint,
  tone,
}: {
  label: string;
  value: number;
  base: number;
  rate?: number;
  hint?: string;
  tone: string;
}) {
  const width = base > 0 ? Math.max(3, (value / base) * 100) : 3;
  return (
    <div className="space-y-1">
      <div className="flex items-baseline justify-between text-sm">
        <span className="font-medium">{label}</span>
        <span className="tabular-nums">
          <b className="text-lg">{value}</b>
          {rate != null && (
            <span className="text-muted-foreground ml-2">{rate}%</span>
          )}
        </span>
      </div>
      <div className="h-7 bg-muted rounded overflow-hidden">
        <div
          className={`h-full ${tone} transition-all flex items-center justify-end pr-2`}
          style={{ width: `${width}%` }}
        />
      </div>
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}

/** 일별 가입 추이 막대 차트(순수 div). */
function TrendChart({ trend }: { trend: { date: string; signups: number }[] }) {
  const max = Math.max(1, ...trend.map((t) => t.signups));
  const total = trend.reduce((s, t) => s + t.signups, 0);
  return (
    <div className="rounded-xl ring-1 ring-foreground/10 p-4">
      <div className="flex items-baseline justify-between mb-3">
        <h3 className="text-sm font-semibold">일별 신규 가입</h3>
        <span className="text-xs text-muted-foreground">
          기간 합계 {total}명 · 최대 {max}명/일
        </span>
      </div>
      {trend.length === 0 ? (
        <p className="text-sm text-muted-foreground">데이터 없음</p>
      ) : (
        <div className="flex items-end gap-[2px] h-32">
          {trend.map((t) => (
            <div
              key={t.date}
              className="flex-1 group relative flex flex-col justify-end"
              title={`${t.date}: ${t.signups}명`}
            >
              <div
                className={`w-full rounded-t ${
                  t.signups > 0 ? "bg-primary/70 group-hover:bg-primary" : "bg-muted"
                } transition`}
                style={{ height: `${(t.signups / max) * 100}%`, minHeight: 2 }}
              />
            </div>
          ))}
        </div>
      )}
      {trend.length > 0 && (
        <div className="flex justify-between text-[10px] text-muted-foreground mt-1">
          <span>{trend[0].date.slice(5)}</span>
          <span>{trend[trend.length - 1].date.slice(5)}</span>
        </div>
      )}
    </div>
  );
}

/** 어디가 새는지 한 줄 진단. */
function diagnose(c: FunnelCohort): { msg: string; tone: string } {
  if (c.signups === 0)
    return {
      msg: "이 기간 신규 가입이 0입니다 → 유입(트래픽) 자체가 문제. 마케팅·SEO부터.",
      tone: "text-amber-600",
    };
  if (c.activation_rate < 40)
    return {
      msg: `가입은 있는데 활성화율 ${c.activation_rate}% → 가입 후 분석을 안 돌립니다. 온보딩·첫 경험이 새는 구멍.`,
      tone: "text-red-500",
    };
  if (c.activated > 0 && c.paid_rate < 3)
    return {
      msg: `활성화는 ${c.activation_rate}%로 양호하나 결제 전환 ${c.paid_rate}% → 가치는 느끼지만 지갑이 안 열림. 가격·결제 설득이 구멍.`,
      tone: "text-orange-500",
    };
  return {
    msg: `활성화 ${c.activation_rate}% · 결제 ${c.paid_rate}% — 단계별로 큰 누수는 없음. 상단(유입) 볼륨을 키우는 단계.`,
    tone: "text-emerald-600",
  };
}

export default function AdminFunnelPage() {
  const [days, setDays] = useState(30);
  const { data, isLoading, isError } = useQuery({
    queryKey: ["admin", "funnel", days],
    queryFn: () => adminApi.funnel(days),
  });

  const c = data?.cohort;
  const diag = c ? diagnose(c) : null;

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-2">
        <span className="text-sm text-muted-foreground mr-1">기간</span>
        {RANGES.map((r) => (
          <button
            key={r.days}
            onClick={() => setDays(r.days)}
            className={`px-3 py-1.5 rounded-md text-sm ring-1 transition ${
              days === r.days
                ? "bg-primary text-primary-foreground ring-primary"
                : "ring-foreground/15 text-muted-foreground hover:text-foreground"
            }`}
          >
            {r.label}
          </button>
        ))}
      </div>

      {isLoading && <p className="text-sm text-muted-foreground">집계 중...</p>}
      {isError && <p className="text-sm text-red-500">조회 실패 (권한 확인)</p>}

      {data && c && (
        <>
          {/* 한 줄 진단 */}
          {diag && (
            <div className="rounded-xl bg-card ring-1 ring-foreground/10 p-4">
              <p className="text-xs text-muted-foreground mb-1">진단</p>
              <p className={`text-sm font-medium ${diag.tone}`}>{diag.msg}</p>
            </div>
          )}

          {/* 일별 가입 추이 */}
          <TrendChart trend={data.trend} />

          {/* 코호트 퍼널 */}
          <div className="rounded-xl ring-1 ring-foreground/10 p-4 space-y-4">
            <div className="flex items-baseline justify-between">
              <h3 className="text-sm font-semibold">
                최근 {days}일 가입자 퍼널
              </h3>
              <span className="text-xs text-muted-foreground">
                가입 대비 비율
              </span>
            </div>
            <FunnelBar
              label="가입"
              value={c.signups}
              base={c.signups}
              tone="bg-primary"
            />
            <FunnelBar
              label="활성화 (분석 1회+)"
              value={c.activated}
              base={c.signups}
              rate={c.activation_rate}
              tone="bg-primary/75"
              hint={
                c.median_hours_to_activate > 0
                  ? `가입→첫 분석 중앙값 ${c.median_hours_to_activate}시간`
                  : undefined
              }
            />
            <FunnelBar
              label="체험 시작"
              value={c.trial}
              base={c.signups}
              rate={c.trial_rate}
              tone="bg-primary/55"
            />
            <FunnelBar
              label="결제 (Pro)"
              value={c.paid}
              base={c.signups}
              rate={c.paid_rate}
              tone="bg-emerald-500/70"
              hint={
                c.activated > 0
                  ? `활성화→결제 전환 ${c.activated_to_paid_rate}%`
                  : undefined
              }
            />
          </div>

          {/* 전체(all-time) */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="rounded-xl bg-card ring-1 ring-foreground/10 p-4">
              <p className="text-xs text-muted-foreground">전체 가입자</p>
              <p className="text-2xl font-bold mt-1 tabular-nums">
                {data.overall.total}
              </p>
            </div>
            <div className="rounded-xl bg-card ring-1 ring-foreground/10 p-4">
              <p className="text-xs text-muted-foreground">전체 활성화율</p>
              <p className="text-2xl font-bold mt-1 tabular-nums">
                {data.overall.activation_rate}%
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                {data.overall.activated}명 분석 경험
              </p>
            </div>
            <div className="rounded-xl bg-card ring-1 ring-foreground/10 p-4">
              <p className="text-xs text-muted-foreground">전체 결제</p>
              <p className="text-2xl font-bold mt-1 tabular-nums">
                {data.overall.paid}
              </p>
            </div>
            <div className="rounded-xl bg-card ring-1 ring-foreground/10 p-4">
              <p className="text-xs text-muted-foreground">활동 유저(누적)</p>
              <p className="text-2xl font-bold mt-1 tabular-nums">
                {data.engaged_total}
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                분석·검증·발견 1회+
              </p>
            </div>
          </div>

          <p className="text-xs text-muted-foreground">
            ※ 방문자(트래픽) 수는 이 콘솔이 아닌 Vercel Analytics·GA에서 확인하세요.
            여기 &quot;가입&quot;이 깔때기의 첫 단계입니다. 관리자 계정은 집계에서 제외됩니다.
          </p>
        </>
      )}
    </div>
  );
}
