/**
 * 마케팅 콘텐츠 공장 API 타입 + 페처 — 백엔드 /api/admin/marketing/* (모두 _is_admin 게이트).
 * 스레드(Threads)용 종목 글 초안을 생성/검수/수정한다. (Phase 1: 생성+검수+복사)
 */
import { apiCall } from "@/lib/api";

export type DraftStatus = "draft" | "approved" | "archived" | "published";

export interface MarketingDraft {
  id: string;
  kind: "stock" | "briefing" | "index" | "education";
  index_key?: string; // 지수 차트 글의 지수 식별자 (KS11 등)
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
  warnings: string[]; // 독자시점/길이 가드 경고 (하네스 v2)
  score: number; // 편집 자가채점 0~30 (하네스 v2)
  angle: string; // 글의 핵심 긴장 (하네스 v2)
  archetype: string; // 앵글 유형 (다양화 point 2)
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

export interface IndexChoice {
  key: string;
  name: string;
  is_kr: boolean;
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
  generateWeekendBriefing: () =>
    apiCall<{ created: MarketingDraft[]; count: number }>(
      "/api/admin/marketing/weekend-briefing/generate",
      { method: "POST" },
    ),
  indices: () =>
    apiCall<{ indices: IndexChoice[] }>(
      "/api/admin/marketing/index-chart/indices",
    ),
  generateIndexChart: (keys: string[]) =>
    apiCall<{ created: MarketingDraft[]; count: number }>(
      "/api/admin/marketing/index-chart/generate",
      { method: "POST", body: JSON.stringify({ keys }) },
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
