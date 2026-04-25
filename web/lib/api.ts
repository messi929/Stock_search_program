/**
 * Axis API 클라이언트 — Firebase ID 토큰 자동 첨부.
 *
 * 환경변수:
 *   NEXT_PUBLIC_API_BASE_URL — Axis Cloud Run URL
 *   (예: https://axis-staging-1043976673827.asia-northeast3.run.app)
 */
import { auth } from "./firebase";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

export class APIError extends Error {
  constructor(
    public code: string,
    public override message: string,
    public status: number,
  ) {
    super(message);
    this.name = "APIError";
  }
}

export async function apiCall<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const token = await auth.currentUser?.getIdToken();

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });

  if (!response.ok) {
    let code = "UNKNOWN";
    let message = response.statusText;
    try {
      const body = await response.json();
      if (typeof body.detail === "object" && body.detail !== null) {
        code = body.detail.code ?? code;
        message = body.detail.message ?? body.detail.detail ?? message;
      } else if (typeof body.detail === "string") {
        message = body.detail;
      } else if (typeof body.message === "string") {
        message = body.message;
      }
    } catch {
      /* ignore parse error */
    }
    throw new APIError(code, message, response.status);
  }

  return (await response.json()) as T;
}

/**
 * SSE 스트리밍 호출 — 이벤트별 콜백 처리.
 * /api/ai/analyze stream=true 응답 처리에 사용.
 */
export async function apiStream(
  path: string,
  body: unknown,
  onEvent: (event: string, data: unknown) => void,
  signal?: AbortSignal,
): Promise<void> {
  const token = await auth.currentUser?.getIdToken();
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      Accept: "text/event-stream",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
    signal,
  });

  if (!response.ok || !response.body) {
    throw new APIError("STREAM_FAILED", `${response.status}`, response.status);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // SSE 프로토콜: 빈 줄(\n\n)이 이벤트 구분자
    let blockEnd: number;
    while ((blockEnd = buffer.indexOf("\n\n")) !== -1) {
      const block = buffer.slice(0, blockEnd);
      buffer = buffer.slice(blockEnd + 2);
      let eventName = "message";
      let dataBuf = "";
      for (const line of block.split("\n")) {
        if (line.startsWith("event: ")) eventName = line.slice(7).trim();
        else if (line.startsWith("data: ")) dataBuf += line.slice(6);
      }
      if (dataBuf) {
        try {
          onEvent(eventName, JSON.parse(dataBuf));
        } catch {
          onEvent(eventName, dataBuf);
        }
      }
    }
  }
}
