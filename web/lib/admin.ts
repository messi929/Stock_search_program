/**
 * 관리자 콘솔 API 타입 + 페처 — 백엔드 /api/admin/* (모두 _is_admin 게이트).
 * apiCall이 Firebase ID 토큰을 자동 첨부한다(서버가 ADMIN_EMAILS로 권한 판정).
 */
import { apiCall } from "@/lib/api";

// ── 가입자(stats) ──
export interface AdminStats {
  total: number;
  pro: number;
  free: number;
  trial_active: number;
  suspicious: number;
  suspended: number;
}

// ── 수입 ──
export interface RevenueUpcoming {
  uid: string;
  email: string;
  plan: string;
  period_end: string | null;
  cancel_at_period_end: boolean;
}
export interface AdminRevenue {
  active_subscriptions: number;
  by_plan: { monthly: number; yearly: number };
  trial_active: number;
  cancel_scheduled: number;
  mrr_krw: number;
  arr_krw: number;
  upcoming_renewals: RevenueUpcoming[];
  prices: { monthly: number; yearly: number };
  estimated: boolean;
}

// ── 사용량 ──
export interface UsageUserRow {
  uid: string;
  email: string;
  krw: number;
  usd: number;
  analyses: number;
  validations: number;
  discoveries: number;
}
export interface AdminUsage {
  month: string;
  totals: {
    krw: number;
    usd: number;
    analyses: number;
    validations: number;
    discoveries: number;
    active_users: number;
  };
  by_agent: Record<string, number>;
  by_user: UsageUserRow[];
}

// ── 사용자 ──
export interface AdminUser {
  uid: string;
  email: string;
  tier: string;
  created_at: string | null;
  trial_started: boolean;
  trial_ends_at: string | null;
  suspended: boolean;
  suspicious: boolean;
  admin_note: string;
  subscription_status: string;
  subscription_plan: string;
  subscription_period_end: string | null;
  lemon_customer_id: string;
}
export interface AdminUsersResp {
  users: AdminUser[];
  count: number;
  filter: string;
}
export interface LoginEntry {
  ip: string;
  user_agent: string;
  timestamp: string;
}
export interface SessionEntry {
  session_id: string;
  ip: string;
  user_agent: string;
  last_seen: string;
}
export interface AdminUserDetail {
  user: AdminUser;
  login_history: LoginEntry[];
  active_sessions: SessionEntry[];
  unique_ips_30d: number;
}

// ── 에러 ──
export interface AdminErrorItem {
  id: string;
  type: string;
  message: string;
  uid: string;
  ticker: string;
  agent: string;
  context: Record<string, unknown>;
  created_at: string | null;
}
export interface AdminErrors {
  errors: AdminErrorItem[];
  count: number;
}
export interface AdminErrorsSummary {
  days: number;
  total: number;
  by_type: Record<string, number>;
  by_day: Record<string, number>;
}

// ── 페처 ──
export const adminApi = {
  stats: () => apiCall<AdminStats>("/api/admin/stats"),
  revenue: () => apiCall<AdminRevenue>("/api/admin/revenue"),
  usage: (month?: string) =>
    apiCall<AdminUsage>(`/api/admin/usage${month ? `?month=${month}` : ""}`),
  users: (filter = "") =>
    apiCall<AdminUsersResp>(`/api/admin/users${filter ? `?filter=${filter}` : ""}`),
  user: (uid: string) => apiCall<AdminUserDetail>(`/api/admin/users/${uid}`),
  errors: (params = "") => apiCall<AdminErrors>(`/api/admin/errors${params}`),
  errorsSummary: (days = 7) =>
    apiCall<AdminErrorsSummary>(`/api/admin/errors/summary?days=${days}`),
  suspend: (uid: string, reason: string) =>
    apiCall<{ ok: boolean }>(`/api/admin/users/${uid}/suspend`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    }),
  unsuspend: (uid: string) =>
    apiCall<{ ok: boolean }>(`/api/admin/users/${uid}/unsuspend`, {
      method: "POST",
      body: JSON.stringify({}),
    }),
  extendTrial: (uid: string, days: number) =>
    apiCall<{ ok: boolean }>(`/api/admin/users/${uid}/extend-trial`, {
      method: "POST",
      body: JSON.stringify({ days }),
    }),
  setNote: (uid: string, note: string) =>
    apiCall<{ ok: boolean }>(`/api/admin/users/${uid}/note`, {
      method: "POST",
      body: JSON.stringify({ note }),
    }),
};

// ── 포맷 헬퍼 ──
export const won = (n: number | null | undefined): string =>
  `₩${Math.round(n ?? 0).toLocaleString("ko-KR")}`;

export const fmtDate = (iso: string | null | undefined): string => {
  if (!iso) return "-";
  try {
    return new Date(iso).toLocaleString("ko-KR", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
};
