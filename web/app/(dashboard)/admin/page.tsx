"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";

import { adminApi, won } from "@/lib/admin";

function Stat({
  label,
  value,
  sub,
  href,
}: {
  label: string;
  value: string;
  sub?: string;
  href?: string;
}) {
  const body = (
    <div className="rounded-xl bg-card ring-1 ring-foreground/10 p-4 h-full hover:ring-foreground/20 transition">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="text-2xl font-bold mt-1 tabular-nums">{value}</p>
      {sub && <p className="text-xs text-muted-foreground mt-1">{sub}</p>}
    </div>
  );
  return href ? (
    <Link href={href} className="block">
      {body}
    </Link>
  ) : (
    body
  );
}

export default function AdminOverviewPage() {
  const stats = useQuery({ queryKey: ["admin", "stats"], queryFn: adminApi.stats });
  const funnel = useQuery({ queryKey: ["admin", "funnel", 30], queryFn: () => adminApi.funnel(30) });
  const revenue = useQuery({ queryKey: ["admin", "revenue"], queryFn: adminApi.revenue });
  const usage = useQuery({ queryKey: ["admin", "usage", "current"], queryFn: () => adminApi.usage() });
  const errors = useQuery({
    queryKey: ["admin", "errors-summary", 7],
    queryFn: () => adminApi.errorsSummary(7),
  });

  const todayKey = new Date().toISOString().slice(0, 10);
  const errToday = errors.data?.by_day?.[todayKey] ?? 0;

  return (
    <div className="space-y-6">
      {/* 가입자 */}
      <section>
        <h2 className="text-sm font-semibold text-muted-foreground mb-2">가입자</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Stat label="총 가입자" value={(stats.data?.total ?? "—").toString()} href="/admin/users" />
          <Stat label="Pro" value={(stats.data?.pro ?? "—").toString()} href="/admin/users?filter=pro" />
          <Stat label="Free" value={(stats.data?.free ?? "—").toString()} href="/admin/users?filter=free" />
          <Stat
            label="체험 중"
            value={(stats.data?.trial_active ?? "—").toString()}
            sub={`의심 ${stats.data?.suspicious ?? 0} · 정지 ${stats.data?.suspended ?? 0}`}
            href="/admin/users?filter=trial"
          />
        </div>
      </section>

      {/* 퍼널 (최근 30일) */}
      <section>
        <h2 className="text-sm font-semibold text-muted-foreground mb-2">
          가입·전환 퍼널 <span className="font-normal">(최근 30일)</span>
        </h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Stat
            label="신규 가입"
            value={(funnel.data?.cohort.signups ?? "—").toString()}
            href="/admin/funnel"
          />
          <Stat
            label="활성화율"
            value={funnel.data ? `${funnel.data.cohort.activation_rate}%` : "—"}
            sub={`분석 1회+ ${funnel.data?.cohort.activated ?? 0}명`}
            href="/admin/funnel"
          />
          <Stat
            label="체험 전환"
            value={funnel.data ? `${funnel.data.cohort.trial_rate}%` : "—"}
            href="/admin/funnel"
          />
          <Stat
            label="결제 전환"
            value={funnel.data ? `${funnel.data.cohort.paid_rate}%` : "—"}
            sub={`결제 ${funnel.data?.cohort.paid ?? 0}명`}
            href="/admin/funnel"
          />
        </div>
      </section>

      {/* 수입 */}
      <section>
        <h2 className="text-sm font-semibold text-muted-foreground mb-2">
          수입 <span className="font-normal">(추정)</span>
        </h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Stat label="MRR (월 환산)" value={won(revenue.data?.mrr_krw)} href="/admin/revenue" />
          <Stat label="ARR (연 환산)" value={won(revenue.data?.arr_krw)} href="/admin/revenue" />
          <Stat
            label="활성 구독"
            value={(revenue.data?.active_subscriptions ?? "—").toString()}
            sub={`월 ${revenue.data?.by_plan.monthly ?? 0} · 연 ${revenue.data?.by_plan.yearly ?? 0}`}
            href="/admin/revenue"
          />
          <Stat
            label="해지 예정"
            value={(revenue.data?.cancel_scheduled ?? "—").toString()}
            href="/admin/revenue"
          />
        </div>
      </section>

      {/* 사용량 / 에러 */}
      <section>
        <h2 className="text-sm font-semibold text-muted-foreground mb-2">
          사용량 · 에러
        </h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Stat
            label={`이달 AI 비용 (${usage.data?.month ?? ""})`}
            value={won(usage.data?.totals.krw)}
            sub={`분석 ${usage.data?.totals.analyses ?? 0} · 활성 ${usage.data?.totals.active_users ?? 0}명`}
            href="/admin/usage"
          />
          <Stat
            label="오늘 에러"
            value={errToday.toString()}
            href="/admin/errors"
          />
          <Stat
            label="최근 7일 에러"
            value={(errors.data?.total ?? "—").toString()}
            href="/admin/errors"
          />
          <Stat
            label="검증/발견 (이달)"
            value={`${usage.data?.totals.validations ?? 0} / ${usage.data?.totals.discoveries ?? 0}`}
            href="/admin/usage"
          />
        </div>
      </section>

      {(stats.isError || funnel.isError || revenue.isError || usage.isError || errors.isError) && (
        <p className="text-sm text-red-500">
          일부 데이터를 불러오지 못했습니다. 새로고침하거나 권한을 확인하세요.
        </p>
      )}
    </div>
  );
}
