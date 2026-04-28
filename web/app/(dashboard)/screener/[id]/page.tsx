/**
 * /screener/[id] — 카테고리별 종목 결과 페이지.
 *
 * Next.js 16: params Promise. 서버에서 풀어 클라이언트 뷰에 id만 전달.
 */
import { ScreenerResultView } from "@/components/screener/ScreenerResultView";

export default async function ScreenerCategoryPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <div className="max-w-6xl">
      <ScreenerResultView categoryId={id} />
    </div>
  );
}
