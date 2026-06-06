"use client";

import { useRouter } from "next/navigation";
import { useRef } from "react";
import { toast } from "sonner";

import { Disclaimer } from "@/components/legal/Disclaimer";
import { SearchTab } from "@/components/watchlist/SearchTab";
import { ThemesTab } from "@/components/watchlist/ThemesTab";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";

const DEBOUNCE_MS = 800;

export default function AddWatchlistPage() {
  const router = useRouter();
  const lastClickRef = useRef<number>(0);

  // 테마 선택 → 종목 발견(/discover)으로 런치. AI 발견은 이제 종목 발견 페이지가 전담.
  const launchDiscover = (query: string) => {
    const now = Date.now();
    if (now - lastClickRef.current < DEBOUNCE_MS) {
      toast.info("잠시만 기다려주세요...");
      return;
    }
    lastClickRef.current = now;
    router.push(`/discover?q=${encodeURIComponent(query)}`);
  };

  return (
    <div className="space-y-6 max-w-3xl">
      <header>
        <h1 className="text-2xl font-bold">⭐ 관심 종목 추가</h1>
        <p className="text-sm text-muted-foreground mt-1">
          종목 코드로 직접 검색해 추가하거나, 테마에서 골라 AI 발견으로 이어가세요.
          (AI에게 조건으로 찾기는{" "}
          <span className="font-medium">사이드바 · 종목 발견</span>)
        </p>
      </header>

      <Tabs defaultValue="search">
        <TabsList>
          <TabsTrigger value="search">🔎 검색</TabsTrigger>
          <TabsTrigger value="themes">🎯 테마</TabsTrigger>
        </TabsList>

        <TabsContent value="search">
          <SearchTab />
        </TabsContent>

        <TabsContent value="themes">
          <ThemesTab
            isPending={false}
            onSelect={(_label, query) => launchDiscover(query)}
          />
        </TabsContent>
      </Tabs>

      <Disclaimer />
    </div>
  );
}
