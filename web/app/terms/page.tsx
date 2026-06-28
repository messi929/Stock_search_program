/**
 * /terms — 이용약관.
 * 출처: docs/axis/LEGAL.md (Article X/Y/Z)
 *
 * 주의: 정식 런칭 전 변호사 1회 검토 권장.
 */
import Link from "next/link";

export const metadata = {
  title: "이용약관 — Axis",
  description: "Axis 서비스 이용약관 — 투자 분석 도구의 성격 및 면책 조항",
};

const LAST_UPDATED = "2026-05-31";
const CONTACT_EMAIL = "wogus711929@gmail.com";

export default function TermsPage() {
  return (
    <main className="min-h-screen bg-background text-foreground">
      <div className="max-w-3xl mx-auto px-6 py-12">
        <Link
          href="/"
          className="text-sm text-muted-foreground hover:text-foreground"
        >
          ← 홈으로
        </Link>
        <h1 className="text-3xl font-bold mt-4 mb-2">이용약관</h1>
        <p className="text-sm text-muted-foreground mb-10">
          최종 수정일: {LAST_UPDATED}
        </p>

        <Section n="제1조" title="목적">
          <p>
            본 약관은 Axis(이하 &ldquo;회사&rdquo;)가 제공하는 투자 정보 분석 서비스(이하
            &ldquo;본 서비스&rdquo;)의 이용에 관한 권리·의무 및 책임 사항, 기타 필요한
            사항을 규정함을 목적으로 합니다.
          </p>
        </Section>

        <Section n="제2조" title="서비스의 성격">
          <ol className="list-decimal pl-5 space-y-2">
            <li>
              본 서비스는 <strong>투자 정보 제공 및 분석 도구</strong>이며, 투자
              자문 서비스가 아닙니다.
            </li>
            <li>
              회사는 자본시장과 금융투자업에 관한 법률(이하 &ldquo;자본시장법&rdquo;)
              상의 <strong>투자자문업 또는 투자중개업 면허를 보유하지 않습니다</strong>.
            </li>
            <li>
              본 서비스가 제공하는 모든 분석, 데이터, AI 응답은 투자 권유가 아닌
              <strong>정보 제공</strong>이며, 사용자는 이를 참고용으로만 사용합니다.
            </li>
            <li>
              모든 투자 결정과 결과에 대한 책임은 사용자 본인에게 있습니다.
            </li>
          </ol>
        </Section>

        <Section n="제3조" title="회원가입 및 계정">
          <ol className="list-decimal pl-5 space-y-2">
            <li>
              사용자는 Google 계정을 통해 본 서비스에 가입할 수 있습니다.
            </li>
            <li>
              사용자는 정확한 정보를 제공해야 하며, 타인의 계정을 도용하거나
              부정한 방법으로 가입할 수 없습니다.
            </li>
            <li>
              사용자는 언제든지 계정 탈퇴를 요청할 수 있으며, 회사는 관련 법령이
              요구하는 보존 기간을 제외하고 사용자 데이터를 삭제합니다.
            </li>
          </ol>
        </Section>

        <Section n="제4조" title="요금제 및 결제">
          <ol className="list-decimal pl-5 space-y-2">
            <li>
              본 서비스는 무료(Free)와 Pro(월 39,000원 또는 연 398,000원)
              요금제로 운영되며, 연 구독은 약 2개월치가 할인됩니다. Pro는 신규
              가입 시 첫 7일 무료 체험을 제공합니다.
            </li>
            <li>
              유료 요금제는 <strong>월 또는 연 단위 자동 갱신 구독</strong>이며, 결제·청구·
              환불은 결제대행사{" "}
              <strong>Lemon Squeezy(Lemon Squeezy Inc., Merchant of Record)</strong>
              를 통해 처리됩니다. 구독 관리 및 해지는 Lemon Squeezy 영수증 이메일의
              &ldquo;Manage subscription&rdquo; 링크 또는 서비스 내 구독 관리
              메뉴에서 가능합니다.
            </li>
            <li>
              유료 결제는 <strong>결제일로부터 14일 이내 전액 환불</strong>을
              보장합니다. 환불 가능 기간·요청 방법·갱신분 처리 등 자세한 사항은{" "}
              <Link href="/refund" className="underline hover:text-foreground">
                환불정책
              </Link>
              을 따릅니다.
            </li>
            <li>
              회사는 사전 공지 후 요금 정책을 변경할 수 있으며, 변경 사항은 공지
              후 30일이 경과한 시점부터 적용됩니다.
            </li>
          </ol>
        </Section>

        <Section n="제5조" title="AI 응답의 한계">
          <ol className="list-decimal pl-5 space-y-2">
            <li>
              본 서비스는 Anthropic의 Claude AI 모델을 활용합니다.
            </li>
            <li>
              AI 응답은 학습 데이터의 한계, 추론 오류, 데이터 신선도 문제 등으로
              <strong>부정확할 수 있습니다</strong>.
            </li>
            <li>
              사용자는 AI 응답을 절대적으로 신뢰하지 말고, 본 서비스의
              &ldquo;검증&rdquo; 기능을 활용해 데이터를 재확인할 것을 권고합니다.
            </li>
            <li>
              AI는 시장 미래를 예측할 수 없으며, 본 서비스의 모든 분석은 과거
              데이터 기반입니다.
            </li>
          </ol>
        </Section>

        <Section n="제6조" title="면책 조항">
          <ol className="list-decimal pl-5 space-y-2">
            <li>
              회사는 본 서비스가 제공하는 정보의 정확성, 완전성, 적시성을
              <strong>보증하지 않습니다</strong>.
            </li>
            <li>
              사용자가 본 서비스의 정보를 기반으로 한 투자로 인해 발생한 손실에
              대해 회사는 책임지지 않습니다.
            </li>
            <li>
              회사는 AI 모델의 한계로 인해 잘못된 정보가 제공될 수 있음을
              사용자에게 고지합니다.
            </li>
            <li>
              사용자는 투자 결정 시 반드시 다른 정보원을 함께 참고하고, 필요시
              면허 보유 전문가와 상담해야 합니다.
            </li>
            <li>
              회사는 천재지변, 외부 서비스 장애 등 불가항력으로 인한 서비스
              중단에 대해 책임지지 않습니다.
            </li>
          </ol>
        </Section>

        <Section n="제7조" title="금지 행위">
          <p className="mb-2">사용자는 다음 행위를 해서는 안 됩니다.</p>
          <ul className="list-disc pl-5 space-y-1">
            <li>본 서비스를 이용해 타인에게 투자 자문을 제공하는 행위</li>
            <li>본 서비스 데이터를 무단으로 크롤링·복제·재배포하는 행위</li>
            <li>본 서비스의 면책 문구·경고 표시를 제거한 채 분석 결과를 공유하는 행위</li>
            <li>회사의 사전 동의 없이 본 서비스를 영리 목적으로 이용하는 행위</li>
          </ul>
        </Section>

        <Section n="제8조" title="개인정보 처리">
          <p>
            개인정보의 수집·이용·보관·파기에 관한 사항은 별도의{" "}
            <Link href="/privacy" className="underline hover:text-foreground">
              개인정보처리방침
            </Link>
            을 따릅니다.
          </p>
        </Section>

        <Section n="제9조" title="약관의 변경">
          <ol className="list-decimal pl-5 space-y-2">
            <li>
              회사는 필요시 본 약관을 변경할 수 있으며, 변경 시 시행일 7일 이전에
              공지합니다.
            </li>
            <li>
              사용자에게 불리한 변경의 경우 30일 이전에 공지하고, 사용자가
              명시적으로 거부 의사를 표시하지 않으면 변경된 약관에 동의한 것으로
              간주됩니다.
            </li>
          </ol>
        </Section>

        <Section n="제10조" title="분쟁 해결">
          <ol className="list-decimal pl-5 space-y-2">
            <li>
              본 약관과 관련된 분쟁은 대한민국 법령에 따라 해결합니다.
            </li>
            <li>
              관할 법원은 회사의 본점 소재지를 관할하는 법원으로 합니다.
            </li>
          </ol>
        </Section>

        <Section n="제11조" title="문의처">
          <ul className="list-disc pl-5 space-y-1">
            <li>
              <strong>서비스명</strong>: Axis (axislytics.com)
            </li>
            <li>
              운영·개인정보·환불 문의:{" "}
              <a
                href={`mailto:${CONTACT_EMAIL}`}
                className="underline hover:text-foreground"
              >
                {CONTACT_EMAIL}
              </a>
            </li>
            <li>
              결제 대행사: Lemon Squeezy Inc. (Merchant of Record)
            </li>
          </ul>
        </Section>

        <div className="mt-12 p-4 rounded-md bg-muted/50 text-xs text-muted-foreground">
          <p className="font-medium mb-1">📌 핵심 요약</p>
          <p>
            Axis는 자본시장법상 투자자문업 면허가 없는 정보 제공 도구입니다.
            모든 분석은 참고용이며, 투자 결정과 결과에 대한 책임은 사용자에게
            있습니다.
          </p>
        </div>
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
