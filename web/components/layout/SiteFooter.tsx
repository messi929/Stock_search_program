import Link from "next/link";

/** 공통 푸터에 노출할 법적/유의사항 링크. */
const FOOTER_LINKS = [
  { href: "/pricing", label: "요금제" },
  { href: "/terms", label: "이용약관" },
  { href: "/privacy", label: "개인정보처리방침" },
  { href: "/refund", label: "환불정책" },
] as const;

/**
 * 사이트 공통 푸터 — 페이지 최하단의 법적/유의사항 링크 모음.
 *
 * 일반 웹사이트처럼 로그인 후(대시보드) 화면에서도 가격·약관·개인정보·환불 정책에
 * 접근할 수 있도록 콘텐츠 맨 아래에 둔다. (랜딩 페이지는 자체 푸터 보유)
 */
export function SiteFooter({ className = "" }: { className?: string }) {
  return (
    <footer className={`mt-12 border-t pt-6 ${className}`}>
      <nav
        aria-label="푸터"
        className="flex flex-wrap items-center gap-x-1 text-xs text-muted-foreground"
      >
        {FOOTER_LINKS.map((l) => (
          <Link
            key={l.href}
            href={l.href}
            className="inline-flex items-center min-h-[36px] px-2 hover:text-foreground hover:underline"
          >
            {l.label}
          </Link>
        ))}
      </nav>
      <p className="mt-2 px-2 text-[11px] leading-relaxed text-muted-foreground">
        본 서비스가 제공하는 정보는 투자 권유가 아니라 정보 제공이며, 최종 투자 판단과
        책임은 이용자 본인에게 있습니다. Axis는 투자자문업 등록 사업자가 아닙니다.
      </p>
    </footer>
  );
}
