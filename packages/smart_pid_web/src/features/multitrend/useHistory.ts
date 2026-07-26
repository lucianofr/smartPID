import { useQuery, type UseQueryResult } from '@tanstack/react-query';
import type { ApiError } from '@/api/client';
import { endpoints } from '@/api/endpoints';
import { queryKeys } from '@/api/queryKeys';
import type { HistoryResponse, TelemetryFrame } from '@/api/types';
import { decimateHistory } from './decimate';
import type { AlignedSeries, SignalKey } from './types';
import { SIGNALS } from './types';

/**
 * Historical telemetry for one loop (§6.8). The operator picks a DURATION, not
 * two datetimes: "the last two hours" is the question a trend answers, and the
 * end bound is always now.
 *
 * `/history/{controller_id}` takes optional start/end/limit (unlike
 * `/alarms/history`, which requires both bounds) — both are still sent, because
 * an unbounded replay of a historian table is not a window.
 */

export type HistoryUnit = 'segundo' | 'minuto' | 'hora';

export const HISTORY_UNITS: readonly HistoryUnit[] = ['segundo', 'minuto', 'hora'];

const UNIT_SECONDS: Record<HistoryUnit, number> = { segundo: 1, minuto: 60, hora: 3600 };
const SECONDS_PER_HOUR = 3600;

/** Row cap: ~1 Hz over 24 h, well past any window the form can request. */
export const HISTORY_LIMIT = 100_000;

export interface HistoryWindow {
  controllerId: number;
  /** Window length in HOURS — the duration in its canonical unit. */
  hours: number;
  /** ISO-8601 bounds derived from `hours`, ending at the request instant. */
  start: string;
  end: string;
  limit: number;
}

export function historyWindow(
  controllerId: number,
  amount: number,
  unit: HistoryUnit,
  now: number = Date.now(),
): HistoryWindow {
  const seconds = Math.max(1, amount) * UNIT_SECONDS[unit];
  return {
    controllerId,
    hours: seconds / SECONDS_PER_HOUR,
    start: new Date(now - seconds * 1000).toISOString(),
    end: new Date(now).toISOString(),
    limit: HISTORY_LIMIT,
  };
}

/** `null` keeps the query idle — the page must not replay history unasked. */
export function useHistory(range: HistoryWindow | null): UseQueryResult<HistoryResponse, ApiError> {
  return useQuery<HistoryResponse, ApiError>({
    queryKey: queryKeys.history(range ?? { idle: true }),
    queryFn: () => {
      if (range === null) throw new Error('history query ran without a window');
      return endpoints.history(range.controllerId, {
        start: range.start,
        end: range.end,
        limit: range.limit,
      });
    },
    enabled: range !== null,
  });
}

/**
 * Wire frames → decimated uPlot columns. `timestamp` is an ISO date-time on
 * this route (TelemetryFrameDTO), so the epoch-seconds axis is derived here.
 */
export function historySeries(
  controllerId: number,
  frames: readonly TelemetryFrame[],
  pxWidth: number,
): AlignedSeries {
  const keys: SignalKey[] = SIGNALS.map((signal) => ({ loopId: controllerId, signal }));
  const t: number[] = [];
  const rows: number[][] = [[], [], []];
  for (const frame of frames) {
    const ms = Date.parse(frame.timestamp);
    if (Number.isNaN(ms)) continue;
    t.push(ms / 1000);
    rows[0].push(frame.pv);
    rows[1].push(frame.sp);
    rows[2].push(frame.co);
  }
  return { keys, data: decimateHistory(t, rows, pxWidth) };
}
