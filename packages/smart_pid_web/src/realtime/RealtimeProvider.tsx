import {
  createContext,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import {
  createSeqTracker,
  isAuthOk,
  validateEnvelope,
  type AnyEnvelope,
  type RealtimeType,
} from '../lib/envelope';
import type { ResyncRunner } from './resync';

export type ConnectionPhase = 'idle' | 'connecting' | 'resyncing' | 'live' | 'auth-failed';

type Handler = (env: AnyEnvelope) => void;

export interface RealtimeContextValue {
  phase: ConnectionPhase;
  /** Socket authenticated (live or resyncing). */
  connected: boolean;
  /** Live render allowed — resync (§7) has completed. */
  live: boolean;
  subscribe(type: RealtimeType, handler: Handler): () => void;
  lastSeenTs(type: RealtimeType): number | null;
}

export const RealtimeContext = createContext<RealtimeContextValue | null>(null);

export interface RealtimeProviderProps {
  token: string | null;
  /** The §7 resync set — createResyncRunner(...) in App (phase 4); fakes in tests. */
  resync: ResyncRunner;
  /** WS close 4401 = token invalid → force re-login (§11). Wire to auth logout. */
  onAuthExpired(): void;
  children?: ReactNode;
}

const INITIAL_BACKOFF_MS = 500;
const MAX_BACKOFF_MS = 10_000;
/** Mirrors the backend per-connection lossless cap (realtime.py:28). */
const RESYNC_BUFFER_MAX = 256;

export function RealtimeProvider({ token, resync, onAuthExpired, children }: RealtimeProviderProps) {
  const [phase, setPhase] = useState<ConnectionPhase>('idle');
  const subs = useRef(new Map<RealtimeType, Set<Handler>>());
  const tracker = useRef(createSeqTracker());
  const wsRef = useRef<WebSocket | null>(null);
  const phaseRef = useRef<ConnectionPhase>('idle');
  const hadSession = useRef(false);
  const backoff = useRef(INITIAL_BACKOFF_MS);
  // Resync buffering — backend ConnectionBuffer policy (realtime.py:168-191):
  // status/stats coalesce per (type, loop_id); everything else queues lossless.
  const coalesced = useRef(new Map<string, AnyEnvelope>());
  const lossless = useRef<AnyEnvelope[]>([]);

  const setPhaseBoth = (p: ConnectionPhase): void => {
    phaseRef.current = p;
    setPhase(p);
  };

  const subscribe = useCallback((type: RealtimeType, handler: Handler) => {
    const set = subs.current.get(type) ?? new Set<Handler>();
    set.add(handler);
    subs.current.set(type, set);
    return () => {
      set.delete(handler);
    };
  }, []);

  const lastSeenTs = useCallback(
    (type: RealtimeType) => tracker.current.lastSeenTs(type),
    [],
  );

  useEffect(() => {
    if (!token) {
      setPhaseBoth('idle');
      return;
    }
    let cancelled = false;
    let reconnectTimer: ReturnType<typeof setTimeout> | undefined;

    const dispatch = (env: AnyEnvelope): void => {
      subs.current.get(env.type)?.forEach((h) => h(env));
    };

    const bufferDuringResync = (env: AnyEnvelope): void => {
      if (env.type === 'status' || env.type === 'stats') {
        coalesced.current.set(`${env.type}:${env.loop_id ?? 'null'}`, env);
      } else if (lossless.current.length < RESYNC_BUFFER_MAX) {
        lossless.current.push(env);
      }
      // Beyond the cap events drop — the resync that is already running
      // re-establishes truth from REST, mirroring the backend overflow policy.
    };

    const flushResyncBuffer = (): void => {
      const held = [...coalesced.current.values(), ...lossless.current];
      coalesced.current.clear();
      lossless.current = [];
      held.forEach(dispatch);
    };

    const runResync = (ws: WebSocket): void => {
      setPhaseBoth('resyncing');
      resync({ lastSeenAlarmTs: tracker.current.lastSeenTs('alarm') })
        .then(() => {
          if (cancelled || wsRef.current !== ws) return;
          flushResyncBuffer();
          setPhaseBoth('live');
        })
        .catch(() => {
          if (cancelled || wsRef.current !== ws) return;
          // Failed resync ⇒ state unknown: recycle the socket; backoff retries
          // the whole handshake + resync.
          ws.close();
        });
    };

    const connect = (): void => {
      setPhaseBoth('connecting');
      const proto = location.protocol === 'https:' ? 'wss' : 'ws';
      const ws = new WebSocket(`${proto}://${location.host}/ws/realtime`);
      wsRef.current = ws;
      tracker.current.reset(); // new connection = new seq baseline (last_seen_ts kept)

      ws.onopen = () => {
        ws.send(JSON.stringify({ type: 'auth', token })); // realtime.py:208-216
      };

      ws.onmessage = (e: { data: string }) => {
        let raw: unknown;
        try {
          raw = JSON.parse(e.data);
        } catch {
          return;
        }
        if (isAuthOk(raw)) {
          backoff.current = INITIAL_BACKOFF_MS;
          if (hadSession.current) {
            runResync(ws); // §8: resync on reconnect, before live render resumes
          } else {
            hadSession.current = true;
            setPhaseBoth('live');
          }
          return;
        }
        if (!validateEnvelope(raw)) return; // reuse the parse above — no second JSON.parse
        const env = raw;
        const obs = tracker.current.observe(env);
        if (phaseRef.current === 'resyncing') {
          bufferDuringResync(env);
          return;
        }
        if (obs.gap && phaseRef.current === 'live') {
          bufferDuringResync(env); // the envelope AFTER the gap is still valid
          runResync(ws); // §8: resync on detected seq gap
          return;
        }
        dispatch(env);
      };

      ws.onclose = (e: { code: number }) => {
        if (cancelled) return;
        if (e.code === 4401) {
          // Token invalid (realtime.py:27) → force re-login; never reconnect.
          setPhaseBoth('auth-failed');
          onAuthExpired();
          return;
        }
        // Includes any future server overflow close: reconnect → resync (§11).
        setPhaseBoth('connecting');
        reconnectTimer = setTimeout(connect, backoff.current);
        backoff.current = Math.min(backoff.current * 2, MAX_BACKOFF_MS);
      };
    };

    connect();
    return () => {
      cancelled = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [token, resync, onAuthExpired]);

  const value = useMemo<RealtimeContextValue>(
    () => ({
      phase,
      connected: phase === 'live' || phase === 'resyncing',
      live: phase === 'live',
      subscribe,
      lastSeenTs,
    }),
    [phase, subscribe, lastSeenTs],
  );
  return <RealtimeContext.Provider value={value}>{children}</RealtimeContext.Provider>;
}