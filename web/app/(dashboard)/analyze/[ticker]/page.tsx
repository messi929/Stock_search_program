/**
 * 종목 딥다이브 (/analyze/{ticker}) — 4 에이전트 LangGraph 분석.
 *
 * Next.js 16: params가 Promise라 server 페이지에서 await 후 ticker만
 * 클라이언트 AnalyzeView로 전달. SSE 스트리밍과 페르소나 토글은
 * 클라이언트 사이드에서 처리.
 */
import { AnalyzeView } from "@/components/analyze/AnalyzeView";

export default async function AnalyzePage({
  params,
}: {
  params: Promise<{ ticker: string }>;
}) {
  const { ticker } = await params;
  return <AnalyzeView ticker={ticker} />;
}
