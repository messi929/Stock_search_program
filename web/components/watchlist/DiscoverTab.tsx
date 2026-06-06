"use client";

/**
 * 관심 종목 추가 페이지의 'AI 발견' 탭 — 고도화된 DiscoverView 재사용(중복 제거).
 * 테마 탭에서 넘어오는 externalQuery를 그대로 전달.
 */
import { DiscoverView } from "@/components/discover/DiscoverView";

interface DiscoverTabProps {
  externalQuery?: { query: string; nonce: number } | null;
}

export function DiscoverTab({ externalQuery = null }: DiscoverTabProps = {}) {
  return <DiscoverView externalQuery={externalQuery} />;
}
