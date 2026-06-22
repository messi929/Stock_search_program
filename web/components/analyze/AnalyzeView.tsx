"use client";

/**
 * 분석 페이지 클라이언트 컨테이너 — 투자 시계 기반 SSE 스트리밍 오케스트레이션.
 *
 * UX 흐름:
 *  1. 종목 진입 → HorizonChooser로 투자 시계(단기/단중기/중기/장기)를 선택 (자동 실행 X)
 *  2. "분석 시작" → 선택한 시계로 1회 실행 (불필요한 과금 방지)
 *  3. 결과 후 HorizonSwitch로 다른 시계 재실행 가능
 *
 * 시계 기반 분석은 항상 strategist 흐름(4노드):
 *   start → research/analyst → validator → strategist → complete
 *
 * 페르소나(블랙록/ARK/그레이엄)는 2026-06-22 시계(horizon)로 전면 대체됨. 데이터 노드
 * (event/macro/korean)는 내부 제공자로만 잔존(UI 미노출) — 카드 렌더링은 휴면 폴백.
 */
import Link from "next/link";
import { toast } from "sonner";

import { AddToWatchlistButton } from "@/components/analyze/AddToWatchlistButton";
import { AnalystCard } from "@/components/analyze/AnalystCard";
import { EventAnalystCard } from "@/components/analyze/EventAnalystCard";
import { InstantCard } from "@/components/analyze/InstantCard";
import { KisCandleChart } from "@/components/analyze/KisCandleChart";
import { KisInvestorFlow } from "@/components/analyze/KisInvestorFlow";
import { KisOrderbook } from "@/components/analyze/KisOrderbook";
import { UsCandleChart } from "@/components/analyze/UsCandleChart";
import { KoreanSpecialistCard } from "@/components/analyze/KoreanSpecialistCard";
import { MacroPmCard } from "@/components/analyze/MacroPmCard";
import { HorizonChooser, HorizonSwitch } from "@/components/analyze/HorizonChooser";
import { PreviousAnalysisCard } from "@/components/analyze/PreviousAnalysisCard";
import { ResearchCard } from "@/components/analyze/ResearchCard";
import { SaveEntryPointsButton } from "@/components/analyze/SaveEntryPointsButton";
import { StrategistCard } from "@/components/analyze/StrategistCard";
import { ValidateButton } from "@/components/analyze/ValidateButton";
import { ValidatorCard } from "@/components/analyze/ValidatorCard";
import { Disclaimer } from "@/components/legal/Disclaimer";
import { Card, CardContent } from "@/components/ui/card";
import { useKisPrice } from "@/hooks/useKisPrice";
import { useStockSearch } from "@/hooks/useStockSearch";
import { useUserProfile } from "@/hooks/useUserProfile";
import {
  useAnalysisStore,
  type DataDriven,
  type DataDrivenStatus,
  type StrategistFlow,
  type StrategistStatus,
} from "@/store/analysisStore";
import { useHorizonStore } from "@/store/horizonStore";
import {
  HORIZON_BY_ID,
  type HorizonId,
  type PersonaId,
} from "@/types/persona";

// 시계 기반 분석은 페르소나와 무관하게 strategist 흐름으로 실행된다.
// run.persona는 형식상 필요하므로 중립적인 strategist 페르소나를 캐리어로 둔다.
const HORIZON_CARRIER_PERSONA: PersonaId = "blackrock";

const EMPTY_FLOW: StrategistFlow = {
  research: null,
  analyst: null,
  validator: null,
  strategist: null,
};
const PENDING_STRATEGIST: StrategistStatus = {
  research: "pending",
  analyst: "pending",
  validator: "pending",
  strategist: "pending",
};
const EMPTY_DATA: DataDriven = { event: null, macro: null, korean: null };
const PENDING_DATA: DataDrivenStatus = {
  event: "pending",
  macro: "pending",
  korean: "pending",
};

export function AnalyzeView({ ticker }: { ticker: string }) {
  const storeHorizon = useHorizonStore((s) => s.current);
  const setStoreHorizon = useHorizonStore((s) => s.setHorizon);
  const { profile } = useUserProfile();

  // 분석 상태는 전역 store에 보관 — 화면을 떠나도 SSE가 백그라운드로 계속 진행되고
  // 재진입 시 그대로 복원된다(언마운트로 중단하지 않음). key=ticker.
  const run = useAnalysisStore((s) => s.runs[ticker.toUpperCase()]);
  const startRun = useAnalysisStore((s) => s.start);
  const setValidatorInStore = useAnalysisStore((s) => s.setValidator);

  // runPersona: 실행 중/완료된 페르소나. null이면 미선택 → 선택 화면 표시(자동 실행 X).
  const runPersona = run?.persona ?? null;
  const isStrategist = run?.isStrategist ?? false;

  // 분석이 끝나기 전(~10s)에도 종목명·현재가를 노출 — Analyst가 채워주기 전 fallback.
  // 데이터 페르소나 흐름(이벤트/매크로/한국)은 Analyst를 안 돌리므로 이 fallback이 영구.
  const { data: stockSearch } = useStockSearch(ticker, 1);
  const earlyStock = stockSearch?.stocks?.find(
    (s) => s.ticker === ticker.toUpperCase(),
  );
  const earlyName = earlyStock?.name ?? null;
  const earlyPrice = earlyStock?.close ?? null;

  // KIS 라이브 가격 — KR 종목만, 백엔드 5초 캐시. 분석 미완료 단계에서 헤더에 노출.
  const { data: kisPriceData } = useKisPrice(ticker);
  const kisPrice = kisPriceData?.data?.stck_prpr
    ? Number(kisPriceData.data.stck_prpr)
    : null;
  const kisChangePct = kisPriceData?.data?.prdy_ctrt
    ? Number(kisPriceData.data.prdy_ctrt)
    : null;

  // store run에서 파생 (run 없으면 빈/대기 fallback — 선택 화면 단계).
  const strategistFlow = run?.strategistFlow ?? EMPTY_FLOW;
  const strategistStatus = run?.strategistStatus ?? PENDING_STRATEGIST;
  const dataDriven = run?.dataDriven ?? EMPTY_DATA;
  const dataDrivenStatus = run?.dataDrivenStatus ?? PENDING_DATA;
  const overallElapsed = run?.elapsed ?? null;
  const likelyCached = run?.likelyCached ?? false;
  const runError = run?.error ?? null;
  // 한도/잠금 에러 시 업그레이드 CTA 링크 (백엔드 upgrade_url; Pro 공정사용 한도는 null)
  const runUpgradeUrl = run?.upgradeUrl ?? null;

  // 사용자 프로필 페이로드 — 분석 요청 본문에 동봉(시계/페르소나 공통).
  const userProfilePayload = () =>
    profile
      ? {
          investing_experience: profile.investing_experience,
          holding_period: profile.holding_period,
          volatility_tolerance: profile.volatility_tolerance,
          interested_sectors: profile.interested_sectors,
          investment_principles: profile.investment_principles,
        }
      : null;

  // 시계 기반 분석 시작(chooser → 의도적 1회) — store가 SSE를 백그라운드로 실행.
  const startHorizon = (horizon: HorizonId) => {
    setStoreHorizon(horizon);
    startRun(
      ticker,
      HORIZON_CARRIER_PERSONA,
      userProfilePayload(),
      earlyName ?? "",
      horizon,
    );
  };

  // 분석 결과 공유 — 현재 URL 클립보드 복사 + 토스트.
  const handleShare = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      toast.success("분석 링크가 복사되었습니다");
    } catch {
      toast.error("링크 복사 실패");
    }
  };

  // HorizonSwitch 클릭(결과 후 다른 시계로 재실행) — 비용 발생 인지 강제.
  // 같은 시계는 no-op. 사용자 지갑 보호용 confirm.
  const switchHorizon = (horizon: HorizonId) => {
    if (horizon === run?.horizon) return;
    const meta = HORIZON_BY_ID[horizon];
    const ok = window.confirm(
      `'${meta.name}' 시계로 다시 분석합니다.\n새 분석 1회 비용이 발생합니다. 진행하시겠어요?`,
    );
    if (ok) startHorizon(horizon);
  };

  // 종목명 표시 — Strategist 흐름은 analyst가 채워줌, 데이터 페르소나는 earlyName fallback
  const displayName = strategistFlow.analyst?.name ?? earlyName;
  // 가격 우선순위: Analyst 결과 > KIS 라이브(KR) > 스크리너 캐시 fallback.
  // KIS는 5초 백엔드 캐시라 거의 실시간. 분석 진행 중에도 헤더가 갱신됨.
  const displayPrice =
    strategistFlow.analyst?.technical.current_price ?? kisPrice ?? earlyPrice;
  // 등락률 — KIS 라이브가 있을 때만 (Analyst는 등락률을 별도 필드로 안 줌)
  const displayChangePct =
    !strategistFlow.analyst && kisChangePct != null ? kisChangePct : null;
  // 데이터 갱신 시각 — Analyst 결과 있을 때만 (KR 스크리너 updated_at).
  const displayUpdatedAt = strategistFlow.analyst?.timestamp ?? null;

  // 시장 구분 — 6자리 숫자 = KR, 그 외 = US. analyst 결과에 KOSPI/KOSDAQ/NASDAQ 등
  // 실제 거래소가 있으면 사용, 없으면 국가만 표시.
  const isKR = /^\d{6}$/.test(ticker);
  const analystMarket = strategistFlow.analyst?.market?.toUpperCase?.() ?? "";
  const exchangeLabel = analystMarket.includes("KOSPI")
    ? "KOSPI"
    : analystMarket.includes("KOSDAQ")
      ? "KOSDAQ"
      : analystMarket.includes("NASDAQ")
        ? "NASDAQ"
        : analystMarket.includes("NYSE")
          ? "NYSE"
          : isKR
            ? "한국 시장"
            : "미국 시장";
  const marketFlag = isKR ? "🇰🇷" : "🇺🇸";

  return (
    <div className="space-y-6 max-w-5xl">
      {/* Header */}
      <header className="space-y-4">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h1 className="text-2xl font-bold font-mono">{ticker}</h1>
              <span
                className={`text-xs px-2 py-0.5 rounded-full border font-medium ${
                  isKR
                    ? "bg-rose-500/10 text-rose-700 border-rose-500/30"
                    : "bg-sky-500/10 text-sky-700 border-sky-500/30"
                }`}
                title={isKR ? "한국 시장 — 일별 외국인·기관 수급, Korean Specialist 페르소나 적용" : "미국 시장 — 일별 수급 데이터 없음, Korean Specialist 비활성"}
              >
                {marketFlag} {exchangeLabel}
              </span>
            </div>
            {displayName ? (
              <p className="text-sm text-muted-foreground mt-1">
                {displayName}
                {displayPrice != null
                  ? ` · ${displayPrice.toLocaleString()}${isKR ? "원" : "달러"}`
                  : ""}
                {displayChangePct != null && (
                  <span
                    className={`ml-1 text-xs font-medium ${
                      displayChangePct > 0
                        ? "text-red-500"
                        : displayChangePct < 0
                          ? "text-blue-500"
                          : "text-gray-500"
                    }`}
                    title="KIS 라이브 등락률 (백엔드 5초 캐시)"
                  >
                    {displayChangePct > 0 ? "+" : ""}
                    {displayChangePct.toFixed(2)}%
                  </span>
                )}
                {displayUpdatedAt && (
                  <span className="ml-2 text-[10px]" title="Analyst 분석 시점">
                    ⏱ {new Date(displayUpdatedAt).toLocaleString("ko-KR", {
                      month: "numeric",
                      day: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </span>
                )}
              </p>
            ) : null}
          </div>
          {/* 결과 단계에서만 시계 전환 노출(재실행). 선택 단계에선 chooser가 담당. */}
          {run?.horizon ? (
            <HorizonSwitch current={run.horizon} onSelect={switchHorizon} />
          ) : null}
        </div>

        {/* Action buttons — 결과 단계 + Strategist 흐름에서만 */}
        {runPersona && isStrategist && (
          <div className="flex flex-wrap items-start gap-2">
            <AddToWatchlistButton ticker={ticker} />
            <ValidateButton
              ticker={ticker}
              research={strategistFlow.research}
              analyst={strategistFlow.analyst}
              onResult={(v) => setValidatorInStore(ticker, v)}
            />
            <SaveEntryPointsButton
              ticker={ticker}
              strategist={strategistFlow.strategist}
            />
            <button
              type="button"
              onClick={handleShare}
              title="현재 분석 페이지 링크를 클립보드에 복사"
              className="inline-flex items-center h-9 px-3 rounded-md border text-sm hover:bg-muted/50 transition"
            >
              🔗 공유
            </button>
          </div>
        )}
        {runPersona && !isStrategist && (
          <div className="flex flex-wrap items-start gap-2">
            <AddToWatchlistButton ticker={ticker} />
            <button
              type="button"
              onClick={handleShare}
              title="현재 분석 페이지 링크를 클립보드에 복사"
              className="inline-flex items-center h-9 px-3 rounded-md border text-sm hover:bg-muted/50 transition"
            >
              🔗 공유
            </button>
          </div>
        )}
      </header>

      {/* KIS 라이브 시장 데이터 — KR 종목만, AI 분석 진행 중에도 즉시 노출 */}
      {isKR && (
        <section className="space-y-4">
          <KisCandleChart ticker={ticker} />
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <KisOrderbook ticker={ticker} />
            <KisInvestorFlow ticker={ticker} />
          </div>
        </section>
      )}

      {/* US 종목 — 일봉 차트 (yfinance). 호가/투자자흐름은 US 데이터 없음 */}
      {!isKR && (
        <section className="space-y-4">
          <UsCandleChart ticker={ticker} />
        </section>
      )}

      {/* 이전 분석 핵심 — 차트 하단. 직전 strategist 분석의 진입/손절을 참고로 표시.
          직전 분석이 없으면 렌더 안 함. 그 아래에서 새 분석 진행. */}
      <PreviousAnalysisCard
        ticker={ticker}
        currentPrice={displayPrice}
        isKR={isKR}
      />

      {/* 선택 단계 — 투자 시계 선택 (자동 실행 없음) */}
      {!runPersona ? (
        <Card>
          <CardContent className="p-5">
            <HorizonChooser
              defaultHorizon={storeHorizon}
              onStart={startHorizon}
            />
          </CardContent>
        </Card>
      ) : (
        <>
          {/* Overall status */}
          {runError ? (
            <Card>
              <CardContent className="p-4 text-sm text-destructive space-y-2">
                <p>⚠️ {runError}</p>
                {runUpgradeUrl && (
                  <Link
                    href={runUpgradeUrl}
                    className="inline-flex items-center rounded-md bg-amber-500/90 px-3 py-1.5 text-xs font-medium text-white hover:bg-amber-500"
                  >
                    Pro 플랜 보기 →
                  </Link>
                )}
              </CardContent>
            </Card>
          ) : overallElapsed !== null ? (
            <p className="text-xs text-muted-foreground">
              전체 분석 완료 ({overallElapsed}초)
              {likelyCached && (
                <span
                  className="ml-2 px-1.5 py-0.5 rounded bg-sky-500/15 text-sky-700 text-[10px] font-medium"
                  title="이전 분석 결과가 캐시돼 즉시 응답됨 (Claude API 비호출, 비용 없음)"
                >
                  ⚡ 캐시된 결과
                </span>
              )}
            </p>
          ) : (
            <p className="text-xs text-muted-foreground">
              분석 진행 중... (보통 30~90초, 캐시 시 즉시)
            </p>
          )}

          {/* 페르소나 그룹별 카드 분기 */}
          {isStrategist ? (
            <>
              {/* 빠른 참고 — 정밀 종합(Strategist) 도착 전까지만 노출 */}
              {run?.instantSnapshot && strategistStatus.strategist !== "done" && (
                <InstantCard
                  snapshot={run.instantSnapshot}
                  summary={run.instantSummary}
                />
              )}
              <StrategistCard
                data={strategistFlow.strategist}
                status={strategistStatus.strategist}
                currentPrice={strategistFlow.analyst?.technical.current_price ?? null}
                ticker={ticker}
              />
              <ValidatorCard
                data={strategistFlow.validator}
                status={strategistStatus.validator}
              />
              <AnalystCard
                data={strategistFlow.analyst}
                status={strategistStatus.analyst}
              />
              <ResearchCard
                data={strategistFlow.research}
                status={strategistStatus.research}
              />
            </>
          ) : runPersona === "event" ? (
            <EventAnalystCard data={dataDriven.event} status={dataDrivenStatus.event} />
          ) : runPersona === "macro" ? (
            <MacroPmCard data={dataDriven.macro} status={dataDrivenStatus.macro} />
          ) : runPersona === "korean" ? (
            <KoreanSpecialistCard
              data={dataDriven.korean}
              status={dataDrivenStatus.korean}
            />
          ) : null}
        </>
      )}

      <Disclaimer />
    </div>
  );
}
