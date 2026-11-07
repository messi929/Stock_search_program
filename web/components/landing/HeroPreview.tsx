/**
 * 랜딩 Hero 제품 미리보기 — 실제 분석 결과 화면을 본뜬 정적 목업.
 *
 * 목적: "뭘 해주는지"를 텍스트가 아닌 화면으로 즉시 전달(신뢰도↑).
 * LEGAL: 목업 카피도 권유성 단어 금지 — "관찰 구간/참고/분석 결과"만 사용.
 * 색상: KR 종목이라 상승=빨강(한국식).
 */
import { ShieldCheck, Target } from "lucide-react";

// [시가, 고가, 저가, 종가] 예시값. 값이 작을수록 위쪽이다.
const CANDLES = [
  [44, 40, 50, 46], [46, 38, 48, 40], [40, 36, 46, 44], [44, 30, 46, 32], [32, 28, 38, 36],
  [36, 24, 38, 26], [26, 22, 32, 30], [30, 16, 32, 18], [18, 14, 24, 22], [22, 8, 24, 10],
  [10, 6, 16, 14], [14, 4, 16, 6],
];

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-muted px-3 py-2">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-0.5 font-semibold tabular-nums">{value}</p>
    </div>
  );
}

export function HeroPreview() {
  return (
    <div className="rounded-2xl border bg-card p-5 shadow-xl space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-lg font-bold">삼성전자</p>
          <p className="text-xs text-muted-foreground tabular-nums">005930 · KOSPI</p>
        </div>
        <span className="inline-flex items-center gap-1 whitespace-nowrap rounded-md bg-success/10 px-2 py-1 text-xs font-medium text-success">
          <ShieldCheck aria-hidden="true" className="size-3.5" />
          수치 검증 완료
        </span>
      </div>

      <svg viewBox="0 0 240 56" className="h-24 w-full" role="img" aria-label="예시 주가 차트">
        {CANDLES.map(([open, high, low, close], i) => {
          const x = 10 + i * 19;
          const rising = close < open;
          return (
            <g key={x} className={rising ? "text-up" : "text-down"}>
              <line x1={x} x2={x} y1={high} y2={low} stroke="currentColor" strokeWidth="1" />
              <rect
                x={x - 5}
                y={Math.min(open, close)}
                width="10"
                height={Math.max(Math.abs(open - close), 1.5)}
                rx="1"
                fill="currentColor"
              />
            </g>
          );
        })}
      </svg>

      <div className="grid grid-cols-3 gap-2">
        <Stat label="PER" value="14.2배" />
        <Stat label="PBR" value="1.3배" />
        <Stat label="ROE" value="9.1%" />
      </div>

      <div className="rounded-xl border p-3.5">
        <p className="flex items-center gap-1.5 text-sm font-semibold">
          <Target aria-hidden="true" className="size-4 text-primary" />
          AI 종합 분석
          <span className="text-xs font-normal text-muted-foreground">· 중기 관점</span>
        </p>
        <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">
          반도체 업황 회복 국면에서 환율 변동성을 핵심 관찰 변수로 봅니다.
          수치마다 쉬운 설명을 함께 보여드려요.
        </p>
      </div>

      <p className="text-xs text-muted-foreground">
        예시 화면입니다. 투자 권유가 아닌 정보 제공이며, 판단은 사용자 책임입니다.
      </p>
    </div>
  );
}
