/**
 * 마케팅 콘텐츠 공장 API 타입 + 페처 — 백엔드 /api/admin/marketing/* (모두 _is_admin 게이트).
 * 스레드(Threads)용 종목 글 초안을 생성/검수/수정한다. (Phase 1: 생성+검수+복사)
 */
import { apiCall } from "@/lib/api";

export type DraftStatus = "draft" | "approved" | "archived" | "published";

export interface MarketingDraft {
  id: string;
  kind: "stock" | "briefing";
  ticker: string;
  name: string;
  market: string;
  is_kr: boolean;
  fmt: string;
  fmt_label: string;
  text: string;
  char_count: number;
  status: DraftStatus;
  filtered: string[];
  source: string;
  permalink: string;
  published_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface MarketingFormat {
  key: string;
  label: string;
}

export interface MarketingFormatsResp {
  formats: MarketingFormat[];
  default: string[];
  max_chars: number;
}

export interface GenerateReq {
  tickers?: string[];
  formats?: string[];
  hot_count?: number;
}

export const marketingApi = {
  formats: () => apiCall<MarketingFormatsResp>("/api/admin/marketing/formats"),
  drafts: (status = "") =>
    apiCall<{ drafts: MarketingDraft[]; count: number }>(
      `/api/admin/marketing/drafts${status ? `?status=${status}` : ""}`,
    ),
  generate: (req: GenerateReq) =>
    apiCall<{ created: MarketingDraft[]; count: number }>(
      "/api/admin/marketing/generate",
      { method: "POST", body: JSON.stringify(req) },
    ),
  generateBriefing: () =>
    apiCall<{ created: MarketingDraft[]; count: number }>(
      "/api/admin/marketing/briefing/generate",
      { method: "POST" },
    ),
  update: (id: string, patch: { text?: string; status?: DraftStatus }) =>
    apiCall<{ ok: boolean; draft: MarketingDraft }>(
      `/api/admin/marketing/drafts/${id}`,
      { method: "PATCH", body: JSON.stringify(patch) },
    ),
  remove: (id: string) =>
    apiCall<{ ok: boolean }>(`/api/admin/marketing/drafts/${id}`, {
      method: "DELETE",
    }),
  publishStatus: () =>
    apiCall<{ enabled: boolean }>("/api/admin/marketing/publish-status"),
  publish: (id: string) =>
    apiCall<{ ok: boolean; draft: MarketingDraft }>(
      `/api/admin/marketing/drafts/${id}/publish`,
      { method: "POST" },
    ),
};
