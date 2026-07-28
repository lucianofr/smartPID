import { useEffect, useState } from 'react';
import type { StatusData } from '@/lib/envelope';
import { useRealtime } from '@/realtime/useRealtime';

/**
 * Latest STATUS frame per loop.
 *
 * Uses the every-event `subscribe` relay rather than `last`: a burst that
 * carries one frame per loop inside a single task would collapse to the final
 * envelope under React 18 auto-batching, and every other loop would stay '—'.
 */
export function useLoopStatuses(): ReadonlyMap<number, StatusData> {
  const { subscribe } = useRealtime<StatusData>(null, 'status');
  const [byLoop, setByLoop] = useState<ReadonlyMap<number, StatusData>>(() => new Map());

  useEffect(
    () =>
      subscribe((env) => {
        const loopId = env.loop_id;
        if (loopId === null) return;
        setByLoop((prev) => new Map(prev).set(loopId, env.data));
      }),
    [subscribe],
  );

  return byLoop;
}
