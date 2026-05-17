"use client";

/**
 * /screener/custom — Pro 전용 커스텀 스크리너 뷰.
 *
 * 게이트:
 *   - usePersonas() user_plan === "free" → ProGate
 *   - 백엔드 CRUD 라우트도 402 PRO_REQUIRED 응답 (이중 방어)
 *
 * 흐름:
 *   1. FilterBuilder 폼 (controlled state)
 *   2. "실행" → useRunCustomScreener → ResultsTable
 *   3. "저장" → 다이얼로그 (이름 입력) → POST → SavedScreenersList 갱신
 *   4. 목록에서 클릭 → 폼에 로드 (activeId 트래킹)
 */
import { useState } from "react";
import Link from "next/link";
import { toast } from "sonner";

import { Disclaimer } from "@/components/legal/Disclaimer";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  useRunCustomScreener,
  useSaveCustomScreener,
} from "@/hooks/useCustomScreeners";
import { usePersonas } from "@/hooks/usePersonas";
import type { CustomScreener, CustomScreenerFilters } from "@/types/api";

import {
  DEFAULT_RESULT_COLUMNS,
  type SortKey,
} from "./customScreenerOptions";
import { FilterBuilder, type FilterBuilderValue } from "./FilterBuilder";
import { ProGate } from "./ProGate";
import { ResultsTable, type StockRow } from "./ResultsTable";
import { SavedScreenersList } from "./SavedScreenersList";

const INITIAL_VALUE: FilterBuilderValue = {
  filters: {},
  sort_by: "buy_score" as SortKey,
  sort_asc: false,
};

export function CustomScreenerView() {
  const { data: personas, isLoading: planLoading } = usePersonas();
  const userPlan = (personas?.user_plan ?? "free").toLowerCase();
  const isPro = userPlan === "pro" || userPlan === "premium";

  const [value, setValue] = useState<FilterBuilderValue>(INITIAL_VALUE);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [runFilters, setRunFilters] = useState<{
    filters: CustomScreenerFilters;
    sort_by: SortKey;
    sort_asc: boolean;
  } | null>(null);
  const [saveDialogOpen, setSaveDialogOpen] = useState(false);
  const [saveName, setSaveName] = useState("");

  const scanQuery = useRunCustomScreener(
    runFilters?.filters ?? null,
    runFilters?.sort_by ?? "buy_score",
    runFilters?.sort_asc ?? false,
  );
  const save = useSaveCustomScreener();

  // ─── 게이트 ────────────────────────────────
  if (planLoading) {
    return <p className="text-sm text-muted-foreground">플랜 정보 확인 중...</p>;
  }
  if (!isPro) {
    return (
      <div className="space-y-4">
        <Header />
        <ProGate categoryName="커스텀 스크리너" />
        <Disclaimer />
      </div>
    );
  }

  // ─── 핸들러 ────────────────────────────────
  const hasAnyFilter = Object.keys(value.filters).length > 0;

  const handleRun = () => {
    if (!hasAnyFilter) {
      toast.warning("최소 하나의 조건을 입력해주세요.");
      return;
    }
    // 범위 역전 검증 — 백엔드도 422로 막지만 즉시 피드백 위해
    const ranges: [keyof typeof value.filters, keyof typeof value.filters, string][] = [
      ["per_min", "per_max", "PER"],
      ["pbr_min", "pbr_max", "PBR"],
      ["roe_min", "roe_max", "ROE"],
      ["market_cap_min", "market_cap_max", "시총"],
      ["change_pct_min", "change_pct_max", "등락률"],
      ["rsi_min", "rsi_max", "RSI"],
    ];
    for (const [minK, maxK, label] of ranges) {
      const min = value.filters[minK];
      const max = value.filters[maxK];
      if (typeof min === "number" && typeof max === "number" && min > max) {
        toast.error(`${label} 최소값(${min})이 최대값(${max})보다 큽니다.`);
        return;
      }
    }
    setRunFilters({
      filters: value.filters,
      sort_by: value.sort_by,
      sort_asc: value.sort_asc,
    });
  };

  const handleReset = () => {
    setValue(INITIAL_VALUE);
    setActiveId(null);
    setRunFilters(null);
  };

  const handleLoad = (s: CustomScreener) => {
    setValue({
      filters: s.filters,
      sort_by: (s.sort_by as SortKey) ?? "buy_score",
      sort_asc: !!s.sort_asc,
    });
    setActiveId(s.id);
    setRunFilters({
      filters: s.filters,
      sort_by: (s.sort_by as SortKey) ?? "buy_score",
      sort_asc: !!s.sort_asc,
    });
    toast.info(`"${s.name}" 로드됨.`);
  };

  const handleOpenSave = () => {
    if (!hasAnyFilter) {
      toast.warning("최소 하나의 조건을 입력해주세요.");
      return;
    }
    setSaveName("");
    setSaveDialogOpen(true);
  };

  const handleSaveConfirm = async () => {
    const name = saveName.trim();
    if (!name) {
      toast.warning("이름을 입력해주세요.");
      return;
    }
    if (name.length > 40) {
      toast.warning("이름은 40자 이내로 입력해주세요.");
      return;
    }
    try {
      await save.mutateAsync({
        name,
        filters: value.filters,
        sort_by: value.sort_by,
        sort_asc: value.sort_asc,
      });
      toast.success("저장되었습니다.");
      setSaveDialogOpen(false);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "저장 실패";
      toast.error(msg);
    }
  };

  // ─── 결과 영역 ─────────────────────────────
  let resultArea: React.ReactNode;
  if (!runFilters) {
    resultArea = (
      <Card>
        <CardContent className="p-6 text-center text-sm text-muted-foreground">
          조건을 설정하고 &quot;실행&quot; 버튼을 눌러주세요.
        </CardContent>
      </Card>
    );
  } else if (scanQuery.isLoading) {
    resultArea = <p className="text-sm text-muted-foreground">스캔 중...</p>;
  } else if (scanQuery.isError || !scanQuery.data) {
    resultArea = (
      <Card>
        <CardContent className="p-6 text-center space-y-2">
          <div className="text-2xl">⚠️</div>
          <p className="text-sm text-muted-foreground">
            스캔에 실패했습니다. 잠시 후 다시 시도해주세요.
          </p>
        </CardContent>
      </Card>
    );
  } else {
    const rawStocks = scanQuery.data.stocks;
    const stocks = rawStocks.filter(
      (s): s is StockRow => typeof (s as { ticker?: unknown }).ticker === "string",
    );
    const total = scanQuery.data.total;
    if (!stocks.length) {
      resultArea = (
        <Card>
          <CardContent className="p-6 space-y-2 text-sm">
            <p>조건에 맞는 종목이 없습니다.</p>
            {scanQuery.data.message && (
              <p className="text-xs text-muted-foreground whitespace-pre-line">
                {scanQuery.data.message}
              </p>
            )}
          </CardContent>
        </Card>
      );
    } else {
      resultArea = (
        <div className="space-y-2">
          <p className="text-xs text-muted-foreground">총 {total.toLocaleString("ko-KR")}건</p>
          <ResultsTable
            columns={DEFAULT_RESULT_COLUMNS}
            stocks={stocks}
            caption={`커스텀 스크리너 결과 (총 ${total.toLocaleString("ko-KR")}건)`}
          />
        </div>
      );
    }
  }

  return (
    <div className="space-y-6">
      <Header />

      {/* 저장된 목록 */}
      <section className="space-y-2">
        <h2 className="text-sm font-semibold">저장된 스크리너</h2>
        <SavedScreenersList onLoad={handleLoad} activeId={activeId} />
      </section>

      {/* 빌더 */}
      <Card>
        <CardContent className="p-6 space-y-6">
          <FilterBuilder value={value} onChange={(next) => {
            setValue(next);
            // 폼 변경 시 active 마크 해제 (저장된 것과 달라짐)
            setActiveId(null);
          }} />
          <div className="flex flex-wrap gap-2 pt-2 border-t">
            <Button type="button" onClick={handleRun} disabled={!hasAnyFilter}>
              ▶ 실행
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={handleOpenSave}
              disabled={!hasAnyFilter || save.isPending}
            >
              💾 저장
            </Button>
            <Button type="button" variant="ghost" onClick={handleReset}>
              초기화
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* 결과 */}
      {resultArea}

      <Disclaimer />

      {/* 저장 다이얼로그 */}
      <Dialog open={saveDialogOpen} onOpenChange={setSaveDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>스크리너 저장</DialogTitle>
          </DialogHeader>
          <div className="space-y-2 py-2">
            <label htmlFor="screener-name" className="text-sm">
              이름
            </label>
            <Input
              id="screener-name"
              value={saveName}
              onChange={(e) => setSaveName(e.target.value)}
              maxLength={40}
              placeholder="예: 저PER 고배당"
              autoFocus
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  handleSaveConfirm();
                }
              }}
            />
            <p className="text-xs text-muted-foreground">최대 20개까지 저장 가능합니다.</p>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setSaveDialogOpen(false)} disabled={save.isPending}>
              취소
            </Button>
            <Button onClick={handleSaveConfirm} disabled={save.isPending}>
              {save.isPending ? "저장 중..." : "저장"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function Header() {
  return (
    <header className="space-y-1">
      <div>
        <Link
          href="/screener"
          className="text-sm text-muted-foreground hover:text-foreground"
        >
          ← 스마트 리스트
        </Link>
      </div>
      <h1 className="text-2xl font-bold">🔧 커스텀 스크리너</h1>
      <p className="text-sm text-muted-foreground">
        직접 조건을 조합해 종목을 탐색하고 저장합니다 (Pro 전용)
      </p>
    </header>
  );
}
