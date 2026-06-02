/**
 * /refund — 환불정책.
 * 출처: screener/static/refund.html (Phase 1 흡수, 2026-05-17)
 */
import Link from "next/link";

export const metadata = {
  title: "환불정책 — Axis",
  description: "Axis 유료 구독 환불정책 — 7일 전액 환불 보장",
};

const LAST_UPDATED = "2026-05-31";
const CONTACT_EMAIL = "wogus711929@gmail.com";

export default function RefundPage() {
  return (
    <main className="min-h-screen bg-background text-foreground">
      <div className="max-w-3xl mx-auto px-6 py-12">
        <Link
          href="/"
          className="text-sm text-muted-foreground hover:text-foreground"
        >
          ← 홈으로
        </Link>
        <h1 className="text-3xl font-bold mt-4 mb-2">
          환불정책{" "}
          <span className="text-base font-medium text-muted-foreground">
            / Refund Policy
          </span>
        </h1>
        <p className="text-sm text-muted-foreground mb-10">
          최종 수정일: {LAST_UPDATED}
        </p>

        <div className="mb-10 p-4 rounded-md border border-amber-500/40 bg-amber-500/10 text-sm">
          <p className="font-medium mb-1">한 줄 요약 (Summary)</p>
          <p className="text-muted-foreground">
            Pro 구독은 <strong className="text-foreground">결제일로부터 7일 이내</strong>{" "}
            요청 시 <strong className="text-foreground">전액 환불</strong>됩니다.
            이유 불문. 첫 1개월은 무료 체험으로 미리 사용해보실 수 있습니다.
          </p>
        </div>

        <Section n="1" title="적용 범위 (Scope)">
          <p>
            본 정책은 Axis의 모든 유료 구독(월간·연간)에 적용됩니다. 무료(Free)
            플랜은 과금이 없으므로 환불 대상이 아닙니다.
          </p>
        </Section>

        <Section n="2" title="7일 전액 환불 보장 (7-Day Money-Back Guarantee)">
          <ol className="list-decimal pl-5 space-y-2">
            <li>
              최초 결제일로부터 <strong>7일 이내</strong>에 환불을 요청하시면,
              이유를 묻지 않고 <strong>전액 환불</strong>됩니다.
            </li>
            <li>
              환불 요청 접수 후 영업일 기준 <strong>3~5일 이내</strong> 처리되며,
              실제 카드사 입금까지는 결제 수단에 따라 추가로 5~14일 소요될 수
              있습니다.
            </li>
            <li>환불은 결제 시 사용한 동일 결제수단으로 반환됩니다.</li>
          </ol>
        </Section>

        <Section n="3" title="갱신 결제(Renewal)의 환불">
          <ol className="list-decimal pl-5 space-y-2">
            <li>
              구독은 설정된 주기(월 또는 연)에 따라 <strong>자동 갱신</strong>됩니다.
              갱신 결제 후 <strong>7일 이내</strong>에 환불 요청 시 해당 갱신분이
              전액 환불되며, 구독이 즉시 종료됩니다.
            </li>
            <li>
              7일이 지난 갱신분은 원칙적으로 환불되지 않습니다. 단, 서비스 장애·
              중대한 하자 등이 확인되는 경우 운영자 재량으로 부분 환불이 가능합니다.
            </li>
            <li>
              자동 갱신을 원치 않으시면 다음 결제일 전에 언제든 구독을 해지하실
              수 있습니다 (아래 제5항 참조).
            </li>
          </ol>
        </Section>

        <Section n="4" title="환불 불가 사유 (Exceptions)">
          <p className="mb-2">다음의 경우 환불이 제한될 수 있습니다:</p>
          <ul className="list-disc pl-5 space-y-1">
            <li>
              결제일로부터 7일이 지난 시점의 단순 변심 (단, 다음 갱신 전에 해지하면
              이후 과금은 중단됨)
            </li>
            <li>계정이 이용약관 위반으로 정지·해지된 경우</li>
            <li>명백한 환불 남용(Chargeback Abuse) 정황이 있는 경우</li>
            <li>프로모션·할인 코드 조건상 &ldquo;환불 불가&rdquo;로 명시된 상품</li>
          </ul>
        </Section>

        <Section n="5" title="구독 해지 방법 (How to Cancel)">
          <p className="mb-2">
            구독 해지는 언제든 가능하며, 해지 시점까지 결제된 기간 동안 Pro 기능은
            계속 이용하실 수 있습니다. 다음 중 한 가지 방법으로 해지할 수 있습니다:
          </p>
          <ol className="list-decimal pl-5 space-y-2">
            <li>
              <strong>서비스 내</strong>: 로그인 → 계정 메뉴 → &ldquo;구독 관리&rdquo;
              → &ldquo;구독 해지&rdquo;
            </li>
            <li>
              <strong>결제 이메일의 관리 링크</strong>: Lemon Squeezy에서 발송한
              영수증 이메일 하단의 &ldquo;Manage subscription&rdquo; 링크 클릭
            </li>
            <li>
              <strong>이메일 문의</strong>:{" "}
              <a
                href={`mailto:${CONTACT_EMAIL}`}
                className="underline hover:text-foreground"
              >
                {CONTACT_EMAIL}
              </a>
              으로 요청
            </li>
          </ol>
        </Section>

        <Section n="6" title="환불 요청 방법 (How to Request a Refund)">
          <p className="mb-2">아래 정보를 포함하여 이메일로 요청해주세요:</p>
          <ul className="list-disc pl-5 space-y-1">
            <li>
              받는 사람:{" "}
              <a
                href={`mailto:${CONTACT_EMAIL}`}
                className="underline hover:text-foreground"
              >
                {CONTACT_EMAIL}
              </a>
            </li>
            <li>제목: &ldquo;환불 요청 (Refund Request)&rdquo;</li>
            <li>
              내용에 포함할 항목:
              <ul className="list-disc pl-5 mt-1 space-y-1 text-muted-foreground">
                <li>가입 시 사용한 이메일 주소</li>
                <li>결제일 및 결제 금액</li>
                <li>Lemon Squeezy 주문번호 또는 영수증 번호 (이메일에서 확인 가능)</li>
                <li>환불 사유 (선택)</li>
              </ul>
            </li>
          </ul>
          <p className="mt-3">
            요청 접수 후 영업일 기준 <strong>2일 이내</strong>에 확인 회신이
            이루어지며, 승인되면 Lemon Squeezy를 통해 환불이 처리됩니다.
          </p>
        </Section>

        <Section n="7" title="한국 소비자 법령 (Korean Consumers)">
          <p className="mb-2">
            대한민국 거주자는 「전자상거래 등에서의 소비자보호에 관한 법률」에
            따라 다음 권리를 가집니다:
          </p>
          <ul className="list-disc pl-5 space-y-1">
            <li>
              계약 체결일로부터 <strong>7일 이내</strong> 청약철회 가능 (단, 디지털
              콘텐츠의 경우 이용 개시 전에 한함)
            </li>
            <li>서비스에 중대한 하자가 있는 경우 계약 해제 및 전액 환불</li>
          </ul>
          <p className="mt-3">
            본 서비스는 법정 청약철회 기간(7일)에 맞춰{" "}
            <strong>7일 전액 환불</strong>을 보장하며, 이에 더해 가입 첫{" "}
            <strong>1개월 무료 체험</strong>을 제공하여 결제 전 서비스를 충분히
            평가하실 수 있도록 합니다.
          </p>
        </Section>

        <Section n="8" title="분쟁 해결 (Dispute Resolution)">
          <p>
            환불 관련 분쟁은 우선 이메일 문의를 통해 원만히 해결하고자 노력하며,
            합의되지 않는 경우 「소비자기본법」에 따른 한국소비자원 또는 운영자
            주소지 관할 법원에 분쟁 조정·소송을 제기할 수 있습니다.
          </p>
        </Section>

        <Section n="9" title="문의 (Contact)">
          <ul className="list-disc pl-5 space-y-1">
            <li>
              <strong>Axis</strong>
            </li>
            <li>
              이메일:{" "}
              <a
                href={`mailto:${CONTACT_EMAIL}`}
                className="underline hover:text-foreground"
              >
                {CONTACT_EMAIL}
              </a>
            </li>
            <li>
              결제 대행사: Lemon Squeezy Inc. (
              <a
                href="https://www.lemonsqueezy.com/help"
                target="_blank"
                rel="noreferrer"
                className="underline hover:text-foreground"
              >
                Help Center
              </a>
              )
            </li>
          </ul>
        </Section>
      </div>
    </main>
  );
}

function Section({
  n,
  title,
  children,
}: {
  n: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="mb-8 text-sm leading-7">
      <h2 className="font-semibold text-base mb-2">
        {n}. {title}
      </h2>
      <div className="text-muted-foreground">{children}</div>
    </section>
  );
}
