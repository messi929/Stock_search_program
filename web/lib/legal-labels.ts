/**
 * 스크리너 카테고리 — Axis-side 권유성 단어 중립화.
 *
 * 배경:
 *   v7.5 백엔드(screener/core/screener.py)는 "성장주 매수", "종합 추천" 등
 *   권유성 라벨을 그대로 노출. Axis는 LEGAL.md 원칙상 "추천/매수" 단어 사용 금지.
 *
 * 정책:
 *   - 백엔드 코드는 건드리지 않음 (v7.5 main 브랜치 호환 유지)
 *   - Axis 프론트에서만 표시 직전에 변환
 *   - 매핑 누락된 카테고리는 원문 그대로 통과 (안전한 기본값)
 */

import type { SmartListCategory } from "@/types/api";

interface SafeLabel {
  name: string;
  desc?: string;
}

const LEGAL_SAFE_LABELS: Record<string, SafeLabel> = {
  surge: {
    name: "급등 관찰",
    desc: "급등 가능성이 포착된 종목 (참고용)",
  },
  growth: {
    name: "성장 관찰",
    desc: "수익성 + 적정 가격의 장기 성장 후보",
  },
  value: {
    name: "저평가 관찰",
    desc: "실적 대비 저평가 후보, 가격 회복 시 회복 여지",
  },
  dividend: {
    name: "고배당 관찰",
    desc: "꾸준히 배당을 지급하는 안정 수익형 종목",
  },
  turnaround: {
    name: "반등 관찰",
    desc: "바닥권에서 거래가 살아나며 반등 신호가 보이는 종목",
  },
  recommend: {
    name: "종합 점수 상위",
    desc: "기술·모멘텀·수급·가치 종합 30점 이상 (참고용, 판단은 본인 책임)",
  },
};

export function toSafeCategory(c: SmartListCategory): SmartListCategory {
  const override = LEGAL_SAFE_LABELS[c.id];
  if (!override) return c;
  return {
    ...c,
    name: override.name,
    desc: override.desc ?? c.desc,
  };
}

export function toSafeName(id: string, fallback: string): string {
  return LEGAL_SAFE_LABELS[id]?.name ?? fallback;
}
