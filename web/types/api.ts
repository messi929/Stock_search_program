/**
 * Axis 백엔드 API 응답 타입 (Pydantic 스키마와 1:1 대응).
 *
 * 백엔드: agents/{research,analyst,validator,strategist,discoverer}.py
 */

// ─── Research ─────────────────────────────
export type NewsItem = {
  headline: string;
  source: string;
  published_at: string;
  impact: "positive" | "negative" | "neutral";
  relevance_score: number;
};

export type MacroContext = {
  fomc_next: string | null;
  key_risks: string[];
  key_opportunities: string[];
};

export type SectorStatus = {
  name: string;
  status: "강세" | "약세" | "횡보" | string;
  key_drivers: string[];
  rally_participation: string;
};

export type ResearchResult = {
  market_sentiment: "낙관적" | "신중" | "비관적" | string;
  relevant_news: NewsItem[];
  macro_context: MacroContext;
  sector_status: SectorStatus[];
  foreign_inst_flow: Record<string, unknown>;
  summary: string;
  timestamp: string;
};

// ─── Analyst ───────────────────────────────
export type TechnicalAnalysis = {
  current_price: number;
  ma_status: string;
  ma5: number;
  ma20: number;
  ma60: number;
  rsi: number;
  rsi_status: string;
  support_level: number | null;
  resistance_level: number | null;
  vs_high_52w: number;
  vs_low_52w: number;
  signal: string;
};

export type FundamentalAnalysis = {
  per: number;
  pbr: number;
  roe: number;
  div_yield: number;
  peer_avg_per: number | null;
  earnings_surprise: string | null;
  valuation_judgment: string;
};

export type BuyScoreInterpretation = {
  buy_score: number;
  score_tier: "상위" | "준상위" | "중간" | "관찰" | string;
  interpretation: string;
  contributing_factors: string[];
};

export type AnalystResult = {
  ticker: string;
  name: string;
  technical: TechnicalAnalysis;
  fundamental: FundamentalAnalysis;
  buy_score: BuyScoreInterpretation;
  peer_comparison: Array<Record<string, unknown>>;
  summary: string;
  timestamp: string;
};

// ─── Validator ─────────────────────────────
export type ValidationCheck = {
  item: string;
  claimed: number;
  verified: number | null;
  diff_pct: number | null;
  status: "OK" | "WARN" | "FAIL" | "ERROR";
  last_data_update: string | null;
  error: string | null;
};

export type ContrarianScenario = {
  title: string;
  description: string;
  impact_estimate: string;
  probability: "LOW" | "MEDIUM" | "HIGH";
  indicators_to_watch: string[];
};

export type ValidatorResult = {
  overall_status: "PASS" | "WARN" | "FAIL";
  checks: ValidationCheck[];
  stale_data_count: number;
  fresh_data_count: number;
  contrarian_scenarios: ContrarianScenario[];
  blind_spots: string[];
  confidence_score: number;
  requires_reanalysis: boolean;
  timestamp: string;
};

// ─── Strategist ────────────────────────────
export type EntryPoints = {
  tier_1: number;
  tier_2: number;
  tier_3: number;
  technical_basis: string[];
};

export type ExitPoints = {
  stop_loss: number;
  take_profit_1: number;
  take_profit_final: number;
};

export type AlertCondition = {
  condition_type: string;
  threshold: number;
  action: string;
};

import type { PersonaId } from "./persona";

export type StrategistResult = {
  persona_used: PersonaId | string;
  persona_perspective: string;
  summary: string;
  entry_points: EntryPoints | null;
  exit_points: ExitPoints | null;
  alert_conditions: AlertCondition[];
  user_principles_alignment: Record<string, string>;
  follow_up_questions: string[];
  confidence_note: string | null;
  disclaimer: string;
  timestamp: string;
};

// ─── /api/ai/analyze 응답 (non-stream) ──────
export type AnalyzeResponse = {
  ticker: string;
  persona: string;
  research: ResearchResult;
  analyst: AnalystResult;
  validator: ValidatorResult;
  strategist: StrategistResult;
  metadata: {
    total_elapsed: number;
    retry_count: number;
    validation_status: "PASS" | "WARN" | "FAIL";
  };
  disclaimer: string;
};

// ─── /api/ai/personas 응답 ─────────────────
export type Persona = {
  id: PersonaId;
  name: string;
  description: string;
  icon: string;
  available_to_free: boolean;
};

export type PersonasResponse = {
  personas: Persona[];
  user_plan: "free" | "pro" | "premium";
  user_default_persona: string;
};

// ─── /api/ai/discover 응답 ─────────────────
export type StockSuggestion = {
  ticker: string;
  name: string;
  market: string;
  sector: string;
  current_price: number;
  reason: string;
};

export type DiscoverResponse = {
  query: string;
  interpretation: string;
  stocks: StockSuggestion[];
  timestamp: string;
  elapsed_seconds: number;
};

// ─── /api/all-stocks (v7.5) ────────────────
// 종목명·티커 LIKE 검색 — 자동완성 용도
export type StockSearchHit = {
  ticker: string;
  name: string;
  close: number;
  market: string;
};

export type StockSearchResponse = {
  stocks: StockSearchHit[];
};

// ─── /api/screener/smart-lists ─────────────
export type SmartListCategory = {
  id: string;
  name: string;
  group: string;
  desc: string;
  icon: string;
  columns: string[];
  requires_phase: number;
  available_to_free: boolean;
};

export type SmartListsResponse = {
  categories: SmartListCategory[];
  user_plan: string;
  scan_endpoint: string;
};

// ─── /api/ai/screeners/custom ──────────────
// 백엔드 화이트리스트(api/routes/ai.py CUSTOM_FILTER_SCHEMA)와 1:1
export type CustomScreenerFilters = {
  market?: "ALL" | "KR" | "US" | string;
  per_min?: number;
  per_max?: number;
  pbr_min?: number;
  pbr_max?: number;
  div_yield_min?: number;
  roe_min?: number;
  roe_max?: number;
  market_cap_min?: number;
  market_cap_max?: number;
  volume_ratio_min?: number;
  trading_value_min?: number;
  change_pct_min?: number;
  change_pct_max?: number;
  rsi_min?: number;
  rsi_max?: number;
  golden_cross?: boolean;
  ma_aligned?: boolean;
};

export type CustomScreener = {
  id: string;
  name: string;
  filters: CustomScreenerFilters;
  sort_by: string;
  sort_asc: boolean;
  created_at: string | null;
  updated_at: string | null;
};

export type CustomScreenersResponse = {
  screeners: CustomScreener[];
};

// ─── /api/ai/notifications/preferences ─────
export type NotificationPreferences = {
  daily_briefing_enabled: boolean;
  entry_point_alerts_enabled: boolean;
  email_override: string | null;
};

export type NotificationPreferencesResponse = {
  preferences: NotificationPreferences;
  user_email: string | null;
};

// ─── /api/ai/usage ─────────────────────────
export type UsageMetric = { used: number; limit: number; remaining: number };

export type UsageResponse = {
  user_uid: string;
  plan: string;
  month: string;
  usage: {
    analyses: UsageMetric;
    validations: UsageMetric;
    discoveries: UsageMetric;
  };
  reset_at: string;
  upgrade_url: string;
};
