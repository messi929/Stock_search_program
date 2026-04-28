/**
 * /screener/custom — 커스텀 스크리너 (Pro 전용).
 * 클라이언트 컴포넌트가 플랜 게이트 + 폼 + 결과 모두 처리.
 */
import { CustomScreenerView } from "@/components/screener/CustomScreenerView";

export default function CustomScreenerPage() {
  return (
    <div className="max-w-5xl">
      <CustomScreenerView />
    </div>
  );
}
