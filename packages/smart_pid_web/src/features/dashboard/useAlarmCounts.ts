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
import { ALARM_SEVERITIES, priorityRank, toSeverity } from '@/features/alarms/severity';
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
  controllerId: number;
  severity: AlarmSeverity;
  state: AlarmPointState;
}

/** Alarms carry no row id on the wire — they are keyed by (controller, type). */
const pointKey = (controllerId: number, alarmType: string): string =>
  `${controllerId}:${alarmType}`;

function fromRows(rows: readonly AlarmRow[]): ReadonlyMap<string, AlarmPoint> {
  // One point can own SEVERAL rows: every occurrence of (controller, type) is
  // its own row, and each stays in `/alarms/active` until acknowledged. Only
  // the newest describes the point's state now — folding them in arrival order
  // let the OLDEST win, so one stale `CLEARED_UNACK` masked a live alarm and
  // kept the bar lit for a process that had long since returned to normal.
  const newest = new Map<string, AlarmRow>();
  for (const row of rows) {
    const key = pointKey(row.controller_id, row.alarm_type);
    const seen = newest.get(key);
    if (seen === undefined || row.timestamp > seen.timestamp) newest.set(key, row);
  }

  const map = new Map<string, AlarmPoint>();
  for (const [key, row] of newest) {
    map.set(key, {
      controllerId: row.controller_id,
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

interface AlarmPointsResult {
  points: ReadonlyMap<string, AlarmPoint>;
  lastEvent: AlarmEventData | null;
}

/**
 * Shared point machine behind both `useAlarmCounts` (the §6.9 footer) and
 * `useLoopAlarmSeverity` (the §6.9 card border): one REST snapshot, one
 * EVENT.ALARM subscription, one (controller, type) → point map.
 *
 * REST is truth: every `/alarms/active` snapshot (initial load, ACK ALL
 * invalidation, §7 resync) replaces the point map. EVENT.ALARM frames then
 * advance it through the phase-3 machine, so a cleared-but-unacknowledged point
 * keeps demanding acknowledgement instead of silently vanishing.
 */
function useAlarmPoints(): AlarmPointsResult {
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
            controllerId: event.controller_id,
            severity: toSeverity(event.priority),
            state: transition(current, { kind: event.transition }),
          });
          return next;
        });
      }),
    [subscribe],
  );

  return { points, lastEvent };
}

/** Four-bucket alarm summary for the §6.9 footer. */
export function useAlarmCounts(): AlarmCounts {
  const { points, lastEvent } = useAlarmPoints();

  return useMemo(() => {
    const buckets = emptyBuckets();
    let totalUnacked = 0;
    for (const point of points.values()) {
      // ALM-5: an alarm leaves the banner once the process condition returns to
      // normal — acknowledged or not. A normalized-but-unacked point stays
      // listed and ackable on the alarms page (CLEARED_UNACK filter); it must
      // not keep the footer lit, because a quiet process needs a quiet footer.
      // Same predicate `useLoopAlarmSeverity` already applies to the card border.
      if (!isActive(point.state)) continue;
      const bucket = buckets[point.severity];
      bucket.active += 1;
      if (isUnacked(point.state)) {
        bucket.unacked += 1;
        totalUnacked += 1;
      }
    }
    return { buckets, totalUnacked, lastEvent };
  }, [points, lastEvent]);
}

/**
 * Highest-priority ACTIVE alarm per loop (§6.9 card border): the card border
 * shows the process alarm's own severity, distinct from the fieldbus-quality
 * signal the card's corner dot already owns. "Active" follows the phase-3
 * machine, not just "unacknowledged" — an acknowledged alarm whose condition
 * has not cleared must still color the border, because the process is still
 * out of limits even once someone has seen it.
 */
export function useLoopAlarmSeverity(): ReadonlyMap<number, AlarmSeverity> {
  const { points } = useAlarmPoints();

  return useMemo(() => {
    const map = new Map<number, AlarmSeverity>();
    for (const point of points.values()) {
      if (!isActive(point.state)) continue;
      const current = map.get(point.controllerId);
      if (current === undefined || priorityRank(point.severity) < priorityRank(current)) {
        map.set(point.controllerId, point.severity);
      }
    }
    return map;
  }, [points]);
}
