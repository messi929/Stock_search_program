"use client";

/**
 * 분석 형태 선택 (2단 구조) — 종목 진입 후 "어떻게 분석할지" 의도적으로 고른 뒤 1회 실행.
 *
 * 자동 실행을 없애 불필요한 과금(분석 1회 ≈ ₩215~450)을 방지하고,
 * 사용자가 분석 관점을 의식적으로 선택하게 한다.
 *
 * 시각 계층:
 *  Tier 1 (분석 방식): 큼지막한 카드. 진한 강조.
 *  Tier 2 (관점/데이터셋): 들여쓰기 + 배경색으로 "선택한 방식의 하위 옵션"임을 명시.
 *
 * 잠금 유형:
 *  - Pro 잠금 (Free 플랜에서 Pro 페르소나): 🔒 Pro 배지 + /pricing 안내.
 *  - 시장 비호환 (US 종목에 한국 시장 페르소나): 🇰🇷 한국 종목 전용 배지 + 비활성.
 */
import Link from "next/link";
import { useState } from "react";

import { Card, CardContent } from "@/components/ui/card";
import { usePersonas } from "@/hooks/usePersonas";
import {
  DATA_DRIVEN_PERSONAS,
  isStrategistPersona,
  PERSONA_BY_ID,
  STRATEGIST_PERSONAS,
  type PersonaId,
} from "@/types/persona";

type Group = "strategist" | "data_driven";

/** 한국 종목 여부 — 6자리 숫자 = KR (KOSPI/KOSDAQ), 그 외(영문) = US. */
function isKRTicker(ticker: string): boolean {
  return /^\d{6}$/.test(ticker || "");
}

/** 페르소나가 현재 종목 시장과 호환되지 않는지. 현재 korean만 KR 전용. */
function isMarketIncompatible(id: PersonaId, ticker: string): boolean {
  if (id === "korean") return !isKRTicker(ticker);
  return false;
}

export function PersonaChooser({
  ticker,
  defaultPersona,
  onStart,
}: {
  ticker: string;
  defaultPersona: PersonaId;
  onStart: (persona: PersonaId) => void;
}) {
  // 초기 선택 보정: 기본이 시장 비호환이면 첫 호환 페르소나로 교체.
  const initialDefault = isMarketIncompatible(defaultPersona, ticker)
    ? "blackrock"
    : defaultPersona;

  const [group, setGroup] = useState<Group>(
    isStrategistPersona(initialDefault) ? "strategist" : "data_driven",
  );
  const [selected, setSelected] = useState<PersonaId>(initialDefault);

  // Pro 잠금 — 사용자 플랜 + 페르소나별 free 허용 여부.
  const { data: personasData } = usePersonas();
  const isFree = (personasData?.user_plan ?? "free") === "free";
  const freeMap = new Map(
    (personasData?.personas ?? []).map((p) => [p.id, p.available_to_free]),
  );
  const isProLocked = (id: PersonaId): boolean => {
    if (!isFree) return false;
    const free = freeMap.get(id) ?? id === "blackrock";
    return !free;
  };

  const selectedProLocked = isProLocked(selected);
  const selectedMarketBlocked = isMarketIncompatible(selected, ticker);

  const tier2 = group === "strategist" ? STRATEGIST_PERSONAS : DATA_DRIVEN_PERSONAS;

  const pickGroup = (g: Group) => {
    setGroup(g);
    const list = g === "strategist" ? STRATEGIST_PERSONAS : DATA_DRIVEN_PERSONAS;
    // 그룹 전환 시 현재 선택이 그룹 밖이거나 시장 비호환이면 첫 호환 항목으로 교정.
    if (!list.includes(selected) || isMarketIncompatible(selected, ticker)) {
      const fallback = list.find((id) => !isMarketIncompatible(id, ticker)) ?? list[0];
      setSelected(fallback);
    }
  };

  return (
    <div className="space-y-1">
      {/* Tier 1 — 분석 방식 (큰 카드, 진한 강조) */}
      <section>
        <div className="flex items-baseline gap-2 mb-3">
          <span className="text-xs font-bold text-primary bg-primary/10 px-2 py-0.5 rounded">
            1단계
          </span>
          <h2 className="text-base font-semibold">분석 방식 선택</h2>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <GroupCard
            active={group === "strategist"}
            icon="🧭"
            title="종합 전략 분석"
            desc="리서치 → 분석 → 검증 → 종합 4단계로 한 종목을 깊게. (약 5~10초)"
            onClick={() => pickGroup("strategist")}
          />
          <GroupCard
            active={group === "data_driven"}
            icon="📡"
            title="데이터 특화 분석"
            desc="이벤트·매크로·한국 시장 등 특정 데이터셋에 집중. (빠름)"
            onClick={() => pickGroup("data_driven")}
          />
        </div>
      </section>

      {/* 연결 표시 — Tier1 → Tier2 종속 관계를 시각화 */}
      <div className="flex flex-col items-center py-2 -my-1" aria-hidden="true">
        <div className="h-3 w-px bg-border" />
        <div className="text-[10px] text-muted-foreground">
          ↓ 위 방식의 관점/데이터셋
        </div>
      </div>

      {/* Tier 2 — 들여쓰기 + 옅은 배경으로 sub-option 시각화 */}
      <section className="rounded-lg border border-dashed bg-muted/30 p-3 sm:pl-6 sm:ml-2">
        <div className="flex items-baseline gap-2 mb-2 flex-wrap">
          <span className="text-xs font-bold text-primary bg-primary/10 px-2 py-0.5 rounded">
            2단계
          </span>
          <h3 className="text-sm font-semibold">
            {group === "strategist" ? "분석 관점" : "데이터셋"} 선택
          </h3>
          <span className="text-[11px] text-muted-foreground">
            ({group === "strategist" ? "종합 전략" : "데이터 특화"} 방식)
          </span>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
          {tier2.map((id) => {
            const meta = PERSONA_BY_ID[id];
            const active = selected === id;
            const proLocked = isProLocked(id);
            const marketBlocked = isMarketIncompatible(id, ticker);
            const disabled = marketBlocked;
            return (
              <button
                key={id}
                type="button"
                onClick={() => {
                  if (disabled) return;
                  setSelected(id);
                }}
                aria-pressed={active}
                aria-disabled={disabled}
                className={`text-left rounded-md border p-2.5 transition bg-background ${
                  active && !disabled
                    ? "border-primary ring-1 ring-primary/40"
                    : "hover:bg-muted/50"
                } ${disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
              >
                <div className="font-medium text-sm flex items-center justify-between gap-2">
                  <span className="truncate">
                    <span className="mr-1">{meta.icon}</span>
                    {meta.name}
                  </span>
                  {marketBlocked ? (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground shrink-0 whitespace-nowrap">
                      🇰🇷 KR 전용
                    </span>
                  ) : proLocked ? (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-700 shrink-0">
                      🔒 Pro
                    </span>
                  ) : null}
                </div>
                <div className="text-xs text-muted-foreground mt-0.5">
                  {meta.tagline}
                </div>
              </button>
            );
          })}
        </div>
      </section>

      {/* 시작 버튼 — 4가지 상태: 시장차단 / Pro잠금 / 정상 */}
      <div className="pt-3">
        {selectedMarketBlocked ? (
          <div className="space-y-2">
            <button
              type="button"
              disabled
              className="w-full sm:w-auto px-6 py-2.5 rounded-md bg-muted text-muted-foreground font-medium text-sm cursor-not-allowed"
            >
              🇰🇷 {PERSONA_BY_ID[selected].name}는 한국 종목 전용
            </button>
            <p className="text-xs text-muted-foreground">
              미국 종목엔 일별 외국인·기관 수급 같은 한국 시장 데이터가 존재하지
              않아 적용할 수 없습니다. 다른 관점을 선택하세요.
            </p>
          </div>
        ) : selectedProLocked ? (
          <div className="space-y-2">
            <Link
              href="/pricing"
              className="inline-flex items-center w-full sm:w-auto px-6 py-2.5 rounded-md bg-amber-500/90 text-white font-medium text-sm hover:bg-amber-500 transition"
            >
              🔒 {PERSONA_BY_ID[selected].name}는 Pro 페르소나 — 업그레이드 안내
            </Link>
            <p className="text-xs text-muted-foreground">
              Free 플랜은 <strong>안정·리스크관리</strong> 한 가지만 사용 가능합니다.
              다른 5개 관점은 Pro에서 모두 열립니다.
            </p>
          </div>
        ) : (
          <>
            <button
              type="button"
              onClick={() => onStart(selected)}
              className="w-full sm:w-auto px-6 py-2.5 rounded-md bg-primary text-primary-foreground font-medium text-sm hover:bg-primary/90 transition"
            >
              🔍 {PERSONA_BY_ID[selected].name} 관점으로 분석 시작
            </button>
            <p className="text-xs text-muted-foreground mt-2">
              분석은 선택한 방식으로 1회 실행됩니다. 결과 후 다른 관점으로 다시
              분석할 수 있습니다.
            </p>
          </>
        )}
      </div>
    </div>
  );
}

function GroupCard({
  active,
  icon,
  title,
  desc,
  onClick,
}: {
  active: boolean;
  icon: string;
  title: string;
  desc: string;
  onClick: () => void;
}) {
  return (
    <Card
      onClick={onClick}
      className={`cursor-pointer transition ${
        active
          ? "border-2 border-primary bg-primary/5 shadow-sm"
          : "border hover:bg-muted/40 hover:border-foreground/20"
      }`}
    >
      <CardContent className="p-4 space-y-1.5">
        <div className="flex items-center justify-between gap-2">
          <div className="font-semibold text-base">
            <span className="mr-1.5">{icon}</span>
            {title}
          </div>
          {active && (
            <span className="text-[10px] font-bold text-primary bg-primary/10 px-2 py-0.5 rounded shrink-0">
              ✓ 선택됨
            </span>
          )}
        </div>
        <p className="text-xs text-muted-foreground leading-relaxed">{desc}</p>
      </CardContent>
    </Card>
  );
}
