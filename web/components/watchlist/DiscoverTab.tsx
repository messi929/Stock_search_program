"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useDiscover } from "@/hooks/useDiscover";
import { useAddToWatchlist, useWatchlist } from "@/hooks/useWatchlist";
import type { StockSuggestion } from "@/types/api";

const EXAMPLES = [
  "저PER 저PBR 가치주",
  "외국인 연속 매수 + 실적 호조",
  "AI 2차 수혜주",
  "안정 배당 + ROE 10% 이상",
];

interface DiscoverTabProps {
  /** 외부에서 검색 트리거 — nonce 변경 시 query를 채우고 자동 발견 */
  externalQuery?: { query: string; nonce: number } | null;
}

export function DiscoverTab({ externalQuery = null }: DiscoverTabProps = {}) {
  const [query, setQuery] = useState("");
  const discover = useDiscover();
  const result = discover.data;

  // 외부 트리거 처리 (ThemesTab 클릭 등) — 같은 쿼리는 dedupe
  const lastNonceRef = useRef<number | null>(null);
  useEffect(() => {
    if (!externalQuery) return;
    if (lastNonceRef.current === externalQuery.nonce) return;
    lastNonceRef.current = externalQuery.nonce;
    setQuery(externalQuery.query);
    if (discover.isPending) return; // 진행 중이면 무시
    if (lastSubmittedRef.current === externalQuery.query && discover.data) return;
    lastSubmittedRef.current = externalQuery.query;
    discover.mutate({ query: externalQuery.query, max_results: 5 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [externalQuery]);

  // 동일 쿼리 dedupe — 비용 보호 (~70원/호출)
  const lastSubmittedRef = useRef<string | null>(null);
  const startDiscover = (q: string) => {
    if (discover.isPending) return;
    if (q.length < 2) {
      toast.error("2자 이상 입력하세요.");
      return;
    }
    if (lastSubmittedRef.current === q && discover.data) {
      toast.info("동일 쿼리 — 이전 결과 유지");
      return;
    }
    lastSubmittedRef.current = q;
    discover.mutate({ query: q, max_results: 5 });
  };

  const submit = () => startDiscover(query.trim());

  return (
    <Card>
      <CardContent className="p-5 space-y-4">
        <header className="space-y-1">
          <h3 className="font-semibold">🤖 AI에게 자연어로 발견 요청</h3>
          <p className="text-sm text-muted-foreground">
            예: 시장 상황·테마·재무 조건을 자유롭게 설명하세요.
          </p>
        </header>

        <div className="flex gap-2">
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                submit();
              }
            }}
            placeholder="찾고 싶은 관찰 가치 종목의 조건..."
          />
          <Button
            type="button"
            onClick={submit}
            disabled={discover.isPending || query.trim().length < 2}
          >
            {discover.isPending ? "분석 중..." : "발견"}
          </Button>
        </div>

        {!result && (
          <div className="flex flex-wrap gap-2">
            {EXAMPLES.map((e) => (
              <button
                key={e}
                type="button"
                disabled={discover.isPending}
                onClick={() => {
                  setQuery(e);
                  startDiscover(e);
                }}
                className="text-xs px-2 py-1 rounded border border-border text-muted-foreground hover:bg-muted disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {e}
              </button>
            ))}
          </div>
        )}

        {discover.isError && (
          <p className="text-sm text-destructive">
            {(discover.error as Error)?.message ?? "조회 실패"}
          </p>
        )}

        {result && (
          <div className="space-y-3">
            <section>
              <h4 className="text-xs font-medium text-muted-foreground mb-1">
                쿼리 해석
              </h4>
              <p className="text-sm leading-relaxed">{result.interpretation}</p>
            </section>

            <section className="space-y-2">
              <h4 className="text-xs font-medium text-muted-foreground">
                관찰 가치 종목 ({result.stocks.length})
              </h4>
              {result.stocks.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  쿼리에 부합하는 후보가 없습니다.
                </p>
              ) : (
                <ul className="space-y-2">
                  {result.stocks.map((s) => (
                    <SuggestionRow key={s.ticker} suggestion={s} />
                  ))}
                </ul>
              )}
              <p className="text-[10px] text-muted-foreground pt-1">
                ⚠️ AI 발견 결과는 참고용이며 투자 판단은 사용자 본인의 책임입니다.
              </p>
            </section>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function SuggestionRow({ suggestion }: { suggestion: StockSuggestion }) {
  const { data } = useWatchlist();
  const add = useAddToWatchlist();
  const list = data?.watchlist ?? [];
  const already = list.includes(suggestion.ticker);

  const handleAdd = async () => {
    try {
      // closure stale 방지 — mutation 내부에서 fresh list 조회
      const res = await add.mutateAsync(suggestion.ticker);
      if (res.alreadyPresent) {
        toast.info("이미 관심 종목에 있습니다.");
      } else {
        toast.success(`${suggestion.name} 관심 종목 추가됨`);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "추가 실패";
      toast.error(msg);
    }
  };

  return (
    <li className="p-3 rounded-md border bg-muted/20">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 text-sm">
            <span className="font-mono">{suggestion.ticker}</span>
            <span className="font-medium">{suggestion.name}</span>
            {suggestion.market && (
              <span className="text-xs text-muted-foreground">
                {suggestion.market}
              </span>
            )}
            {suggestion.current_price > 0 && (
              <span className="text-xs font-mono text-muted-foreground">
                {suggestion.current_price.toLocaleString()}원
              </span>
            )}
          </div>
          <p className="text-xs text-muted-foreground mt-1">{suggestion.reason}</p>
        </div>
        <div className="flex gap-2">
          <Link
            href={`/analyze/${suggestion.ticker}`}
            className="text-xs px-2 py-1 rounded border border-border hover:bg-muted"
          >
            상세 분석 →
          </Link>
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={handleAdd}
            disabled={already || add.isPending}
          >
            {already ? "등록됨" : add.isPending ? "추가 중..." : "+ 추가"}
          </Button>
        </div>
      </div>
    </li>
  );
}
