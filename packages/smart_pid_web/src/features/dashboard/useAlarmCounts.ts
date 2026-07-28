import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { endpoints } from '@/api/endpoints';
import { queryKeys } from '@/api/queryKeys';
import type { AlarmRow } from '@/api/types';
import {
  fromActiveRow,
  isActive,
  isUnacked,
  transition,
  type AlarmPointState,
} from '@/lib/alarmMachine';
import type { AlarmEventData } from '@/lib/envelope';
import { useRealtime } from '@/realtime/useRealtime';
import { ALARM_SEVERITIES, toSeverity } from '@/features/alarms/severity';
import type { AlarmSeverity } from '@/features/alarms/types';

/**
 * The severity vocabulary lives in `features/alarms` (§6.4 presentation map);
 * it is re-exported here because the footer and its tests were written against
 * this module first — one definition, two entry points.
 */
export { ALARM_SEVERITIES };
export type { AlarmSeverity };

export interface AlarmBucket {
  active: number;
  unacked: number;
}

export interface AlarmCounts {
  buckets: Record<AlarmSeverity, AlarmBucket>;
  totalUnacked: number;
  lastEvent: AlarmEventData | null;
}

interface AlarmPoint {
  severity: AlarmSeverity;
  state: AlarmPointState;
}

/** Alarms carry no row id on the wire — they are keyed by (controller, type). */
const pointKey = (controllerId: number, alarmType: string): string =>
  `${controllerId}:${alarmType}`;

function fromRows(rows: readonly AlarmRow[]): ReadonlyMap<string, AlarmPoint> {
  const map = new Map<string, AlarmPoint>();
  for (const row of rows) {
    map.set(pointKey(row.controller_id, row.alarm_type), {
      severity: toSeverity(row.priority),
      state: fromActiveRow(row),
    });
  }
  return map;
}

function emptyBuckets(): Record<AlarmSeverity, AlarmBucket> {
  return {
    CRITICAL: { active: 0, unacked: 0 },
    WARNING: { active: 0, unacked: 0 },
    ADVISORY: { active: 0, unacked: 0 },
    LOG: { active: 0, unacked: 0 },
  };
}

/**
 * Four-bucket alarm summary for the §6.9 footer.
 *
 * REST is truth: every `/alarms/active` snapshot (initial load, ACK ALL
 * invalidation, §7 resync) replaces the point map. EVENT.ALARM frames then
 * advance it through the phase-3 machine, so a cleared-but-unacknowledged point
 * keeps demanding acknowledgement instead of silently vanishing.
 */
export function useAlarmCounts(): AlarmCounts {
  const { data: rows } = useQuery({
    queryKey: queryKeys.alarmsActive,
    queryFn: () => endpoints.activeAlarms(),
  });
  const { subscribe } = useRealtime<AlarmEventData>(null, 'alarm');
  const [points, setPoints] = useState<ReadonlyMap<string, AlarmPoint>>(() => new Map());
  const [lastEvent, setLastEvent] = useState<AlarmEventData | null>(null);

  useEffect(() => {
    setPoints(fromRows(rows ?? []));
  }, [rows]);

  useEffect(
    () =>
      subscribe((env) => {
        const event = env.data;
        setLastEvent(event);
        setPoints((prev) => {
          const key = pointKey(event.controller_id, event.alarm_type);
          const current = prev.get(key)?.state ?? 'NORMAL';
          const next = new Map(prev);
          next.set(key, {
            severity: toSeverity(event.priority),
            state: transition(current, { kind: event.transition }),
          });
          return next;
        });
      }),
    [subscribe],
  );

  return useMemo(() => {
    const buckets = emptyBuckets();
    let totalUnacked = 0;
    for (const point of points.values()) {
      const bucket = buckets[point.severity];
      if (isActive(point.state)) bucket.active += 1;
      if (isUnacked(point.state)) {
        bucket.unacked += 1;
        totalUnacked += 1;
      }
    }
    return { buckets, totalUnacked, lastEvent };
  }, [points, lastEvent]);
}
