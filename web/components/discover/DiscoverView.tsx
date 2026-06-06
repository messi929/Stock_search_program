"use client";

/**
 * 종목 발견 (고도화) — 가이드 입력 + 시장(KR/US/전체) + 풍부한 결과 + 반복 정제.
 *
 * - 빈칸 공포 해소: 카테고리별 프리셋 칩으로 한 클릭 발견.
 * - 시장 토글: KR / US / 전체 (백엔드 후보 풀 선택).
 * - 결과 풍부화: buy_score·PER/PBR/ROE·수급 등 지표 + 매칭 사유.
 * - 반복 정제: "다른 종목 더 보기"(기존 제외 재요청)로 후보 누적.
 * externalQuery(테마 탭 등)로 외부 트리거도 지원.
 */
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useDiscover } from "@/hooks/useDiscover";
import { useAddToWatchlist, useWatchlist } from "@/hooks/useWatchlist";
import { APIError } from "@/lib/api";
import type { StockSuggestion } from "@/types/api";

type Market = "KR" | "US" | "ALL";

const MARKETS: { id: Market; label: string }[] = [
  { id: "KR", label: "🇰🇷 국내" },
  { id: "US", label: "🇺🇸 미국" },
  { id: "ALL", label: "🌐 전체" },
];

const PRESET_GROUPS: { label: string; items: string[] }[] = [
  { label: "💎 가치", items: ["저PER 저PBR 가치주", "PBR 1배 미만 자산주"] },
  { label: "🚀 성장", items: ["매출·이익 고성장주", "AI 2차 수혜주"] },
  { label: "💰 배당", items: ["안정 배당 + ROE 10% 이상", "고배당 우량주"] },
  { label: "📈 모멘텀", items: ["외국인 연속 매수 + 실적 호조", "52주 신고가 근접"] },
  { label: "🔄 역발상", items: ["급등 후 조정 재진입 후보", "52주 저점 낙폭 과대"] },
];

interface Props {
  externalQuery?: { query: string; nonce: number } | null;
}

export function DiscoverView({ externalQuery = null }: Props = {}) {
  const [query, setQuery] = useState("");
  const [market, setMarket] = useState<Market>("KR");
  const [suggestions, setSuggestions] = useState<StockSuggestion[]>([]);
  const [interpretation, setInterpretation] = useState("");
  const [activeQuery, setActiveQuery] = useState("");
  const discover = useDiscover();

  const runDiscover = (q: string, append = false) => {
    if (discover.isPending) return;
    const qq = q.trim();
    if (qq.length < 2) {
      toast.error("2자 이상 입력하세요.");
      return;
    }
    const exclude = append ? suggestions.map((s) => s.ticker) : [];
    discover.mutate(
      { query: qq, market, max_results: 6, exclude_tickers: exclude },
      {
        onSuccess: (res) => {
          setInterpretation(res.interpretation);
          setActiveQuery(qq);
          setSuggestions((prev) => (append ? [...prev, ...res.stocks] : res.stocks));
          if (append && res.stocks.length === 0) {
            toast.info("더 이상 새 후보가 없습니다.");
          }
        },
      },
    );
  };

  // 외부 트리거 (테마 탭 등)
  const lastNonceRef = useRef<number | null>(null);
  useEffect(() => {
    if (!externalQuery) return;
    if (lastNonceRef.current === externalQuery.nonce) return;
    lastNonceRef.current = externalQuery.nonce;
    setQuery(externalQuery.query);
    runDiscover(externalQuery.query);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [externalQuery]);

  const reset = () => {
    setSuggestions([]);
    setInterpretation("");
    setActiveQuery("");
    discover.reset();
  };

  const hasResults = suggestions.length > 0;

  return (
    <div className="space-y-4">
      {/* 입력 카드 */}
      <Card>
        <CardContent className="p-5 space-y-4">
          <header className="space-y-1">
            <h3 className="font-semibold">🧭 AI 종목 발견</h3>
            <p className="text-sm text-muted-foreground">
              조건을 자유롭게 설명하거나, 아래 프리셋을 눌러 바로 발견하세요.
            </p>
          </header>

          {/* 시장 토글 */}
          <div className="inline-flex rounded-md border p-0.5 text-sm">
            {MARKETS.map((m) => (
              <button
                key={m.id}
                type="button"
                onClick={() => setMarket(m.id)}
                className={`px-3 py-1 rounded ${
                  market === m.id
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-muted"
                }`}
              >
                {m.label}
              </button>
            ))}
          </div>

          {/* 자유 입력 */}
          <div className="flex gap-2">
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  runDiscover(query);
                }
              }}
              placeholder="예: AI 반도체 소재 + 외국인 매수, 저평가 배당주..."
            />
            <Button
              type="button"
              onClick={() => runDiscover(query)}
              disabled={discover.isPending || query.trim().length < 2}
            >
              {discover.isPending ? "발견 중..." : "발견"}
            </Button>
          </div>

          {/* 가이드 프리셋 — 결과 없을 때만 */}
          {!hasResults && (
            <div className="space-y-2">
              {PRESET_GROUPS.map((g) => (
                <div key={g.label} className="flex items-center gap-2 flex-wrap">
                  <span className="text-xs text-muted-foreground w-16 shrink-0">
                    {g.label}
                  </span>
                  {g.items.map((q) => (
                    <button
                      key={q}
                      type="button"
                      disabled={discover.isPending}
                      onClick={() => {
                        setQuery(q);
                        runDiscover(q);
                      }}
                      className="text-xs px-2 py-1 rounded-full border border-border text-muted-foreground hover:bg-muted disabled:opacity-50"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              ))}
            </div>
          )}

          <p className="text-[10px] text-muted-foreground">
            AI 발견 1회당 비용이 발생합니다(동일 조건은 캐시 0원). 결과는 참고용이며
            투자 판단은 본인 책임입니다.
          </p>
        </CardContent>
      </Card>

      {/* 에러 */}
      {discover.isError && (
        <Card>
          <CardContent className="p-4 space-y-2 text-sm text-destructive">
            <p>{(discover.error as Error)?.message ?? "조회 실패"}</p>
            {(discover.error as APIError)?.upgradeUrl && (
              <Link
                href={(discover.error as APIError).upgradeUrl!}
                className="inline-flex items-center rounded-md bg-amber-500/90 px-3 py-1.5 text-xs font-medium text-white hover:bg-amber-500"
              >
                Pro 플랜 보기 →
              </Link>
            )}
          </CardContent>
        </Card>
      )}

      {/* 결과 */}
      {(hasResults || interpretation) && (
        <Card>
          <CardContent className="p-5 space-y-4">
            {interpretation && (
              <section>
                <h4 className="text-xs font-medium text-muted-foreground mb-1">
                  쿼리 해석
                </h4>
                <p className="text-sm leading-relaxed">{interpretation}</p>
              </section>
            )}

            <section className="space-y-2">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-medium text-muted-foreground">
                  관찰 가치 종목 ({suggestions.length})
                </h4>
                <button
                  type="button"
                  onClick={reset}
                  className="text-xs text-muted-foreground hover:text-foreground underline"
                >
                  초기화
                </button>
              </div>

              {suggestions.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  조건에 부합하는 후보가 없습니다. 다른 표현이나 시장을 바꿔보세요.
                </p>
              ) : (
                <ul className="space-y-2">
                  {suggestions.map((s) => (
                    <SuggestionRow key={s.ticker} s={s} />
                  ))}
                </ul>
              )}

              {/* 반복 정제 */}
              {suggestions.length > 0 && activeQuery && (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="w-full"
                  disabled={discover.isPending}
                  onClick={() => runDiscover(activeQuery, true)}
                >
                  {discover.isPending ? "찾는 중..." : "↻ 다른 종목 더 보기"}
                </Button>
              )}
            </section>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="text-center">
      <div className="text-[10px] text-muted-foreground">{label}</div>
      <div className="font-mono text-xs font-medium">{value}</div>
    </div>
  );
}

function scoreColor(v: number): string {
  if (v >= 70) return "bg-emerald-500/15 text-emerald-700";
  if (v >= 50) return "bg-amber-500/15 text-amber-700";
  return "bg-muted text-muted-foreground";
}

function SuggestionRow({ s }: { s: StockSuggestion }) {
  const { data } = useWatchlist();
  const add = useAddToWatchlist();
  const already = (data?.watchlist ?? []).includes(s.ticker);
  const isKR = /^\d{6}$/.test(s.ticker);
  const cur = isKR ? "원" : "$";

  const handleAdd = async () => {
    try {
      const res = await add.mutateAsync(s.ticker);
      toast[res.alreadyPresent ? "info" : "success"](
        res.alreadyPresent ? "이미 관심 종목에 있습니다." : `${s.name} 추가됨`,
      );
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "추가 실패");
    }
  };

  return (
    <li className="p-3 rounded-md border bg-muted/20 space-y-2">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 text-sm flex-wrap">
            <span className="font-mono">{s.ticker}</span>
            <span className="font-medium">{s.name}</span>
            {s.market && (
              <span className="text-xs text-muted-foreground">{s.market}</span>
            )}
            {s.current_price > 0 && (
              <span className="text-xs font-mono text-muted-foreground">
                {isKR
                  ? `${s.current_price.toLocaleString()}${cur}`
                  : `${cur}${s.current_price.toLocaleString()}`}
              </span>
            )}
            {s.buy_score != null && s.buy_score > 0 && (
              <span
                className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${scoreColor(s.buy_score)}`}
                title="종합 점수 (buy_score)"
              >
                점수 {s.buy_score.toFixed(0)}
              </span>
            )}
          </div>
          <p className="text-xs text-muted-foreground mt-1">{s.reason}</p>
        </div>
        <div className="flex gap-2 shrink-0">
          <Link
            href={`/analyze/${s.ticker}`}
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
            {already ? "등록됨" : "+ 추가"}
          </Button>
        </div>
      </div>

      {/* 핵심 지표 */}
      <div className="grid grid-cols-5 gap-1 pt-1 border-t">
        <Metric label="PER" value={s.per ? s.per.toFixed(1) : "-"} />
        <Metric label="PBR" value={s.pbr ? s.pbr.toFixed(2) : "-"} />
        <Metric label="ROE" value={s.roe ? `${s.roe.toFixed(0)}%` : "-"} />
        <Metric
          label="배당"
          value={s.div_yield ? `${s.div_yield.toFixed(1)}%` : "-"}
        />
        <Metric
          label="52w고점차"
          value={
            s.vs_high_52w != null && s.vs_high_52w !== 0
              ? `${s.vs_high_52w.toFixed(0)}%`
              : "-"
          }
        />
      </div>
      {(s.foreign_consecutive ?? 0) > 0 || s.themes ? (
        <div className="flex items-center gap-2 flex-wrap text-[10px] text-muted-foreground">
          {(s.foreign_consecutive ?? 0) > 0 && (
            <span className="px-1.5 py-0.5 rounded bg-sky-500/10 text-sky-700">
              외국인 {s.foreign_consecutive}일 연속
            </span>
          )}
          {s.themes && <span className="truncate">🏷 {s.themes}</span>}
        </div>
      ) : null}
    </li>
  );
}
