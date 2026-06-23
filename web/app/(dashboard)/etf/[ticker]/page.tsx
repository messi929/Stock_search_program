/**
 * ETF 전용 상세 (/etf/{ticker}) — 정보 + 구성종목 + 섹터/국가/자산 비중.
 *
 * 일반 종목 딥다이브(/analyze)와 분리. KR 상장 ETF(국내 + 국내상장 국외) 대상.
 * Next.js 16: params가 Promise라 await 후 클라이언트 EtfDetailView로 전달.
 */
import { EtfDetailView } from "@/components/etf/EtfDetailView";

export default async function EtfPage({
  params,
}: {
  params: Promise<{ ticker: string }>;
}) {
  const { ticker } = await params;
  return <EtfDetailView ticker={ticker} />;
}
