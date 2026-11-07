"use client";

/**
 * 종목 검색 입력 — 종목명·티커 자동완성. 상단바·홈·분석 화면에서 공유한다.
 *
 * 동작:
 *   - 입력 → 250ms 디바운스 → /api/all-stocks?q=
 *   - 한글 IME 합성 중에는 발사 안 함 (onCompositionStart/End)
 *   - 결과 dropdown — ↑/↓ 키보드 네비, Enter 선택
 *   - 결과 클릭 또는 Enter → /analyze/{ticker} 이동 (ETF는 /etf/{ticker})
 *   - 결과 없을 때 ticker 직접 입력 fallback
 */
import { Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { Input } from "@/components/ui/input";
import { useDebounced, useStockSearch } from "@/hooks/useStockSearch";
import { cn } from "@/lib/utils";

const TICKER_REGEX = /^[A-Z0-9.]{1,10}$/i;

export function StockSearch({
  placeholder = "종목명이나 코드를 입력하세요",
  size = "default",
  className,
  shortcut = false,
}: {
  placeholder?: string;
  size?: "default" | "lg";
  className?: string;
  /** "/" 키로 입력창에 포커스 (상단바 전용) */
  shortcut?: boolean;
}) {
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
  const [prevQuery, setPrevQuery] = useState(queryToSend);
  if (prevQuery !== queryToSend) {
    setPrevQuery(queryToSend);
    setActiveIdx(0);
  }

  // hits 길이 변동 시 인덱스 자동 클램프 (state 변경 없이 파생)
  const effectiveActiveIdx = hits.length > 0 ? Math.min(activeIdx, hits.length - 1) : -1;

  useEffect(() => {
    if (!shortcut) return;
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement;
      if (e.key !== "/" || el.isContentEditable || /INPUT|TEXTAREA|SELECT/.test(el.tagName)) return;
      e.preventDefault();
      inputRef.current?.focus();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [shortcut]);

  const navigate = (ticker: string, stockType?: string) => {
    if (!ticker) return;
    const tk = ticker.toUpperCase();
    setValue("");
    router.push(stockType === "etf" ? `/etf/${tk}` : `/analyze/${tk}`);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (composing) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIdx((i) => Math.min(hits.length - 1, i + 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIdx((i) => Math.max(0, i - 1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      // 1) 자동완성 후보 선택 우선
      if (effectiveActiveIdx >= 0) {
        navigate(hits[effectiveActiveIdx].ticker, hits[effectiveActiveIdx].stock_type);
        return;
      }
      // 2) 후보 없을 때 ticker 직접 입력 fallback
      const v = value.trim();
      if (TICKER_REGEX.test(v)) navigate(v);
    } else if (e.key === "Escape") {
      setValue("");
      setActiveIdx(-1);
    }
  };

  const showDropdown = queryToSend.length > 0;

  return (
    <div className={cn("relative", className)}>
      <Search
        aria-hidden="true"
        className={cn(
          "pointer-events-none absolute top-1/2 -translate-y-1/2 text-muted-foreground",
          size === "lg" ? "left-4 size-5" : "left-3 size-4",
        )}
      />
      <Input
        ref={inputRef}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        onCompositionStart={() => setComposing(true)}
        onCompositionEnd={() => setComposing(false)}
        placeholder={placeholder}
        aria-label="종목 검색"
        aria-autocomplete="list"
        aria-expanded={showDropdown && hits.length > 0}
        aria-activedescendant={effectiveActiveIdx >= 0 ? `stock-hit-${effectiveActiveIdx}` : undefined}
        className={cn(size === "lg" ? "h-13 rounded-xl pl-12 text-base md:text-base" : "pl-9")}
      />
      {showDropdown && (
        <div
          role="listbox"
          className="absolute z-30 mt-1.5 max-h-80 w-full overflow-auto rounded-xl border bg-popover shadow-lg"
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
                className={cn(
                  "flex w-full items-center justify-between gap-3 px-3.5 py-2.5 text-left text-sm transition",
                  i === effectiveActiveIdx && "bg-accent",
                )}
              >
                <span className="min-w-0">
                  <span className="block truncate font-medium">{hit.name}</span>
                  <span className="block text-xs text-muted-foreground">
                    {hit.ticker} · {hit.market || "—"}
                  </span>
                </span>
                {hit.close > 0 && (
                  <span className="shrink-0 tabular-nums">{hit.close.toLocaleString("ko-KR")}</span>
                )}
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}

function NoMatchHint({ value, onSubmit }: { value: string; onSubmit: (ticker: string) => void }) {
  const trimmed = value.trim();
  if (!TICKER_REGEX.test(trimmed)) {
    return <p className="p-3 text-sm text-muted-foreground">일치하는 종목이 없습니다.</p>;
  }
  return (
    <button
      type="button"
      onClick={() => onSubmit(trimmed)}
      className="block w-full px-3.5 py-2.5 text-left text-sm transition hover:bg-accent"
    >
      <span className="font-medium">{trimmed.toUpperCase()}</span>
      <span className="ml-2 text-xs text-muted-foreground">코드로 바로 분석</span>
    </button>
  );
}
