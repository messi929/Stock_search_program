"use client";

import { Card, CardContent } from "@/components/ui/card";
import { useStatus } from "@/hooks/useStatus";

function formatRelative(iso: string): string {
  try {
    const t = new Date(iso).getTime();
    const diff = Date.now() - t;
    const min = Math.floor(diff / 60_000);
    if (min < 1) return "방금 전";
    if (min < 60) return `${min}분 전`;
    const hr = Math.floor(min / 60);
    if (hr < 24) return `${hr}시간 전`;
    return `${Math.floor(hr / 24)}일 전`;
  } catch {
    return "—";
  }
}

export function MarketStatus() {
  const { data, isLoading, isError } = useStatus();

  if (isLoading) {
    return (
      <Card>
        <CardContent className="p-4 text-sm text-muted-foreground">
          데이터 상태 조회 중...
        </CardContent>
      </Card>
    );
  }

  if (isError || !data) {
    return (
      <Card>
        <CardContent className="p-4 text-sm text-muted-foreground">
          ⚠️ 백엔드 상태 조회 실패. (axis-staging 응답 없음)
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardContent className="p-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div>
            <p className="text-muted-foreground">상태</p>
            <p className="font-medium">
              {data.status === "ready" ? "✅ 준비 완료" : `⏳ ${data.status}`}
            </p>
          </div>
          <div>
            <p className="text-muted-foreground">KR 종목</p>
            <p className="font-medium">{data.total_stocks.toLocaleString()}건</p>
          </div>
          <div>
            <p className="text-muted-foreground">테마</p>
            <p className="font-medium">{data.total_themes}개</p>
          </div>
          <div>
            <p className="text-muted-foreground">데이터 갱신</p>
            <p className="font-medium" title={data.last_update}>
              {formatRelative(data.last_update)}
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
