"use client";

import { StockSearch } from "@/components/stocks/StockSearch";
import { Card, CardContent } from "@/components/ui/card";

/** 카드형 종목 검색 — 분석 시작 화면과 관심 종목 추가 화면에서 사용. */
export function SearchTab() {
  return (
    // overflow-visible: 기본 Card는 overflow-hidden이라 absolute 드롭다운이 잘림.
    <Card className="overflow-visible">
      <CardContent className="space-y-2 p-5">
        <StockSearch size="lg" placeholder="예: 삼성전자, 005930, AAPL" />
        <p className="text-xs text-muted-foreground">
          목록에 없으면 6자리 종목코드나 미국 티커를 입력한 뒤 Enter를 눌러주세요.
        </p>
      </CardContent>
    </Card>
  );
}
