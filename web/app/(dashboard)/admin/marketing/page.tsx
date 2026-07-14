"use client";

/**
 * 관리자 — 마케팅 콘텐츠 공장 (Phase 1).
 * 스레드(Threads)용 종목 글을 Haiku로 생성 → 검수/수정 → 복사.
 * (Phase 2에서 Threads API 자동 발행 버튼 추가 예정)
 */
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  DraftStatus,
  MarketingDraft,
  PART_SEP,
  marketingApi,
  splitParts,
} from "@/lib/marketing";

const STATUS_FILTERS: { key: string; label: string }[] = [
  { key: "", label: "전체" },
  { key: "draft", label: "초안" },
  { key: "approved", label: "승인됨" },
  { key: "published", label: "발행됨" },
  { key: "partial", label: "발행 끊김" },
  { key: "archived", label: "보관" },
];

// 백엔드 threads_client.MAX_PARTS와 같은 값. 파트가 많을수록 발행 중간에 끊길 지점도 늘어난다.
const MAX_PARTS = 6;

const STATUS_BADGE: Record<DraftStatus, string> = {
  draft: "bg-slate-500/15 text-slate-300",
  approved: "bg-emerald-500/15 text-emerald-300",
  published: "bg-sky-500/15 text-sky-300",
  partial: "bg-rose-500/15 text-rose-300",
  archived: "bg-zinc-500/15 text-zinc-400",
};

const STATUS_LABEL: Record<DraftStatus, string> = {
  draft: "초안",
  approved: "승인됨",
  published: "발행됨",
  partial: "발행 끊김",
  archived: "보관",
};

export default function AdminMarketingPage() {
  // ── 생성 패널 상태 ──
  const [tickersInput, setTickersInput] = useState("");
  const [hotCount, setHotCount] = useState(3);
  // null = 아직 사용자가 손대지 않음 → 서버 기본값 사용
  const [selectedFormats, setSelectedFormats] = useState<string[] | null>(null);
  const [generating, setGenerating] = useState(false);
  const [briefingGenerating, setBriefingGenerating] = useState(false);
  const [weekendGenerating, setWeekendGenerating] = useState(false);
  const [selectedIndices, setSelectedIndices] = useState<string[]>([]);
  const [indexGenerating, setIndexGenerating] = useState(false);
  const [narrativeGenerating, setNarrativeGenerating] = useState(false);
  const [statusFilter, setStatusFilter] = useState("");

  const indicesQ = useQuery({
    queryKey: ["admin", "marketing", "indices"],
    queryFn: marketingApi.indices,
    staleTime: 60 * 60_000,
  });

  const publishStatusQ = useQuery({
    queryKey: ["admin", "marketing", "publish-status"],
    queryFn: marketingApi.publishStatus,
    staleTime: 5 * 60_000,
  });
  const publishEnabled = publishStatusQ.data?.enabled ?? false;

  const formatsQ = useQuery({
    queryKey: ["admin", "marketing", "formats"],
    queryFn: marketingApi.formats,
    staleTime: 60 * 60_000,
  });
  const maxChars = formatsQ.data?.max_chars ?? 500;

  // effect 없이 렌더 단계에서 파생: 사용자 선택 없으면 서버 기본값.
  const effFormats = selectedFormats ?? formatsQ.data?.default ?? [];

  const draftsQ = useQuery({
    queryKey: ["admin", "marketing", "drafts", statusFilter],
    queryFn: () => marketingApi.drafts(statusFilter),
  });

  const toggleFormat = (key: string) => {
    setSelectedFormats((prev) => {
      const base = prev ?? formatsQ.data?.default ?? [];
      return base.includes(key)
        ? base.filter((k) => k !== key)
        : [...base, key];
    });
  };

  const generate = async () => {
    const tickers = tickersInput
      .split(/[\s,]+/)
      .map((t) => t.trim().toUpperCase())
      .filter(Boolean);
    if (effFormats.length === 0) {
      toast.error("포맷을 1개 이상 선택하세요");
      return;
    }
    setGenerating(true);
    try {
      const res = await marketingApi.generate({
        tickers,
        formats: effFormats,
        hot_count: hotCount,
      });
      toast.success(`초안 ${res.count}건 생성됨`);
      draftsQ.refetch();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "생성 실패");
    } finally {
      setGenerating(false);
    }
  };

  const generateNarrative = async () => {
    const tickers = tickersInput
      .split(/[\s,]+/)
      .map((t) => t.trim().toUpperCase())
      .filter(Boolean);
    setNarrativeGenerating(true);
    try {
      const res = await marketingApi.generateNarrative(tickers);
      const d = res.created?.[0];
      toast.success(`서사 타래 생성됨 (${d?.part_count ?? 0}파트)`);
      draftsQ.refetch();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "서사 타래 생성 실패");
    } finally {
      setNarrativeGenerating(false);
    }
  };

  const generateBriefing = async () => {
    setBriefingGenerating(true);
    try {
      const res = await marketingApi.generateBriefing();
      toast.success(`브리핑 ${res.count}건 생성됨`);
      draftsQ.refetch();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "브리핑 생성 실패");
    } finally {
      setBriefingGenerating(false);
    }
  };

  const generateWeekendBriefing = async () => {
    setWeekendGenerating(true);
    try {
      const res = await marketingApi.generateWeekendBriefing();
      toast.success(`주말 브리핑 ${res.count}건 생성됨`);
      draftsQ.refetch();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "주말 브리핑 생성 실패");
    } finally {
      setWeekendGenerating(false);
    }
  };

  const toggleIndex = (key: string) => {
    setSelectedIndices((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key],
    );
  };

  const generateIndexChart = async () => {
    if (selectedIndices.length === 0) {
      toast.error("지수를 1개 이상 선택하세요");
      return;
    }
    setIndexGenerating(true);
    try {
      const res = await marketingApi.generateIndexChart(selectedIndices);
      toast.success(`지수 차트 글 ${res.count}건 생성됨`);
      draftsQ.refetch();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "지수 차트 생성 실패");
    } finally {
      setIndexGenerating(false);
    }
  };

  const drafts = draftsQ.data?.drafts ?? [];

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h2 className="font-semibold">마케팅 콘텐츠 공장</h2>
        <p className="text-sm text-muted-foreground mt-1">
          스레드 글을 AI로 생성하고, 검수·수정 후 발행합니다. 종목을 비우면 오늘 화제
          종목을 자동 선정합니다. (추천 표현은 자동 필터됩니다)
        </p>
      </div>

      {/* ── 🧵 서사 타래 — 브로드캐스트의 기본 포맷 ── */}
      <div className="space-y-3 rounded-lg border border-primary/40 bg-primary/5 p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-sm font-medium">🧵 서사 타래 (브로드캐스트 기본)</p>
            <p className="text-xs text-muted-foreground mt-0.5">
              오늘의 사건(뉴스·지수)에서 출발해 갈라볼 프레임을 주고, 화제 종목의 실측
              수치로 시연한 뒤 댓글로 초대하는 3~5파트 타래. 종목은 <b>삽화</b>로만
              쓰입니다.
            </p>
          </div>
          <Button
            type="button"
            onClick={generateNarrative}
            disabled={narrativeGenerating}
          >
            {narrativeGenerating ? "생성 중... (수십초)" : "🧵 타래 생성"}
          </Button>
        </div>
        <Input
          value={tickersInput}
          onChange={(e) => setTickersInput(e.target.value)}
          placeholder="삽화로 쓸 종목 (비우면 화제 종목 자동) · 예: 005930, 000660"
        />
      </div>

      {/* ── 종목글 (강등: 브로드캐스트용 아님) ── */}
      <details className="space-y-4 rounded-lg border p-4">
        <summary className="cursor-pointer text-sm font-medium">
          📉 종목 단독 글{" "}
          <span className="text-xs font-normal text-muted-foreground">
            — 브로드캐스트용 아님(스레드에서 죽는 형태). 댓글 요청에 답할 초안용으로만.
          </span>
        </summary>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-3">
          <div className="sm:col-span-2">
            <label className="text-xs text-muted-foreground">
              종목 (위 입력칸 공유 · 비우면 자동)
            </label>
            <Input
              value={tickersInput}
              onChange={(e) => setTickersInput(e.target.value)}
              placeholder="예: 005930, 000660, AAPL"
            />
          </div>
          <div>
            <label className="text-xs text-muted-foreground">
              자동 선정 개수
            </label>
            <Input
              type="number"
              min={1}
              max={10}
              value={hotCount}
              onChange={(e) => setHotCount(Number(e.target.value) || 3)}
            />
          </div>
        </div>

        <div>
          <label className="text-xs text-muted-foreground">글 포맷</label>
          <div className="flex flex-wrap gap-2 mt-1.5">
            {(formatsQ.data?.formats ?? []).map((f) => {
              const on = effFormats.includes(f.key);
              return (
                <button
                  key={f.key}
                  type="button"
                  onClick={() => toggleFormat(f.key)}
                  className={`px-3 py-1.5 rounded-full text-xs border transition ${
                    on
                      ? "border-primary bg-primary/10 text-primary font-medium"
                      : "border-border text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {on ? "✓ " : ""}
                  {f.label}
                </button>
              );
            })}
          </div>
        </div>

        <div className="flex items-center justify-between">
          <span className="text-xs text-muted-foreground">
            {tickersInput.trim()
              ? "입력한 종목으로 생성"
              : `오늘 화제 종목 ${hotCount}개 자동 선정`}{" "}
            × 포맷 {effFormats.length}개
          </span>
          <Button
            type="button"
            variant="outline"
            onClick={generate}
            disabled={generating}
          >
            {generating ? "생성 중... (수초 소요)" : "✨ 종목글 생성"}
          </Button>
        </div>
      </details>

      {/* ── 새벽 미국시장 브리핑 생성 ── */}
      <div className="flex items-center justify-between gap-3 rounded-lg border p-4">
        <div>
          <p className="text-sm font-medium">🌙 새벽 미국시장 브리핑</p>
          <p className="text-xs text-muted-foreground mt-0.5">
            간밤 S&P500·나스닥·다우·반도체·환율을 모아 중립 브리핑 글을 생성합니다.
            종목 입력 불필요.
          </p>
        </div>
        <Button
          type="button"
          variant="outline"
          onClick={generateBriefing}
          disabled={briefingGenerating}
        >
          {briefingGenerating ? "생성 중..." : "🌙 브리핑 생성"}
        </Button>
      </div>

      {/* ── 주말 결산 브리핑 생성 ── */}
      <div className="flex items-center justify-between gap-3 rounded-lg border p-4">
        <div>
          <p className="text-sm font-medium">🗓️ 주말 결산 브리핑</p>
          <p className="text-xs text-muted-foreground mt-0.5">
            주말 주요 소식 + 지난 금요일 미국장 마감을 정리해 다음 거래일(월요일) 국내장
            관전 포인트를 담은 글을 생성합니다. (일요일 밤 자동 발행 대상)
          </p>
        </div>
        <Button
          type="button"
          variant="outline"
          onClick={generateWeekendBriefing}
          disabled={weekendGenerating}
        >
          {weekendGenerating ? "생성 중..." : "🗓️ 주말 브리핑 생성"}
        </Button>
      </div>

      {/* ── 지수 차트 글 생성 ── */}
      <div className="space-y-3 rounded-lg border p-4">
        <div>
          <p className="text-sm font-medium">📈 지수 차트 글</p>
          <p className="text-xs text-muted-foreground mt-0.5">
            코스피·코스닥·나스닥 등 지수의 차트 국면(이동평균·52주 고저·RSI·추세)을 구체적
            지수 레벨로 읽고 등락 배경 한 줄을 곁들입니다. 선택한 지수마다 개별 글로 생성됩니다.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {(indicesQ.data?.indices ?? []).map((idx) => {
            const on = selectedIndices.includes(idx.key);
            return (
              <button
                key={idx.key}
                type="button"
                onClick={() => toggleIndex(idx.key)}
                className={`px-3 py-1.5 rounded-full text-xs border transition ${
                  on
                    ? "border-primary bg-primary/10 text-primary font-medium"
                    : "border-border text-muted-foreground hover:text-foreground"
                }`}
              >
                {on ? "✓ " : ""}
                {idx.name}
              </button>
            );
          })}
        </div>
        <div className="flex items-center justify-between">
          <span className="text-xs text-muted-foreground">
            지수 {selectedIndices.length}개 선택
          </span>
          <Button
            type="button"
            variant="outline"
            onClick={generateIndexChart}
            disabled={indexGenerating}
          >
            {indexGenerating ? "생성 중... (수초 소요)" : "📈 지수 차트 생성"}
          </Button>
        </div>
      </div>

      {!publishEnabled && (
        <p className="text-xs text-amber-400">
          ⚠ Threads 자동발행이 비활성 상태입니다(토큰 미설정). 지금은 복사 후 수동 발행만
          가능합니다.
        </p>
      )}

      {/* ── 상태 필터 ── */}
      <div className="flex items-center gap-1.5">
        {STATUS_FILTERS.map((s) => (
          <button
            key={s.key}
            type="button"
            onClick={() => setStatusFilter(s.key)}
            className={`px-3 py-1 rounded-full text-xs transition ${
              statusFilter === s.key
                ? "bg-primary text-primary-foreground font-medium"
                : "bg-muted text-muted-foreground hover:text-foreground"
            }`}
          >
            {s.label}
          </button>
        ))}
        <span className="ml-auto text-xs text-muted-foreground">
          {drafts.length}건
        </span>
      </div>

      {/* ── 초안 목록 ── */}
      {draftsQ.isLoading ? (
        <p className="text-sm text-muted-foreground">로딩 중...</p>
      ) : drafts.length === 0 ? (
        <p className="text-sm text-muted-foreground py-8 text-center">
          초안이 없습니다. 위에서 생성해보세요.
        </p>
      ) : (
        <div className="space-y-4">
          {drafts.map((d) => (
            <DraftCard
              key={d.id}
              draft={d}
              maxChars={maxChars}
              publishEnabled={publishEnabled}
              onChanged={() => draftsQ.refetch()}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ──────────────────────────────────────────────
// 초안 카드 — 편집 + 글자수 + OG미리보기 + 복사/승인/삭제
// ──────────────────────────────────────────────

function DraftCard({
  draft,
  maxChars,
  publishEnabled,
  onChanged,
}: {
  draft: MarketingDraft;
  maxChars: number;
  publishEnabled: boolean;
  onChanged: () => void;
}) {
  const [text, setText] = useState(draft.text);
  const [prevText, setPrevText] = useState(draft.text);
  const [busy, setBusy] = useState(false);
  const [showOg, setShowOg] = useState(false);
  const [ogError, setOgError] = useState(false);

  // 외부(서버 refetch)로 draft.text가 바뀌면 편집값 동기화 — effect 없이 렌더 단계에서.
  if (draft.text !== prevText) {
    setPrevText(draft.text);
    setText(draft.text);
  }

  const isBriefing = draft.kind === "briefing";
  const isIndex = draft.kind === "index";
  const isStock = draft.kind === "stock";
  const isEducation = draft.kind === "education";
  const isNarrative = draft.kind === "narrative";
  const kindEmoji = isBriefing
    ? "🌙 "
    : isIndex
      ? "📈 "
      : isEducation
        ? "🎓 "
        : isNarrative
          ? "🧵 "
          : "";
  const isPublished = draft.status === "published";
  const isPartial = draft.status === "partial"; // 타래 중간에서 끊김 → 이어서 발행만 가능
  const dirty = text !== draft.text;

  // 발행 단위는 파트다. 500자는 글 전체가 아니라 **파트 하나**의 한도.
  const parts = useMemo(() => splitParts(text), [text]);
  const overIdx = parts.findIndex((p) => p.length > maxChars);
  const over = overIdx >= 0 || parts.length === 0 || parts.length > MAX_PARTS;

  const ogUrl = useMemo(
    () => `/stocks/${encodeURIComponent(draft.ticker)}/opengraph-image`,
    [draft.ticker],
  );

  const publish = async () => {
    const remaining = draft.part_count - draft.published_upto;
    const msg = isPartial
      ? `남은 ${remaining}개 파트를 마지막 글에 이어서 발행할까요?`
      : parts.length > 1
        ? `${parts.length}개 파트를 타래로 발행할까요? (되돌릴 수 없습니다 — Threads는 글삭제 API가 없습니다)`
        : "이 글을 Threads에 지금 발행할까요? (되돌릴 수 없습니다)";
    if (!confirm(msg)) return;
    setBusy(true);
    try {
      await marketingApi.publish(draft.id);
      toast.success(parts.length > 1 ? "타래로 발행됨" : "Threads에 발행됨");
      onChanged();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "발행 실패");
    } finally {
      setBusy(false);
    }
  };

  const save = async () => {
    setBusy(true);
    try {
      await marketingApi.update(draft.id, { text });
      toast.success("저장됨");
      onChanged();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "저장 실패");
    } finally {
      setBusy(false);
    }
  };

  const setStatus = async (status: DraftStatus) => {
    setBusy(true);
    try {
      await marketingApi.update(draft.id, { status });
      toast.success(status === "approved" ? "승인됨" : "상태 변경됨");
      onChanged();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "변경 실패");
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    if (!confirm("이 초안을 삭제할까요?")) return;
    setBusy(true);
    try {
      await marketingApi.remove(draft.id);
      toast.success("삭제됨");
      onChanged();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "삭제 실패");
    } finally {
      setBusy(false);
    }
  };

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      toast.success("복사됨 — 스레드에 붙여넣으세요");
    } catch {
      toast.error("복사 실패 (브라우저 권한 확인)");
    }
  };

  return (
    <div className="rounded-lg border p-4 space-y-3">
      {/* 헤더 */}
      <div className="flex items-center gap-2 flex-wrap">
        <span className="font-semibold text-sm">
          {kindEmoji}
          {draft.name || draft.ticker}
        </span>
        {isStock && (
          <span className="text-xs text-muted-foreground">{draft.ticker}</span>
        )}
        <span className="px-2 py-0.5 rounded-full text-[11px] bg-blue-500/15 text-blue-300">
          {draft.fmt_label}
        </span>
        <span
          className={`px-2 py-0.5 rounded-full text-[11px] ${STATUS_BADGE[draft.status]}`}
        >
          {STATUS_LABEL[draft.status]}
        </span>
        {draft.filtered.length > 0 && (
          <span className="px-2 py-0.5 rounded-full text-[11px] bg-amber-500/15 text-amber-300">
            ⚠ 필터됨: {draft.filtered.join(", ")}
          </span>
        )}
        {(draft.score ?? 0) > 0 && (
          <span
            className={`px-2 py-0.5 rounded-full text-[11px] ${
              draft.score >= 25
                ? "bg-emerald-500/15 text-emerald-300"
                : draft.score >= 18
                  ? "bg-amber-500/15 text-amber-300"
                  : "bg-rose-500/15 text-rose-300"
            }`}
            title="편집 단계 자가채점(후킹·긴장·구체성·독자시점·담백함·법적안전 6축 합산)"
          >
            품질 {draft.score}/30
          </span>
        )}
        {(draft.warnings?.length ?? 0) > 0 && (
          <span
            className="px-2 py-0.5 rounded-full text-[11px] bg-orange-500/15 text-orange-300"
            title="자기언급·내부용어·길이 등 사람이 한번 더 볼 지점"
          >
            ⚠ 점검: {draft.warnings.join(", ")}
          </span>
        )}
        {isPublished && draft.permalink && (
          <a
            href={draft.permalink}
            target="_blank"
            rel="noreferrer"
            className="text-[11px] text-sky-400 underline underline-offset-2"
          >
            발행글 보기 ↗
          </a>
        )}
      </div>

      {/* 글의 핵심 긴장(앵글) — 하네스 v2 */}
      {!isBriefing && draft.angle && (
        <p className="text-[11px] text-muted-foreground">
          🎯 앵글: {draft.angle}
        </p>
      )}

      {/* 발행이 중간에 끊긴 초안 — 이미 나간 파트는 지울 수 없다(Threads 글삭제 API 없음) */}
      {isPartial && (
        <p className="rounded-md bg-rose-500/10 px-3 py-2 text-xs text-rose-300">
          {draft.part_count}개 파트 중 <b>{draft.published_upto}개까지 발행</b>된 상태로
          끊겼습니다. 이미 나간 글은 코드로 지울 수 없습니다(앱에서 수동 삭제). 남은 파트를
          고친 뒤 <b>이어서 발행</b>하면 마지막 글에 이어 붙습니다.
        </p>
      )}

      {/* 편집 textarea — `---` 단독 줄이 파트(글) 경계 */}
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={8}
        className="w-full rounded-md border bg-background px-3 py-2 text-sm leading-relaxed resize-y focus:outline-none focus:ring-1 focus:ring-primary"
      />
      <p className="text-[11px] text-muted-foreground">
        <code>{PART_SEP}</code> 단독 줄 = 글 경계. 파트가 2개 이상이면 각 파트가 직전 글의
        답글로 붙어 <b>타래</b>가 됩니다(서비스 안내 줄이 마지막 파트 = 첫 댓글).
      </p>

      {/* 파트별 글자수 + 액션 — 500자는 글 전체가 아니라 파트 하나의 한도다 */}
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-xs tabular-nums text-muted-foreground">
          {parts.map((p, i) => (
            <span
              key={i}
              className={
                p.length > maxChars ? "text-red-500 font-semibold" : undefined
              }
            >
              {i > 0 && " · "}
              {parts.length > 1 && `${i + 1}/${parts.length} `}
              {p.length}자
            </span>
          ))}
          {parts.length > 1 && ` (한도 ${maxChars}자/파트)`}
        </span>
        {parts.length > MAX_PARTS && (
          <span className="text-xs text-red-500">
            파트 {parts.length}개 — 최대 {MAX_PARTS}개
          </span>
        )}
        <div className="ml-auto flex items-center gap-2">
          {dirty && !isPublished && (
            <Button size="sm" variant="outline" onClick={save} disabled={busy}>
              저장
            </Button>
          )}
          <Button size="sm" variant="outline" onClick={copy} disabled={over}>
            📋 복사
          </Button>
          {isStock && (
            <Button
              size="sm"
              variant="outline"
              onClick={() => setShowOg((v) => !v)}
            >
              {showOg ? "카드 숨기기" : "🖼 OG카드"}
            </Button>
          )}
          {!isPublished && publishEnabled && (
            <Button
              size="sm"
              onClick={publish}
              disabled={busy || over || dirty}
              title={
                dirty
                  ? "수정사항을 먼저 저장하세요"
                  : isPartial
                    ? "끊긴 지점부터 남은 파트를 마지막 글에 이어 붙입니다"
                    : "Threads에 발행"
              }
              className="bg-sky-600 hover:bg-sky-500"
            >
              {isPartial ? "▶ 이어서 발행" : "🚀 발행"}
            </Button>
          )}
          {!isPublished &&
            (draft.status !== "approved" ? (
              <Button size="sm" variant="outline" onClick={() => setStatus("approved")} disabled={busy}>
                ✓ 승인
              </Button>
            ) : (
              <Button
                size="sm"
                variant="outline"
                onClick={() => setStatus("draft")}
                disabled={busy}
              >
                초안으로
              </Button>
            ))}
          <Button
            size="sm"
            variant="outline"
            onClick={remove}
            disabled={busy}
            className="text-red-500"
          >
            삭제
          </Button>
        </div>
      </div>

      {/* OG 카드 미리보기 (공유 링크에 첨부될 이미지) */}
      {showOg &&
        (ogError ? (
          <p className="text-xs text-muted-foreground">
            이 종목의 OG 카드를 불러올 수 없습니다(미지원 종목일 수 있음).
          </p>
        ) : (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={ogUrl}
            alt={`${draft.ticker} OG 카드`}
            className="w-full rounded-md border"
            onError={() => setOgError(true)}
          />
        ))}
    </div>
  );
}
