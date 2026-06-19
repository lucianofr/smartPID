import {
  createContext, useCallback, useEffect, useMemo, useRef, useState, type ReactNode,
} from 'react';
import type { RealtimeEnvelope, RealtimeType, StatusData, StatsData } from './envelope';

type Handler = (env: RealtimeEnvelope) => void;

export interface RealtimeContextValue {
  connected: boolean;
  lastStatus: ReadonlyMap<number, StatusData>;
  lastStats: ReadonlyMap<number, StatsData>;
  subscribe: (type: RealtimeType, handler: Handler) => () => void;
  onResync: (cb: () => void) => () => void;
}
export const RealtimeContext = createContext<RealtimeContextValue | null>(null);

const MAX_BACKOFF = 10_000;

export function RealtimeProvider({ token, children }: { token: string | null; children?: ReactNode }) {
  const [connected, setConnected] = useState(false);
  const lastStatus = useRef(new Map<number, StatusData>());
  const lastStats = useRef(new Map<number, StatsData>());
  const subs = useRef(new Map<RealtimeType, Set<Handler>>());
  const resyncCbs = useRef(new Set<() => void>());
  const wsRef = useRef<WebSocket | null>(null);
  const backoff = useRef(500);
  const hadConnection = useRef(false);
  const [version, forceRender] = useState(0);

  const subscribe = useCallback((type: RealtimeType, handler: Handler) => {
    const set = subs.current.get(type) ?? new Set<Handler>();
    set.add(handler);
    subs.current.set(type, set);
    return () => set.delete(handler);
  }, []);

  const onResync = useCallback((cb: () => void) => {
    resyncCbs.current.add(cb);
    return () => resyncCbs.current.delete(cb);
  }, []);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    let reconnectTimer: ReturnType<typeof setTimeout> | undefined;

    const connect = () => {
      const proto = location.protocol === 'https:' ? 'wss' : 'ws';
      const ws = new WebSocket(`${proto}://${location.host}/ws/realtime`);
      wsRef.current = ws;
      ws.onopen = () => {
        ws.send(JSON.stringify({ type: 'auth', token }));
        setConnected(true);
        backoff.current = 500;
        if (hadConnection.current) {
          resyncCbs.current.forEach((cb) => cb());
        }
        hadConnection.current = true;
      };
      ws.onmessage = (e) => {
        let env: RealtimeEnvelope;
        try {
          env = JSON.parse(e.data) as RealtimeEnvelope;
        } catch {
          return;
        }
        if (env.type === 'status' && env.loop_id !== null) {
          lastStatus.current = new Map(lastStatus.current).set(env.loop_id, env.data as StatusData);
          forceRender((n) => n + 1);
        } else if (env.type === 'stats' && env.loop_id !== null) {
          lastStats.current = new Map(lastStats.current).set(env.loop_id, env.data as StatsData);
          forceRender((n) => n + 1);
        } else {
          subs.current.get(env.type)?.forEach((h) => h(env));
        }
      };
      ws.onclose = () => {
        setConnected(false);
        if (cancelled) return;
        reconnectTimer = setTimeout(connect, backoff.current);
        backoff.current = Math.min(backoff.current * 2, MAX_BACKOFF);
      };
    };
    connect();
    return () => {
      cancelled = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      wsRef.current?.close();
    };
  }, [token]);

  const value = useMemo<RealtimeContextValue>(
    () => ({
      connected,
      lastStatus: lastStatus.current,
      lastStats: lastStats.current,
      subscribe,
      onResync,
    }),
    [connected, version, subscribe, onResync],
  );
  return <RealtimeContext.Provider value={value}>{children}</RealtimeContext.Provider>;
}
