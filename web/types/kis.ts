/**
 * KIS (한국투자증권 OpenAPI) 응답 타입.
 *
 * 백엔드: api/routes/kis.py
 * KIS 원본 응답은 모든 필드가 string. 프론트에서 표시 시 number 파싱 필요.
 */

// ─── 현재가 ─────────────────────────────────
export type KisPriceData = {
  stck_prpr: string;        // 현재가
  prdy_vrss: string;        // 전일 대비 (음수도 string)
  prdy_ctrt: string;        // 등락률 (%)
  prdy_vrss_sign?: string;  // 1상한 2상승 3보합 4하한 5하락
  acml_vol: string;         // 누적 거래량
  acml_tr_pbmn?: string;    // 누적 거래대금
  stck_oprc: string;        // 시가
  stck_hgpr: string;        // 고가
  stck_lwpr: string;        // 저가
  stck_mxpr?: string;       // 상한가
  stck_llam?: string;       // 하한가
  hts_kor_isnm?: string;    // 종목명 한글
  bstp_kor_isnm?: string;   // 업종명
  per?: string;
  pbr?: string;
  eps?: string;
  bps?: string;
  [k: string]: string | undefined;
};

export type KisPriceResponse = {
  ticker: string;
  data: KisPriceData;
  source: "kis";
};

// ─── 차트 (일/주/월/년/분봉 공통 — 필드 일부 다름) ─────
export type KisDailyBar = {
  stck_bsop_date: string;   // YYYYMMDD
  stck_clpr: string;        // 종가
  stck_oprc: string;        // 시가
  stck_hgpr: string;        // 고가
  stck_lwpr: string;        // 저가
  acml_vol: string;         // 거래량
  acml_tr_pbmn?: string;    // 거래대금
  prdy_vrss?: string;
  prdy_ctrt?: string;
  [k: string]: string | undefined;
};

export type KisMinuteBar = {
  stck_bsop_date: string;   // YYYYMMDD
  stck_cntg_hour: string;   // 체결시각 HHMMSS
  stck_prpr: string;        // 현재가 (분봉 종가)
  stck_oprc: string;
  stck_hgpr: string;
  stck_lwpr: string;
  cntg_vol: string;         // 체결량
  acml_tr_pbmn?: string;
  [k: string]: string | undefined;
};

export type KisChartResponse = {
  ticker: string;
  period?: "D" | "W" | "M" | "Y";
  bars: KisDailyBar[] | KisMinuteBar[];
  source: "kis";
};

// ─── 10호가 ─────────────────────────────────
export type KisOrderbookFrame = {
  aspr_acpt_hour?: string;          // 호가접수시각
  // askp1~10, bidp1~10, askp_rsqn1~10, bidp_rsqn1~10
  total_askp_rsqn?: string;
  total_bidp_rsqn?: string;
  [k: string]: string | undefined;
};

export type KisExpectedFrame = {
  antc_cnpr?: string;       // 예상체결가
  antc_cntg_vrss?: string;  // 예상체결 전일대비
  antc_vol?: string;        // 예상체결 거래량
  [k: string]: string | undefined;
};

export type KisOrderbookResponse = {
  ticker: string;
  orderbook: KisOrderbookFrame;
  expected: KisExpectedFrame;
  source: "kis";
};

// ─── 투자자별 매매동향 ───────────────────
export type KisInvestorRow = {
  stck_bsop_date: string;
  stck_clpr?: string;
  prsn_ntby_qty: string;    // 개인 순매수
  frgn_ntby_qty: string;    // 외국인 순매수
  orgn_ntby_qty: string;    // 기관 순매수
  [k: string]: string | undefined;
};

export type KisInvestorResponse = {
  ticker: string;
  trend: KisInvestorRow[];
  source: "kis";
};

// ─── 헬스 ───────────────────────────────
export type KisHealthResponse = {
  ok: boolean;
  env?: "real" | "paper";
  app_key_prefix?: string;
  token_in_memory?: boolean;
  stats?: string;
  cache_size?: number;
  reason?: string;
};
