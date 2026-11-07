/**
 * 투자 용어 쉬운 풀이 — 화면의 <Term>이 사용한다.
 * LEGAL: 값의 높고 낮음을 좋다/나쁘다로 단정하지 말고, 무엇을 뜻하는지만 설명한다.
 */
export interface GlossaryEntry {
  label: string;
  plain: string;
  tip?: string;
}

const entries = {
  per: {
    label: "PER",
    plain: "주가가 1주당 1년 순이익의 몇 배인지 나타내요.",
    tip: "업종마다 평균이 달라서 같은 업종끼리 비교합니다.",
  },
  pbr: {
    label: "PBR",
    plain: "주가가 1주당 순자산의 몇 배인지 나타내요.",
    tip: "1배는 시가총액과 장부상 순자산이 같다는 뜻이에요.",
  },
  roe: {
    label: "ROE",
    plain: "회사가 자기 자본으로 1년에 얼마나 이익을 냈는지 나타내요.",
  },
  rsi: {
    label: "RSI",
    plain: "최근 상승과 하락의 힘을 0~100으로 나타낸 지표예요.",
    tip: "보통 70 이상은 과열, 30 이하는 침체 구간으로 해석합니다.",
  },
  div_yield: {
    label: "배당수익률",
    plain: "현재 주가 대비 1년 배당금의 비율이에요.",
  },
  market_cap: {
    label: "시가총액",
    plain: "주가에 전체 주식 수를 곱한 값으로, 회사의 시장 평가 규모예요.",
  },
  vs_high_52w: {
    label: "52주 고점 대비",
    plain: "최근 1년 최고가에서 현재가가 얼마나 떨어져 있는지 나타내요.",
  },
  vs_low_52w: {
    label: "52주 저점 대비",
    plain: "최근 1년 최저가에서 현재가가 얼마나 올라와 있는지 나타내요.",
  },
  foreign_consecutive: {
    label: "외국인 연속 순매수",
    plain: "외국인이 산 금액이 판 금액보다 많은 날이 며칠 이어졌는지 나타내요.",
  },
  supply: {
    label: "수급",
    plain: "외국인·기관·개인 중 누가 사고 누가 팔았는지를 보여주는 흐름이에요.",
  },
  advance_ratio: {
    label: "상승 종목 비율",
    plain: "오늘 시장 전체 종목 중 주가가 오른 종목의 비율이에요.",
  },
  above_ma20: {
    label: "20일선 위 종목",
    plain: "현재가가 최근 20거래일 평균 가격보다 높은 종목의 비율이에요.",
  },
  observation_zone: {
    label: "관찰 구간",
    plain: "데이터로 계산한 참고 가격대예요. 앞으로의 가격을 예측한 값은 아닙니다.",
  },
  validation: {
    label: "실시간 검증",
    plain: "AI 답변에 쓰인 수치를 지금 시점 데이터와 다시 대조해 차이를 알려줘요.",
  },
};

export type GlossaryId = keyof typeof entries;

export const GLOSSARY: Record<GlossaryId, GlossaryEntry> = entries;

/** 스크리너 표 컬럼 키 → 용어 */
export const COLUMN_TERMS: Record<string, GlossaryId> = {
  per: "per",
  pbr: "pbr",
  roe: "roe",
  rsi: "rsi",
  div_yield: "div_yield",
  market_cap: "market_cap",
  vs_high_52w: "vs_high_52w",
  vs_low_52w: "vs_low_52w",
  foreign_consecutive: "foreign_consecutive",
};
