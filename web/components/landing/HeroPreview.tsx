/**
 * 랜딩 Hero 제품 미리보기 — 실제 분석 결과 화면을 본뜬 정적 목업.
 *
 * 목적: "뭘 해주는지"를 텍스트가 아닌 화면으로 즉시 전달(신뢰도↑).
 * LEGAL: 목업 카피도 권유성 단어 금지 — "관찰 구간/참고/분석 결과"만 사용.
 * 색상: KR 종목이라 상승=빨강(한국식).
 */
export function HeroPreview() {
  return (
    <div className="relative">
      {/* 카드 본체 */}
      <div className="rounded-2xl border bg-card shadow-xl overflow-hidden">
        {/* 상단 바 (브라우저 크롬 느낌) */}
        <div className="flex items-center gap-1.5 px-4 py-2.5 border-b bg-muted/40">
          <span className="size-2.5 rounded-full bg-rose-400/70" />
          <span className="size-2.5 rounded-full bg-amber-400/70" />
          <span className="size-2.5 rounded-full bg-emerald-400/70" />
          <span className="ml-3 text-xs text-muted-foreground font-mono">
            axislytics.com/analyze/005930
          </span>
        </div>

        <div className="p-5 space-y-4">
          {/* 종목 헤더 */}
          <div className="flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2">
                <span className="text-lg font-bold font-mono">005930</span>
                <span className="text-xs px-2 py-0.5 rounded-full border bg-rose-500/10 text-rose-600 border-rose-500/30">
                  🇰🇷 KOSPI
                </span>
              </div>
              <p className="text-sm text-muted-foreground mt-0.5">
                삼성전자 · 360,500원
                <span className="ml-1 text-xs font-medium text-rose-500">+0.83%</span>
              </p>
            </div>
            <span className="text-xs px-2 py-1 rounded-md bg-emerald-500/10 text-emerald-600 font-medium whitespace-nowrap">
              ✅ 실시간 검증
            </span>
          </div>

          {/* Strategist 요약 카드 */}
          <div className="rounded-lg border bg-background p-3.5 space-y-1.5">
            <div className="flex items-center gap-1.5 text-sm font-semibold">
              <span>🎯</span>
              <span>종합 전략</span>
              <span className="text-xs font-normal text-muted-foreground">
                · 중기 관점
              </span>
            </div>
            <p className="text-sm text-muted-foreground leading-relaxed">
              반도체 업황 회복 국면에서 환율 변동성을 핵심 관찰 구간으로 봅니다.
              분할 접근 시 MA60(약 31.2만) 부근이 참고 지지대로 거론됩니다.
            </p>
          </div>

          {/* 검증 디테일 */}
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span className="text-emerald-600">✅ 검증 통과</span>
            <span>·</span>
            <span>현재가·PER 14.2·PBR 1.3·ROE 9.1% 재확인</span>
            <span>·</span>
            <span>신선도 2.1%</span>
          </div>

          {/* 4 에이전트 칩 */}
          <div className="flex flex-wrap gap-1.5 pt-1">
            {[
              { icon: "🔍", label: "Research" },
              { icon: "🧮", label: "Analyst" },
              { icon: "🛡️", label: "Validator" },
              { icon: "🎯", label: "Strategist" },
            ].map((a) => (
              <span
                key={a.label}
                className="text-xs px-2 py-1 rounded-md bg-muted text-muted-foreground"
              >
                {a.icon} {a.label}
              </span>
            ))}
          </div>

          {/* 면책 */}
          <p className="text-[10px] text-muted-foreground/80 pt-1 border-t">
            📌 예시 화면입니다. 투자 권유가 아닌 정보 제공이며, 판단은 사용자 책임입니다.
          </p>
        </div>
      </div>

      {/* 장식 글로우 */}
      <div
        className="absolute -inset-4 -z-10 rounded-3xl bg-gradient-to-tr from-amber-500/10 via-transparent to-sky-500/10 blur-2xl"
        aria-hidden="true"
      />
    </div>
  );
}
