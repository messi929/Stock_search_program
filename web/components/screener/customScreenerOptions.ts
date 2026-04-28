/**
 * 커스텀 스크리너 옵션 — sort_by 화이트리스트 (백엔드 ALLOWED_SORT_KEYS와 일치).
 */

export const ALLOWED_SORT_OPTIONS = [
  { value: "buy_score", label: "종합점수" },
  { value: "change_pct", label: "등락률" },
  { value: "volume_ratio", label: "거래량비" },
  { value: "rsi", label: "RSI" },
  { value: "per", label: "PER" },
  { value: "pbr", label: "PBR" },
  { value: "roe", label: "ROE" },
  { value: "market_cap", label: "시총" },
  { value: "div_yield", label: "배당률" },
  { value: "vs_high_52w", label: "52주高 대비" },
  { value: "trading_value", label: "거래대금" },
] as const;

export type SortKey = (typeof ALLOWED_SORT_OPTIONS)[number]["value"];

export const DEFAULT_RESULT_COLUMNS = [
  "per",
  "pbr",
  "roe",
  "rsi",
  "change_pct",
  "volume_ratio",
  "market_cap",
];
