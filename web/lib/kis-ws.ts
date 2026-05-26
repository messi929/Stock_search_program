/**
 * KIS 실시간 시세 WebSocket 클라이언트 (브라우저 측).
 *
 * 백엔드 endpoint: /api/kis/ws/stream
 * - 한 페이지에 1개 connection 권장. 종목별 subscribe/unsubscribe.
 * - 끊김 시 exponential backoff 재접속.
 * - 재접속 시 기존 구독 자동 복원.
 *
 * 사용 예:
 *   const c = new KisWsClient();
 *   c.onTick((ticker, tick) => console.log(ticker, tick.price));
 *   await c.connect();
 *   c.subscribe(["005930", "000660"]);
 */

export type KisTickEvent = {
  ticker: string;
  price?: string;
  prdy_vrss?: string;
  prdy_ctrt?: string;
  cntg_vol?: string;
  acml_vol?: string;
  exec_time?: string;
  [k: string]: string | undefined;
};

type ServerMessage =
  | { type: "tick"; ticker: string; data: KisTickEvent }
  | { type: "subscribed"; ticker: string }
  | { type: "unsubscribed"; ticker: string }
  | { type: "pong" }
  | { type: "error"; message: string; ticker?: string };

type TickHandler = (ticker: string, tick: KisTickEvent) => void;
type ErrorHandler = (message: string, ticker?: string) => void;

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

function toWsUrl(httpBase: string, path: string): string {
  if (!httpBase) {
    // Same-origin
    if (typeof window === "undefined") return `ws://localhost${path}`;
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${proto}//${window.location.host}${path}`;
  }
  const u = new URL(httpBase);
  u.protocol = u.protocol === "https:" ? "wss:" : "ws:";
  return `${u.toString().replace(/\/$/, "")}${path}`;
}

const RECONNECT_BASE_MS = 1_000;
const RECONNECT_MAX_MS = 30_000;
const PING_INTERVAL_MS = 25_000;

export class KisWsClient {
  private ws: WebSocket | null = null;
  private url: string;
  private tickHandlers = new Set<TickHandler>();
  private errorHandlers = new Set<ErrorHandler>();
  private subscribed = new Set<string>();
  private reconnectMs = RECONNECT_BASE_MS;
  private closedByUser = false;
  private pingTimer: ReturnType<typeof setInterval> | null = null;

  constructor(path = "/api/kis/ws/stream") {
    this.url = toWsUrl(API_BASE, path);
  }

  onTick(h: TickHandler): () => void {
    this.tickHandlers.add(h);
    return () => this.tickHandlers.delete(h);
  }

  onError(h: ErrorHandler): () => void {
    this.errorHandlers.add(h);
    return () => this.errorHandlers.delete(h);
  }

  /** 접속 (이미 열려있으면 noop). */
  connect(): Promise<void> {
    if (this.ws && this.ws.readyState <= WebSocket.OPEN) return Promise.resolve();
    this.closedByUser = false;
    return new Promise((resolve, reject) => {
      try {
        this.ws = new WebSocket(this.url);
      } catch (e) {
        reject(e);
        return;
      }

      this.ws.addEventListener("open", () => {
        this.reconnectMs = RECONNECT_BASE_MS;
        // 재접속 시 기존 구독 복원
        if (this.subscribed.size > 0) {
          this.send({ action: "subscribe", tickers: [...this.subscribed] });
        }
        this.startPing();
        resolve();
      });

      this.ws.addEventListener("message", (ev) => {
        try {
          const msg = JSON.parse(ev.data) as ServerMessage;
          this.handleMessage(msg);
        } catch {
          /* invalid frame */
        }
      });

      this.ws.addEventListener("close", () => {
        this.stopPing();
        this.ws = null;
        if (!this.closedByUser) this.scheduleReconnect();
      });

      this.ws.addEventListener("error", () => {
        // close 이벤트가 뒤따르므로 여기선 promise 거부 안 함 (재접속 흐름에 맡김)
      });
    });
  }

  /** 끊고 재접속 안 함. */
  close(): void {
    this.closedByUser = true;
    this.stopPing();
    if (this.ws) {
      try {
        this.ws.close();
      } catch {
        /* ignore */
      }
      this.ws = null;
    }
  }

  /** 종목 구독 (배열). 끊김 상태면 다음 연결 시 자동 복원. */
  subscribe(tickers: string[]): void {
    const normalized = tickers.map((t) => t.padStart(6, "0"));
    normalized.forEach((t) => this.subscribed.add(t));
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.send({ action: "subscribe", tickers: normalized });
    }
  }

  unsubscribe(tickers: string[]): void {
    const normalized = tickers.map((t) => t.padStart(6, "0"));
    normalized.forEach((t) => this.subscribed.delete(t));
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.send({ action: "unsubscribe", tickers: normalized });
    }
  }

  // ─── 내부 ────────────────────────────────

  private send(payload: unknown): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(payload));
    }
  }

  private handleMessage(msg: ServerMessage): void {
    if (msg.type === "tick") {
      for (const h of this.tickHandlers) {
        try {
          h(msg.ticker, msg.data);
        } catch {
          /* handler 예외 무시 */
        }
      }
    } else if (msg.type === "error") {
      for (const h of this.errorHandlers) {
        try {
          h(msg.message, msg.ticker);
        } catch {
          /* ignore */
        }
      }
    }
    // subscribed / unsubscribed / pong은 ack — 별도 처리 없음
  }

  private scheduleReconnect(): void {
    setTimeout(() => {
      if (!this.closedByUser) {
        this.connect().catch(() => {
          /* 다음 close에서 재스케줄 */
        });
      }
    }, this.reconnectMs);
    this.reconnectMs = Math.min(this.reconnectMs * 2, RECONNECT_MAX_MS);
  }

  private startPing(): void {
    this.stopPing();
    this.pingTimer = setInterval(() => {
      this.send({ action: "ping" });
    }, PING_INTERVAL_MS);
  }

  private stopPing(): void {
    if (this.pingTimer) {
      clearInterval(this.pingTimer);
      this.pingTimer = null;
    }
  }
}

// ─── React 훅 (관심종목 페이지용 — 향후 사용) ─────

/**
 * 단일 KisWsClient 싱글톤 + 종목별 tick 콜백 등록 헬퍼.
 * (Phase 3D MVP에선 명시 사용처 미적용. WatchlistView 등에서 사용 예정.)
 */
let _singleton: KisWsClient | null = null;
export function getKisWsClient(): KisWsClient {
  if (typeof window === "undefined") {
    // SSR에서 호출되지 않게 — 호출 측에서 useEffect로 가드 필수
    throw new Error("KisWsClient는 브라우저에서만 사용 가능");
  }
  if (_singleton === null) {
    _singleton = new KisWsClient();
  }
  return _singleton;
}
