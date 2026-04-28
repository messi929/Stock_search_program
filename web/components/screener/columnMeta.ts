/**
 * v7.5 StockItem 컬럼 → Axis 라벨/포매터 매핑.
 *
 * LEGAL: buy_grade ("적극매수"/"매수") 같은 권유성 라벨은 score_tier 중립
 * ("상위"/"준상위"/"중간"/"관찰")로 변환. 신규 LEGAL 단어 추가 시 여기서 일괄 처리.
 */

export type Align = "left" | "right";

export interface ColumnMeta {
  label: string;
  align: Align;
  format: (value: unknown) => string;
  /**
   * 셀 텍스트에 적용할 색상 클래스 (옵션). 등락률·연속매수 등 부호별 색상.
   */
  colorize?: (value: unknown) => string | undefined;
}

const fmtInt = (v: unknown): string => {
  const n = Number(v);
  if (!Number.isFinite(n)) return "-";
  return n.toLocaleString("ko-KR");
};

const fmtDecimal = (digits: number) => (v: unknown): string => {
  const n = Number(v);
  if (!Number.isFinite(n)) return "-";
  return n.toFixed(digits);
};

const fmtPct = (v: unknown): string => {
  const n = Number(v);
  if (!Number.isFinite(n)) return "-";
  return `${n.toFixed(2)}%`;
};

const fmtSignedPct = (v: unknown): string => {
  const n = Number(v);
  if (!Number.isFinite(n)) return "-";
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(2)}%`;
};

const fmtCompactKR = (v: unknown): string => {
  const n = Number(v);
  if (!Number.isFinite(n) || n === 0) return "-";
  if (n >= 1e12) return `${(n / 1e12).toFixed(2)}조`;
  if (n >= 1e8) return `${(n / 1e8).toFixed(0)}억`;
  if (n >= 1e4) return `${(n / 1e4).toFixed(0)}만`;
  return n.toLocaleString("ko-KR");
};

const fmtBool01 = (v: unknown): string => (Number(v) > 0 ? "✓" : "-");

// LEGAL: buy_grade 변환 — score_tier 중립 라벨로
// v7.5 metrics.py:515-518에서 부여되는 정식 값: 적극매수 / 매수 / 관심 / 관망
const fmtBuyGradeNeutral = (v: unknown): string => {
  const s = String(v ?? "").trim();
  const map: Record<string, string> = {
    "적극매수": "상위",
    "매수": "준상위",
    "관심": "관찰",
    "관망": "보류",
    // 일부 경로에서 추가로 나타날 수 있는 값
    "중립": "중간",
    "관찰": "중간",
    "주의": "관찰",
    "부적합": "관찰",
  };
  // LEGAL: 알 수 없는 값은 "기타"로 — 권유성 단어가 그대로 흘러나가지 않도록
  return map[s] ?? (s ? "기타" : "-");
};

// LEGAL 최종 방어선: 어떤 컬럼이든 권유성 단어가 raw로 통과하면 중립화
const FORBIDDEN_GRADE_TOKENS = ["적극매수", "매수", "매도", "추천"];
const sanitizeGradeText = (s: string): string => {
  for (const t of FORBIDDEN_GRADE_TOKENS) {
    if (s.includes(t)) return "기타";
  }
  return s;
};

const colorBySign = (v: unknown): string | undefined => {
  const n = Number(v);
  if (!Number.isFinite(n) || n === 0) return undefined;
  return n > 0 ? "text-rose-500" : "text-blue-500";
};

const colorByGrade = (v: unknown): string | undefined => {
  const tier = fmtBuyGradeNeutral(v);
  if (tier === "상위") return "text-amber-500 font-semibold";
  if (tier === "준상위") return "text-amber-400";
  if (tier === "관찰" || tier === "보류") return "text-muted-foreground";
  return undefined;
};

const COLUMN_META: Record<string, ColumnMeta> = {
  // ── 가격/거래 ──
  close: { label: "현재가", align: "right", format: fmtInt },
  change_pct: { label: "등락률", align: "right", format: fmtSignedPct, colorize: colorBySign },
  volume: { label: "거래량", align: "right", format: fmtCompactKR },
  volume_ratio: { label: "거래량비", align: "right", format: fmtDecimal(2) },
  trading_value: { label: "거래대금", align: "right", format: fmtCompactKR },
  market_cap: { label: "시총", align: "right", format: fmtCompactKR },

  // ── 펀더멘털 ──
  per: { label: "PER", align: "right", format: fmtDecimal(2) },
  pbr: { label: "PBR", align: "right", format: fmtDecimal(2) },
  roe: { label: "ROE", align: "right", format: fmtPct },
  div_yield: { label: "배당률", align: "right", format: fmtPct },
  div_years: { label: "배당년수", align: "right", format: fmtInt },
  div_growth: { label: "배당성장", align: "right", format: fmtPct },
  forward_pe: { label: "Fwd PER", align: "right", format: fmtDecimal(2) },
  peg_ratio: { label: "PEG", align: "right", format: fmtDecimal(2) },
  ev_ebitda: { label: "EV/EBITDA", align: "right", format: fmtDecimal(2) },
  profit_margin: { label: "순이익률", align: "right", format: fmtPct },
  operating_margin: { label: "영업이익률", align: "right", format: fmtPct },
  fcf_yield: { label: "FCF Yield", align: "right", format: fmtPct },
  debt_equity: { label: "부채비율", align: "right", format: fmtDecimal(2) },
  revenue_growth: { label: "매출성장", align: "right", format: fmtPct },
  target_price: { label: "목표가(컨센)", align: "right", format: fmtInt },
  target_upside: { label: "상승여력(컨센)", align: "right", format: fmtSignedPct, colorize: colorBySign },

  // ── 기술적 ──
  ma5: { label: "MA5", align: "right", format: fmtInt },
  ma20: { label: "MA20", align: "right", format: fmtInt },
  ma60: { label: "MA60", align: "right", format: fmtInt },
  golden_cross: { label: "골든크로스(중)", align: "right", format: fmtBool01 },
  golden_cross_long: { label: "골든크로스(장)", align: "right", format: fmtBool01 },
  ma_aligned: { label: "MA 정배열", align: "right", format: fmtBool01 },
  rsi: { label: "RSI", align: "right", format: fmtDecimal(1) },
  vs_high_52w: { label: "52주高대비", align: "right", format: fmtSignedPct, colorize: colorBySign },
  vs_low_52w: { label: "52주低대비", align: "right", format: fmtSignedPct, colorize: colorBySign },

  // ── 모멘텀/매집 ──
  surge_score: { label: "급등점수", align: "right", format: fmtInt },
  pre_surge_score: { label: "선행점수", align: "right", format: fmtInt },
  volume_trend: { label: "거래량추세", align: "right", format: fmtInt },
  ma_squeeze: { label: "MA수렴", align: "right", format: fmtDecimal(2) },
  accumulation: { label: "매집", align: "right", format: fmtBool01 },
  breakout_score: { label: "돌파점수", align: "right", format: fmtInt },
  consecutive_gains: { label: "연속상승", align: "right", format: fmtInt },

  // ── 수급 ──
  foreign_net: { label: "외국인순매수", align: "right", format: fmtCompactKR, colorize: colorBySign },
  inst_net: { label: "기관순매수", align: "right", format: fmtCompactKR, colorize: colorBySign },
  foreign_consecutive: { label: "외국인연속", align: "right", format: fmtInt, colorize: colorBySign },
  supply_intensity: { label: "수급강도", align: "right", format: fmtDecimal(2) },
  supply_grade: {
    label: "수급등급",
    align: "left",
    format: (v) => sanitizeGradeText(String(v ?? "-")),
  },
  dual_buy: { label: "쌍끌이", align: "right", format: (v) => (v ? "✓" : "-") },

  // ── 종합 점수 ──
  buy_score: { label: "종합점수", align: "right", format: fmtDecimal(1) },
  // LEGAL: 권유성 라벨 → 중립 변환
  buy_grade: { label: "관찰등급", align: "left", format: fmtBuyGradeNeutral, colorize: colorByGrade },
  risk_grade: {
    label: "리스크",
    align: "left",
    format: (v) => sanitizeGradeText(String(v ?? "-")),
  },
  position_size: { label: "권장비중", align: "right", format: fmtPct },
  volatility_20d: { label: "변동성(20D)", align: "right", format: fmtPct },
  atr_14: { label: "ATR14", align: "right", format: fmtDecimal(2) },

  // ── 분류/메타 ──
  themes: { label: "테마", align: "left", format: (v) => String(v ?? "-") },
  sector: { label: "섹터", align: "left", format: (v) => String(v ?? "-") },
  industry: { label: "산업", align: "left", format: (v) => String(v ?? "-") },
  etf_category: { label: "ETF분류", align: "left", format: (v) => String(v ?? "-") },
  nav: { label: "NAV", align: "right", format: fmtDecimal(2) },
  earning_rate: { label: "수익률", align: "right", format: fmtSignedPct, colorize: colorBySign },
};

export function getColumnMeta(key: string): ColumnMeta {
  return (
    COLUMN_META[key] ?? {
      label: key,
      align: "left",
      format: (v) => (v == null ? "-" : String(v)),
    }
  );
}
