"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { toast } from "sonner";

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

const EXPERIENCE_OPTIONS: { id: InvestingExperience; label: string; tag?: string }[] = [
  { id: "beginner", label: "초보 (1년 미만)" },
  { id: "1-5y", label: "1~5년차", tag: "주요 타깃" },
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

export default function OnboardingPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const { profile, onboarded, loading: profileLoading, save } = useUserProfile();

  const [step, setStep] = useState(1);
  const [experience, setExperience] = useState<InvestingExperience>("1-5y");
  const [sectors, setSectors] = useState<string[]>([]);
  const [principleInput, setPrincipleInput] = useState("");
  const [principles, setPrinciples] = useState<string[]>([]);
  const [horizon, setHorizon] = useState<PreferredHorizon>("mid");
  const [holdingPeriod, setHoldingPeriod] = useState<HoldingPeriod>("1-2y");
  const [busy, setBusy] = useState(false);

  // 미인증 → /login. 이미 온보딩 완료 → /dashboard
  useEffect(() => {
    if (authLoading || profileLoading) return;
    if (!user) {
      router.replace("/login");
      return;
    }
    if (onboarded) {
      router.replace("/dashboard");
    }
  }, [user, onboarded, authLoading, profileLoading, router]);

  // 이전에 일부 작성한 적 있으면 복원
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

  const handleFinish = async () => {
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
      toast.success("온보딩 완료. 환영합니다!");
      router.replace("/dashboard");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "저장 실패";
      console.warn("[onboarding] save failed:", err);
      toast.error(msg);
    } finally {
      setBusy(false);
    }
  };

  if (authLoading || profileLoading || !user) {
    return <p className="text-sm text-muted-foreground">로딩 중...</p>;
  }

  return (
    <Card className="w-full max-w-xl">
      <CardContent className="p-8 space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-bold">온보딩</h1>
          <span className="text-sm text-muted-foreground">{step} / 4</span>
        </div>

        {/* progress bar */}
        <div className="h-1 w-full bg-muted rounded">
          <div
            className="h-1 bg-amber-500 rounded transition-all"
            style={{ width: `${(step / 4) * 100}%` }}
          />
        </div>

        {step === 1 && (
          <div className="space-y-4">
            <h2 className="font-semibold">투자 경력은 어떻게 되세요?</h2>
            <div className="space-y-2">
              {EXPERIENCE_OPTIONS.map((opt) => (
                <button
                  key={opt.id}
                  type="button"
                  onClick={() => setExperience(opt.id)}
                  className={`w-full text-left p-3 rounded-md border transition ${
                    experience === opt.id
                      ? "border-amber-500 bg-amber-500/10"
                      : "border-border hover:bg-muted"
                  }`}
                >
                  <span>{opt.label}</span>
                  {opt.tag && (
                    <span className="ml-2 text-xs text-amber-500">{opt.tag}</span>
                  )}
                </button>
              ))}
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-4">
            <h2 className="font-semibold">관심 섹터를 선택해주세요 (복수)</h2>
            <div className="grid grid-cols-3 gap-2">
              {SECTOR_OPTIONS.map((s) => {
                const on = sectors.includes(s);
                return (
                  <button
                    key={s}
                    type="button"
                    onClick={() => toggleSector(s)}
                    className={`p-3 rounded-md border text-sm transition ${
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
            <p className="text-xs text-muted-foreground">
              {sectors.length}개 선택 (최소 0개, 권장 2~3개)
            </p>
          </div>
        )}

        {step === 3 && (
          <div className="space-y-4">
            <h2 className="font-semibold">투자 원칙을 알려주세요</h2>
            <p className="text-sm text-muted-foreground">
              자유 입력. 예: &quot;이미 오른 것은 피한다&quot;, &quot;장기 보유 우선&quot;
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

            <div className="pt-4">
              <h3 className="font-semibold mb-2">보유 기간 선호</h3>
              <div className="grid grid-cols-2 gap-2">
                {HOLDING_PERIOD_OPTIONS.map((opt) => (
                  <button
                    key={opt.id}
                    type="button"
                    onClick={() => setHoldingPeriod(opt.id)}
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
            </div>
          </div>
        )}

        {step === 4 && (
          <div className="space-y-4">
            <h2 className="font-semibold">주로 어느 기간 관점으로 보시나요?</h2>
            <p className="text-sm text-muted-foreground">
              기본 시계일 뿐, 분석 화면에서 종목마다 자유롭게 바꿀 수 있습니다.
            </p>
            <div className="space-y-2">
              {HORIZON_OPTIONS.map((h) => (
                <button
                  key={h.id}
                  type="button"
                  onClick={() => setHorizon(h.id)}
                  className={`w-full text-left p-4 rounded-md border transition ${
                    horizon === h.id
                      ? "border-amber-500 bg-amber-500/10"
                      : "border-border hover:bg-muted"
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <span className="text-2xl">{h.icon}</span>
                    <div>
                      <div className="font-semibold">{h.name}</div>
                      <div className="text-xs text-muted-foreground">{h.tagline}</div>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="flex justify-between pt-2">
          <Button
            type="button"
            variant="outline"
            disabled={step === 1 || busy}
            onClick={() => setStep((s) => Math.max(1, s - 1))}
          >
            이전
          </Button>
          {step < 4 ? (
            <Button
              type="button"
              onClick={() => setStep((s) => Math.min(4, s + 1))}
              disabled={busy}
            >
              다음
            </Button>
          ) : (
            <Button type="button" onClick={handleFinish} disabled={busy}>
              {busy ? "저장 중..." : "시작하기"}
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
