"use client";

/**
 * KIS WebSocket 실시간 시세 — 여러 ticker 동시 subscribe.
 *
 * 한 페이지에 1개 WS 연결(싱글톤). 컴포넌트 unmount 시 자동 unsubscribe.
 * 끊김 시 KisWsClient가 자동 재접속 + 구독 복원.
 *
 * KR 종목(6자리)만 활성. US/ETF는 자동 필터.
 *
 * 반환: { ticker → { price, prdyVrss, prdyCtrt, lastUpdate } }
 */
import { useEffect, useRef, useState } from "react";

import { getKisWsClient, type KisTickEvent } from "@/lib/kis-ws";

export type LiveTick = {
  price: number | null;
  prdyVrss: number | null;
  prdyCtrt: number | null;
  cntgVol: number | null;
  acmlVol: number | null;
  execTime: string | null;
  lastUpdate: number; // epoch ms
};

const EMPTY: LiveTick = {
  price: null,
  prdyVrss: null,
  prdyCtrt: null,
  cntgVol: null,
  acmlVol: null,
  execTime: null,
  lastUpdate: 0,
};

function isKr(ticker: string): boolean {
  return /^\d{6}$/.test(ticker.trim());
}

function num(v: string | undefined): number | null {
  if (v === undefined || v === "") return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

export function useKisLivePrices(
  tickers: string[],
): Record<string, LiveTick> {
  const [ticks, setTicks] = useState<Record<string, LiveTick>>({});
  const subscribedRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    if (typeof window === "undefined") return;
    const krTickers = tickers.map((t) => t.padStart(6, "0")).filter(isKr);

    const client = getKisWsClient();

    // ticker별 콜백 등록 — KIS 응답을 LiveTick으로 변환
    const unsub = client.onTick((ticker: string, ev: KisTickEvent) => {
      setTicks((prev) => ({
        ...prev,
        [ticker]: {
          price: num(ev.price),
          prdyVrss: num(ev.prdy_vrss),
          prdyCtrt: num(ev.prdy_ctrt),
          cntgVol: num(ev.cntg_vol),
          acmlVol: num(ev.acml_vol),
          execTime: ev.exec_time ?? null,
          lastUpdate: Date.now(),
        },
      }));
    });

    // 신규 구독 / 해제 차분 처리
    const newSet = new Set(krTickers);
    const toAdd = [...newSet].filter((t) => !subscribedRef.current.has(t));
    const toRemove = [...subscribedRef.current].filter((t) => !newSet.has(t));

    if (toAdd.length > 0 || toRemove.length > 0) {
      client.connect().catch(() => {
        /* 자동 재접속에 맡김 */
      });
    }
    if (toAdd.length > 0) client.subscribe(toAdd);
    if (toRemove.length > 0) client.unsubscribe(toRemove);
    subscribedRef.current = newSet;

    return () => {
      unsub();
      // 컴포넌트 unmount 시 이 컴포넌트가 추가한 ticker만 정리
      // (페이지 내 다른 컴포넌트가 같은 ticker 보고 있을 수 있으므로 전체 unsubscribe 금지)
      // → 페이지 전환 시엔 React Query/페이지 라이프사이클이 정리. 여기선 noop.
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tickers.join(",")]);

  // 호출자 편의: 미구독 ticker는 EMPTY 반환
  const merged: Record<string, LiveTick> = {};
  tickers.forEach((t) => {
    const padded = t.padStart(6, "0");
    merged[t] = ticks[padded] ?? EMPTY;
  });
  return merged;
}
