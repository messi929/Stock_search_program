"use client";

/**
 * 알림 설정 GET/PUT 훅 — Mailgun 발송은 v1.1 도입.
 *
 * 백엔드: GET/PUT /api/ai/notifications/preferences
 *        users/{uid}.notification_preferences 필드에 저장.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiCall } from "@/lib/api";
import type {
  NotificationPreferences,
  NotificationPreferencesResponse,
} from "@/types/api";

const QK = ["notification-preferences"] as const;

export function useNotificationPreferences() {
  return useQuery({
    queryKey: QK,
    queryFn: () =>
      apiCall<NotificationPreferencesResponse>("/api/ai/notifications/preferences"),
    staleTime: 30_000,
  });
}

export function useSaveNotificationPreferences() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (prefs: NotificationPreferences) =>
      apiCall<{ ok: boolean }>("/api/ai/notifications/preferences", {
        method: "PUT",
        body: JSON.stringify(prefs),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: QK }),
  });
}
