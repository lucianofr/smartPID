import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import type { ApiError } from '@/api/client';
import { endpoints } from '@/api/endpoints';
import { queryKeys } from '@/api/queryKeys';
import type { StatsResponse } from '@/api/types';
import { STATS_POLL_MS, useRealtimeStats } from '@/features/multitrend/useStats';

/**
 * Full-precision loop stats for the Stats screen (§6.8 detail view).
 *
 * `multitrend/useStats` narrows each row to its 9-field `StatsRow` for the
 * trend workspace's comparison table. This screen wants EVERY metric
 * `StatsResponse` carries, so it shares the same canonical `queryKeys.allStats`
 * query and the exported `useRealtimeStats()` overlay instead of duplicating
 * the fetch/poll wiring — TanStack dedupes the request across both pages.
 */

/** One loop's full metric set, camelCase identity + the wire's metric fields verbatim. */
export type LoopStatsRow = Omit<StatsResponse, 'controller_id'> & { controllerId: number };

export interface UseLoopStatsResult {
  rows: LoopStatsRow[];
  isPending: boolean;
  isError: boolean;
  refetch(): void;
}

function toRow(controllerId: number, dto: Omit<StatsResponse, 'controller_id'>): LoopStatsRow {
  return { ...dto, controllerId };
}

export function useLoopStats(): UseLoopStatsResult {
  const query = useQuery<StatsResponse[], ApiError>({
    queryKey: queryKeys.allStats,
    queryFn: () => endpoints.allStats(),
    refetchInterval: STATS_POLL_MS,
  });

  const stats = useRealtimeStats();

  const rows = useMemo(() => {
    const byLoop = new Map<number, LoopStatsRow>();
    for (const row of query.data ?? []) {
      const { controller_id, ...rest } = row;
      byLoop.set(controller_id, toRow(controller_id, rest));
    }
    for (const [loopId, data] of stats) byLoop.set(loopId, toRow(loopId, data));
    return [...byLoop.values()].sort((a, b) => a.controllerId - b.controllerId);
  }, [query.data, stats]);

  return {
    rows,
    isPending: query.isPending,
    isError: query.isError,
    refetch: () => void query.refetch(),
  };
}
