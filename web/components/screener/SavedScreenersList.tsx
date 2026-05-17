"use client";

/**
 * 저장된 커스텀 스크리너 목록 — 클릭 시 폼에 로드, X 버튼으로 삭제.
 * 비어있을 땐 안내 텍스트만.
 */
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  useCustomScreeners,
  useDeleteCustomScreener,
} from "@/hooks/useCustomScreeners";
import type { CustomScreener } from "@/types/api";

interface Props {
  onLoad: (s: CustomScreener) => void;
  activeId?: string | null;
}

export function SavedScreenersList({ onLoad, activeId }: Props) {
  const { data, isLoading, isError } = useCustomScreeners();
  const del = useDeleteCustomScreener();

  if (isLoading) {
    return <p className="text-xs text-muted-foreground">저장된 스크리너 로딩 중...</p>;
  }
  if (isError) {
    return <p className="text-xs text-muted-foreground">⚠️ 저장된 스크리너 조회 실패</p>;
  }
  const items = data?.screeners ?? [];
  if (items.length === 0) {
    return (
      <p className="text-xs text-muted-foreground">
        저장된 스크리너가 없습니다. 조건을 설정하고 &quot;저장&quot; 버튼을 눌러보세요.
      </p>
    );
  }

  const handleDelete = async (id: string, name: string) => {
    if (!confirm(`"${name}" 스크리너를 삭제할까요?`)) return;
    try {
      await del.mutateAsync(id);
      toast.success("삭제되었습니다.");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "삭제 실패");
    }
  };

  return (
    <div className="flex flex-wrap gap-2" role="list" aria-label="저장된 스크리너">
      {items.map((s) => {
        const active = s.id === activeId;
        return (
          <div
            key={s.id}
            role="listitem"
            className={`flex items-center gap-1 rounded-full border pl-3 pr-1 py-0.5 text-sm transition ${
              active
                ? "border-amber-500 bg-amber-500/10"
                : "hover:bg-muted"
            }`}
          >
            <button
              type="button"
              onClick={() => onLoad(s)}
              className="font-medium focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500 rounded"
            >
              {s.name}
            </button>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-6 w-6 p-0 text-muted-foreground hover:text-destructive"
              onClick={() => handleDelete(s.id, s.name)}
              aria-label={`${s.name} 삭제`}
              disabled={del.isPending}
            >
              ✕
            </Button>
          </div>
        );
      })}
    </div>
  );
}
