"use client";

import { useRef, useState } from "react";
import { toast } from "sonner";

import { Disclaimer } from "@/components/legal/Disclaimer";
import { DiscoverTab } from "@/components/watchlist/DiscoverTab";
import { SearchTab } from "@/components/watchlist/SearchTab";
import { ThemesTab } from "@/components/watchlist/ThemesTab";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";

type TabId = "search" | "discover" | "themes";

const THEME_DEBOUNCE_MS = 800;

export default function AddWatchlistPage() {
  const [tab, setTab] = useState<TabId>("search");
  const [externalQuery, setExternalQuery] = useState<{
    query: string;
    nonce: number;
  } | null>(null);
  const [debouncing, setDebouncing] = useState(false);
  const lastClickRef = useRef<number>(0);

  const triggerDiscover = (query: string) => {
    // 800ms 내 중복 클릭 차단 (비용 보호 — Discover Sonnet ~70원/호출)
    const now = Date.now();
    if (now - lastClickRef.current < THEME_DEBOUNCE_MS) {
      toast.info("잠시만 기다려주세요...");
      return;
    }
    lastClickRef.current = now;
    setDebouncing(true);
    window.setTimeout(() => setDebouncing(false), THEME_DEBOUNCE_MS);
    setExternalQuery({ query, nonce: now });
    setTab("discover");
  };

  return (
    <div className="space-y-6 max-w-3xl">
      <header>
        <h1 className="text-2xl font-bold">⭐ 관심 종목 추가</h1>
        <p className="text-sm text-muted-foreground mt-1">
          종목 코드 검색, AI에게 자연어 발견 요청, 큐레이션 테마 중 선택하세요.
        </p>
      </header>

      <Tabs value={tab} onValueChange={(v) => setTab(v as TabId)}>
        <TabsList>
          <TabsTrigger value="search">🔎 검색</TabsTrigger>
          <TabsTrigger value="discover">🤖 AI 발견</TabsTrigger>
          <TabsTrigger value="themes">🎯 테마</TabsTrigger>
        </TabsList>

        <TabsContent value="search">
          <SearchTab />
        </TabsContent>

        <TabsContent value="discover">
          <DiscoverTab externalQuery={externalQuery} />
        </TabsContent>

        <TabsContent value="themes">
          <ThemesTab
            isPending={debouncing}
            onSelect={(_label, query) => triggerDiscover(query)}
          />
        </TabsContent>
      </Tabs>

      <Disclaimer />
    </div>
  );
}
