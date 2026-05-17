"use client";

/**
 * 커스텀 스크리너 필터 빌더 — 컨트롤드 폼.
 *
 * 단순화: range slider 대신 min/max 숫자 입력 (모바일 호환·정밀도).
 * 토글: golden_cross, ma_aligned (true일 때만 백엔드로 전송)
 *
 * UX: 비어있는 필드는 "조건 없음" 의미. 입력 후 Tab 또는 blur 시 onChange 발사.
 */
import { useId } from "react";

import type { CustomScreenerFilters } from "@/types/api";

import { ALLOWED_SORT_OPTIONS, type SortKey } from "./customScreenerOptions";

type Market = "ALL" | "KR" | "US";

export interface FilterBuilderValue {
  filters: CustomScreenerFilters;
  sort_by: SortKey;
  sort_asc: boolean;
}

interface Props {
  value: FilterBuilderValue;
  onChange: (next: FilterBuilderValue) => void;
}

export function FilterBuilder({ value, onChange }: Props) {
  const update = <K extends keyof CustomScreenerFilters>(
    key: K,
    val: CustomScreenerFilters[K] | undefined,
  ) => {
    const next = { ...value.filters };
    if (val === undefined || val === "" || (typeof val === "number" && Number.isNaN(val))) {
      delete next[key];
    } else {
      next[key] = val;
    }
    onChange({ ...value, filters: next });
  };

  const market = (value.filters.market ?? "ALL") as Market;

  return (
    <div className="space-y-6">
      {/* 시장 */}
      <FieldGroup title="시장">
        <div className="flex gap-1 rounded-md border p-1 w-fit" role="radiogroup" aria-label="시장 선택">
          {(["ALL", "KR", "US"] as Market[]).map((m) => (
            <button
              key={m}
              type="button"
              role="radio"
              aria-checked={market === m}
              onClick={() => update("market", m === "ALL" ? undefined : m)}
              className={`px-3 py-1.5 text-sm rounded transition ${
                market === m
                  ? "bg-amber-500 text-black font-medium"
                  : "hover:bg-muted"
              }`}
            >
              {m === "ALL" ? "전체" : m === "KR" ? "🇰🇷 한국" : "🇺🇸 미국"}
            </button>
          ))}
        </div>
      </FieldGroup>

      {/* 가치 (PER/PBR/ROE) */}
      <FieldGroup title="가치">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <RangeInput
            label="PER"
            min={value.filters.per_min}
            max={value.filters.per_max}
            onMinChange={(v) => update("per_min", v)}
            onMaxChange={(v) => update("per_max", v)}
            placeholder="예: 5 ~ 20"
            step={0.1}
          />
          <RangeInput
            label="PBR"
            min={value.filters.pbr_min}
            max={value.filters.pbr_max}
            onMinChange={(v) => update("pbr_min", v)}
            onMaxChange={(v) => update("pbr_max", v)}
            placeholder="예: 0.5 ~ 2"
            step={0.1}
          />
          <RangeInput
            label="ROE %"
            min={value.filters.roe_min}
            max={value.filters.roe_max}
            onMinChange={(v) => update("roe_min", v)}
            onMaxChange={(v) => update("roe_max", v)}
            placeholder="예: 10 ~"
            step={1}
          />
        </div>
      </FieldGroup>

      {/* 배당 / 시장정보 */}
      <FieldGroup title="배당 · 규모">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <SingleMinInput
            label="배당률 ≥ (%)"
            value={value.filters.div_yield_min}
            onChange={(v) => update("div_yield_min", v)}
            placeholder="예: 3"
            step={0.1}
          />
          <RangeInput
            label="시총 (억)"
            min={value.filters.market_cap_min}
            max={value.filters.market_cap_max}
            onMinChange={(v) => update("market_cap_min", v)}
            onMaxChange={(v) => update("market_cap_max", v)}
            placeholder="예: 5000 ~"
            step={100}
          />
          <SingleMinInput
            label="거래대금 ≥ (백만)"
            value={value.filters.trading_value_min}
            onChange={(v) => update("trading_value_min", v)}
            placeholder="예: 5000"
            step={100}
          />
        </div>
      </FieldGroup>

      {/* 가격·모멘텀 */}
      <FieldGroup title="가격 · 모멘텀">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <RangeInput
            label="당일 등락률 (%)"
            min={value.filters.change_pct_min}
            max={value.filters.change_pct_max}
            onMinChange={(v) => update("change_pct_min", v)}
            onMaxChange={(v) => update("change_pct_max", v)}
            placeholder="예: -3 ~ 5"
            step={0.5}
          />
          <RangeInput
            label="RSI"
            min={value.filters.rsi_min}
            max={value.filters.rsi_max}
            onMinChange={(v) => update("rsi_min", v)}
            onMaxChange={(v) => update("rsi_max", v)}
            placeholder="예: 30 ~ 70"
            step={1}
          />
          <SingleMinInput
            label="거래량비 ≥"
            value={value.filters.volume_ratio_min}
            onChange={(v) => update("volume_ratio_min", v)}
            placeholder="예: 1.5"
            step={0.1}
          />
        </div>
      </FieldGroup>

      {/* 기술적 토글 */}
      <FieldGroup title="기술적 시그널">
        <div className="flex flex-wrap gap-2">
          <ToggleChip
            label="골든크로스"
            active={!!value.filters.golden_cross}
            onClick={() =>
              update("golden_cross", value.filters.golden_cross ? undefined : true)
            }
          />
          <ToggleChip
            label="이평선 정배열"
            active={!!value.filters.ma_aligned}
            onClick={() =>
              update("ma_aligned", value.filters.ma_aligned ? undefined : true)
            }
          />
        </div>
      </FieldGroup>

      {/* 정렬 */}
      <FieldGroup title="정렬">
        <div className="flex flex-wrap gap-3 items-center">
          <select
            value={value.sort_by}
            onChange={(e) =>
              onChange({ ...value, sort_by: e.target.value as SortKey })
            }
            className="rounded-md border bg-background px-3 py-1.5 text-sm"
            aria-label="정렬 기준"
          >
            {ALLOWED_SORT_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={() => onChange({ ...value, sort_asc: !value.sort_asc })}
            className="text-sm rounded-md border px-3 py-1.5 hover:bg-muted"
          >
            {value.sort_asc ? "↑ 오름차순" : "↓ 내림차순"}
          </button>
        </div>
      </FieldGroup>
    </div>
  );
}

// ─── 보조 컴포넌트 ─────────────────────────

function FieldGroup({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-2">
      <h3 className="text-sm font-semibold text-muted-foreground">{title}</h3>
      {children}
    </section>
  );
}

function RangeInput({
  label,
  min,
  max,
  onMinChange,
  onMaxChange,
  placeholder,
  step = 1,
}: {
  label: string;
  min: number | undefined;
  max: number | undefined;
  onMinChange: (v: number | undefined) => void;
  onMaxChange: (v: number | undefined) => void;
  placeholder?: string;
  step?: number;
}) {
  const id = useId();
  const minId = `${id}-min`;
  const maxId = `${id}-max`;
  return (
    <div className="space-y-1">
      <label htmlFor={minId} className="text-xs text-muted-foreground">
        {label} {placeholder && <span className="opacity-60">({placeholder})</span>}
      </label>
      <div className="flex items-center gap-1">
        <input
          id={minId}
          type="number"
          step={step}
          inputMode="decimal"
          value={min ?? ""}
          onChange={(e) => onMinChange(parseNumOrUndefined(e.target.value))}
          placeholder="최소"
          className="w-full rounded-md border bg-background px-2 py-1.5 text-sm"
          aria-label={`${label} 최소`}
        />
        <span className="text-xs text-muted-foreground">~</span>
        <input
          id={maxId}
          type="number"
          step={step}
          inputMode="decimal"
          value={max ?? ""}
          onChange={(e) => onMaxChange(parseNumOrUndefined(e.target.value))}
          placeholder="최대"
          className="w-full rounded-md border bg-background px-2 py-1.5 text-sm"
          aria-label={`${label} 최대`}
        />
      </div>
    </div>
  );
}

function SingleMinInput({
  label,
  value,
  onChange,
  placeholder,
  step = 1,
}: {
  label: string;
  value: number | undefined;
  onChange: (v: number | undefined) => void;
  placeholder?: string;
  step?: number;
}) {
  const id = useId();
  return (
    <div className="space-y-1">
      <label htmlFor={id} className="text-xs text-muted-foreground">
        {label}
      </label>
      <input
        id={id}
        type="number"
        step={step}
        inputMode="decimal"
        value={value ?? ""}
        onChange={(e) => onChange(parseNumOrUndefined(e.target.value))}
        placeholder={placeholder}
        className="w-full rounded-md border bg-background px-2 py-1.5 text-sm"
      />
    </div>
  );
}

function ToggleChip({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`rounded-full border px-3 py-1 text-sm transition ${
        active
          ? "border-amber-500 bg-amber-500/10 text-amber-500"
          : "hover:bg-muted"
      }`}
    >
      {active ? "✓ " : ""}
      {label}
    </button>
  );
}

function parseNumOrUndefined(s: string): number | undefined {
  if (!s.trim()) return undefined;
  const n = Number(s);
  return Number.isFinite(n) ? n : undefined;
}
