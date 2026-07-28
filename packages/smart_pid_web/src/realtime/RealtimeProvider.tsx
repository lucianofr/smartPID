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
import { createFrameCache, frameKey } from './frameCache';

/**
 * `idle` — no session yet: no token, or the very first socket is still in
 * flight. Nothing has ever rendered, so there is nothing to distrust.
 * `connecting` — we HAD a link and lost it. Strictly re-connecting, which is
 * what makes it safe for the shell to treat as an operator-facing alarm.
 */
export type ConnectionPhase = 'idle' | 'connecting' | 'resyncing' | 'live' | 'auth-failed';

type Handler = (env: AnyEnvelope) => void;

export interface RealtimeContextValue {
  phase: ConnectionPhase;
  /** Socket authenticated (live or resyncing). */
  connected: boolean;
  /** Live render allowed — resync (§7) has completed. */
  live: boolean;
  /**
   * The frames on screen are older than {@link STALE_AFTER_MS}.
   *
   * Deliberately INDEPENDENT of `phase`: a socket can sit in `readyState:
   * OPEN` and deliver nothing (dead upstream behind a proxy, a half-open TCP
   * path, a stalled field bus), and in that state `live` is true while every
   * number on screen is a lie. Consumers mark values from this, never from
   * `live`.
   */
  stale: boolean;
  /** Epoch ms of the newest frame received before the link went quiet; null while fresh. */
  staleSince: number | null;
  subscribe(type: RealtimeType, handler: Handler): () => void;
  /**
   * Push the cached last frame of `type` (one per loop) into `handler`, the
   * same §7 late-subscriber guarantee `subscribe` gives. Exposed separately so
   * a relay registered *after* its owning `subscribe` call — which is every
   * consumer of `useRealtime().subscribe`, since React runs the hook's own
   * effect first — can still be handed the frames it missed.
   */
  replay(type: RealtimeType, handler: Handler): void;
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

/**
 * Link liveness (E2E-047).
 *
 * A closed socket is the EASY outage: `onclose` fires and the backoff below
 * takes over. The dangerous one is the socket that stays `OPEN` and stops
 * delivering — measured against this stack, killing the daemon behind the Vite
 * dev proxy produces exactly that: no `error`, no `close`, `readyState` 1
 * forever, and the dashboard keeps rendering pre-outage PV as if live. A NAT
 * timeout, a dropped firewall state or a frozen VM does the same in the field.
 * TCP will not tell us, so the client keeps its own dead-man timer.
 *
 * Both thresholds are sized against the measured frame cadence of the running
 * plant: STATUS arrives ~1 Hz per loop (p95 inter-frame gap 859 ms, max 906 ms
 * over a 30 s window, 4 loops).
 */
/** Silence beyond this and the values on screen are no longer presented as live. */
export const STALE_AFTER_MS = 6_000;
/** Silence beyond this and the socket itself is presumed dead: recycle it. */
export const SILENCE_RECYCLE_MS = 12_000;
/** Dead-man timer resolution. Only flips state when a threshold is actually crossed. */
const LIVENESS_TICK_MS = 1_000;

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
  // Last frame per (type, loop_id): a subscriber mounting after a frame arrived
  // renders it at once instead of blanking until the next one (§7 replay).
  const frames = useRef(createFrameCache());
  // Two clocks, deliberately separate.
  //  - `lastArrivalAt` — the link is delivering SOMETHING. Drives the socket
  //    watchdog: a frame held back by a resync is still proof the pipe works.
  //  - `lastRenderAt` — a frame actually reached the subscribers, i.e. the
  //    numbers on screen changed. Drives `stale`. Collapsing the two let a
  //    reconnect whose resync kept failing clear the stale mark while the
  //    dashboard was still showing pre-outage values: frozen AND unmarked,
  //    the exact failure this ticket exists to remove.
  // Refs, not state: frames land ~4/s and nothing reads a timestamp while the
  // link is healthy. Only the derived `stale` flag is state, written on flip.
  const lastArrivalAt = useRef<number | null>(null);
  const lastRenderAt = useRef<number | null>(null);
  const recycledForSilence = useRef(false);
  const [staleSince, setStaleSince] = useState<number | null>(null);

  const setPhaseBoth = (p: ConnectionPhase): void => {
    phaseRef.current = p;
    setPhase(p);
  };

  const subscribe = useCallback((type: RealtimeType, handler: Handler) => {
    const set = subs.current.get(type) ?? new Set<Handler>();
    set.add(handler);
    subs.current.set(type, set);
    frames.current.replay(type, handler);
    return () => {
      set.delete(handler);
    };
  }, []);

  const replay = useCallback((type: RealtimeType, handler: Handler) => {
    frames.current.replay(type, handler);
  }, []);

  const lastSeenTs = useCallback(
    (type: RealtimeType) => tracker.current.lastSeenTs(type),
    [],
  );

  useEffect(() => {
    if (!token) {
      setPhaseBoth('idle');
      lastArrivalAt.current = null;
      lastRenderAt.current = null;
      recycledForSilence.current = false;
      setStaleSince(null);
      return;
    }
    let cancelled = false;
    let reconnectTimer: ReturnType<typeof setTimeout> | undefined;
    const cache = frames.current; // stable for this effect run; safe in cleanup

    /** The link is delivering — regardless of whether we may render it yet. */
    const markArrival = (): void => {
      lastArrivalAt.current = Date.now();
      recycledForSilence.current = false;
    };

    const dispatch = (env: AnyEnvelope): void => {
      cache.put(env);
      subs.current.get(env.type)?.forEach((h) => h(env));
      // The screen now shows a current value, so and only so does `stale`
      // clear. Bails out without a render while already fresh (Object.is).
      lastRenderAt.current = Date.now();
      setStaleSince((prev) => (prev === null ? prev : null));
    };

    const bufferDuringResync = (env: AnyEnvelope): void => {
      if (env.type === 'status' || env.type === 'stats') {
        coalesced.current.set(frameKey(env), env);
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
      // REST becomes the truth again: every cached frame predates the gap.
      cache.clear();
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

    const scheduleReconnect = (): void => {
      setPhaseBoth('connecting');
      reconnectTimer = setTimeout(connect, backoff.current);
      backoff.current = Math.min(backoff.current * 2, MAX_BACKOFF_MS);
    };

    const connect = (): void => {
      // Deliberately does NOT set `connecting`: that phase is the shell's
      // "link lost" alarm, and flashing it for the ~50 ms of a healthy first
      // handshake on every page load is how an operator learns to ignore it.
      // `scheduleReconnect` owns the transition; the first attempt stays `idle`.
      const proto = location.protocol === 'https:' ? 'wss' : 'ws';
      const ws = new WebSocket(`${proto}://${location.host}/ws/realtime`);
      wsRef.current = ws;
      tracker.current.reset(); // new connection = new seq baseline (last_seen_ts kept)

      ws.onopen = () => {
        ws.send(JSON.stringify({ type: 'auth', token })); // realtime.py:208-216
      };

      ws.onmessage = (e: { data: string }) => {
        // Only the socket we currently own may speak. A socket from a previous
        // effect run, or one the watchdog already gave up on, must never mark
        // the link alive or push a frame — that is how a half-open connection
        // that wakes up late resurrects itself behind a live one.
        if (cancelled || wsRef.current !== ws) return;
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
        markArrival();
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
        scheduleReconnect();
      };
    };

    /**
     * Dead-man timer. Two escalating consequences for one input — silence:
     *  - past STALE_AFTER_MS the readouts stop claiming to be live;
     *  - past SILENCE_RECYCLE_MS the socket itself is presumed dead and
     *    replaced, which is the ONLY way out of a half-open connection.
     *
     * At most one recycle per silent episode: a genuinely quiet plant behind a
     * healthy socket must settle into "stale but connected", not flap the
     * banner once every SILENCE_RECYCLE_MS.
     */
    const checkLiveness = (): void => {
      // Staleness is about the SCREEN: how long since a frame was rendered.
      const rendered = lastRenderAt.current;
      if (rendered !== null && Date.now() - rendered > STALE_AFTER_MS) {
        setStaleSince((prev) => (prev === rendered ? prev : rendered));
      }

      // Recycling is about the SOCKET: how long since anything arrived. A
      // resync that keeps failing still proves the pipe works, so it must not
      // trigger a recycle on top of the one §8 already schedules.
      const at = lastArrivalAt.current;
      if (at === null) return; // nothing has ever arrived — not an outage yet
      const silentFor = Date.now() - at;
      const dead = wsRef.current;
      if (
        silentFor > SILENCE_RECYCLE_MS &&
        phaseRef.current === 'live' &&
        dead !== null &&
        !recycledForSilence.current
      ) {
        recycledForSilence.current = true;
        // Detach BEFORE closing: a proxy that eventually notices the dead
        // upstream would otherwise deliver a close for a socket we have already
        // replaced, stacking a second reconnect on the one scheduled here.
        dead.onopen = null;
        dead.onmessage = null;
        dead.onclose = null;
        wsRef.current = null;
        dead.close();
        scheduleReconnect();
      }
    };

    connect();
    const liveness = setInterval(checkLiveness, LIVENESS_TICK_MS);
    return () => {
      cancelled = true;
      clearInterval(liveness);
      clearTimeout(reconnectTimer);
      wsRef.current?.close();
      wsRef.current = null;
      lastArrivalAt.current = null;
      lastRenderAt.current = null;
      recycledForSilence.current = false;
      // A new socket starts from a clean slate: leaving the flag set would
      // strand the banner on a link that is about to be rebuilt.
      setStaleSince(null);
      cache.clear();
    };
  }, [token, resync, onAuthExpired]);

  const value = useMemo<RealtimeContextValue>(
    () => ({
      phase,
      connected: phase === 'live' || phase === 'resyncing',
      live: phase === 'live',
      stale: staleSince !== null,
      staleSince,
      subscribe,
      replay,
      lastSeenTs,
    }),
    [phase, staleSince, subscribe, replay, lastSeenTs],
  );
  return <RealtimeContext.Provider value={value}>{children}</RealtimeContext.Provider>;
}