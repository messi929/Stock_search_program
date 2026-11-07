"use client";

import { ChartCandlestick, CheckCircle2, ListFilter, Star } from "lucide-react";
import Link from "next/link";

import { Card, CardContent } from "@/components/ui/card";

const STEPS = [
  {
    href: "/analyze",
    icon: ChartCandlestick,
    tint: "bg-tint-1/15 text-tint-1",
    title: "궁금한 종목을 분석해 보세요",
    desc: "아는 회사 이름을 검색하면 됩니다. 삼성전자처럼 익숙한 종목부터 시작해도 좋아요.",
  },
  {
    href: "/screener",
    icon: ListFilter,
    tint: "bg-tint-2/15 text-tint-2",
    title: "조건에 맞는 종목을 둘러보세요",
    desc: "배당, 저평가, 외국인 매수 같은 주제별 목록을 이미 만들어 두었습니다.",
  },
  {
    href: "/watchlist/add",
    icon: Star,
    tint: "bg-tint-3/15 text-tint-3",
    title: "관심 종목을 모아두세요",
    desc: "추가해 두면 홈에서 가격 움직임을 한눈에 볼 수 있습니다.",
  },
];

/** 첫 방문자 안내 — 관심 종목도, 분석 이력도 없을 때만 홈에 노출한다. */
export function GettingStarted() {
  return (
    <section aria-labelledby="getting-started" className="space-y-3">
      <h2 id="getting-started" className="flex items-center gap-1.5 font-semibold">
        <CheckCircle2 aria-hidden="true" className="size-[18px] text-primary" />
        처음이라면 이렇게 시작해 보세요
      </h2>
      <ol className="grid gap-3 md:grid-cols-3">
        {STEPS.map((s, i) => {
          const Icon = s.icon;
          return (
            <li key={s.href}>
              <Link href={s.href} className="block h-full rounded-xl focus-visible:ring-2 focus-visible:ring-ring">
                <Card className="h-full transition hover:ring-primary/40">
                  <CardContent className="space-y-2 p-5">
                    <div className="flex items-center justify-between">
                      <span className={`flex size-9 items-center justify-center rounded-lg ${s.tint}`}>
                        <Icon aria-hidden="true" className="size-5" />
                      </span>
                      <span className="text-xs font-medium text-muted-foreground">{i + 1}단계</span>
                    </div>
                    <h3 className="font-semibold">{s.title}</h3>
                    <p className="leading-relaxed text-muted-foreground">{s.desc}</p>
                  </CardContent>
                </Card>
              </Link>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
