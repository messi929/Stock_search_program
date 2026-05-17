"use client";

/**
 * /portfolio — 포트폴리오 리스크 분석.
 *
 * v7.5 흡수: POST /portfolio/risk 결과(건강도·MDD·상관관계·섹터·관찰 메시지)
 * 를 카드 UI로 시각화. 입력은 Watchlist 기반(동등 비중) 우선.
 *
 * MVP 골격: Watchlist 자동 사용 → 분석 결과 카드 + 핵심 메트릭.
 * 향후 확장: holdings (실제 보유 수량) 입력 폼, 상관관계 매트릭스 히트맵.
 */
import Link from "next/link";

import { Disclaimer } from "@/components/legal/Disclaimer";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { usePortfolioRisk } from "@/hooks/usePortfolioRisk";
import { useWatchlist } from "@/hooks/useWatchlist";

export default function PortfolioPage() {
  const watchlist = useWatchlist();
  const risk = usePortfolioRisk();

  const tickers = watchlist.data?.watchlist ?? [];
  const canAnalyze = tickers.length >= 2;

  const handleAnalyze = () => {
    if (!canAnalyze) return;
    risk.mutate({ tickers });
  };

  return (
    <div className="space-y-6 max-w-4xl">
      <header className="space-y-1">
        <Link
          href="/dashboard"
          className="text-sm text-muted-foreground hover:text-foreground"
        >
          ← 대시보드
        </Link>
        <h1 className="text-2xl font-bold">🧮 포트폴리오 리스크 분석</h1>
        <p className="text-sm text-muted-foreground">
          관심 종목 기반으로 건강도·집중도·상관관계·MDD를 점검합니다.
        </p>
      </header>

      {watchlist.isLoading ? (
        <p className="text-sm text-muted-foreground">관심 종목 로딩 중...</p>
      ) : !canAnalyze ? (
        <Card>
          <CardContent className="p-6 space-y-3 text-center">
            <div className="text-4xl">📋</div>
            <p className="text-sm">관심 종목이 2개 이상 필요합니다.</p>
            <p className="text-xs text-muted-foreground">
              현재 {tickers.length}개 등록됨.
            </p>
            <Link href="/watchlist/add">
              <Button variant="outline" size="sm">
                관심 종목 추가
              </Button>
            </Link>
          </CardContent>
        </Card>
      ) : (
        <>
          <Card>
            <CardContent className="p-6 space-y-3">
              <p className="text-sm text-muted-foreground">
                분석 대상 ({tickers.length}개)
              </p>
              <p className="text-xs text-muted-foreground break-all">
                {tickers.join(", ")}
              </p>
              <div className="flex gap-2 pt-2">
                <Button onClick={handleAnalyze} disabled={risk.isPending}>
                  {risk.isPending ? "분석 중..." : "리스크 분석 실행"}
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">
                * 동등 비중 가정. 실제 보유 수량 기반 분석은 향후 도입 예정.
              </p>
            </CardContent>
          </Card>

          {risk.isError && (
            <Card>
              <CardContent className="p-6 text-center text-sm text-muted-foreground">
                ⚠️ 분석 요청 실패. 잠시 후 다시 시도해주세요.
              </CardContent>
            </Card>
          )}

          {risk.data && !risk.data.error && (
            <RiskResultView data={risk.data} />
          )}

          {risk.data?.error && (
            <Card>
              <CardContent className="p-6 text-center text-sm text-muted-foreground">
                {risk.data.error}
              </CardContent>
            </Card>
          )}
        </>
      )}

      <Disclaimer />
    </div>
  );
}

function RiskResultView({
  data,
}: {
  data: NonNullable<ReturnType<typeof usePortfolioRisk>["data"]>;
}) {
  const sectorTop = Object.entries(data.sector_concentration ?? {})
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5);

  return (
    <div className="space-y-4">
      <Card>
        <CardContent className="p-6 space-y-3">
          <div className="flex items-baseline gap-3">
            <span className="text-4xl font-bold">{data.health_score}</span>
            <span className="text-sm text-muted-foreground">/100</span>
            <span className="text-base font-medium">
              {data.health_grade}
            </span>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
            <Metric
              label="변동성(연)"
              value={`${data.portfolio_volatility.toFixed(1)}%`}
            />
            <Metric
              label="기대수익(연)"
              value={`${data.annualized_return.toFixed(1)}%`}
            />
            <Metric
              label="Sharpe"
              value={data.sharpe_ratio.toFixed(2)}
            />
            <Metric
              label="최대낙폭"
              value={`-${data.max_drawdown.toFixed(1)}%`}
            />
            <Metric
              label="평균상관"
              value={data.avg_correlation.toFixed(2)}
            />
            <Metric
              label="최상위 비중"
              value={`${data.top_weight_pct}% (${data.top_weight_name})`}
            />
          </div>
        </CardContent>
      </Card>

      {sectorTop.length > 0 && (
        <Card>
          <CardContent className="p-6 space-y-2">
            <h2 className="font-semibold text-sm">섹터 집중도</h2>
            <ul className="space-y-1 text-sm">
              {sectorTop.map(([sector, pct]) => (
                <li key={sector} className="flex justify-between">
                  <span>{sector}</span>
                  <span className="tabular-nums text-muted-foreground">
                    {pct}%
                  </span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {data.recommendations && data.recommendations.length > 0 && (
        <Card>
          <CardContent className="p-6 space-y-2">
            <h2 className="font-semibold text-sm">관찰 포인트</h2>
            <ul className="space-y-2 text-sm">
              {data.recommendations.map((r, i) => (
                <li key={i} className="text-muted-foreground">
                  {r.msg}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border p-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="font-semibold mt-0.5">{value}</p>
    </div>
  );
}
