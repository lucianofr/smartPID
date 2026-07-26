import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import type { ApiError } from '@/api/client';
import { endpoints } from '@/api/endpoints';
import { queryKeys } from '@/api/queryKeys';
import type { AiTuningLogRow, OpcuaStatus, SystemStatusResponse } from '@/api/types';
import { useControllers } from '@/features/dashboard/useControllers';
import { useLoopStatuses } from '@/features/dashboard/useLoopStatuses';
import { useStats } from '@/features/multitrend/useStats';
import type { SystemEventData } from '@/lib/envelope';
import { useRealtime } from '@/realtime/useRealtime';
import {
  aggregate,
  aiRoi,
  healthOf,
  rankBadActors,
  type AggregateKpis,
  type AiRoi,
  type BackendHealthState,
  type ExecutiveLoop,
  type OpcState,
} from './types';

/**
 * Executive dashboard data (§13 phase 9).
 *
 * REST seeds the whole page; the live bus overlays it. Nothing here re-fetches
 * what an operational feature already owns:
 *  - the roster is `useControllers` (canonical `queryKeys.controllers`, so the
 *    §7 resync's `setQueryData` lands here without a refetch),
 *  - the metrics are phase 7's `useStats` — REST poll + STATS.{id} overlay,
 *  - the live modes are phase 4's `useLoopStatuses`.
 * Only `/system/status`, `/opcua/status` and the AI tuning log are fetched here.
 *
 * The stats overlay is read-only by construction: `useStats` merges the live
 * frame into a derived map and never writes back into the query cache, so a
 * REST refetch still returns the server's own snapshot.
 */

/** REST cadence for the two page-owned snapshots; the bus keeps stats fresh. */
export const EXECUTIVE_POLL_MS = 10_000;

export type ExecutivePeriod = '1h' | '8h' | '24h' | '7d';

const HOUR_MS = 3_600_000;

export const PERIOD_OPTIONS: readonly { key: ExecutivePeriod; label: string; ms: number }[] = [
  { key: '1h', label: 'Última hora', ms: HOUR_MS },
  { key: '8h', label: 'Últimas 8 h', ms: 8 * HOUR_MS },
  { key: '24h', label: 'Últimas 24 h', ms: 24 * HOUR_MS },
  { key: '7d', label: 'Últimos 7 dias', ms: 7 * 24 * HOUR_MS },
];

export interface ExecutiveWindow {
  start: string;
  end: string;
}

export function periodWindow(period: ExecutivePeriod, endMs: number): ExecutiveWindow {
  const span = PERIOD_OPTIONS.find((o) => o.key === period)?.ms ?? 24 * HOUR_MS;
  return { start: new Date(endMs - span).toISOString(), end: new Date(endMs).toISOString() };
}

/**
 * Window anchor, rounded down to the minute. A fresh `Date.now()` per render
 * would mint a new query key every render and refetch forever; a frozen anchor
 * would stop showing tunings as the shift goes on. A minute is the compromise.
 */
const ANCHOR_MS = 60_000;
function useMinuteAnchor(): number {
  const [anchor, setAnchor] = useState(() => Math.floor(Date.now() / ANCHOR_MS) * ANCHOR_MS);
  useEffect(() => {
    const id = setInterval(
      () => setAnchor(Math.floor(Date.now() / ANCHOR_MS) * ANCHOR_MS),
      ANCHOR_MS / 2,
    );
    return () => clearInterval(id);
  }, []);
  return anchor;
}

export interface ExecutiveData {
  loops: ExecutiveLoop[];
  kpis: AggregateKpis;
  badActors: ExecutiveLoop[];
  /** null when the tuning log cannot support a before/after comparison. */
  roi: AiRoi | null;
  tuningEvents: number;
  health: BackendHealthState;
  opc: OpcState;
  /** Latest EVENT.SYSTEM frame; the bus carries no counters, only events. */
  lastSystemEvent: SystemEventData | null;
  window: ExecutiveWindow;
  isPending: boolean;
  isError: boolean;
  refetch(): void;
}

export function useExecutiveData(period: ExecutivePeriod): ExecutiveData {
  const anchor = useMinuteAnchor();
  const window = useMemo(() => periodWindow(period, anchor), [period, anchor]);

  const controllers = useControllers();
  const statuses = useLoopStatuses();
  const stats = useStats();

  const opcua = useQuery<OpcuaStatus, ApiError>({
    queryKey: queryKeys.opcuaStatus,
    queryFn: () => endpoints.opcuaStatus(),
    refetchInterval: EXECUTIVE_POLL_MS,
  });

  const system = useQuery<SystemStatusResponse, ApiError>({
    queryKey: queryKeys.systemStatus,
    queryFn: () => endpoints.systemStatus(),
    refetchInterval: EXECUTIVE_POLL_MS,
  });

  const tuning = useQuery<AiTuningLogRow[], ApiError>({
    queryKey: queryKeys.aiTuningHistory(window),
    queryFn: () => endpoints.aiTuningHistory(window),
  });

  const systemEvent = useRealtime<SystemEventData>(null, 'system');

  const loops = useMemo<ExecutiveLoop[]>(() => {
    const metrics = new Map(stats.rows.map((r) => [r.loopId, r]));
    return (controllers.data ?? []).map((c) => {
      const live = statuses.get(c.id);
      const mode = live?.mode ?? c.mode;
      const row = metrics.get(c.id);
      return {
        loopId: c.id,
        name: c.name,
        mode,
        // Roster-level truth: the AI only acts on a loop that has optimization
        // switched on AND an engine selected (`NONE` is the opted-out default).
        ai: c.optimization_enabled === true && (c.ai_config?.engine ?? 'NONE') !== 'NONE',
        iae: row?.iae ?? null,
        variabilityRange: row?.varRange ?? null,
        tv: row?.tv ?? null,
        health: healthOf(mode, live !== undefined),
      };
    });
  }, [controllers.data, statuses, stats.rows]);

  const kpis = useMemo(() => aggregate(loops), [loops]);
  const badActors = useMemo(() => rankBadActors(loops), [loops]);
  const roi = useMemo(() => aiRoi(tuning.data ?? []), [tuning.data]);

  return {
    loops,
    kpis,
    badActors,
    roi,
    tuningEvents: tuning.data?.length ?? 0,
    health: system.data ?? {},
    opc: opcua.data?.state ?? 'OFFLINE',
    lastSystemEvent: systemEvent.last?.data ?? null,
    window,
    isPending: controllers.isPending || system.isPending,
    isError: controllers.isError || system.isError || opcua.isError,
    refetch: () => {
      void controllers.refetch();
      void opcua.refetch();
      void system.refetch();
      void tuning.refetch();
      stats.refetch();
    },
  };
}
