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
    id: "blackrock",
    icon: "🏛",
    name: "블랙록",
    tagline: "리스크 우선, 장기 가치",
    group: "strategist",
    time_horizon: "long",
    accent: "slate",
  },
  {
    id: "ark",
    icon: "🚀",
    name: "ARK",
    tagline: "파괴적 혁신, 5년 시계",
    group: "strategist",
    time_horizon: "long",
    accent: "violet",
  },
  {
    id: "graham",
    icon: "📚",
    name: "그레이엄",
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
