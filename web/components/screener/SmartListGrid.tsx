"use client";

import Link from "next/link";

import { Card, CardContent } from "@/components/ui/card";
import { useSmartLists } from "@/hooks/useSmartLists";
import { toSafeCategory } from "@/lib/legal-labels";
import type { SmartListCategory } from "@/types/api";

const GROUP_LABELS: Record<string, string> = {
  strategy: "📈 전략",
  fundamental: "💎 펀더멘털",
  supply: "💸 수급",
  technical: "📊 기술적",
  etc: "기타",
};

function groupBy(items: SmartListCategory[]): Record<string, SmartListCategory[]> {
  const out: Record<string, SmartListCategory[]> = {};
  for (const it of items) {
    const g = it.group || "etc";
    (out[g] ??= []).push(it);
  }
  return out;
}

export function SmartListGrid() {
  const { data, isLoading, isError } = useSmartLists();

  if (isLoading) {
    return <p className="text-sm text-muted-foreground">스마트 리스트 로딩 중...</p>;
  }
  if (isError || !data) {
    return <p className="text-sm text-muted-foreground">⚠️ 스마트 리스트 조회 실패</p>;
  }

  // LEGAL: 권유성 카테고리 라벨을 Axis 정책에 맞게 변환 후 표시
  const safeCategories = data.categories.map(toSafeCategory);
  const groups = groupBy(safeCategories);
  const order = ["strategy", "fundamental", "supply", "technical", "etc"];

  return (
    <div className="space-y-6">
      {order
        .filter((g) => groups[g])
        .map((g) => (
          <section key={g}>
            <h2 className="font-semibold mb-3">{GROUP_LABELS[g] ?? g}</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {groups[g].map((c) => (
                <Link
                  key={c.id}
                  href={`/screener/${c.id}`}
                  className="block focus:outline-none"
                >
                  <Card className="hover:bg-muted transition cursor-pointer">
                    <CardContent className="p-4 space-y-2">
                      <div className="flex items-center justify-between">
                        <h3 className="font-medium">{c.name}</h3>
                        {!c.available_to_free && (
                          <span className="text-xs px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-500">
                            Pro
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-muted-foreground line-clamp-2">
                        {c.desc || c.id}
                      </p>
                    </CardContent>
                  </Card>
                </Link>
              ))}
            </div>
          </section>
        ))}
    </div>
  );
}
