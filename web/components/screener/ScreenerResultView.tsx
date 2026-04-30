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
 * LEGAL: buy_grade 같은 권유성 라벨은 columnMeta에서 중립 변환.
 *        하단 Disclaimer 필수.
 */

import Link from "next/link";

import { Disclaimer } from "@/components/legal/Disclaimer";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useScan, useSmartLists } from "@/hooks/useSmartLists";
import { toSafeCategory } from "@/lib/legal-labels";
import type { SmartListCategory } from "@/types/api";

import { ProGate } from "./ProGate";
import { ResultsTable, type StockRow } from "./ResultsTable";

interface Props {
  categoryId: string;
}

export function ScreenerResultView({ categoryId }: Props) {
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
  const scanQuery = useScan(scanEnabled ? categoryId : undefined, 50);

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
        <p className="text-sm text-muted-foreground">종목 스캔 중...</p>
      </div>
    );
  }

  // ─── Scan 에러 ───────────────────────────
  if (scanQuery.isError || !scanQuery.data) {
    return (
      <div className="space-y-4">
        <Header category={category} />
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
        <Card>
          <CardContent className="p-6 space-y-3">
            <p className="text-sm">조건에 맞는 종목이 현재 없습니다.</p>
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

  // ─── 결과 표 ─────────────────────────────
  return (
    <div className="space-y-4">
      <Header category={category} total={total} />
      <ResultsTable
        columns={category.columns}
        stocks={stocks}
        caption={`${category.name} 스마트 리스트 결과 (총 ${total.toLocaleString("ko-KR")}건)`}
      />
      <Disclaimer />
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

