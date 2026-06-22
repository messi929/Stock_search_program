"use client";

/**
 * /settings/profile — 투자 프로필 편집 (단일 폼).
 *
 * 온보딩(/onboarding)은 4-step wizard로 신규 가입자를 안내. 편집은 한 번에 보고
 * 바꾸길 원하므로 단일 폼이 적합. 옵션 상수는 온보딩과 일관성 유지.
 */
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { SubscriptionSection } from "@/components/settings/SubscriptionSection";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/hooks/useAuth";
import {
  useUserProfile,
  type AxisProfile,
  type HoldingPeriod,
  type InvestingExperience,
  type PreferredHorizon,
} from "@/hooks/useUserProfile";
import { apiCall } from "@/lib/api";
import { signOut } from "@/lib/auth-actions";

// 온보딩과 동일 구성 — 추후 변경 시 양쪽 동기화 필요.
const EXPERIENCE_OPTIONS: { id: InvestingExperience; label: string }[] = [
  { id: "beginner", label: "초보 (1년 미만)" },
  { id: "1-5y", label: "1~5년차" },
  { id: "5y+", label: "5년 이상" },
];

const SECTOR_OPTIONS = [
  "AI/반도체",
  "2차전지",
  "바이오",
  "로봇/자동화",
  "원전/에너지",
  "조선/방산",
  "K-푸드",
  "금융",
  "리츠/부동산",
];

const HOLDING_PERIOD_OPTIONS: { id: HoldingPeriod; label: string }[] = [
  { id: "1m", label: "1개월 이내" },
  { id: "6m", label: "6개월" },
  { id: "1-2y", label: "1~2년" },
  { id: "3y+", label: "3년 이상" },
];

const HORIZON_OPTIONS: { id: PreferredHorizon; icon: string; name: string; tagline: string }[] = [
  { id: "short", icon: "⚡", name: "단기", tagline: "수일~1개월 · 추세·거래량·수급" },
  { id: "short_mid", icon: "📈", name: "단중기", tagline: "1~3개월 · 분기 실적 모멘텀 + 기술" },
  { id: "mid", icon: "⚖️", name: "중기", tagline: "3개월~1년 · 밸류·성장 균형" },
  { id: "long", icon: "🏔", name: "장기", tagline: "1년+ · 펀더멘털·해자·매크로 사이클" },
];

export default function SettingsProfilePage() {
  const router = useRouter();
  const { user } = useAuth();
  const { profile, save, loading } = useUserProfile();

  const [experience, setExperience] = useState<InvestingExperience>("1-5y");
  const [holdingPeriod, setHoldingPeriod] = useState<HoldingPeriod>("1-2y");
  const [sectors, setSectors] = useState<string[]>([]);
  const [principleInput, setPrincipleInput] = useState("");
  const [principles, setPrinciples] = useState<string[]>([]);
  const [horizon, setHorizon] = useState<PreferredHorizon>("mid");
  const [busy, setBusy] = useState(false);

  // 프로필 로드 시 폼 초기화
  useEffect(() => {
    if (!profile) return;
    if (profile.investing_experience) setExperience(profile.investing_experience);
    if (profile.holding_period) setHoldingPeriod(profile.holding_period);
    if (profile.interested_sectors) setSectors(profile.interested_sectors);
    if (profile.investment_principles) setPrinciples(profile.investment_principles);
    if (profile.preferred_horizon) setHorizon(profile.preferred_horizon);
  }, [profile]);

  const toggleSector = (s: string) =>
    setSectors((prev) => (prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s]));

  const addPrinciple = () => {
    const v = principleInput.trim();
    if (!v) return;
    if (principles.length >= 5) {
      toast.warning("최대 5개까지 입력 가능합니다.");
      return;
    }
    setPrinciples((prev) => [...prev, v]);
    setPrincipleInput("");
  };

  const removePrinciple = (idx: number) =>
    setPrinciples((prev) => prev.filter((_, i) => i !== idx));

  const handleSave = async () => {
    setBusy(true);
    try {
      const next: AxisProfile = {
        investing_experience: experience,
        holding_period: holdingPeriod,
        interested_sectors: sectors,
        investment_principles: principles,
        preferred_horizon: horizon,
      };
      await save(next);
      toast.success("프로필 저장됨");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "저장 실패";
      toast.error(msg);
    } finally {
      setBusy(false);
    }
  };

  if (loading || !user) {
    return <p className="text-sm text-muted-foreground">로딩 중...</p>;
  }

  return (
    <div className="space-y-6 max-w-3xl">
      <header className="flex items-start justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-2xl font-bold">⚙️ 설정 · 투자 프로필</h1>
          <p className="text-sm text-muted-foreground mt-1">
            분석 결과 톤·가중치에 반영됩니다. 언제든 바꿀 수 있어요.
          </p>
        </div>
        <a
          href="/settings/notifications"
          className="text-xs underline text-muted-foreground hover:text-foreground transition"
        >
          🔔 알림 설정 →
        </a>
      </header>

      {/* 구독 관리 (Lemon Squeezy) */}
      <SubscriptionSection />

      {/* 투자 경력 */}
      <Card>
        <CardContent className="p-5 space-y-3">
          <h2 className="font-semibold">투자 경력</h2>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
            {EXPERIENCE_OPTIONS.map((opt) => (
              <button
                key={opt.id}
                type="button"
                onClick={() => setExperience(opt.id)}
                aria-pressed={experience === opt.id}
                className={`p-3 rounded-md border text-sm transition ${
                  experience === opt.id
                    ? "border-amber-500 bg-amber-500/10"
                    : "border-border hover:bg-muted"
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* 보유 기간 */}
      <Card>
        <CardContent className="p-5 space-y-3">
          <h2 className="font-semibold">보유 기간 선호</h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            {HOLDING_PERIOD_OPTIONS.map((opt) => (
              <button
                key={opt.id}
                type="button"
                onClick={() => setHoldingPeriod(opt.id)}
                aria-pressed={holdingPeriod === opt.id}
                className={`p-2 rounded-md border text-sm transition ${
                  holdingPeriod === opt.id
                    ? "border-amber-500 bg-amber-500/10"
                    : "border-border hover:bg-muted"
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* 관심 섹터 */}
      <Card>
        <CardContent className="p-5 space-y-3">
          <h2 className="font-semibold">관심 섹터 (복수)</h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            {SECTOR_OPTIONS.map((s) => {
              const on = sectors.includes(s);
              return (
                <button
                  key={s}
                  type="button"
                  onClick={() => toggleSector(s)}
                  aria-pressed={on}
                  className={`p-2 rounded-md border text-sm transition ${
                    on
                      ? "border-amber-500 bg-amber-500/10"
                      : "border-border hover:bg-muted"
                  }`}
                >
                  {on ? "✓ " : ""}
                  {s}
                </button>
              );
            })}
          </div>
          <p className="text-xs text-muted-foreground">{sectors.length}개 선택</p>
        </CardContent>
      </Card>

      {/* 투자 원칙 */}
      <Card>
        <CardContent className="p-5 space-y-3">
          <h2 className="font-semibold">투자 원칙</h2>
          <p className="text-xs text-muted-foreground">
            예: &quot;이미 오른 것은 피한다&quot;, &quot;장기 보유 우선&quot; (최대 5개)
          </p>
          <div className="flex gap-2">
            <Input
              value={principleInput}
              onChange={(e) => setPrincipleInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  addPrinciple();
                }
              }}
              placeholder="투자 원칙 입력..."
            />
            <Button type="button" onClick={addPrinciple} variant="outline">
              추가
            </Button>
          </div>
          {principles.length > 0 && (
            <ul className="space-y-1">
              {principles.map((p, i) => (
                <li
                  key={`${p}-${i}`}
                  className="flex items-center justify-between p-2 rounded-md bg-muted/50"
                >
                  <span className="text-sm">• {p}</span>
                  <button
                    type="button"
                    onClick={() => removePrinciple(i)}
                    className="text-xs text-muted-foreground hover:text-destructive"
                  >
                    삭제
                  </button>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      {/* 선호 시계(투자 시간축) */}
      <Card>
        <CardContent className="p-5 space-y-3">
          <h2 className="font-semibold">선호 시계 (투자 시간축)</h2>
          <p className="text-xs text-muted-foreground">
            기본값일 뿐 분석 화면에서 종목마다 자유롭게 바꿀 수 있습니다.
          </p>
          <div className="space-y-2">
            {HORIZON_OPTIONS.map((h) => (
              <button
                key={h.id}
                type="button"
                onClick={() => setHorizon(h.id)}
                aria-pressed={horizon === h.id}
                className={`w-full text-left p-3 rounded-md border transition ${
                  horizon === h.id
                    ? "border-amber-500 bg-amber-500/10"
                    : "border-border hover:bg-muted"
                }`}
              >
                <div className="flex items-center gap-3">
                  <span className="text-2xl">{h.icon}</span>
                  <div>
                    <div className="font-semibold text-sm">{h.name}</div>
                    <div className="text-xs text-muted-foreground">{h.tagline}</div>
                  </div>
                </div>
              </button>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* 저장 */}
      <div className="flex flex-col sm:flex-row gap-2 sm:justify-end">
        <Button
          type="button"
          variant="outline"
          onClick={() => router.push("/dashboard")}
          disabled={busy}
        >
          취소
        </Button>
        <Button type="button" onClick={handleSave} disabled={busy}>
          {busy ? "저장 중..." : "💾 저장"}
        </Button>
      </div>

      {/* 위험 영역 — 계정 영구 삭제 (개인정보 보호 권리) */}
      <DangerZone />
    </div>
  );
}

function DangerZone() {
  const router = useRouter();
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);

  const handleDelete = async () => {
    const ok = window.confirm(
      "정말 계정을 영구 삭제하시겠어요?\n\n· 프로필·관심 종목·진입선·구독 정보가 모두 삭제됩니다.\n· 되돌릴 수 없습니다.\n· 같은 Google 계정으로 다시 가입하실 수 있습니다.",
    );
    if (!ok) return;
    setBusy(true);
    try {
      await apiCall<{ ok: boolean }>("/api/user/account", { method: "DELETE" });
      await signOut();
      toast.success("계정이 삭제되었습니다.");
      router.replace("/");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "삭제 실패";
      toast.error(msg);
      setBusy(false);
    }
  };

  return (
    <Card className="border-destructive/40 bg-destructive/5 mt-8">
      <CardContent className="p-5 space-y-3">
        <h2 className="font-semibold text-destructive">⚠️ 위험 영역</h2>
        <p className="text-xs text-muted-foreground leading-relaxed">
          계정 영구 삭제 — Firestore 사용자 데이터(프로필·관심종목·진입선·티어)
          전체 + Firebase 인증 계정이 즉시 삭제됩니다. 되돌릴 수 없습니다.
          같은 Google 계정으로 새로 가입은 가능합니다.
        </p>
        {!confirming ? (
          <Button
            type="button"
            variant="outline"
            className="border-destructive/50 text-destructive hover:bg-destructive/10"
            onClick={() => setConfirming(true)}
          >
            계정 삭제 시작
          </Button>
        ) : (
          <div className="flex flex-col sm:flex-row gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => setConfirming(false)}
              disabled={busy}
            >
              취소
            </Button>
            <Button
              type="button"
              onClick={handleDelete}
              disabled={busy}
              className="bg-destructive hover:bg-destructive/90"
            >
              {busy ? "삭제 중..." : "🗑 영구 삭제 확인"}
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
