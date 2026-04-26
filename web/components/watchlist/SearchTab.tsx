"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

/**
 * 검색 탭 — MVP: ticker 직접 입력 → /analyze/{ticker}로 이동.
 * v1.1에서 종목명 자동완성 추가 예정 (v7.5에 search 엔드포인트 부재).
 */
export function SearchTab() {
  const router = useRouter();
  const [value, setValue] = useState("");

  const submit = () => {
    const v = value.trim();
    if (!v) return;
    // 6자리 숫자(KR) 또는 알파벳(US) 종목 코드만 허용
    if (!/^[A-Z0-9.]{1,10}$/i.test(v)) return;
    router.push(`/analyze/${v.toUpperCase()}`);
  };

  return (
    <Card>
      <CardContent className="p-5 space-y-3">
        <h3 className="font-semibold">🔎 종목 코드로 검색</h3>
        <p className="text-sm text-muted-foreground">
          KR: 6자리 숫자 (예: 207940) · US: 티커 (예: AAPL)
        </p>
        <div className="flex gap-2">
          <Input
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                submit();
              }
            }}
            placeholder="종목 코드 입력..."
            className="font-mono"
          />
          <Button type="button" onClick={submit} disabled={!value.trim()}>
            분석 →
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">
          💡 종목명 자동완성은 다음 버전에서 추가됩니다.
        </p>
      </CardContent>
    </Card>
  );
}
