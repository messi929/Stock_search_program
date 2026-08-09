"use client";

/**
 * 관리자 — 네이버 프리미엄콘텐츠 발행 워크스페이스.
 *
 * 2026-08-09 신설. 근거: docs/axis/NAVER_PREMIUM.md
 *
 * ⚠️ 이 화면에는 "발행" 버튼이 없다. 프리미엄콘텐츠는 발행 API가 없어서
 *    스튜디오 에디터에 사람이 붙여넣는 수밖에 없다. 그래서 흐름이 이렇다:
 *
 *      생성 → 검수·수정 → [전문 복사] → 스튜디오에 붙여넣기(사람) → URL 회수 → 발행 기록
 *
 *    마케팅(스레드) 탭과 헷갈리면 "발행했는데 왜 안 올라갔지"가 된다.
 */
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  PremiumDraft,
  PremiumStatus,
  premiumApi,
} from "@/lib/premium";

const STATUS_FILTERS: { key: string; label: string }[] = [
  { key: "", label: "전체" },
  { key: "draft", label: "초안" },
  { key: "approved", label: "승인됨" },
  { key: "published", label: "발행됨" },
  { key: "archived", label: "보관" },
];

const STATUS_BADGE: Record<PremiumStatus, string> = {
  draft: "bg-slate-500/15 text-slate-300",
  approved: "bg-emerald-500/15 text-emerald-300",
  published: "bg-sky-500/15 text-sky-300",
  archived: "bg-zinc-500/15 text-zinc-400",
};

const STATUS_LABEL: Record<PremiumStatus, string> = {
  draft: "초안",
  approved: "승인됨",
  published: "발행됨",
  archived: "보관",
};

/** 분량 게이지 — 이 판의 경쟁 글이 17,000자라 길이가 곧 품질 신호다. */
function LengthBar({
  chars,
  min,
  target,
}: {
  chars: number;
  min: number;
  target: number;
}) {
  const pct = Math.min(100, Math.round((chars / target) * 100));
  const tone =
    chars < min
      ? "bg-rose-500"
      : chars < target * 0.8
        ? "bg-amber-500"
        : "bg-emerald-500";
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-28 rounded bg-white/10 overflow-hidden">
        <div className={`h-full ${tone}`} style={{ width: `${pct}%` }} />
      </div>
      <span
        className={`text-xs tabular-nums ${chars < min ? "text-rose-400" : "text-muted-foreground"}`}
      >
        {chars.toLocaleString()}자
      </span>
    </div>
  );
}

export default function AdminPremiumPage() {
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);
  const [openId, setOpenId] = useState<string | null>(null);

  // 편집 버퍼 — 열려 있는 초안의 전문. 목록 응답은 400자로 잘려 오므로 detail()로 채운다.
  const [draftBody, setDraftBody] = useState("");
  const [draftTitle, setDraftTitle] = useState("");
  const [facts, setFacts] = useState("");
  const [showFacts, setShowFacts] = useState(false);
  const [publishUrl, setPublishUrl] = useState("");

  const meta = useQuery({
    queryKey: ["premium-meta"],
    queryFn: () => premiumApi.meta(),
    staleTime: 5 * 60_000,
  });

  const list = useQuery({
    queryKey: ["premium-drafts", status],
    queryFn: () => premiumApi.drafts(status),
  });

  const drafts = list.data?.drafts ?? [];
  const minChars = meta.data?.min_chars ?? 6000;
  const targetChars = meta.data?.target_chars ?? 12000;

  // 초안을 펼치면 전문을 받아온다(목록은 미리보기만 담고 있다).
  useEffect(() => {
    if (!openId) return;
    let alive = true;
    premiumApi
      .detail(openId)
      .then((r) => {
        if (!alive) return;
        setDraftBody(r.draft.body);
        setDraftTitle(r.draft.title);
        setFacts(r.draft.facts);
        setPublishUrl(r.draft.published_url);
      })
      .catch(() => toast.error("전문을 불러오지 못했습니다"));
    return () => {
      alive = false;
    };
  }, [openId]);

  async function onGenerate() {
    setBusy(true);
    try {
      const r = await premiumApi.generate("weekly");
      toast.success(`초안 생성 — ${r.draft.char_count.toLocaleString()}자`);
      await list.refetch();
      setOpenId(r.draft.id);
    } catch (e) {
      // 422 = 데이터 부족으로 서버가 생성을 거부한 것. 실패가 아니라 설계된 동작이다.
      toast.error(e instanceof Error ? e.message : "생성 실패");
    } finally {
      setBusy(false);
    }
  }

  async function onSave(id: string, patch: Parameters<typeof premiumApi.update>[1]) {
    try {
      const r = await premiumApi.update(id, patch);
      toast.success("저장됨");
      setDraftBody(r.draft.body);
      await list.refetch();
    } catch {
      toast.error("저장 실패");
    }
  }

  async function onCopy(text: string) {
    try {
      await navigator.clipboard.writeText(text);
      toast.success("전문 복사됨 — 스튜디오에 붙여넣으세요");
    } catch {
      toast.error("복사 실패");
    }
  }

  async function onMarkPublished(id: string) {
    if (!publishUrl.startsWith("http")) {
      toast.error("발행된 콘텐츠 URL을 입력하세요");
      return;
    }
    try {
      await premiumApi.markPublished(id, publishUrl);
      toast.success("발행 기록됨");
      await list.refetch();
    } catch {
      toast.error("기록 실패");
    }
  }

  async function onDelete(id: string) {
    if (!confirm("이 초안을 삭제할까요?")) return;
    try {
      await premiumApi.remove(id);
      if (openId === id) setOpenId(null);
      await list.refetch();
    } catch {
      toast.error("삭제 실패");
    }
  }

  return (
    <div className="space-y-5">
      {/* 발행 방식 고지 — 스레드 탭과 가장 크게 다른 지점이라 화면 최상단에 박아둔다. */}
      <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-3 text-sm">
        <p className="font-semibold text-amber-300">
          프리미엄콘텐츠는 자동 발행이 없습니다
        </p>
        <p className="mt-1 text-muted-foreground">
          네이버가 발행 API를 제공하지 않습니다. 여기서 초안을 만들고 검수한 뒤{" "}
          <b>전문을 복사</b>해 스튜디오에 직접 붙여넣으세요. 발행 후 URL을 돌려주면
          기록됩니다.
        </p>
        {meta.data?.studio_url && (
          <a
            href={meta.data.studio_url}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-2 inline-block text-xs text-amber-300 underline"
          >
            프리미엄콘텐츠 스튜디오 열기 ↗
          </a>
        )}
      </div>

      {/* 생성 */}
      <div className="rounded-lg border p-4 space-y-3">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div>
            <h2 className="font-semibold">주간 시그널 리포트</h2>
            <p className="text-xs text-muted-foreground mt-0.5">
              업종·규모별·종목 기여·거래대금 귀속을 교차한 컬럼. 목표{" "}
              {targetChars.toLocaleString()}자, 최소 {minChars.toLocaleString()}자.
            </p>
          </div>
          <Button onClick={onGenerate} disabled={busy}>
            {busy ? "생성 중..." : "초안 생성"}
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">
          주간 등락을 산출할 데이터가 부족하면 생성하지 않고 거부합니다(헛글 방지).
        </p>

        {meta.data?.kinds
          ?.filter((k) => !k.ready)
          .map((k) => (
            <p key={k.key} className="text-xs text-muted-foreground/70">
              · {k.label} — {k.desc} <span className="opacity-60">(미구현)</span>
            </p>
          ))}
      </div>

      {/* 상태 필터 */}
      <div className="flex gap-1 flex-wrap">
        {STATUS_FILTERS.map((f) => (
          <button
            key={f.key}
            onClick={() => setStatus(f.key)}
            className={`px-3 py-1 text-xs rounded-full border transition ${
              status === f.key
                ? "border-primary text-primary"
                : "border-white/10 text-muted-foreground hover:text-foreground"
            }`}
          >
            {f.label}
          </button>
        ))}
        <span className="ml-auto self-center text-xs text-muted-foreground">
          {list.data?.count ?? 0}건
        </span>
      </div>

      {/* 목록 */}
      {list.isLoading && (
        <p className="text-sm text-muted-foreground py-8 text-center">불러오는 중...</p>
      )}
      {!list.isLoading && drafts.length === 0 && (
        <p className="text-sm text-muted-foreground py-8 text-center">
          초안이 없습니다. 위에서 생성하세요.
        </p>
      )}

      <div className="space-y-3">
        {drafts.map((d: PremiumDraft) => {
          const open = openId === d.id;
          return (
            <div key={d.id} className="rounded-lg border overflow-hidden">
              <button
                onClick={() => setOpenId(open ? null : d.id)}
                className="w-full text-left p-4 hover:bg-white/[0.02] transition"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span
                        className={`px-2 py-0.5 rounded text-xs ${STATUS_BADGE[d.status]}`}
                      >
                        {STATUS_LABEL[d.status]}
                      </span>
                      {d.week_label && (
                        <span className="text-xs text-muted-foreground">
                          {d.week_label}
                        </span>
                      )}
                      {d.warnings.length > 0 && (
                        <span className="px-2 py-0.5 rounded text-xs bg-amber-500/15 text-amber-300">
                          경고 {d.warnings.length}
                        </span>
                      )}
                    </div>
                    <p className="mt-1.5 font-medium truncate">
                      {d.title || "(제목 없음)"}
                    </p>
                  </div>
                  <div className="shrink-0">
                    <LengthBar
                      chars={d.char_count}
                      min={minChars}
                      target={targetChars}
                    />
                  </div>
                </div>
              </button>

              {open && (
                <div className="border-t p-4 space-y-3">
                  {d.warnings.length > 0 && (
                    <div className="rounded border border-amber-500/30 bg-amber-500/5 p-2 text-xs text-amber-300">
                      {d.warnings.join(" · ")}
                    </div>
                  )}
                  {d.filtered.length > 0 && (
                    <div className="rounded border border-rose-500/30 bg-rose-500/5 p-2 text-xs text-rose-300">
                      금지표현 치환: {d.filtered.join(", ")}
                    </div>
                  )}

                  <Input
                    value={draftTitle}
                    onChange={(e) => setDraftTitle(e.target.value)}
                    placeholder="제목 — 관찰 + 반전 + 구체 수치"
                  />

                  <textarea
                    value={draftBody}
                    onChange={(e) => setDraftBody(e.target.value)}
                    rows={20}
                    className="w-full rounded-md border bg-transparent p-3 text-sm font-mono leading-relaxed"
                    spellCheck={false}
                  />

                  <div className="flex items-center gap-2 flex-wrap">
                    <LengthBar
                      chars={draftBody.length}
                      min={minChars}
                      target={targetChars}
                    />
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => onCopy(draftBody)}
                    >
                      전문 복사
                    </Button>
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() =>
                        onSave(d.id, { title: draftTitle, body: draftBody })
                      }
                    >
                      저장
                    </Button>
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => onSave(d.id, { status: "approved" })}
                    >
                      승인
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => setShowFacts((v) => !v)}
                    >
                      {showFacts ? "원본 수치 닫기" : "원본 수치 대조"}
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="text-rose-400 ml-auto"
                      onClick={() => onDelete(d.id)}
                    >
                      삭제
                    </Button>
                  </div>

                  {/* 검수자가 본문 수치를 스냅샷과 눈으로 대조하는 자리.
                      '미확인 수치' 경고가 떴을 때 여기서 확인한다. */}
                  {showFacts && (
                    <pre className="max-h-72 overflow-auto rounded border bg-black/20 p-3 text-xs whitespace-pre-wrap">
                      {facts || "(원본 수치 없음)"}
                    </pre>
                  )}

                  <div className="rounded border p-3 space-y-2">
                    <p className="text-xs text-muted-foreground">
                      스튜디오에서 발행한 뒤 콘텐츠 URL을 남겨주세요. 나중에 검색 유입을
                      계측하려면 실제 주소가 필요합니다.
                    </p>
                    <div className="flex gap-2">
                      <Input
                        value={publishUrl}
                        onChange={(e) => setPublishUrl(e.target.value)}
                        placeholder="https://contents.premium.naver.com/..."
                      />
                      <Button size="sm" onClick={() => onMarkPublished(d.id)}>
                        발행 기록
                      </Button>
                    </div>
                    {d.published_url && (
                      <a
                        href={d.published_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-sky-400 underline break-all"
                      >
                        {d.published_url}
                      </a>
                    )}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
