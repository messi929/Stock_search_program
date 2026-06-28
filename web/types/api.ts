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
  /** 거래소 — KOSPI / KOSDAQ / NASDAQ / NYSE 등 (백엔드 _fetch_stock_data가 제공). */
  market?: string;
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

import type { HorizonId, PersonaId } from "./persona";

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

// ─── 데이터 페르소나 (event/macro/korean) ──────
//
// 백엔드 agents/event_analyst.py / macro_pm.py / korean_specialist.py
// Pydantic 모델과 1:1 일치. 신규 필드 추가 시 백엔드도 동기 갱신 필요.

// Event Analyst
export type CertaintyBreakdown = {
  source: number;
  source_rationale?: string;
  timing: number;
  timing_rationale?: string;
  probability: number;
  probability_rationale?: string;
  impact: number;
  impact_rationale?: string;
  final_score: number;
  mode: "Full Analysis" | "Cautious" | "Probabilistic Only" | "Refused" | string;
};

export type EventSummary = {
  event_type: string;
  event_target: string;
  d_day?: string;
  certainty_breakdown: CertaintyBreakdown;
  badge: string;
};

export type ImpactMapping = {
  direct_beneficiary?: { ticker?: string; rationale?: string };
  secondary_beneficiaries?: Array<{ ticker?: string; rationale?: string }>;
  tertiary_beneficiaries?: Array<{ ticker?: string; rationale?: string }>;
};

export type SignalBlock = {
  available: boolean;
  interpretation?: string;
  key_observations?: string[];
};

export type HistoricalStatistics = {
  comparable_events_count: number;
  sample_reliability: string;
  comparable_events: Array<Record<string, unknown>>;
  fabrication_warning: string;
};

export type ReferenceZones = {
  current_position_vs_history?: string;
  historical_volatility_lower_1sigma?: string;
  historical_volatility_upper_1sigma?: string;
  note?: string;
};

export type ScenarioCase = {
  trigger: string;
  historical_pattern: string;
  probability: string;
};

export type ScenarioAnalysis = {
  bullish_case: ScenarioCase;
  base_case: ScenarioCase;
  bearish_case: ScenarioCase;
};

export type TopHolder = {
  holder: string;
  pct_held?: number | null;
  shares?: number | null;
  value?: number | null;
  date_reported?: string | null;
  pct_change?: number | null;
};

// 미국 종목 기관 보유 스냅샷 (정보 제공용 — 신호/점수 아님, 분기 13F 스냅샷)
export type InstitutionalOwnership = {
  available: boolean;
  institutions_pct?: number | null;
  insiders_pct?: number | null;
  institutions_float_pct?: number | null;
  institutions_count?: number | null;
  top_holders: TopHolder[];
  as_of?: string | null;
  data_source?: string;
  note?: string;
};

export type EventAnalystResult = {
  ticker: string;
  market: "KR" | "US" | string;
  event_summary: EventSummary;
  impact_mapping: ImpactMapping;
  volume_supply_analysis: SignalBlock;
  options_signals: SignalBlock;
  credit_short_signals: SignalBlock;
  historical_statistics: HistoricalStatistics;
  reference_observation_zones: ReferenceZones;
  scenario_analysis: ScenarioAnalysis;
  key_risks: string[];
  what_to_watch: string[];
  institutional_ownership?: InstitutionalOwnership | null;
  summary_neutral: string;
  persona: "event";
  timestamp: string;
};

// Macro PM
export type CycleStage = {
  stage: string;
  key_indicators?: Record<string, unknown>;
  rationale?: string;
};

export type CycleAnalysis = {
  interest_rate: CycleStage;
  business_cycle: CycleStage;
  currency_cycle: CycleStage;
  inflation_cycle: CycleStage;
};

export type MacroRegime = {
  current_regime: string;
  transition_to: string | null;
  regime_confidence: number;
};

export type WeightingUsed = {
  us_weight: number;
  kr_weight: number;
  rationale: string;
};

export type StockMacroAlignment = {
  ticker?: string;
  sector?: string;
  macro_alignment: string;
  alignment_score: number;
  interpretation?: string;
};

export type TransitionSignal = {
  signal: string;
  current?: string;
  trigger_level?: string;
  implication?: string;
};

export type MacroPmResult = {
  macro_regime: MacroRegime;
  cycle_analysis: CycleAnalysis;
  regime_implications: Record<string, unknown>;
  transition_signals_to_monitor: TransitionSignal[];
  stock_specific_analysis?: StockMacroAlignment | null;
  weighting_used: WeightingUsed;
  summary_neutral: string;
  persona: "macro";
  timestamp: string;
};

// Korean Specialist
export type KoreaSpecificScore = {
  foreign_supply: number;
  governance: number;
  valueup_alignment: number;
  theme_position: number;
  policy_friendliness: number;
  weighted_total: number;
  interpretation?: string;
};

export type KoreanSpecialistResult = {
  korea_specific_analysis: Record<string, unknown>;
  foreign_supply_analysis: Record<string, unknown>;
  chaebol_structure_analysis: Record<string, unknown>;
  value_up_analysis: Record<string, unknown>;
  theme_cycle_analysis: Record<string, unknown>;
  policy_risk_analysis: Record<string, unknown>;
  korea_specific_score: KoreaSpecificScore;
  what_to_watch_korea_specific: string[];
  summary_neutral: string;
  persona: "korean";
  timestamp: string;
};

// ─── /api/ai/analyze 응답 (non-stream) ──────
//
// 페르소나 그룹별 nullable:
//   - strategist 흐름(blackrock/ark/graham): research/analyst/validator/strategist 채워짐, event/macro/korean=null
//   - 데이터 페르소나(event/macro/korean): 해당 1개만 채워짐, 나머지=null
export type AnalyzeResponse = {
  ticker: string;
  persona: string;
  research: ResearchResult | null;
  analyst: AnalystResult | null;
  validator: ValidatorResult | null;
  strategist: StrategistResult | null;
  event: EventAnalystResult | null;
  macro: MacroPmResult | null;
  korean: KoreanSpecialistResult | null;
  metadata: {
    total_elapsed: number;
    retry_count: number;
    validation_status: "PASS" | "WARN" | "FAIL" | null;
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

/** 시간 시계(Horizon) — 신규 1차 축. 페르소나와 같은 구조. */
export type Horizon = {
  id: HorizonId;
  name: string;
  description: string;
  icon: string;
  available_to_free: boolean;
};

export type PersonasResponse = {
  personas: Persona[];
  user_plan: "free" | "pro";
  user_default_persona: string;
  /** 4개 시간 시계 (단기/단중기/중기/장기). */
  horizons: Horizon[];
  /** 기본 시계 — 보통 "mid". */
  user_default_horizon: string;
};

// ─── /api/ai/discover 응답 ─────────────────
export type StockSuggestion = {
  ticker: string;
  name: string;
  market: string;
  sector: string;
  current_price: number;
  reason: string;
  // 결과 풍부화 (백엔드 결정론 주입)
  buy_score?: number;
  per?: number;
  pbr?: number;
  roe?: number;
  div_yield?: number;
  vs_high_52w?: number;
  foreign_consecutive?: number;
  themes?: string;
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
  stock_type?: string; // "etf"면 /etf/ 상세로 라우팅
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

// ─── /api/ai/history (사용량 항목별 분석 이력) ─────
export type HistoryKind = "analysis" | "validation" | "discovery";

export type HistoryItem = {
  kind: HistoryKind;
  ticker: string;
  name: string; // 종목명 (백엔드 snapshot 조인)
  persona: string;
  query: string;
  summary: string; // 그 시점 분석 결과 요약 (strategist.summary 또는 summary_neutral)
  price: number | null; // 당시 현재가
  at: string; // ISO8601
};

export type HistoryResponse = { items: HistoryItem[] };

// ─── /api/subscription (Lemon Squeezy) ─────
export type Subscription = {
  plan: string; // "monthly" | "yearly" | "admin"
  status: string; // "active" | "on_trial" | "cancelled" | "expired" 등
  current_period_end: string | null; // ISO8601
  cancel_at_period_end: boolean;
};

export type SubscriptionResponse = {
  tier: string; // "free" | "pro"
  subscription: Subscription | null;
  trial_eligible?: boolean; // 무료 트라이얼 가능 여부(과거 구독/트라이얼 이력 없을 때만)
};

export type CheckoutResponse = { url: string };

// ─── /portfolio/risk (v7.5) ────────────────
export type PortfolioHolding = {
  ticker: string;
  buy_price?: number;
  qty?: number;
};

export type PortfolioRiskRequest = {
  tickers?: string[];
  holdings?: PortfolioHolding[];
};

export type PortfolioPosition = {
  ticker: string;
  name: string;
  sector: string;
  weight_pct: number;
};

export type PortfolioRecommendation = {
  level: "success" | "info" | "warning" | string;
  msg: string;
};

export type PortfolioRiskResponse = {
  tickers: string[];
  positions: PortfolioPosition[];
  correlation_matrix: number[][];
  portfolio_volatility: number;
  annualized_return: number;
  sharpe_ratio: number;
  max_drawdown: number;
  health_score: number;
  health_grade: string;
  avg_correlation: number;
  top_weight_ticker: string;
  top_weight_name: string;
  top_weight_pct: number;
  sector_concentration: Record<string, number>;
  market_split: Record<string, number>;
  recommendations?: PortfolioRecommendation[];
  risk_warning?: string;
  error?: string;
};
