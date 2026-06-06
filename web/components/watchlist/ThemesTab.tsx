"use client";

import { Card, CardContent } from "@/components/ui/card";

const THEMES: Array<{ id: string; icon: string; label: string; query: string }> = [
  { id: "ai", icon: "🤖", label: "AI/반도체", query: "AI·반도체 메가트렌드 1차 또는 2차 수혜주" },
  { id: "battery", icon: "🔋", label: "2차전지", query: "2차전지 소재·셀 메이커 우량주" },
  { id: "bio", icon: "💊", label: "바이오", query: "바이오 신약 파이프라인·CDMO 글로벌 수혜주" },
  { id: "robot", icon: "🦾", label: "로봇/자동화", query: "산업용 로봇·협동로봇·자동화 수혜주" },
  { id: "energy", icon: "⚡", label: "원전/에너지", query: "원자력·재생에너지 발전 인프라 종목" },
  { id: "defense", icon: "🛡", label: "조선/방산", query: "K-방산·조선 글로벌 수주 수혜주" },
  { id: "kfood", icon: "🍜", label: "K-푸드", query: "K-푸드 해외 수출·브랜드력 보유 종목" },
  { id: "finance", icon: "🏦", label: "금융", query: "은행·보험·증권 배당 + 밸류업 수혜주" },
  { id: "reit", icon: "🏢", label: "리츠/부동산", query: "리츠·부동산 임대수익 안정 배당주" },
];

interface Props {
  onSelect: (label: string, query: string) => void;
  /** 부모가 전달하는 진행 중 상태 — 다중 클릭 차단 */
  isPending?: boolean;
}

/**
 * 큐레이션 테마 그리드 — 클릭 시 부모가 종목 발견(/discover?q=)으로 런치.
 * 자체 useDiscover()를 가지지 않음. 부모에서 debounce 처리.
 */
export function ThemesTab({ onSelect, isPending = false }: Props) {
  return (
    <Card>
      <CardContent className="p-5 space-y-3">
        <h3 className="font-semibold">🎯 큐레이션 테마</h3>
        <p className="text-sm text-muted-foreground">
          클릭 시 종목 발견에서 자동으로 검색됩니다.
        </p>
        <div className="grid grid-cols-3 gap-2">
          {THEMES.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => onSelect(t.label, t.query)}
              disabled={isPending}
              className="p-3 rounded-md border border-border text-sm hover:bg-muted text-center disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <div className="text-2xl mb-1">{t.icon}</div>
              <div>{t.label}</div>
            </button>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
