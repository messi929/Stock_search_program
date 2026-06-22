/**
 * /privacy — 개인정보처리방침.
 * 출처: docs/axis/LEGAL.md (개인정보 처리방침 핵심)
 */
import Link from "next/link";

export const metadata = {
  title: "개인정보처리방침 — Axis",
  description: "Axis 서비스 개인정보처리방침 — 수집 항목 및 제3자 공유",
};

const LAST_UPDATED = "2026-04-28";
const CONTACT_EMAIL = "wogus711929@gmail.com";

export default function PrivacyPage() {
  return (
    <main className="min-h-screen bg-background text-foreground">
      <div className="max-w-3xl mx-auto px-6 py-12">
        <Link
          href="/"
          className="text-sm text-muted-foreground hover:text-foreground"
        >
          ← 홈으로
        </Link>
        <h1 className="text-3xl font-bold mt-4 mb-2">개인정보처리방침</h1>
        <p className="text-sm text-muted-foreground mb-10">
          최종 수정일: {LAST_UPDATED}
        </p>

        <Section n="1" title="수집하는 개인정보 항목">
          <p className="mb-3 font-medium text-foreground">필수 항목 (계정 식별)</p>
          <ul className="list-disc pl-5 space-y-1 mb-4">
            <li>이메일 주소 (Google 계정)</li>
            <li>Firebase 사용자 식별자(UID)</li>
            <li>표시 이름 (Google 계정 프로필명)</li>
          </ul>

          <p className="mb-3 font-medium text-foreground">
            선택 항목 (온보딩 / 서비스 개인화)
          </p>
          <ul className="list-disc pl-5 space-y-1 mb-4">
            <li>투자 경력 (1년 미만 / 1~5년차 / 5년 이상)</li>
            <li>관심 섹터 (사용자가 선택)</li>
            <li>투자 원칙 (사용자가 자유 입력)</li>
            <li>선호 투자 시계 (단기 / 단중기 / 중기 / 장기)</li>
            <li>보유 기간 선호</li>
            <li>알림 수신 이메일 (기본 이메일과 다른 경우)</li>
          </ul>

          <p className="mb-3 font-medium text-foreground">자동 수집 항목</p>
          <ul className="list-disc pl-5 space-y-1">
            <li>분석 횟수, 투자 시계 사용 빈도 등 사용 로그</li>
            <li>접속 시 IP 주소, 브라우저 종류, 기기 유형</li>
            <li>관심 종목 목록 및 진입선 메타데이터 (사용자가 저장한 경우)</li>
          </ul>

          <div className="mt-4 p-3 rounded-md bg-muted/50 text-xs">
            <p className="font-medium mb-1">수집하지 않는 정보</p>
            <p className="text-muted-foreground">
              실명, 주민등록번호, 계좌번호, 정밀 위치 정보, 실제 보유 종목
              (사용자가 자발적으로 입력하지 않는 한)
            </p>
          </div>
        </Section>

        <Section n="2" title="개인정보 수집 및 이용 목적">
          <ol className="list-decimal pl-5 space-y-2">
            <li>회원 가입·식별, 본인 확인, 부정 이용 방지</li>
            <li>분석 서비스 제공 및 개인화 (투자 시계·관심 섹터 반영)</li>
            <li>요금제 결제·환불 처리</li>
            <li>알림 발송 (사용자가 동의한 경우에 한함)</li>
            <li>서비스 개선을 위한 통계 분석 (개인 식별 정보 제외)</li>
            <li>법령상 의무 이행</li>
          </ol>
        </Section>

        <Section n="3" title="개인정보 보유 및 이용 기간">
          <ol className="list-decimal pl-5 space-y-2">
            <li>
              회원 가입 정보: 회원 탈퇴 시까지. 단, 다음의 경우 명시된 기간까지
              보존:
              <ul className="list-disc pl-5 mt-1 space-y-1 text-muted-foreground">
                <li>전자상거래법: 결제 기록 5년, 분쟁 처리 기록 3년</li>
                <li>통신비밀보호법: 로그 기록 3개월</li>
              </ul>
            </li>
            <li>
              사용 로그: 12개월 (그 이후 익명화 또는 삭제)
            </li>
            <li>
              회원이 탈퇴를 요청하면 즉시 또는 다음 영업일 내에 삭제
              (위 보존 의무 항목 제외).
            </li>
          </ol>
        </Section>

        <Section n="4" title="제3자 제공 및 처리 위탁">
          <p className="mb-3">
            회사는 다음의 외부 서비스를 통해 개인정보를 처리합니다.
            모두 서비스 제공에 필수적이며, 사용자가 동의 시점부터 처리됩니다.
          </p>
          <table className="w-full text-xs border rounded-md overflow-hidden">
            <thead className="bg-muted/50">
              <tr>
                <th className="px-3 py-2 text-left">수탁자</th>
                <th className="px-3 py-2 text-left">위탁 항목</th>
                <th className="px-3 py-2 text-left">목적</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-t">
                <td className="px-3 py-2">Google (Firebase)</td>
                <td className="px-3 py-2">이메일·UID·인증 정보</td>
                <td className="px-3 py-2">로그인·세션 관리</td>
              </tr>
              <tr className="border-t">
                <td className="px-3 py-2">Anthropic</td>
                <td className="px-3 py-2">분석 쿼리 (종목명·사용자 원칙)</td>
                <td className="px-3 py-2">AI 분석 응답 생성</td>
              </tr>
              <tr className="border-t">
                <td className="px-3 py-2">Google Cloud (Cloud Run, Firestore)</td>
                <td className="px-3 py-2">사용자 데이터·관심 종목·로그</td>
                <td className="px-3 py-2">서비스 호스팅 및 영속화</td>
              </tr>
              <tr className="border-t">
                <td className="px-3 py-2">Vercel</td>
                <td className="px-3 py-2">웹사이트 트래픽</td>
                <td className="px-3 py-2">프론트엔드 호스팅</td>
              </tr>
              <tr className="border-t">
                <td className="px-3 py-2">Lemon Squeezy*</td>
                <td className="px-3 py-2">결제·청구 정보</td>
                <td className="px-3 py-2">유료 결제 처리</td>
              </tr>
            </tbody>
          </table>
          <p className="mt-3 text-xs text-muted-foreground">
            * Lemon Squeezy는 유료 요금제 결제 도입 시점부터 적용됩니다. 본 방침
            최종 수정일 기준, 회사는 무료로만 운영 중이며 결제 정보 위탁은
            발생하지 않았습니다.
          </p>
          <p className="mt-2 text-xs text-muted-foreground">
            상기 수탁자들은 각자의 개인정보처리방침을 준수합니다. 회사는 수탁자
            변경 시 본 방침을 갱신합니다.
          </p>
        </Section>

        <Section n="5" title="이용자의 권리">
          <p className="mb-2">사용자는 언제든지 다음 권리를 행사할 수 있습니다.</p>
          <ul className="list-disc pl-5 space-y-1">
            <li>개인정보 열람 요청</li>
            <li>오류 정정·삭제 요청</li>
            <li>처리 정지 요청</li>
            <li>회원 탈퇴 및 데이터 삭제 요청</li>
          </ul>
          <p className="mt-3 text-xs text-muted-foreground">
            요청은{" "}
            <a
              href={`mailto:${CONTACT_EMAIL}`}
              className="underline hover:text-foreground"
            >
              {CONTACT_EMAIL}
            </a>
            로 보내주시면 영업일 기준 7일 이내에 처리합니다.
          </p>
        </Section>

        <Section n="6" title="개인정보 보호를 위한 조치">
          <ul className="list-disc pl-5 space-y-1">
            <li>전송 구간 암호화 (HTTPS/TLS)</li>
            <li>저장 데이터는 Google Cloud의 KMS 또는 동등 수준 암호화</li>
            <li>접근 통제: Firebase Auth 토큰 검증으로 사용자별 데이터 격리</li>
            <li>API 키·시크릿은 Google Secret Manager로 관리</li>
            <li>관리자 접근은 최소 인원으로 제한</li>
          </ul>
        </Section>

        <Section n="7" title="쿠키 정책">
          <p>
            본 서비스는 로그인 세션 유지를 위해 Firebase Auth가 발급하는
            인증 쿠키를 사용합니다. 사용자는 브라우저 설정으로 쿠키를 거부할 수
            있으나, 이 경우 일부 기능 이용에 제한이 있을 수 있습니다.
          </p>
        </Section>

        <Section n="8" title="개인정보 보호 책임자">
          <p>
            개인정보보호법 제31조에 따른 개인정보 보호책임자 정보입니다.
          </p>
          <ul className="list-disc pl-5 mt-2 space-y-1">
            <li>성명: 전재현</li>
            <li>직책: 운영자 (개인사업자 단계)</li>
            <li>
              이메일:{" "}
              <a
                href={`mailto:${CONTACT_EMAIL}`}
                className="underline hover:text-foreground"
              >
                {CONTACT_EMAIL}
              </a>
            </li>
          </ul>
          <p className="mt-3 text-xs text-muted-foreground">
            정보 열람·정정·삭제·처리정지 요청은 위 이메일로 보내주시면 영업일
            기준 7일 이내에 처리합니다. 회사가 법인화되거나 전용 도메인이 운영되는
            시점에 본 항목은 갱신됩니다.
          </p>
          <p className="mt-3 text-xs text-muted-foreground">
            그 외 개인정보 침해 신고: 개인정보보호위원회{" "}
            <a
              href="https://www.privacy.go.kr"
              target="_blank"
              rel="noreferrer"
              className="underline hover:text-foreground"
            >
              privacy.go.kr
            </a>{" "}
            (국번 없이 182)
          </p>
        </Section>

        <Section n="9" title="방침의 변경">
          <p>
            회사는 본 방침을 변경할 수 있으며, 변경 시 시행일 7일 이전에
            공지합니다. 사용자에게 불리한 변경은 30일 이전에 공지합니다.
          </p>
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
