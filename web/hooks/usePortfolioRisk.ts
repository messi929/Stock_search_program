"use client";

/**
 * 포트폴리오 리스크 분석 — v7.5 POST /portfolio/risk.
 *
 * 입력: tickers[] (동등 비중) 또는 holdings[] (실제 평가금 비중).
 * 응답: 건강도/MDD/상관관계/섹터/추천 메시지.
 *
 * LEGAL: 응답의 recommendations는 백엔드에서 정의된 메시지로,
 *        screener LEGAL 검사를 통과한 중립 어휘만 포함된다는 전제.
 */
import { useMutation } from "@tanstack/react-query";

import { apiCall } from "@/lib/api";
import type {
  PortfolioRiskRequest,
  PortfolioRiskResponse,
} from "@/types/api";

export function usePortfolioRisk() {
  return useMutation({
    mutationFn: (body: PortfolioRiskRequest) =>
      apiCall<PortfolioRiskResponse>("/portfolio/risk", {
        method: "POST",
        body: JSON.stringify(body),
      }),
  });
}
