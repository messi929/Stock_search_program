/**
 * /pricing — 요금제 페이지 (베타 단계 placeholder).
 *
 * 베타 기간 중에는 결제 미연결 (Lemon Squeezy 도입은 v1.1).
 * 정식 런칭 시점에 결제 버튼 활성화.
 */
import Link from "next/link";

import { Disclaimer } from "@/components/legal/Disclaimer";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

export const metadata = {
  title: "요금제 — Axis",
  description: "Free / Pro / Premium 요금제",
};

const TIERS = [
  {
    id: "free",
    name: "Free",
    price: "0원",
    period: "",
    desc: "처음 시작하는 투자자",
    cta: "베타 신청하기",
    ctaHref: "/#beta",
    highlight: false,
    features: [
      "관심 종목 5개",
      "AI 분석 월 20회",
      "실시간 검증 월 10회",
      "페르소나 1종 (블랙록)",
      "스마트 리스트 6개",
    ],
  },
  {
    id: "pro",
    name: "Pro",
    price: "9,900원",
    period: "/월",
    desc: "꾸준히 분석하는 투자자",
    cta: "베타 신청하기",
    ctaHref: "/#beta",
    highlight: true,
    features: [
      "관심 종목 30개",
      "무제한 AI 분석·검증",
      "페르소나 3종 모두",
      "스마트 리스트 17개 전체",
      "커스텀 스크리너",
      "AI 자연어 종목 발견",
    ],
  },
  {
    id: "premium",
    name: "Premium",
    price: "29,900원",
    period: "/월",
    desc: "주간 리포트 + 우선 지원",
    cta: "v1.1 출시 예정",
    ctaHref: null,
    highlight: false,
    features: [
      "Pro 모든 기능",
      "주간 PDF 리포트",
      "우선 분석 큐",
      "1:1 피드백 채널",
      "(v1.1 출시 예정)",
    ],
  },
];

export default function PricingPage() {
  return (
    <main className="min-h-screen bg-background text-foreground">
      <div className="max-w-5xl mx-auto px-6 py-16">
        <Link
          href="/"
          className="text-sm text-muted-foreground hover:text-foreground"
        >
          ← 홈으로
        </Link>

        <header className="mt-6 mb-12 text-center">
          <span className="inline-block text-xs font-medium px-3 py-1 rounded-full border border-amber-500/40 bg-amber-500/10 text-amber-500 mb-4">
            🚧 베타 기간 중에는 모든 기능 무료
          </span>
          <h1 className="text-3xl md:text-5xl font-bold">요금제</h1>
          <p className="mt-4 text-muted-foreground max-w-xl mx-auto">
            정식 런칭 시 결제가 활성화됩니다. 베타 사용자는 1개월 Pro 무료 혜택이
            예정되어 있습니다.
          </p>
        </header>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {TIERS.map((t) => (
            <Card
              key={t.id}
              className={t.highlight ? "border-amber-500/60 ring-2 ring-amber-500/20" : ""}
            >
              <CardContent className="p-6 space-y-4">
                {t.highlight && (
                  <span className="inline-block text-xs font-medium px-2 py-0.5 rounded bg-amber-500 text-black">
                    추천
                  </span>
                )}
                <div>
                  <h2 className="text-xl font-semibold">{t.name}</h2>
                  <p className="text-xs text-muted-foreground mt-1">{t.desc}</p>
                </div>
                <div className="flex items-end gap-1">
                  <span className="text-3xl font-bold">{t.price}</span>
                  {t.period && (
                    <span className="text-sm text-muted-foreground pb-1">
                      {t.period}
                    </span>
                  )}
                </div>
                <ul className="space-y-2 text-sm">
                  {t.features.map((f) => (
                    <li key={f} className="flex items-start gap-2">
                      <span className="text-amber-500 mt-0.5">✓</span>
                      <span>{f}</span>
                    </li>
                  ))}
                </ul>
                <div className="pt-3">
                  {t.ctaHref ? (
                    <Link href={t.ctaHref} className="block">
                      <Button
                        className="w-full"
                        variant={t.highlight ? "default" : "outline"}
                      >
                        {t.cta}
                      </Button>
                    </Link>
                  ) : (
                    <Button className="w-full" variant="outline" disabled>
                      {t.cta}
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        <section className="mt-16 max-w-3xl mx-auto space-y-6 text-sm">
          <h2 className="text-lg font-semibold">자주 묻는 질문</h2>
          <FaqItem q="언제 결제가 시작되나요?">
            정식 런칭(v1.0) 시점에 결제가 열립니다. 베타 기간에는 모든 기능을
            무료로 사용하실 수 있습니다.
          </FaqItem>
          <FaqItem q="결제 수단은 무엇인가요?">
            Lemon Squeezy를 통해 신용카드·체크카드 결제를 지원할 예정입니다.
            (현재 베타에는 결제 모듈이 활성화되지 않았습니다.)
          </FaqItem>
          <FaqItem q="환불 정책은 어떻게 되나요?">
            결제 후 7일 이내, 누적 사용량이 적은 경우 전액 환불해 드립니다.
            상세 조건은 정식 런칭 시 공지합니다.
          </FaqItem>
          <FaqItem q="베타 사용자에게 혜택이 있나요?">
            피드백을 1건 이상 주신 베타 사용자께는 정식 런칭 후 Pro 1개월
            이용권을 드릴 예정입니다.
          </FaqItem>
        </section>

        <div className="mt-16">
          <Disclaimer lang="both" />
        </div>
      </div>
    </main>
  );
}

function FaqItem({ q, children }: { q: string; children: React.ReactNode }) {
  return (
    <details className="rounded-md border p-4 open:bg-muted/30">
      <summary className="cursor-pointer font-medium">{q}</summary>
      <p className="mt-2 text-muted-foreground leading-relaxed">{children}</p>
    </details>
  );
}
