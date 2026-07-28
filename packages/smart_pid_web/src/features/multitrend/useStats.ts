import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import type { ApiError } from '@/api/client';
import { endpoints } from '@/api/endpoints';
import { queryKeys } from '@/api/queryKeys';
import type { StatsResponse } from '@/api/types';
import type { StatsData } from '@/lib/envelope';
import { useRealtime } from '@/realtime/useRealtime';

/**
 * Loop performance metrics (§6.8).
 *
 * REST is the roster: `GET /controllers/stats` returns one row per controller
 * that has a stats worker, and the multi-trend loop list is exactly that set.
 * STATS.{id} frames carry the SAME snake_case payload minus `controller_id`
 * (loop identity travels in the envelope), so a live frame simply supersedes
 * the polled row for that loop.
 */

/** REST fallback cadence; the live overlay keeps rows fresh between polls. */
export const STATS_POLL_MS = 5000;

/** Metric fields shared by the REST row and the wire payload. */
type StatsFields = Pick<
  StatsResponse,
  | 'iae'
  | 'ise'
  | 'itae'
  | 'mse'
  | 'std_dev'
  | 'total_variation'
  | 'variability_range'
  | 'variability_sp'
  | 'sample_count'
>;

export interface StatsRow {
  loopId: number;
  iae: number;
  ise: number;
  itae: number;
  mse: number;
  /** std_dev — the σ column. */
  sigma: number;
  /** total_variation — the TV column. */
  tv: number;
  /** variability_sp, a RATIO (2σ/SP). */
  varSp: number;
  /** variability_range, a RATIO (2σ/Range). */
  varRange: number;
  sampleCount: number;
}

export function toStatsRow(loopId: number, dto: StatsFields): StatsRow {
  return {
    loopId,
    iae: dto.iae,
    ise: dto.ise,
    itae: dto.itae,
    mse: dto.mse,
    sigma: dto.std_dev,
    tv: dto.total_variation,
    varSp: dto.variability_sp,
    varRange: dto.variability_range,
    sampleCount: dto.sample_count,
  };
}

export interface UseStatsResult {
  rows: StatsRow[];
  /** Controller ids with a stats worker, ascending — the multitrend roster. */
  loops: number[];
  isPending: boolean;
  isError: boolean;
  refetch(): void;
}

export function useStats(): UseStatsResult {
  const query = useQuery<StatsResponse[], ApiError>({
    queryKey: queryKeys.allStats,
    queryFn: () => endpoints.allStats(),
    refetchInterval: STATS_POLL_MS,
  });

  const stats = useRealtimeStats();

  const rows = useMemo(() => {
    const byLoop = new Map<number, StatsRow>();
    for (const row of query.data ?? []) {
      byLoop.set(row.controller_id, toStatsRow(row.controller_id, row));
    }
    for (const [loopId, data] of stats) byLoop.set(loopId, toStatsRow(loopId, data));
    return [...byLoop.values()].sort((a, b) => a.loopId - b.loopId);
  }, [query.data, stats]);

  return {
    rows,
    loops: rows.map((r) => r.loopId),
    isPending: query.isPending,
    isError: query.isError,
    refetch: () => void query.refetch(),
  };
}

/** Latest STATS payload per loop, replaced in place as frames arrive. */
function useRealtimeStats(): ReadonlyMap<number, StatsData> {
  const { subscribe } = useRealtime<StatsData>(null, 'stats');
  const [live, setLive] = useState<ReadonlyMap<number, StatsData>>(() => new Map());

  useEffect(
    () =>
      subscribe((env) => {
        const loopId = env.loop_id;
        if (loopId === null) return;
        setLive((prev) => new Map(prev).set(loopId, env.data));
      }),
    [subscribe],
  );

  return live;
}
