/**
 * ETF 발견 (/etf) — 국내·국내상장 국외·해외 ETF 탐색 진입점.
 * 카드 → /etf/{ticker} 전용 상세.
 */
import { EtfDiscoverView } from "@/components/etf/EtfDiscoverView";

export default function EtfDiscoverPage() {
  return <EtfDiscoverView />;
}
