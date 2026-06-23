"use client";

/**
 * 점검/이용 제한 공지 배너 — 사이트 전역 상단(루트 레이아웃에 마운트).
 * enabled이고 (종료 시각 미설정 또는 아직 종료 전)이면 노출. 종료 시각 지나면 자동 숨김.
 * 비차단(공지만) — 서비스 자체는 계속 동작.
 */
import { useMaintenance } from "@/hooks/useMaintenance";

function fmt(dt: string): string {
  if (!dt) return "";
  const d = new Date(dt);
  if (isNaN(d.getTime())) return dt;
  return d.toLocaleString("ko-KR", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function MaintenanceBanner() {
  const { data } = useMaintenance();
  if (!data) return null;

  // 수동 점검 공지 활성 여부(종료 시각 지나면 자동 숨김).
  let manualActive = !!data.enabled;
  if (manualActive && data.ends_at) {
    const end = new Date(data.ends_at);
    if (!isNaN(end.getTime()) && Date.now() > end.getTime()) manualActive = false;
  }

  // 수동 공지 우선. 없으면 자동 AI 장애 감지 배너.
  if (manualActive) {
    const window =
      data.starts_at || data.ends_at
        ? `점검 시간 ${fmt(data.starts_at)} ~ ${fmt(data.ends_at)}`
        : "";
    return (
      <div
        role="status"
        className="w-full bg-amber-500/15 border-b border-amber-500/40 text-amber-900 dark:text-amber-200 px-4 py-2 text-sm text-center"
      >
        <span className="font-semibold">🛠 점검 안내</span>
        {window && <span className="mx-1.5 font-medium">· {window}</span>}
        <span className="text-amber-800/90 dark:text-amber-200/90">
          {data.message
            ? ` · ${data.message}`
            : " · 점검 중 일부 기능(AI 분석 등) 이용이 제한될 수 있습니다."}
        </span>
      </div>
    );
  }

  if (data.ai_degraded) {
    return (
      <div
        role="status"
        className="w-full bg-red-500/15 border-b border-red-500/40 text-red-900 dark:text-red-200 px-4 py-2 text-sm text-center"
      >
        <span className="font-semibold">⚠️ AI 분석 일시 장애</span>
        <span className="text-red-800/90 dark:text-red-200/90">
          {" · "}
          {data.ai_reason || "AI 분석·검증이 일시적으로 원활하지 않습니다. 잠시 후 다시 시도해주세요."}
        </span>
      </div>
    );
  }

  return null;
}
