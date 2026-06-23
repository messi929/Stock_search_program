"use client";

/**
 * 검색 탭 — 종목명·티커 LIKE 자동완성.
 *
 * 동작:
 *   - 입력 → 250ms 디바운스 → /api/all-stocks?q=
 *   - 한글 IME 합성 중에는 발사 안 함 (onCompositionStart/End)
 *   - 결과 dropdown — ↑/↓ 키보드 네비, Enter 선택
 *   - 결과 클릭 또는 Enter → /analyze/{ticker} 이동
 *   - 결과 없을 때 ticker 직접 입력 fallback (기존 동작 유지)
 */
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";

import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useDebounced, useStockSearch } from "@/hooks/useStockSearch";

const TICKER_REGEX = /^[A-Z0-9.]{1,10}$/i;

export function SearchTab() {
  const router = useRouter();
  const [value, setValue] = useState("");
  const [composing, setComposing] = useState(false);
  const [activeIdx, setActiveIdx] = useState(0);
  const debounced = useDebounced(value, 250);
  const inputRef = useRef<HTMLInputElement>(null);

  // IME 합성 중에는 디바운스 입력을 비워서 검색 발사 안 함
  const queryToSend = composing ? "" : debounced.trim();
  const { data, isFetching } = useStockSearch(queryToSend, 10);
  const hits = data?.stocks ?? [];

  // 쿼리 변경 시 activeIdx 리셋 — React 19 "state during render" 패턴
  // (useEffect+setState 안티패턴 회피)
  const [prevQuery, setPrevQuery] = useState(queryToSend);
  if (prevQuery !== queryToSend) {
    setPrevQuery(queryToSend);
    setActiveIdx(0);
  }

  // hits 길이 변동 시 인덱스 자동 클램프 (state 변경 없이 파생)
  const effectiveActiveIdx =
    hits.length > 0 ? Math.min(activeIdx, hits.length - 1) : -1;

  const navigate = (ticker: string, stockType?: string) => {
    if (!ticker) return;
    const tk = ticker.toUpperCase();
    // ETF는 전용 상세(/etf), 일반 종목은 딥다이브(/analyze)로.
    router.push(stockType === "etf" ? `/etf/${tk}` : `/analyze/${tk}`);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (composing) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIdx((i) => Math.min(hits.length - 1, i + 1));
      return;
    }
    if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIdx((i) => Math.max(0, i - 1));
      return;
    }
    if (e.key === "Enter") {
      e.preventDefault();
      // 1) 자동완성 후보 선택 우선
      if (hits.length > 0 && effectiveActiveIdx >= 0 && effectiveActiveIdx < hits.length) {
        navigate(hits[effectiveActiveIdx].ticker, hits[effectiveActiveIdx].stock_type);
        return;
      }
      // 2) 후보 없을 때 ticker 직접 입력 fallback
      const v = value.trim();
      if (TICKER_REGEX.test(v)) {
        navigate(v);
      }
      return;
    }
    if (e.key === "Escape") {
      setValue("");
      setActiveIdx(-1);
    }
  };

  const showDropdown = queryToSend.length > 0;

  return (
    // overflow-visible: 기본 Card는 overflow-hidden이라 absolute 드롭다운이 잘림.
    <Card className="overflow-visible">
      <CardContent className="p-5 space-y-3">
        <h3 className="font-semibold">🔎 종목명 또는 코드로 검색</h3>
        <p className="text-sm text-muted-foreground">
          예: 삼성전자, 005930, AAPL
        </p>
        <div className="relative">
          <Input
            ref={inputRef}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            onCompositionStart={() => setComposing(true)}
            onCompositionEnd={() => setComposing(false)}
            placeholder="종목명·티커 입력..."
            aria-label="종목 검색"
            aria-autocomplete="list"
            aria-expanded={showDropdown && hits.length > 0}
            aria-activedescendant={
              effectiveActiveIdx >= 0 ? `stock-hit-${effectiveActiveIdx}` : undefined
            }
          />
          {showDropdown && (
            <div
              role="listbox"
              className="absolute z-10 mt-1 w-full rounded-md border bg-popover shadow-md max-h-80 overflow-auto"
            >
              {isFetching && hits.length === 0 ? (
                <p className="p-3 text-sm text-muted-foreground">검색 중...</p>
              ) : hits.length === 0 ? (
                <NoMatchHint value={value} onSubmit={navigate} />
              ) : (
                hits.map((hit, i) => (
                  <button
                    key={hit.ticker}
                    id={`stock-hit-${i}`}
                    role="option"
                    aria-selected={i === effectiveActiveIdx}
                    type="button"
                    onClick={() => navigate(hit.ticker, hit.stock_type)}
                    onMouseEnter={() => setActiveIdx(i)}
                    className={`block w-full text-left px-3 py-2 text-sm transition border-b last:border-b-0 ${
                      i === effectiveActiveIdx ? "bg-amber-500/10" : "hover:bg-muted/50"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium truncate">{hit.name}</span>
                      <span className="text-xs text-muted-foreground shrink-0 font-mono">
                        {hit.ticker}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 text-xs text-muted-foreground mt-0.5">
                      <span>{hit.market || "—"}</span>
                      {hit.close > 0 && (
                        <>
                          <span>·</span>
                          <span className="tabular-nums">
                            {hit.close.toLocaleString("ko-KR")}
                          </span>
                        </>
                      )}
                    </div>
                  </button>
                ))
              )}
            </div>
          )}
        </div>
        <p className="text-xs text-muted-foreground">
          💡 ↑↓ 키로 이동, Enter로 선택. 결과가 없으면 6자리 코드(KR) 또는
          티커(US)를 직접 입력 후 Enter.
        </p>
      </CardContent>
    </Card>
  );
}

function NoMatchHint({
  value,
  onSubmit,
}: {
  value: string;
  onSubmit: (ticker: string) => void;
}) {
  const trimmed = value.trim();
  const isTickerLike = TICKER_REGEX.test(trimmed);
  if (!isTickerLike) {
    return (
      <p className="p-3 text-sm text-muted-foreground">
        일치하는 종목이 없습니다.
      </p>
    );
  }
  return (
    <button
      type="button"
      onClick={() => onSubmit(trimmed)}
      className="block w-full text-left px-3 py-2 text-sm hover:bg-muted/50 transition"
    >
      <span className="font-mono">{trimmed.toUpperCase()}</span>
      <span className="ml-2 text-xs text-muted-foreground">
        티커로 직접 분석 →
      </span>
    </button>
  );
}
