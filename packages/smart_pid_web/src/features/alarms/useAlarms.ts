import { useEffect, useMemo, useRef } from 'react';
import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from '@tanstack/react-query';
import type { ApiError } from '@/api/client';
import { endpoints, type SystemEventRow } from '@/api/endpoints';
import { queryKeys } from '@/api/queryKeys';
import { toast } from '@/components/Toast';
import type { AlarmEventData } from '@/lib/envelope';
import { useRealtime } from '@/realtime/useRealtime';
import { isUnackedStatus, priorityRank, toSeverity } from './severity';
import type { ActiveAlarm, AlarmSeverity, AlarmStatus, AlarmType } from './types';

/**
 * Alarm data access. REST is the ONLY source of alarm ROWS: an EVENT.ALARM
 * envelope carries a (controller, type) transition, never a row id or an ack
 * state (GAP-3b), so it can trigger a reconcile but can never author a row.
 *
 * Acknowledgement is never optimistic — process truth is what the backend
 * returns after the POST, so every mutation settles into a refetch.
 */

/** A flood emits hundreds of frames a second; one reconcile per window is enough. */
export const REFETCH_COALESCE_MS = 500;

/** Backend history default is 100 (alarms.py get_alarm_history) — too small for
 *  an operator window. */
export const HISTORY_LIMIT = 1000;

export type AlarmSort = 'severity' | 'time';

export interface AlarmFilters {
  sort: AlarmSort;
  status: AlarmStatus | 'ALL';
  controllerId: number | 'ALL';
}

export const DEFAULT_ALARM_FILTERS: AlarmFilters = {
  sort: 'severity',
  status: 'ALL',
  controllerId: 'ALL',
};

/** Refetch the authoritative list when the wire says something changed. */
function useAlarmRealtimeSync(): void {
  const queryClient = useQueryClient();
  const { subscribe } = useRealtime<AlarmEventData>(null, 'alarm');
  const pending = useRef<number | undefined>(undefined);

  // Unmount-only: the relay identity is stable, but clearing the timer inside
  // the subscribe effect would still starve the coalescing window whenever
  // that effect re-ran, and the pending refetch must outlive a re-registration.
  useEffect(
    () => () => {
      window.clearTimeout(pending.current);
      pending.current = undefined;
    },
    [],
  );

  useEffect(
    () =>
      subscribe(() => {
        if (pending.current !== undefined) return;
        pending.current = window.setTimeout(() => {
          pending.current = undefined;
          void queryClient.invalidateQueries({ queryKey: queryKeys.alarmsActive });
        }, REFETCH_COALESCE_MS);
      }),
    [subscribe, queryClient],
  );
}

export function useActiveAlarms(): UseQueryResult<ActiveAlarm[], ApiError> {
  useAlarmRealtimeSync();
  return useQuery<ActiveAlarm[], ApiError>({
    queryKey: queryKeys.alarmsActive,
    queryFn: () => endpoints.activeAlarms(),
  });
}

export function useAckAlarm(): UseMutationResult<Record<string, unknown>, ApiError, number> {
  const queryClient = useQueryClient();
  return useMutation<Record<string, unknown>, ApiError, number>({
    mutationFn: (alarmId) => endpoints.ackAlarm(alarmId),
    onError: () => {
      toast({ title: 'Falha ao reconhecer alarme', tone: 'crit' });
    },
    // Settled, not success: a rejected ack must still reconcile with the server.
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.alarmsActive });
    },
  });
}

export function useAckAllAlarms(): UseMutationResult<Record<string, unknown>, ApiError, void> {
  const queryClient = useQueryClient();
  return useMutation<Record<string, unknown>, ApiError, void>({
    mutationFn: () => endpoints.ackAllAlarms(),
    onError: () => {
      toast({ title: 'Falha ao reconhecer alarmes', tone: 'crit' });
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.alarmsActive });
    },
  });
}

export interface AlarmLoop {
  id: number;
  name: string;
}

export interface UseAlarmsResult {
  /** Deduped, filtered and sorted rows — what the panel renders. */
  rows: ActiveAlarm[];
  /** Loops present in the UNFILTERED set, so the loop filter cannot self-empty. */
  loops: AlarmLoop[];
  /** Drives the assertive announcement and the unacked encodings. */
  unackedCritical: number;
  isPending: boolean;
  isError: boolean;
  refetch: () => void;
  ack: UseMutationResult<Record<string, unknown>, ApiError, number>;
}

export function useAlarms(filters: AlarmFilters = DEFAULT_ALARM_FILTERS): UseAlarmsResult {
  const query = useActiveAlarms();
  const ack = useAckAlarm();
  const data = query.data;
  const { sort, status, controllerId } = filters;

  const rows = useMemo(() => {
    // Dedupe by id first: a resync snapshot can overlap the live list.
    const byId = new Map<number, ActiveAlarm>();
    for (const row of data ?? []) byId.set(row.id, row);
    const list = [...byId.values()].filter(
      (row) =>
        (status === 'ALL' || row.status === status) &&
        (controllerId === 'ALL' || row.controller_id === controllerId),
    );
    list.sort((a, b) =>
      sort === 'severity'
        ? priorityRank(toSeverity(a.priority)) - priorityRank(toSeverity(b.priority)) ||
          b.timestamp.localeCompare(a.timestamp)
        : b.timestamp.localeCompare(a.timestamp),
    );
    return list;
  }, [data, sort, status, controllerId]);

  const loops = useMemo(() => {
    const byId = new Map<number, string>();
    for (const row of data ?? []) {
      byId.set(row.controller_id, row.controller_name ?? `#${row.controller_id}`);
    }
    return [...byId]
      .map(([id, name]) => ({ id, name }))
      .sort((a, b) => a.name.localeCompare(b.name));
  }, [data]);

  const unackedCritical = useMemo(
    () =>
      (data ?? []).filter(
        (row) => toSeverity(row.priority) === 'CRITICAL' && isUnackedStatus(row.status),
      ).length,
    [data],
  );

  return {
    rows,
    loops,
    unackedCritical,
    isPending: query.isPending,
    isError: query.isError,
    refetch: () => void query.refetch(),
    ack,
  };
}

export interface AlarmHistoryFilter {
  /** ISO-8601 — the backend REQUIRES both bounds
   *  (alarms.py get_alarm_history). */
  start: string;
  end: string;
  limit: number;
  priority: AlarmSeverity | 'ALL';
  type: AlarmType | 'ALL';
  controllerId: number | 'ALL';
}

/**
 * Alarms and system/optimizer events are two separate backend tables
 * (`Log_Alarmes` / `Log_System_Events`), so a history row is one or the other.
 * `kind` is the discriminator; an event has no alarm type, value, limit or ack
 * state and the renderer must never fabricate them.
 */
export type HistoryRow =
  | ({ kind: 'alarm' } & ActiveAlarm)
  | {
      kind: 'event';
      id: number;
      timestamp: string;
      source: string;
      severity: AlarmSeverity;
      message: string;
    };

/**
 * `priority` and `type` are NOT history query parameters — neither
 * `/alarms/history` nor `/system-events` narrows by them the way the panel
 * needs — so they narrow the fetched window client-side instead of silently
 * doing nothing on the wire.
 */
export function filterHistoryRows(
  rows: readonly HistoryRow[],
  filter: Pick<AlarmHistoryFilter, 'priority' | 'type'>,
): HistoryRow[] {
  return rows.filter((row) => {
    const severity = row.kind === 'alarm' ? toSeverity(row.priority) : row.severity;
    if (filter.priority !== 'ALL' && severity !== filter.priority) return false;
    // `type` names an alarm limit kind. A system event has none, so a specific
    // selection excludes events; `ALL` keeps them.
    if (filter.type !== 'ALL' && (row.kind !== 'alarm' || row.alarm_type !== filter.type)) {
      return false;
    }
    return true;
  });
}

export function useAlarmHistory(
  filter: AlarmHistoryFilter,
  enabled = true,
): UseQueryResult<HistoryRow[], ApiError> {
  return useQuery<HistoryRow[], ApiError>({
    queryKey: queryKeys.alarmsHistory({ ...filter }),
    enabled,
    // A filter change must not blank the table back to a loading state —
    // the operator keeps reading the previous window until the new one lands.
    placeholderData: (previous) => previous,
    queryFn: async () => {
      // A system event carries no controller id, so it can never satisfy a
      // specific-loop selection — skip the request instead of fetching rows the
      // filter would drop. `Malha = Todas` fetches both logs.
      const controllerId = filter.controllerId === 'ALL' ? undefined : filter.controllerId;
      const [alarms, events] = await Promise.all([
        endpoints.alarmHistory({
          start: filter.start,
          end: filter.end,
          limit: filter.limit,
          ...(controllerId === undefined ? {} : { controllerId }),
        }),
        controllerId === undefined
          ? endpoints.systemEvents({
              start: filter.start,
              end: filter.end,
              limit: filter.limit,
            })
          : Promise.resolve<SystemEventRow[]>([]),
      ]);

      const rows: HistoryRow[] = [
        ...alarms.map((row): HistoryRow => ({ kind: 'alarm', ...row })),
        ...events.map(
          (row): HistoryRow => ({
            kind: 'event',
            id: row.id,
            timestamp: row.timestamp,
            source: row.source,
            severity: toSeverity(row.severity),
            message: row.message,
          }),
        ),
      ];
      rows.sort((a, b) => Date.parse(b.timestamp) - Date.parse(a.timestamp));
      return filterHistoryRows(rows, filter);
    },
  });
}
