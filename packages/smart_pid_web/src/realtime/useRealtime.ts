import { useContext, useEffect, useMemo, useRef, useState } from 'react';
import type { RealtimeEnvelope, RealtimeType } from '../lib/envelope';
import { RealtimeContext } from './RealtimeProvider';

export interface UseRealtimeResult<T> {
  /** Socket authenticated (live or resyncing). */
  connected: boolean;
  /** Resync complete — safe to render live values (§8). */
  live: boolean;
  /** Latest envelope for (loopId, type); null before the first one. */
  last: RealtimeEnvelope<T> | null;
  /** Every-event callback subscription (alarm streams, §6.7 AI tick buffering). */
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
  const { connected, live, subscribe } = ctx;

  const [last, setLast] = useState<RealtimeEnvelope<T> | null>(null);
  // Late external subscribers still see events that arrive between render and
  // their own subscribe() call via the shared per-hook relay below.
  const relays = useRef(new Set<(env: RealtimeEnvelope<T>) => void>());

  useEffect(() => {
    setLast(null); // scope changed — a stale loop's frame must not leak
    return subscribe(type, (env) => {
      if (loopId !== null && env.loop_id !== loopId) return;
      const typed = env as unknown as RealtimeEnvelope<T>;
      setLast(typed);
      relays.current.forEach((h) => h(typed));
    });
  }, [subscribe, type, loopId]);

  return useMemo(
    () => ({
      connected,
      live,
      last,
      subscribe(handler: (env: RealtimeEnvelope<T>) => void) {
        relays.current.add(handler);
        return () => {
          relays.current.delete(handler);
        };
      },
    }),
    [connected, live, last],
  );
}