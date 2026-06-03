/**
 * 랜딩 페이지 (/) — 비로그인 방문자 대상.
 *
 * 정식 오픈 기준 (베타 게이팅 제거):
 *  - Hero CTA = 'Google로 시작하기'(/login) + '요금제 보기'(/pricing)
 *  - '3단계로 시작' 가이드로 처음 방문자에게 다음 행동을 명시
 *  - 마지막 '지금 시작' CTA로 다시 한 번 유입
 */
import Link from "next/link";

import { HeroPreview } from "@/components/landing/HeroPreview";
import { LandingRedirect } from "@/components/landing/LandingRedirect";
import { Disclaimer } from "@/components/legal/Disclaimer";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

// Hero 아래 신뢰 배지 — 한 줄에 차별점·정당성 압축
const TRUST_BADGES = [
  { icon: "🏦", label: "KIS 공식 OpenAPI 데이터" },
  { icon: "🛡️", label: "추천 아님 · 정보 제공 도구" },
  { icon: "🎭", label: "6가지 분석 관점" },
  { icon: "🔍", label: "수치 실시간 재검증" },
];

const FEATURES = [
  {
    icon: "🤖",
    title: "4개 AI 에이전트 종합 분석",
    desc: "Research / Analyst / Validator / Strategist — 단일 모델로는 못 잡는 다층 검토",
  },
  {
    icon: "🔍",
    title: "실시간 검증 (핵심 차별점)",
    desc: "AI 답변의 모든 수치를 현재 시점 데이터로 재검증. 신선도 5% 이상 차이는 자동 경고.",
  },
  {
    icon: "🎭",
    title: "페르소나 전환 (6종)",
    desc: "안정·리스크관리 / 고성장·혁신 / 가치·저평가 + 이벤트·매크로·한국 시장 — 같은 종목을 6가지 관점으로",
  },
  {
    icon: "🔔",
    title: "진입선 알림 (v1.1 도입 예정)",
    desc: "관찰 구간 도달 시 이메일·카카오 알림. 지금 미리 토글 켜두면 출시 시 자동 수신.",
  },
];

const PERSONAS = [
  { id: "blackrock", icon: "🏛", name: "안정·리스크관리", tagline: "리스크 우선, 장기 가치" },
  { id: "ark", icon: "🚀", name: "고성장·혁신", tagline: "파괴적 혁신, 5년 시계" },
  { id: "graham", icon: "📚", name: "가치·저평가", tagline: "안전마진, 저평가" },
];

const STEPS = [
  {
    num: "1",
    icon: "🚀",
    title: "Google로 가입",
    desc: "30초, 신용카드 불필요. 투자 성향 4문항 온보딩.",
  },
  {
    num: "2",
    icon: "🔍",
    title: "종목·관점 선택",
    desc: "관심 종목 검색하거나 스마트 리스트에서. 6가지 분석 관점 중 하나 선택.",
  },
  {
    num: "3",
    icon: "📊",
    title: "분석 + 실시간 검증",
    desc: "AI 에이전트 결과를 보고, 수치는 항상 현재 시점 데이터로 재검증.",
  },
];

export default function Home() {
  return (
    <main className="flex-1">
      {/* 로그인 상태면 대시보드로 직행 (랜딩은 비로그인 대상) */}
      <LandingRedirect />

      {/* Sticky 상단 헤더 — 첫 방문자가 로고/로그인 즉시 발견 */}
      <header className="sticky top-0 z-40 w-full border-b bg-background/90 backdrop-blur">
        <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
          <Link href="/" className="text-lg font-bold tracking-tight">
            Axis
          </Link>
          <nav className="flex items-center gap-2">
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
      <section className="px-6 pt-16 pb-10 max-w-6xl mx-auto">
        <div className="grid lg:grid-cols-2 gap-10 lg:gap-12 items-center">
          {/* 좌: 카피 + CTA */}
          <div className="text-center lg:text-left">
            <span className="inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1 rounded-full border bg-muted/50 text-muted-foreground">
              ⚡ 1~5년차 투자자를 위한 AI 분석 파트너
            </span>
            <h1 className="mt-5 text-4xl md:text-5xl xl:text-6xl font-bold tracking-tight leading-[1.1]">
              유튜버 말고,
              <br />
              <span className="text-amber-500">AI 애널리스트</span>와 함께
            </h1>
            <p className="mt-5 text-lg text-muted-foreground max-w-xl mx-auto lg:mx-0 leading-relaxed">
              리스크를 먼저 따지고, 성장을 발굴하고, 가치를 찾습니다. 같은 종목을
              6가지 원칙으로 분석하고, 모든 수치는 실시간으로 재검증합니다.
            </p>
            <div className="mt-8 flex flex-col sm:flex-row justify-center lg:justify-start gap-3">
              <Link href="/login" className={buttonVariants({ size: "lg" })}>
                🚀 무료로 시작하기
              </Link>
              <Link
                href="/pricing"
                className={buttonVariants({ size: "lg", variant: "outline" })}
              >
                요금제 보기
              </Link>
            </div>
            <p className="mt-4 text-xs text-muted-foreground">
              Google·카카오 30초 가입 · 신용카드 불필요 · Free 플랜 즉시 사용
            </p>
          </div>

          {/* 우: 제품 미리보기 목업 */}
          <div className="lg:pl-4">
            <HeroPreview />
          </div>
        </div>

        {/* 신뢰 배지 바 */}
        <div className="mt-14 flex flex-wrap justify-center gap-x-6 gap-y-2">
          {TRUST_BADGES.map((b) => (
            <span
              key={b.label}
              className="inline-flex items-center gap-1.5 text-sm text-muted-foreground"
            >
              <span>{b.icon}</span>
              {b.label}
            </span>
          ))}
        </div>
      </section>

      {/* 3단계로 시작 — 처음 방문자가 '뭘 해야할지' 한눈에 */}
      <section className="px-6 py-12 max-w-5xl mx-auto">
        <h2 className="text-2xl font-semibold text-center mb-2">
          3단계로 시작
        </h2>
        <p className="text-sm text-muted-foreground text-center mb-8">
          첫 분석까지 2분이면 충분합니다.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {STEPS.map((s, i) => (
            <div key={s.num} className="relative">
              <Card className="h-full">
                <CardContent className="p-6 space-y-2">
                  <div className="flex items-baseline gap-2">
                    <span className="text-xs font-bold text-primary bg-primary/10 px-2 py-0.5 rounded">
                      {s.num}
                    </span>
                    <span className="text-2xl">{s.icon}</span>
                  </div>
                  <h3 className="font-semibold">{s.title}</h3>
                  <p className="text-sm text-muted-foreground leading-relaxed">
                    {s.desc}
                  </p>
                </CardContent>
              </Card>
              {i < STEPS.length - 1 && (
                <div className="hidden md:block absolute top-1/2 -right-2 text-muted-foreground" aria-hidden="true">
                  →
                </div>
              )}
            </div>
          ))}
        </div>
      </section>

      {/* Personas */}
      <section className="px-6 py-12 max-w-5xl mx-auto">
        <h2 className="text-2xl font-semibold text-center mb-2">
          같은 종목, 3가지 다른 관점
        </h2>
        <p className="text-sm text-muted-foreground text-center mb-8">
          (이벤트·매크로·한국 시장 등 데이터 특화 3종까지 총 6 페르소나)
        </p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {PERSONAS.map((p) => (
            <Card key={p.id}>
              <CardContent className="p-6 text-center">
                <div className="text-4xl mb-3">{p.icon}</div>
                <h3 className="text-lg font-semibold">{p.name}</h3>
                <p className="text-sm text-muted-foreground mt-2">{p.tagline}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      {/* Features */}
      <section className="px-6 py-12 max-w-5xl mx-auto">
        <h2 className="text-2xl font-semibold text-center mb-8">핵심 기능</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {FEATURES.map((f) => (
            <Card key={f.title}>
              <CardContent className="p-6">
                <div className="text-3xl mb-2">{f.icon}</div>
                <h3 className="font-semibold">{f.title}</h3>
                <p className="text-sm text-muted-foreground mt-2">{f.desc}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      {/* Tagline */}
      <section className="px-6 py-12 max-w-3xl mx-auto text-center">
        <blockquote className="text-xl md:text-2xl font-medium leading-relaxed">
          &ldquo;투자 판단을 AI가 대신해주지 않습니다.
          <br />
          대신 매일 검증해드립니다.&rdquo;
        </blockquote>
      </section>

      {/* 지금 시작 CTA — 페이지 마지막 추진력 */}
      <section className="px-6 py-16 max-w-3xl mx-auto">
        <Card className="border-primary/30 bg-primary/5">
          <CardContent className="p-8 text-center space-y-4">
            <h2 className="text-2xl font-semibold">지금 시작하세요</h2>
            <p className="text-sm text-muted-foreground max-w-xl mx-auto leading-relaxed">
              Free 플랜으로 즉시 시작 · 신용카드 불필요 · 분석 월 20회, 실시간
              검증 월 10회 무료 제공. Pro로 업그레이드 시 6 페르소나·무제한 분석.
            </p>
            <div className="flex flex-col sm:flex-row justify-center gap-3 pt-2">
              <Link
                href="/login"
                className={buttonVariants({ size: "lg" })}
              >
                🚀 Google로 무료 시작
              </Link>
              <Link
                href="/pricing"
                className={buttonVariants({ size: "lg", variant: "outline" })}
              >
                요금제 자세히
              </Link>
            </div>
            <p className="text-xs text-muted-foreground pt-2">
              이미 회원이라면{" "}
              <Link href="/login" className="underline hover:text-foreground">
                로그인
              </Link>
              .
            </p>
          </CardContent>
        </Card>
      </section>

      {/* Footer + Disclaimer */}
      <footer className="px-6 py-10 max-w-5xl mx-auto border-t">
        <nav
          aria-label="푸터"
          className="flex flex-wrap gap-1 text-sm text-muted-foreground mb-4"
        >
          <Link
            href="/pricing"
            className="inline-flex items-center min-h-[44px] px-3 hover:text-foreground hover:underline"
          >
            요금제
          </Link>
          <Link
            href="/terms"
            className="inline-flex items-center min-h-[44px] px-3 hover:text-foreground hover:underline"
          >
            이용약관
          </Link>
          <Link
            href="/privacy"
            className="inline-flex items-center min-h-[44px] px-3 hover:text-foreground hover:underline"
          >
            개인정보처리방침
          </Link>
          <Link
            href="/refund"
            className="inline-flex items-center min-h-[44px] px-3 hover:text-foreground hover:underline"
          >
            환불정책
          </Link>
          <Link
            href="/login"
            className="inline-flex items-center min-h-[44px] px-3 hover:text-foreground hover:underline"
          >
            로그인
          </Link>
        </nav>
        <Disclaimer lang="both" />
      </footer>
    </main>
  );
}
