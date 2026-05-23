"use client";

/**
 * 분석 형태 선택 (2단 구조) — 종목 진입 후 "어떻게 분석할지" 의도적으로 고른 뒤 1회 실행.
 *
 * 자동 실행을 없애 불필요한 과금(분석 1회 ≈ ₩215~450)을 방지하고,
 * 사용자가 분석 관점을 의식적으로 선택하게 한다.
 *
 * Tier 1: 종합 전략 분석(4-에이전트 흐름) vs 데이터 특화 분석(단일 페르소나)
 * Tier 2: 전략 → 안정·리스크관리 / 고성장·혁신 / 가치·저평가
 *         데이터 → 이벤트 / 매크로 / 한국 시장
 *
 * 마지막 선택(defaultPersona)을 미리 선택해 1탭 재실행을 지원.
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

export function PersonaChooser({
  defaultPersona,
  onStart,
}: {
  defaultPersona: PersonaId;
  onStart: (persona: PersonaId) => void;
}) {
  const [group, setGroup] = useState<Group>(
    isStrategistPersona(defaultPersona) ? "strategist" : "data_driven",
  );
  const [selected, setSelected] = useState<PersonaId>(defaultPersona);

  // 사용자 플랜 + 페르소나별 free 허용 여부 — Pro 잠금 표시·실행 차단에 사용.
  const { data: personasData } = usePersonas();
  const isFree = (personasData?.user_plan ?? "free") === "free";
  const freeMap = new Map(
    (personasData?.personas ?? []).map((p) => [p.id, p.available_to_free]),
  );
  const isLocked = (id: PersonaId): boolean => {
    if (!isFree) return false;
    // 메타 미수신 시 보수적으로 blackrock(=안정·리스크관리)만 무료로 간주.
    const free = freeMap.get(id) ?? id === "blackrock";
    return !free;
  };
  const selectedLocked = isLocked(selected);

  const tier2 = group === "strategist" ? STRATEGIST_PERSONAS : DATA_DRIVEN_PERSONAS;

  const pickGroup = (g: Group) => {
    setGroup(g);
    // 그룹 전환 시 해당 그룹 첫 항목으로 선택 보정
    const list = g === "strategist" ? STRATEGIST_PERSONAS : DATA_DRIVEN_PERSONAS;
    if (!list.includes(selected)) setSelected(list[0]);
  };

  return (
    <div className="space-y-5">
      {/* Tier 1 — 분석 방식 */}
      <section>
        <h2 className="text-sm font-medium text-muted-foreground mb-2">
          1. 분석 방식
        </h2>
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

      {/* Tier 2 — 관점/데이터셋 */}
      <section>
        <h2 className="text-sm font-medium text-muted-foreground mb-2">
          2. {group === "strategist" ? "분석 관점" : "데이터셋"}
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
          {tier2.map((id) => {
            const meta = PERSONA_BY_ID[id];
            const active = selected === id;
            const locked = isLocked(id);
            return (
              <button
                key={id}
                type="button"
                onClick={() => setSelected(id)}
                aria-pressed={active}
                className={`text-left rounded-md border p-3 transition ${
                  active
                    ? "border-primary bg-primary/5 ring-1 ring-primary/40"
                    : "hover:bg-muted/50"
                }`}
              >
                <div className="font-medium text-sm flex items-center justify-between gap-2">
                  <span>
                    <span className="mr-1">{meta.icon}</span>
                    {meta.name}
                  </span>
                  {locked && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-700 shrink-0">
                      🔒 Pro
                    </span>
                  )}
                </div>
                <div className="text-xs text-muted-foreground mt-0.5">
                  {meta.tagline}
                </div>
              </button>
            );
          })}
        </div>
      </section>

      {selectedLocked ? (
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
          <p className="text-xs text-muted-foreground">
            분석은 선택한 방식으로 1회 실행됩니다. 결과 후 다른 관점으로 다시 분석할
            수 있습니다.
          </p>
        </>
      )}
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
        active ? "border-primary ring-1 ring-primary/40" : "hover:bg-muted/50"
      }`}
    >
      <CardContent className="p-4 space-y-1">
        <div className="font-semibold">
          <span className="mr-1.5">{icon}</span>
          {title}
        </div>
        <p className="text-xs text-muted-foreground leading-relaxed">{desc}</p>
      </CardContent>
    </Card>
  );
}
