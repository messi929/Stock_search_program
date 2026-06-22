/**
 * 6 페르소나 메타데이터 — 페이지 / 카드 / 탭에서 공유.
 *
 * 기존 3개(blackrock/ark/graham)에 신규 3개(event/macro/korean) 추가.
 * Strategist 흐름 vs Data-driven 흐름 구분도 여기서 노출.
 */

export type PersonaId =
  | "blackrock"
  | "ark"
  | "graham"
  | "event"
  | "macro"
  | "korean";

export type PersonaGroup = "strategist" | "data_driven";

export type PersonaMeta = {
  id: PersonaId;
  icon: string;
  name: string;
  tagline: string;
  group: PersonaGroup;
  /** 시간 시계: 단기/중기/장기 */
  time_horizon: "short" | "medium" | "long";
  /** Tailwind color tag (text-{color}-600 / bg-{color}-50 등) */
  accent: "slate" | "violet" | "emerald" | "amber" | "sky" | "rose";
};

export const PERSONA_META: readonly PersonaMeta[] = [
  {
    // 내부 매핑: 블랙록 스타일 (시스템프롬프트 personas/blackrock.md). UI는 원칙명만 노출.
    id: "blackrock",
    icon: "🏛",
    name: "안정·리스크관리",
    tagline: "리스크 우선, 장기 가치",
    group: "strategist",
    time_horizon: "long",
    accent: "slate",
  },
  {
    // 내부 매핑: ARK 스타일 (personas/ark.md)
    id: "ark",
    icon: "🚀",
    name: "고성장·혁신",
    tagline: "파괴적 혁신, 5년 시계",
    group: "strategist",
    time_horizon: "long",
    accent: "violet",
  },
  {
    // 내부 매핑: 그레이엄 스타일 (personas/graham.md)
    id: "graham",
    icon: "📚",
    name: "가치·저평가",
    tagline: "안전마진, 저평가",
    group: "strategist",
    time_horizon: "long",
    accent: "emerald",
  },
  {
    id: "event",
    icon: "⚡",
    name: "이벤트",
    tagline: "실적·M&A·IPO 통계 분석",
    group: "data_driven",
    time_horizon: "short",
    accent: "amber",
  },
  {
    id: "macro",
    icon: "🌐",
    name: "매크로",
    tagline: "사이클·국면 기반",
    group: "data_driven",
    time_horizon: "medium",
    accent: "sky",
  },
  {
    id: "korean",
    icon: "🇰🇷",
    name: "한국 시장",
    tagline: "외국인·재벌·밸류업",
    group: "data_driven",
    time_horizon: "medium",
    accent: "rose",
  },
] as const;

export const PERSONA_BY_ID: Record<PersonaId, PersonaMeta> = Object.fromEntries(
  PERSONA_META.map((p) => [p.id, p]),
) as Record<PersonaId, PersonaMeta>;

export const STRATEGIST_PERSONAS: PersonaId[] = ["blackrock", "ark", "graham"];
export const DATA_DRIVEN_PERSONAS: PersonaId[] = ["event", "macro", "korean"];
export const ALL_PERSONAS: PersonaId[] = PERSONA_META.map((p) => p.id);

export function isStrategistPersona(id: string): id is PersonaId {
  return (STRATEGIST_PERSONAS as string[]).includes(id);
}

export function isDataDrivenPersona(id: string): id is PersonaId {
  return (DATA_DRIVEN_PERSONAS as string[]).includes(id);
}

export function isValidPersonaId(id: string): id is PersonaId {
  return (ALL_PERSONAS as string[]).includes(id);
}

/* ────────────────────────────────────────────────────────────────────────
 * 시간 시계(Horizon) — 신규 1차 축.
 *
 * 6 페르소나를 대체하는 4개 "투자 시계"다. 시계가 지정되면 백엔드는 페르소나와
 * 무관하게 통합 strategist 파이프라인(research→analyst→validator→strategist)을
 * 항상 실행한다. 페르소나 타입은 하위호환을 위해 그대로 둔다(별도 정리 단계).
 * ──────────────────────────────────────────────────────────────────────── */

export type HorizonId = "short" | "short_mid" | "mid" | "long";

export type HorizonMeta = {
  id: HorizonId;
  icon: string;
  name: string;
  tagline: string;
  /** Tailwind color tag (text-{color}-600 / bg-{color}-50 등) */
  accent: "slate" | "violet" | "emerald" | "amber" | "sky" | "rose";
};

export const HORIZON_META: readonly HorizonMeta[] = [
  {
    id: "short",
    icon: "⚡",
    name: "단기",
    tagline: "수일~1개월 · 추세·거래량·수급 (모멘텀)",
    accent: "amber",
  },
  {
    id: "short_mid",
    icon: "📈",
    name: "단중기",
    tagline: "1~3개월 · 분기 실적 모멘텀 + 기술 강세 (어닝)",
    accent: "sky",
  },
  {
    id: "mid",
    icon: "⚖️",
    name: "중기",
    tagline: "3개월~1년 · 밸류·성장 균형 (GARP)",
    accent: "violet",
  },
  {
    id: "long",
    icon: "🏔",
    name: "장기",
    tagline: "1년+ · 펀더멘털·해자·매크로 사이클 (가치·해자)",
    accent: "emerald",
  },
] as const;

export const HORIZON_BY_ID: Record<HorizonId, HorizonMeta> = Object.fromEntries(
  HORIZON_META.map((h) => [h.id, h]),
) as Record<HorizonId, HorizonMeta>;

export const ALL_HORIZONS: HorizonId[] = HORIZON_META.map((h) => h.id);

/** 기본 시계 — 백엔드 user_default_horizon과 동일. */
export const DEFAULT_HORIZON: HorizonId = "mid";

export function isValidHorizonId(id: string): id is HorizonId {
  return (ALL_HORIZONS as string[]).includes(id);
}
