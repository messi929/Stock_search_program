/**
 * 종목 분석 인덱스 (/analyze) — 검색 + 인기 종목 바로가기.
 *
 * 동작:
 *   - 상단 검색 — SearchTab 컴포넌트 재사용 (선택 시 /analyze/{ticker} 이동)
 *   - 인기 종목 — 시총 상위 KR 종목 8개 카드, 클릭 즉시 분석 진입
 *
 * 분석 1회 ≈ 450원이므로 추가 인지부하 없이 검색 → 진입선까지 1회 이동만 강조.
 */
import Link from "next/link";

import { Disclaimer } from "@/components/legal/Disclaimer";
import { Card, CardContent } from "@/components/ui/card";
import { SearchTab } from "@/components/watchlist/SearchTab";

const POPULAR_TICKERS: Array<{ ticker: string; name: string; sector: string }> = [
  { ticker: "005930", name: "삼성전자", sector: "반도체" },
  { ticker: "000660", name: "SK하이닉스", sector: "반도체" },
  { ticker: "207940", name: "삼성바이오로직스", sector: "바이오" },
  { ticker: "005380", name: "현대차", sector: "자동차" },
  { ticker: "035420", name: "NAVER", sector: "플랫폼" },
  { ticker: "035720", name: "카카오", sector: "플랫폼" },
  { ticker: "051910", name: "LG화학", sector: "2차전지" },
  { ticker: "068270", name: "셀트리온", sector: "바이오" },
];

export default function AnalyzeIndexPage() {
  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold">종목 분석</h1>
        <p className="text-sm text-muted-foreground mt-1">
          궁금한 종목을 검색하거나 아래 인기 종목에서 골라보세요.
        </p>
      </header>

      <SearchTab />

      <section className="space-y-3">
        <h2 className="font-semibold">인기 종목</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          {POPULAR_TICKERS.map((stock) => (
            <Link
              key={stock.ticker}
              href={`/analyze/${stock.ticker}`}
              className="block"
            >
              <Card className="h-full transition hover:ring-primary/40">
                <CardContent className="p-3 space-y-1">
                  <p className="truncate font-semibold">{stock.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {stock.sector} · {stock.ticker}
                  </p>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
        <p className="text-xs text-muted-foreground">
          종목을 고른 뒤 보고 싶은 기간을 선택하면 분석이 시작됩니다. 보통 1분 안팎 걸려요.
        </p>
      </section>

      <Disclaimer />
    </div>
  );
}
