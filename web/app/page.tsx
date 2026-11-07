/**
 * 랜딩 페이지 (/) — 비로그인 방문자 대상.
 *
 * 정식 오픈 기준 (베타 게이팅 제거):
 *  - Hero CTA = '무료로 시작하기'(/login) + '요금제 보기'(/pricing)
 *  - '3단계로 시작' 가이드로 처음 방문자에게 다음 행동을 명시
 *  - 마지막 '지금 시작' CTA로 다시 한 번 유입
 */
import { BellRing, BookOpen, ChartCandlestick, Search, ShieldCheck, Users, type LucideIcon } from "lucide-react";
import Link from "next/link";

import { HorizonIcon } from "@/components/analyze/HorizonIcon";
import { ObservationRange, RsiMeter } from "@/components/viz/Meters";
import { HeroPreview } from "@/components/landing/HeroPreview";
import { LandingRedirect } from "@/components/landing/LandingRedirect";
import { Disclaimer } from "@/components/legal/Disclaimer";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Logo } from "@/components/ui/logo";
import { HORIZON_META } from "@/types/persona";

// Hero 아래 신뢰 배지 — 한 줄에 차별점·정당성 압축
const TRUST_BADGES = [
  "KIS 공식 OpenAPI 데이터",
  "4가지 기간 관점",
  "수치 실시간 재검증",
  "어려운 용어 쉬운 풀이",
];

const STEP_TINTS = ["bg-tint-1/15 text-tint-1", "bg-tint-2/15 text-tint-2", "bg-tint-3/15 text-tint-3"];
const HORIZON_TINTS = ["bg-tint-2/15 text-tint-2", "bg-tint-5/15 text-tint-5", "bg-tint-1/15 text-tint-1", "bg-tint-4/15 text-tint-4"];
const FEATURE_TINTS = [
  "bg-tint-1/15 text-tint-1",
  "bg-tint-4/15 text-tint-4",
  "bg-tint-5/15 text-tint-5",
  "bg-tint-3/15 text-tint-3",
  "bg-tint-2/15 text-tint-2",
  "bg-tint-6/15 text-tint-6",
];

const AGENT_ROLES = ["시장 조사", "데이터 해석", "수치 검증", "종합 정리"];

/** 기능 카드 안의 작은 화면 조각. 실제 앱과 같은 부품을 예시값으로 그린다. */
function FeatureVisual({ index }: { index: number }) {
  if (index === 0) {
    return (
      <ol className="flex flex-wrap gap-1.5">
        {AGENT_ROLES.map((r) => (
          <li key={r} className="rounded-md bg-muted px-2 py-1 text-xs">
            {r}
          </li>
        ))}
      </ol>
    );
  }
  if (index === 1) {
    return (
      <ul className="space-y-1 text-xs">
        {["PER", "현재가", "ROE"].map((k) => (
          <li key={k} className="flex items-center justify-between rounded-md bg-muted px-2 py-1">
            {k}
            <span className="font-medium text-success">일치</span>
          </li>
        ))}
      </ul>
    );
  }
  if (index === 2) {
    return (
      <div className="rounded-md bg-muted px-2 py-2">
        <ObservationRange low={40} high={85} current={58} unit="" />
        <div className="flex justify-between px-2 pt-1 text-xs text-muted-foreground">
          <span>저점</span>
          <span>고점</span>
        </div>
      </div>
    );
  }
  if (index === 3) return <RsiMeter value={58} label="RSI" />;
  return null;
}

const FEATURES: { icon: LucideIcon; title: string; desc: string }[] = [
  {
    icon: Users,
    title: "AI 4명이 역할을 나눠 분석",
    desc: "시장 조사, 데이터 해석, 수치 검증, 종합 정리를 따로 맡아 한 번 더 걸러냅니다.",
  },
  {
    icon: ShieldCheck,
    title: "실시간 검증",
    desc: "AI 답변의 수치를 지금 시점 데이터와 다시 대조합니다. 차이가 크면 바로 알려드려요.",
  },
  {
    icon: ChartCandlestick,
    title: "저점~고점 관찰 범위",
    desc: "단기부터 장기까지, 보는 기간별로 데이터가 가리키는 참고 가격대를 함께 보여드립니다.",
  },
  {
    icon: BookOpen,
    title: "처음이어도 읽히는 화면",
    desc: "PER, RSI 같은 용어를 누르면 쉬운 말로 풀어드려요. 공부하면서 쓰기 좋습니다.",
  },
  {
    icon: BellRing,
    title: "관찰 구간 알림 (준비 중)",
    desc: "저장해 둔 관찰 구간에 가격이 닿으면 알려드리는 기능을 준비하고 있습니다.",
  },
  {
    icon: Search,
    title: "종목 찾기부터 시작",
    desc: "주제별 스마트 리스트와 AI 종목 발견으로 관심 종목을 넓혀보세요.",
  },
];

const STEPS = [
  { title: "가입하기", desc: "30초면 충분합니다. 신용카드는 필요 없어요." },
  { title: "종목과 기간 고르기", desc: "회사 이름을 검색하고 보고 싶은 기간을 선택합니다." },
  { title: "분석 확인하기", desc: "AI 분석을 읽고, 수치는 지금 시점 데이터로 다시 확인합니다." },
];

export default function Home() {
  return (
    <main className="flex-1">
      {/* 로그인 상태면 대시보드로 직행 (랜딩은 비로그인 대상) */}
      <LandingRedirect />

      {/* Sticky 상단 헤더 — 첫 방문자가 로고/로그인 즉시 발견 */}
      <header className="sticky top-0 z-40 w-full border-b bg-background/90 backdrop-blur">
        <div className="max-w-6xl mx-auto px-4 md:px-6 h-14 flex items-center justify-between">
          <Link href="/" className="text-lg">
            <Logo />
          </Link>
          <nav className="flex items-center gap-1">
            <Link
              href="/pricing"
              className="text-sm text-muted-foreground hover:text-foreground px-3 py-1.5"
            >
              요금제
            </Link>
            <Link href="/login" className={buttonVariants({ size: "sm" })}>
              로그인
            </Link>
          </nav>
        </div>
      </header>

      {/* Hero — 좌측 카피/CTA + 우측 제품 미리보기 (2단) */}
      <section className="bg-hero">
      <div className="px-4 md:px-6 pt-12 md:pt-20 pb-12 max-w-6xl mx-auto">
        <div className="grid lg:grid-cols-2 gap-10 lg:gap-14 items-center">
          <div className="text-center lg:text-left">
            <p className="text-sm font-semibold text-[#7fe3d3]">
              주식이 처음이어도, 판단은 전문가처럼
            </p>
            <h1 className="mt-3 text-4xl md:text-5xl xl:text-6xl font-bold tracking-tight leading-[1.15]">
              유튜버 말고,
              <br />
              <span className="text-[#7fe3d3]">AI 애널리스트</span>와 함께
            </h1>
            <p className="mt-5 text-lg text-white/80 max-w-xl mx-auto lg:mx-0 leading-relaxed">
              궁금한 회사 이름만 입력하세요. 기간별로 분석하고, 모든 수치는 지금
              시점 데이터로 다시 확인합니다.
            </p>
            <div className="mt-8 flex flex-col sm:flex-row justify-center lg:justify-start gap-3">
              <Link href="/login" className={`${buttonVariants({ size: "lg" })} !bg-white !text-[#0a3f4a] hover:!bg-white/90`}>
                무료로 시작하기
              </Link>
              <Link
                href="/pricing"
                className={`${buttonVariants({ size: "lg", variant: "ghost" })} border-white/30 text-white hover:bg-white/10 hover:text-white`}
              >
                요금제 보기
              </Link>
            </div>
            <p className="mt-4 text-sm text-white/70">
              Google·카카오 30초 가입 · 신용카드 불필요
            </p>
          </div>

          <div className="text-foreground lg:pl-4">
            <HeroPreview />
          </div>
        </div>

        {/* 신뢰 배지 바 */}
        <ul className="mt-12 flex flex-wrap justify-center gap-2 text-sm text-white/85">
          {TRUST_BADGES.map((label) => (
            <li key={label} className="rounded-full border border-white/20 px-3 py-1">
              {label}
            </li>
          ))}
        </ul>
      </div>
      </section>

      {/* 3단계로 시작 — 처음 방문자가 '뭘 해야할지' 한눈에 */}
      <section className="border-y bg-card">
        <div className="px-4 md:px-6 py-14 max-w-5xl mx-auto">
          <h2 className="text-2xl md:text-3xl font-bold text-center">3단계면 첫 분석 완료</h2>
          <ol className="mt-8 grid grid-cols-1 md:grid-cols-3 gap-6">
            {STEPS.map((s, i) => (
              <li key={s.title} className="relative flex gap-3 md:block">
                {i < STEPS.length - 1 && (
                  <span aria-hidden="true" className="absolute top-[18px] right-0 left-12 hidden h-0.5 rounded-full bg-border md:block" />
                )}
                <span className={`flex size-9 shrink-0 items-center justify-center rounded-full font-bold tabular-nums ${STEP_TINTS[i]}`}>
                  {i + 1}
                </span>
                <div className="md:mt-3">
                  <h3 className="font-semibold">{s.title}</h3>
                  <p className="mt-1 text-sm text-muted-foreground leading-relaxed">{s.desc}</p>
                </div>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* Horizons */}
      <section className="px-4 md:px-6 py-14 max-w-5xl mx-auto">
        <h2 className="text-2xl md:text-3xl font-bold text-center">
          같은 종목도, 보는 기간에 따라 다르게
        </h2>
        <p className="mt-2 text-muted-foreground text-center">
          내 투자 기간에 맞는 관점을 고르면 AI가 살펴보는 데이터가 달라집니다.
        </p>
        <ol className="relative mt-10 grid grid-cols-1 gap-6 sm:grid-cols-2 md:grid-cols-4 md:gap-4">
          <span aria-hidden="true" className="absolute top-5 right-[12%] left-[12%] hidden h-0.5 rounded-full bg-gradient-to-r from-tint-2 via-tint-5 to-tint-4 md:block" />
          {HORIZON_META.map((h, i) => (
            <li key={h.id} className="relative text-center">
              <span className="mx-auto flex size-10 items-center justify-center rounded-full bg-background">
                <span className={`flex size-10 items-center justify-center rounded-full ${HORIZON_TINTS[i]}`}>
                  <HorizonIcon id={h.id} className="size-5" />
                </span>
              </span>
              <h3 className="mt-3 text-lg font-semibold">{h.name}</h3>
              <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{h.plain}</p>
            </li>
          ))}
        </ol>
      </section>

      {/* Features */}
      <section className="px-4 md:px-6 py-14 max-w-5xl mx-auto">
        <h2 className="text-2xl md:text-3xl font-bold text-center mb-8">Axis로 할 수 있는 일</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {FEATURES.map((f, i) => {
            const Icon = f.icon;
            return (
              <Card key={f.title}>
                <CardContent className="flex h-full flex-col p-5">
                  <span className={`flex size-10 items-center justify-center rounded-lg ${FEATURE_TINTS[i]}`}>
                    <Icon aria-hidden="true" className="size-5" />
                  </span>
                  <h3 className="mt-3 font-semibold">{f.title}</h3>
                  <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{f.desc}</p>
                  <div className="mt-auto pt-3">
                    <FeatureVisual index={i} />
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </section>

      {/* 지금 시작 CTA — 페이지 마지막 추진력 */}
      <section className="px-4 md:px-6 py-14 max-w-4xl mx-auto">
        <div className="bg-hero rounded-2xl p-8 md:p-12 text-center">
          <h2 className="text-2xl md:text-3xl font-bold">투자 판단을 대신하지 않습니다.
            <br />
            매일 검증해드립니다.
          </h2>
          <p className="mt-3 text-sm opacity-90 max-w-xl mx-auto leading-relaxed">
            Free 플랜은 분석 월 20회, 실시간 검증 월 10회를 제공합니다.
          </p>
          <Link
            href="/login"
            className={`${buttonVariants({ size: "lg", variant: "secondary" })} mt-6`}
          >
            무료로 시작하기
          </Link>
        </div>
      </section>

      {/* Footer + Disclaimer */}
      <footer className="px-4 md:px-6 py-10 max-w-5xl mx-auto border-t">
        <nav
          aria-label="푸터"
          className="flex flex-wrap gap-1 text-sm text-muted-foreground mb-4"
        >
          {[
            { href: "/pricing", label: "요금제" },
            { href: "/terms", label: "이용약관" },
            { href: "/privacy", label: "개인정보처리방침" },
            { href: "/refund", label: "환불정책" },
            { href: "/login", label: "로그인" },
          ].map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className="inline-flex items-center min-h-[44px] px-3 hover:text-foreground hover:underline"
            >
              {l.label}
            </Link>
          ))}
        </nav>
        <Disclaimer lang="both" />
      </footer>
    </main>
  );
}
