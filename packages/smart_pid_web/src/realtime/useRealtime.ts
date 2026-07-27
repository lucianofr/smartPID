import { useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import type { RealtimeEnvelope, RealtimeType } from '../lib/envelope';
import { RealtimeContext } from './RealtimeProvider';

export interface UseRealtimeResult<T> {
  /** Socket authenticated (live or resyncing). */
  connected: boolean;
  /** Resync complete — safe to render live values (§8). */
  live: boolean;
  /** Latest envelope for (loopId, type); null before the first one. */
  last: RealtimeEnvelope<T> | null;
  /**
   * Every-event callback subscription (alarm streams, §6.7 AI tick buffering).
   * Stable across frames, and — like the provider's own `subscribe` — it hands
   * `handler` the cached frames for this scope straight away, so a consumer
   * that mounts between two frames of a slow loop is not blank until the next.
   */
  subscribe(handler: (env: RealtimeEnvelope<T>) => void): () => void;
}

/**
 * Subscribe to one envelope type, optionally scoped to one loop
 * (loopId null = all loops). Spec §7 signature: useRealtime(loopId, type).
 */
export function useRealtime<T = unknown>(
  loopId: number | null,
  type: RealtimeType,
): UseRealtimeResult<T> {
  const ctx = useContext(RealtimeContext);
  if (!ctx) throw new Error('useRealtime must be used within RealtimeProvider');
  const { connected, live, subscribe, replay } = ctx;

  const [last, setLast] = useState<RealtimeEnvelope<T> | null>(null);
  // Late external subscribers still see events that arrive between render and
  // their own subscribe() call via the shared per-hook relay below.
  const relays = useRef(new Set<(env: RealtimeEnvelope<T>) => void>());

  const inScope = useCallback(
    (env: { loop_id: number | null }) => loopId === null || env.loop_id === loopId,
    [loopId],
  );

  useEffect(() => {
    setLast(null); // scope changed — a stale loop's frame must not leak
    return subscribe(type, (env) => {
      if (!inScope(env)) return;
      const typed = env as unknown as RealtimeEnvelope<T>;
      setLast(typed);
      relays.current.forEach((h) => h(typed));
    });
  }, [subscribe, type, inScope]);

  // Stable across envelopes: keying this on `last` would rebuild it at frame
  // rate and make every consumer effect tear down and re-register ~N times a
  // second. The replay below is what makes registration order irrelevant —
  // React runs the effect above (which triggers the provider's §7 replay)
  // BEFORE the consumer effect that adds `handler`, so without it the whole
  // replay lands in an empty relay set and a coalesced loop never renders.
  const relay = useCallback(
    (handler: (env: RealtimeEnvelope<T>) => void) => {
      relays.current.add(handler);
      replay(type, (env) => {
        if (inScope(env)) handler(env as unknown as RealtimeEnvelope<T>);
      });
      return () => {
        relays.current.delete(handler);
      };
    },
    [replay, type, inScope],
  );

  return useMemo(
    () => ({ connected, live, last, subscribe: relay }),
    [connected, live, last, relay],
  );
}