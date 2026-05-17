/**
 * 모든 분석/추천 응답 하단에 자동 노출되는 면책 컴포넌트.
 * docs/axis/LEGAL.md 원칙에 따라 모든 분석 페이지/카드에 필수.
 *
 * lang="both"는 LS·Paddle 등 해외 결제 심사자가 영문 면책을 확인할 수 있도록
 * `/pricing` 등 결제 진입점에 사용한다.
 */
type Lang = "ko" | "en" | "both";

interface DisclaimerProps {
  compact?: boolean;
  lang?: Lang;
}

export function Disclaimer({ compact = false, lang = "ko" }: DisclaimerProps) {
  if (compact) {
    return (
      <div className="text-xs text-muted-foreground border-t pt-2 mt-4 space-y-1">
        {(lang === "ko" || lang === "both") && (
          <p>
            ⚠️ 본 분석은 투자 권유가 아닌 정보 제공입니다. 최종 판단은 사용자
            본인의 책임이며, Axis는 투자자문업 면허가 없습니다.
          </p>
        )}
        {(lang === "en" || lang === "both") && (
          <p>
            ⚠️ This is information only, not investment advice. Axis holds no
            investment advisory license; all decisions are your own
            responsibility.
          </p>
        )}
      </div>
    );
  }
  return (
    <div className="text-xs text-muted-foreground border-t pt-3 mt-6 space-y-3">
      {(lang === "ko" || lang === "both") && (
        <div className="space-y-1">
          <p>📌 본 분석은 투자 권유가 아닌 정보 제공입니다.</p>
          <p>최종 투자 판단은 사용자 본인의 책임입니다.</p>
          <p>
            Axis는 자본시장법상 투자자문업 면허가 없으며, 특정 종목의 매매를
            권유하지 않습니다.
          </p>
          <p>투자에는 원금 손실 위험이 있습니다.</p>
        </div>
      )}
      {(lang === "en" || lang === "both") && (
        <div className="space-y-1">
          <p>📌 Information only — not investment advice or solicitation.</p>
          <p>All investment decisions are your own responsibility.</p>
          <p>
            Axis holds no investment advisory license under any jurisdiction
            and does not recommend the purchase or sale of any specific
            security.
          </p>
          <p>
            Investing involves risk, including possible loss of principal. Past
            performance does not guarantee future results.
          </p>
        </div>
      )}
    </div>
  );
}
