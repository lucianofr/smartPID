import { useEffect, useRef, useState } from 'react';
import type { TrendData } from '../../components/RealtimeTrend';
import type { StatusData } from '../../realtime/envelope';
import { useSimulatorStatus } from './useSimulatorStatus';

/** Empty [t, pv, sp, co] tuple for an unpopulated twin trend. */
export const EMPTY_TREND: TrendData = [[], [], [], []];

/** Default ring-buffer cap (~600 frames of live twin response). */
const DEFAULT_CAP = 600;

/**
 * Derive epoch SECONDS from a STATUS frame's `timestamp`, tolerant of both
 * publish shapes (see realtime/envelope.ts): number passthrough (monitor mode),
 * ISO-8601 string -> Date.parse / 1000 (execute mode). On unparseable input,
 * continue from the last x (or 0) so the series stays monotonic.
 */
function toEpochSeconds(ts: string | number, prevX: TrendData[0]): number {
  const parsed = typeof ts === 'number' ? ts : Date.parse(ts) / 1000;
  if (!Number.isNaN(parsed)) return parsed;
  const last = prevX.at(-1);
  return last !== undefined ? last + 1 : 0;
}

/**
 * Pure: append one twin sample (pv/sp/co read from FFSignal `.value`) onto a
 * COPY of each series, capped to `cap` keeping the newest. Returns `prev`
 * unchanged when `status` is undefined. All four series stay equal-length.
 */
export function appendTwinSample(
  prev: TrendData,
  status: StatusData | undefined,
  cap = DEFAULT_CAP,
): TrendData {
  if (!status) return prev;
  const x = toEpochSeconds(status.timestamp, prev[0]);
  const next: TrendData = [
    [...prev[0], x],
    [...prev[1], status.pv.value],
    [...prev[2], status.sp.value],
    [...prev[3], status.co.value],
  ];
  if (next[0].length > cap) {
    const excess = next[0].length - cap;
    return [
      next[0].slice(excess),
      next[1].slice(excess),
      next[2].slice(excess),
      next[3].slice(excess),
    ];
  }
  return next;
}

/**
 * Accumulate the live twin response for a single simulator loop into a
 * `TrendData` suitable for `<RealtimeTrend data={...} />`. The per-loop
 * `StatusData` reference changes only when that loop receives a new frame, so
 * the append effect runs once per frame (no render loop). Resets when the
 * selected `controllerId` changes.
 */
export function useTwinTrend(controllerId: number | null): TrendData {
  const status = useSimulatorStatus().live.get(controllerId ?? -1);
  const ref = useRef<TrendData>(EMPTY_TREND);
  const [, forceRender] = useState(0);

  // Reset accumulator when the selected loop changes.
  useEffect(() => {
    ref.current = EMPTY_TREND;
    forceRender((n) => n + 1);
  }, [controllerId]);

  // Append once per new per-loop status frame.
  useEffect(() => {
    const next = appendTwinSample(ref.current, status);
    if (next !== ref.current) {
      ref.current = next;
      forceRender((n) => n + 1);
    }
  }, [status]);

  return ref.current;
}
