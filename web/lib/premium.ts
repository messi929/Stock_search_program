/**
 * 네이버 프리미엄콘텐츠 발행 워크스페이스 API 클라이언트.
 *
 * 2026-08-09 신설. 근거: docs/axis/NAVER_PREMIUM.md
 *
 * ⚠️ 스레드(lib/marketing.ts)와 **완전히 별개 트랙**이다. 타입을 공유하지 않는다 —
 *    전제가 하나도 안 겹친다(500자 타래 vs 1만자 단일 장문, 반말 vs 존댓말,
 *    API 자동발행 vs 수동 복붙).
 *
 * ⚠️ `markPublished`는 발행하지 않는다. 프리미엄콘텐츠는 발행 API가 없어서 사람이
 *    스튜디오에 붙여넣은 뒤 **그 사실과 URL을 기록**하는 것뿐이다.
 */

import { apiCall } from "@/lib/api";

export type PremiumStatus = "draft" | "approved" | "published" | "archived";

export interface PremiumDraft {
  id: string;
  kind: string;
  title: string;
  body: string; // 목록에서는 400자로 잘려 온다. 전문은 detail()
  char_count: number;
  section_count: number;
  week_label: string;
  period_start: string;
  period_end: string;
  facts: string; // 수치 대조용 원본 — 목록에서는 빈 문자열
  warnings: string[];
  filtered: string[];
  status: PremiumStatus;
  published_url: string;
  published_at: string | null;
  source: string;
  created_at: string | null;
  updated_at: string | null;
}

export interface PremiumKind {
  key: string;
  label: string;
  desc: string;
  ready: boolean;
}

export interface PremiumMeta {
  kinds: PremiumKind[];
  min_chars: number;
  target_chars: number;
  max_chars: number;
  studio_url: string;
  manual_publish: boolean;
}

export const premiumApi = {
  meta: () => apiCall<PremiumMeta>("/api/admin/premium/meta"),

  drafts: (status = "") =>
    apiCall<{ drafts: PremiumDraft[]; count: number }>(
      `/api/admin/premium/drafts${status ? `?status=${status}` : ""}`,
    ),

  /** 전문 + facts. 복사·검수는 이걸로 한다. */
  detail: (id: string) =>
    apiCall<{ draft: PremiumDraft }>(`/api/admin/premium/drafts/${id}`),

  /** 데이터 부족 시 서버가 422로 거부한다(헛글 방지). */
  generate: (kind = "weekly", end?: string) =>
    apiCall<{ ok: boolean; draft: PremiumDraft }>(
      "/api/admin/premium/generate",
      { method: "POST", body: JSON.stringify({ kind, end }) },
    ),

  update: (
    id: string,
    patch: { title?: string; body?: string; status?: PremiumStatus },
  ) =>
    apiCall<{ ok: boolean; draft: PremiumDraft }>(
      `/api/admin/premium/drafts/${id}`,
      { method: "PATCH", body: JSON.stringify(patch) },
    ),

  /** 발행 '기록'. 스튜디오에서 실제 발행한 뒤 그 URL을 남긴다. */
  markPublished: (id: string, url: string) =>
    apiCall<{ ok: boolean; draft: PremiumDraft }>(
      `/api/admin/premium/drafts/${id}/publish`,
      { method: "POST", body: JSON.stringify({ url }) },
    ),

  remove: (id: string) =>
    apiCall<{ ok: boolean }>(`/api/admin/premium/drafts/${id}`, {
      method: "DELETE",
    }),
};
