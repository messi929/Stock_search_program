/**
 * 랜딩 페이지 (/) — 비로그인 방문자 대상.
 * docs/axis/frontend/pages.md Hero / Features / Pricing 섹션 기반.
 *
 * 베타 단계: 상단 "Closed Beta" 배지 + 본문 끝에 신청 CTA.
 *   NEXT_PUBLIC_BETA_FORM_URL — Google Forms / Tally / Notion 폼 URL
 *   (없으면 "곧 오픈" 안내)
 */
import Link from "next/link";

import { Disclaimer } from "@/components/legal/Disclaimer";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

const BETA_FORM_URL = process.env.NEXT_PUBLIC_BETA_FORM_URL ?? "";

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
    title: "페르소나 전환",
    desc: "블랙록(리스크) / ARK(혁신) / 그레이엄(가치) — 같은 종목, 3가지 관점",
  },
  {
    icon: "🔔",
    title: "진입선 알림 (v1.1 도입 예정)",
    desc: "관찰 구간 도달 시 이메일·카카오 알림. 베타 기간 중 토글 미리 켜두실 수 있습니다.",
  },
];

const PERSONAS = [
  { id: "blackrock", icon: "🏛", name: "블랙록", tagline: "리스크 우선, 장기 가치" },
  { id: "ark", icon: "🚀", name: "ARK", tagline: "파괴적 혁신, 5년 시계" },
  { id: "graham", icon: "📚", name: "그레이엄", tagline: "안전마진, 저평가" },
];

export default function Home() {
  return (
    <main className="flex-1">
      {/* Hero */}
      <section className="px-6 py-20 max-w-5xl mx-auto text-center">
        <span className="inline-block text-xs font-medium px-3 py-1 rounded-full border border-amber-500/40 bg-amber-500/10 text-amber-500 mb-6">
          🚧 Closed Beta · 한정 인원 모집 중
        </span>
        <h1 className="text-4xl md:text-6xl font-bold tracking-tight">
          유튜버 말고,
          <br />
          <span className="text-amber-500">AI 애널리스트</span>와 함께
        </h1>
        <p className="mt-6 text-lg text-muted-foreground max-w-2xl mx-auto">
          블랙록처럼 분석합니다. ARK처럼 미래를 봅니다. 그레이엄처럼 가치를
          찾습니다.
        </p>
        <p className="mt-2 text-base text-muted-foreground">
          1~5년차 투자자를 위한 AI 분석 파트너 — 정보 제공 도구입니다.
        </p>
        <div className="mt-10 flex justify-center gap-4">
          <a
            href="#beta"
            className={buttonVariants({ size: "lg" })}
          >
            베타 신청하기
          </a>
          <Link
            href="/pricing"
            className={buttonVariants({ size: "lg", variant: "outline" })}
          >
            요금제 보기
          </Link>
        </div>
      </section>

      {/* Personas */}
      <section className="px-6 py-12 max-w-5xl mx-auto">
        <h2 className="text-2xl font-semibold text-center mb-8">
          같은 종목, 3가지 다른 관점
        </h2>
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

      {/* Beta signup */}
      <section id="beta" className="px-6 py-16 max-w-3xl mx-auto">
        <Card className="border-amber-500/40 bg-amber-500/5">
          <CardContent className="p-8 text-center space-y-4">
            <div className="text-3xl">🚧</div>
            <h2 className="text-2xl font-semibold">Closed Beta 신청</h2>
            <p className="text-sm text-muted-foreground max-w-xl mx-auto leading-relaxed">
              실시간 검증 + 4개 에이전트 분석을 먼저 사용해보세요.
              <br />
              현재 한정 인원 모집 중이며, 승인되면 안내 이메일을 보내드립니다.
              피드백 1건 이상 주신 분께는 Pro 1개월을 드립니다.
            </p>
            {BETA_FORM_URL ? (
              <a
                href={BETA_FORM_URL}
                target="_blank"
                rel="noreferrer"
                className={buttonVariants({ size: "lg" })}
              >
                폼으로 신청 →
              </a>
            ) : (
              <p className="text-xs text-muted-foreground italic">
                신청 폼은 곧 오픈됩니다. 알림을 받으시려면 X에서{" "}
                <span className="font-medium">@axis_kr</span>을 팔로우해 주세요.
              </p>
            )}
            <p className="text-xs text-muted-foreground pt-2">
              이미 초대를 받으셨다면{" "}
              <Link href="/login" className="underline hover:text-foreground">
                로그인
              </Link>
              하세요.
            </p>
          </CardContent>
        </Card>
      </section>

      {/* Footer + Disclaimer */}
      <footer className="px-6 py-10 max-w-5xl mx-auto border-t">
        <div className="flex flex-wrap gap-6 text-sm text-muted-foreground mb-4">
          <Link href="/pricing" className="hover:underline">
            요금제
          </Link>
          <Link href="/terms" className="hover:underline">
            이용약관
          </Link>
          <Link href="/privacy" className="hover:underline">
            개인정보처리방침
          </Link>
          <Link href="/login" className="hover:underline">
            로그인
          </Link>
        </div>
        <Disclaimer />
      </footer>
    </main>
  );
}
