"use client";

import Link from "next/link";

import { Disclaimer } from "@/components/legal/Disclaimer";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useAuth } from "@/hooks/useAuth";
import { useUserProfile } from "@/hooks/useUserProfile";

const PERSONA_LABEL: Record<string, string> = {
  blackrock: "🏛 블랙록",
  ark: "🚀 ARK",
  graham: "📚 그레이엄",
};

export default function DashboardHome() {
  const { user } = useAuth();
  const { profile } = useUserProfile();

  return (
    <div className="space-y-6 max-w-5xl">
      <header>
        <h1 className="text-2xl font-bold">
          안녕하세요{user?.displayName ? `, ${user.displayName}` : ""} 👋
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          오늘도 신중한 분석으로 시작합니다.
        </p>
      </header>

      {/* Profile summary */}
      <Card>
        <CardContent className="p-6 space-y-3">
          <h2 className="font-semibold">내 투자 프로필</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <p className="text-muted-foreground">선호 페르소나</p>
              <p className="font-medium">
                {PERSONA_LABEL[profile?.preferred_persona ?? "blackrock"]}
              </p>
            </div>
            <div>
              <p className="text-muted-foreground">투자 경력</p>
              <p className="font-medium">{profile?.investing_experience ?? "—"}</p>
            </div>
            <div>
              <p className="text-muted-foreground">보유 기간</p>
              <p className="font-medium">{profile?.holding_period ?? "—"}</p>
            </div>
            <div>
              <p className="text-muted-foreground">관심 섹터</p>
              <p className="font-medium">
                {profile?.interested_sectors?.length
                  ? `${profile.interested_sectors.length}개`
                  : "—"}
              </p>
            </div>
          </div>
          {profile?.investment_principles?.length ? (
            <div className="pt-2 text-sm">
              <p className="text-muted-foreground mb-1">투자 원칙</p>
              <ul className="space-y-1">
                {profile.investment_principles.map((p) => (
                  <li key={p}>• {p}</li>
                ))}
              </ul>
            </div>
          ) : null}
        </CardContent>
      </Card>

      {/* Quick actions */}
      <section>
        <h2 className="font-semibold mb-3">빠른 시작</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <Link
            href="/screener"
            className={`${buttonVariants({ variant: "outline", size: "lg" })} h-auto py-4 px-4 justify-start`}
          >
            <div className="text-left w-full">
              <div className="font-semibold">📊 스마트 리스트</div>
              <div className="text-xs text-muted-foreground mt-1">
                17 카테고리 / 매수 신호·가치주·모멘텀
              </div>
            </div>
          </Link>
          <Link
            href="/watchlist/add"
            className={`${buttonVariants({ variant: "outline", size: "lg" })} h-auto py-4 px-4 justify-start`}
          >
            <div className="text-left w-full">
              <div className="font-semibold">⭐ 관심 종목 추가</div>
              <div className="text-xs text-muted-foreground mt-1">
                검색 / AI 발견 / 큐레이션 테마
              </div>
            </div>
          </Link>
          <Link
            href="/analyze"
            className={`${buttonVariants({ variant: "outline", size: "lg" })} h-auto py-4 px-4 justify-start`}
          >
            <div className="text-left w-full">
              <div className="font-semibold">🔍 종목 분석</div>
              <div className="text-xs text-muted-foreground mt-1">
                4 에이전트 종합 + 검증
              </div>
            </div>
          </Link>
        </div>
      </section>

      <p className="text-sm text-muted-foreground">
        ⚠️ 다른 페이지(관심 종목·스크리너·분석)는 Week 4 Day 4-5에서 구현됩니다.
      </p>

      <Disclaimer />
    </div>
  );
}
