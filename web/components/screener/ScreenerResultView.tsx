"use client";

/**
 * /screener/[id] 결과 뷰 — v7.5 /api/scan 호출하여 카테고리별 종목 표시.
 *
 * 데이터 흐름:
 *   useSmartLists()  → 카테고리 메타 (이름·columns·available_to_free)
 *   useScan(id, 50)  → v7.5 /api/scan?category=id
 *
 * 게이트:
 *   - SmartLists 로딩/실패: 스피너 / 에러
 *   - 카테고리 미존재: 404 카드
 *   - Pro 카테고리 + free 플랜: ProGate (스캔 호출 안 함)
 *   - Scan 로딩/실패/빈 결과: 각 상태 카드
 *
 * 뷰 모드: 표(table) ↔ 트리맵(treemap) 토글. 클라이언트 state만 사용.
 *
 * LEGAL: buy_grade 같은 권유성 라벨은 columnMeta에서 중립 변환.
 *        하단 Disclaimer 필수.
 */

import { useState } from "react";
import Link from "next/link";

import { Disclaimer } from "@/components/legal/Disclaimer";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useScan, useSmartLists } from "@/hooks/useSmartLists";
import { toSafeCategory } from "@/lib/legal-labels";
import type { SmartListCategory } from "@/types/api";

import { ProGate } from "./ProGate";
import { ResultsTable, type StockRow } from "./ResultsTable";
import { Treemap } from "./Treemap";

type ViewMode = "table" | "treemap";
type Market = "KR" | "US";

interface Props {
  categoryId: string;
}

export function ScreenerResultView({ categoryId }: Props) {
  const [viewMode, setViewMode] = useState<ViewMode>("table");
  const [market, setMarket] = useState<Market>("KR");
  const {
    data: smartLists,
    isLoading: smartListsLoading,
    isError: smartListsError,
  } = useSmartLists();

  // LEGAL: 권유성 카테고리 라벨을 Axis 정책에 맞게 변환
  const rawCategory = smartLists?.categories.find((c) => c.id === categoryId);
  const category: SmartListCategory | undefined = rawCategory
    ? toSafeCategory(rawCategory)
    : undefined;

  const userPlan = (smartLists?.user_plan ?? "free").toLowerCase();
  const proGated = !!category && !category.available_to_free && userPlan === "free";

  // Pro 게이트면 스캔 자체를 호출하지 않음 (소비 절약)
  const scanEnabled = !!category && !proGated;
  // 시장 탭(KR/US) → /api/scan?market= 전달. 백엔드가 source=us 데이터를 분리 보유.
  const scanQuery = useScan(scanEnabled ? categoryId : undefined, 50, market);
  const marketTabs = <MarketTabs market={market} onChange={setMarket} />;

  // ─── 로딩 (SmartLists) ───────────────────
  if (smartListsLoading) {
    return (
      <div className="space-y-4">
        <Header />
        <p className="text-sm text-muted-foreground">카테고리 정보 로딩 중...</p>
      </div>
    );
  }

  if (smartListsError || !smartLists) {
    return (
      <div className="space-y-4">
        <Header />
        <ErrorCard message="카테고리 목록을 불러오지 못했습니다. 잠시 후 다시 시도해주세요." />
      </div>
    );
  }

  // ─── 카테고리 미존재 ─────────────────────
  if (!category) {
    return (
      <div className="space-y-4">
        <Header />
        <Card>
          <CardContent className="p-8 space-y-3 text-center">
            <div className="text-4xl">🔍</div>
            <h2 className="font-semibold">존재하지 않는 카테고리입니다</h2>
            <p className="text-sm text-muted-foreground">
              <code className="px-1 py-0.5 rounded bg-muted">{categoryId}</code>
              {" "}를 찾을 수 없습니다.
            </p>
            <Link href="/screener">
              <Button variant="outline">목록으로</Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    );
  }

  // ─── Pro 게이트 ──────────────────────────
  if (proGated) {
    return (
      <div className="space-y-4">
        <Header category={category} />
        <ProGate categoryName={category.name} />
        <Disclaimer />
      </div>
    );
  }

  // ─── Scan 로딩 ───────────────────────────
  if (scanQuery.isLoading) {
    return (
      <div className="space-y-4">
        <Header category={category} />
        {marketTabs}
        <p className="text-sm text-muted-foreground">종목 스캔 중...</p>
      </div>
    );
  }

  // ─── Scan 에러 ───────────────────────────
  if (scanQuery.isError || !scanQuery.data) {
    return (
      <div className="space-y-4">
        <Header category={category} />
        {marketTabs}
        <ErrorCard message="종목 데이터 조회에 실패했습니다. 잠시 후 다시 시도해주세요." />
        <Disclaimer />
      </div>
    );
  }

  const { stocks: rawStocks, total } = scanQuery.data;
  // ticker 누락 row 방어 (백엔드가 항상 채우지만 React key 안전성 위해)
  const stocks = rawStocks.filter(
    (s): s is StockRow => typeof (s as { ticker?: unknown }).ticker === "string",
  );
  const emptyMessage = scanQuery.data.message ?? "";

  // ─── 빈 결과 ─────────────────────────────
  if (!stocks.length) {
    return (
      <div className="space-y-4">
        <Header category={category} />
        {marketTabs}
        <Card>
          <CardContent className="p-6 space-y-3">
            <p className="text-sm">
              {market === "US" ? "미국" : "국내"} 시장에 조건에 맞는 종목이 현재 없습니다.
            </p>
            <p className="text-xs text-muted-foreground">
              일부 카테고리는 한 시장에만 데이터가 있습니다. 다른 시장 탭(
              {market === "US" ? "🇰🇷 국내" : "🇺🇸 미국"})을 확인해보세요.
            </p>
            {emptyMessage && (
              <p className="text-xs text-muted-foreground whitespace-pre-line">
                {emptyMessage}
              </p>
            )}
            <Link href="/screener">
              <Button variant="outline" size="sm">목록으로</Button>
            </Link>
          </CardContent>
        </Card>
        <Disclaimer />
      </div>
    );
  }

  // ─── 결과 (표 ↔ 트리맵 토글) ─────────────
  const caption = `${category.name} 스마트 리스트 결과 (총 ${total.toLocaleString("ko-KR")}건)`;
  const sizeKey = category.columns.includes("buy_score")
    ? "buy_score"
    : category.columns.includes("market_cap")
      ? "market_cap"
      : category.columns[0];

  return (
    <div className="space-y-4">
      <Header category={category} total={total} />
      {scanQuery.data.data_fresh === false && scanQuery.data.freshness_note && (
        <FreshnessBanner note={scanQuery.data.freshness_note} />
      )}
      <div className="flex flex-wrap items-center justify-between gap-2">
        {marketTabs}
        <ViewToggle mode={viewMode} onChange={setViewMode} />
      </div>
      {viewMode === "table" ? (
        <ResultsTable columns={category.columns} stocks={stocks} caption={caption} />
      ) : (
        <Treemap stocks={stocks} sizeKey={sizeKey} caption={caption} />
      )}
      <Disclaimer />
    </div>
  );
}

function MarketTabs({
  market,
  onChange,
}: {
  market: Market;
  onChange: (m: Market) => void;
}) {
  const tab = (m: Market, label: string) => (
    <button
      type="button"
      role="tab"
      aria-selected={market === m}
      onClick={() => onChange(m)}
      className={`px-3 py-1.5 text-sm rounded-md transition focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500 ${
        market === m
          ? "bg-muted text-foreground font-medium"
          : "text-muted-foreground hover:text-foreground"
      }`}
    >
      {label}
    </button>
  );
  return (
    <div className="inline-flex rounded-md border p-0.5 gap-0.5" role="tablist" aria-label="시장 구분">
      {tab("KR", "🇰🇷 국내")}
      {tab("US", "🇺🇸 미국")}
    </div>
  );
}

function ViewToggle({
  mode,
  onChange,
}: {
  mode: ViewMode;
  onChange: (m: ViewMode) => void;
}) {
  const tab = (m: ViewMode, label: string) => (
    <button
      type="button"
      aria-pressed={mode === m}
      onClick={() => onChange(m)}
      className={`px-3 py-1.5 text-sm rounded-md transition focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500 ${
        mode === m
          ? "bg-muted text-foreground"
          : "text-muted-foreground hover:text-foreground"
      }`}
    >
      {label}
    </button>
  );
  return (
    <div className="inline-flex rounded-md border p-0.5 gap-0.5" role="tablist">
      {tab("table", "📋 표")}
      {tab("treemap", "🗺️ 트리맵")}
    </div>
  );
}

// ─── 보조 컴포넌트 ────────────────────────

function Header({ category, total }: { category?: SmartListCategory; total?: number }) {
  return (
    <header className="space-y-1">
      <div className="flex items-center gap-2">
        <Link
          href="/screener"
          className="text-sm text-muted-foreground hover:text-foreground"
        >
          ← 목록
        </Link>
      </div>
      <h1 className="text-2xl font-bold">
        {category?.name ?? "스마트 리스트"}
      </h1>
      {category?.desc && (
        <p className="text-sm text-muted-foreground">{category.desc}</p>
      )}
      {typeof total === "number" && (
        <p className="text-xs text-muted-foreground">총 {total.toLocaleString("ko-KR")}건</p>
      )}
    </header>
  );
}

function FreshnessBanner({ note }: { note: string }) {
  return (
    <div
      role="status"
      className="flex items-start gap-2 rounded-md border border-amber-300/60 bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:border-amber-500/30 dark:bg-amber-950/30 dark:text-amber-300"
    >
      <span aria-hidden>⚠️</span>
      <span className="whitespace-pre-line">{note}</span>
    </div>
  );
}

function ErrorCard({ message }: { message: string }) {
  return (
    <Card>
      <CardContent className="p-6 text-center space-y-2">
        <div className="text-2xl">⚠️</div>
        <p className="text-sm text-muted-foreground">{message}</p>
      </CardContent>
    </Card>
  );
}

