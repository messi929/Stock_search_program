"use client";

import Link from "next/link";
import { useEffect } from "react";
import { toast } from "sonner";
import { useQueryClient } from "@tanstack/react-query";

import { MarketStatus } from "@/components/dashboard/MarketStatus";
import { RecentAnalyses } from "@/components/dashboard/RecentAnalyses";
import { UsageCard } from "@/components/dashboard/UsageCard";
import { WatchlistPreview } from "@/components/dashboard/WatchlistPreview";
import { Disclaimer } from "@/components/legal/Disclaimer";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useAuth } from "@/hooks/useAuth";
import { useUserProfile } from "@/hooks/useUserProfile";

const HORIZON_LABEL: Record<string, string> = {
  short: "⚡ 단기",
  short_mid: "📈 단중기",
  mid: "⚖️ 중기",
  long: "🏔 장기",
};

export default function DashboardHome() {
  const { user } = useAuth();
  const { profile } = useUserProfile();
  const qc = useQueryClient();

  // 결제 성공 콜백 (?payment=success) — LS 결제 후 리다이렉트
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (new URLSearchParams(window.location.search).get("payment") !== "success") return;
    toast.success("결제가 완료되었습니다! Pro 기능이 활성화됩니다.", { duration: 6000 });
    // 구독/사용량 캐시 갱신 (웹훅 반영까지 약간 지연될 수 있어 재조회)
    qc.invalidateQueries({ queryKey: ["subscription"] });
    qc.invalidateQueries({ queryKey: ["ai-usage"] });
    window.history.replaceState({}, "", "/dashboard");
  }, [qc]);

  return (
    <div className="space-y-6 max-w-5xl">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">
            안녕하세요{user?.displayName ? `, ${user.displayName}` : ""} 👋
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            오늘도 신중한 분석으로 시작합니다.
          </p>
        </div>
        <Link
          href="/settings/notifications"
          className="text-sm text-muted-foreground hover:text-foreground shrink-0"
        >
          🔔 알림 설정
        </Link>
      </header>

      {/* Market status (v7.5 backend) */}
      <MarketStatus />

      {/* Watchlist preview */}
      <WatchlistPreview />

      {/* 최근 분석한 종목 (localStorage 영속) */}
      <RecentAnalyses />

      {/* AI 사용량 (월 한도) */}
      <UsageCard />

      {/* Profile summary */}
      <Card>
        <CardContent className="p-6 space-y-3">
          <div className="flex items-center justify-between gap-2">
            <h2 className="font-semibold">내 투자 프로필</h2>
            <Link
              href="/settings/profile"
              className="text-xs text-amber-500 hover:underline shrink-0"
            >
              ⚙️ 수정 →
            </Link>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <p className="text-muted-foreground">선호 시계</p>
              <p className="font-medium">
                {HORIZON_LABEL[profile?.preferred_horizon ?? "mid"]}
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
                17 카테고리 / 관찰 시그널·가치주·모멘텀
              </div>
            </div>
          </Link>
          <Link
            href="/discover"
            className={`${buttonVariants({ variant: "outline", size: "lg" })} h-auto py-4 px-4 justify-start`}
          >
            <div className="text-left w-full">
              <div className="font-semibold">🧭 종목 발견</div>
              <div className="text-xs text-muted-foreground mt-1">
                AI에게 조건·테마로 관찰 가치 종목 찾기
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

      <Disclaimer />
    </div>
  );
}
