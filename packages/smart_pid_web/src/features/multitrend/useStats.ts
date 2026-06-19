import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiGet } from '../../api/client';
import { useRealtime } from '../../realtime/useRealtime';
import { toStatsRow, type StatsDto } from './format';
import type { StatsRow } from './types';

// GET /controllers/stats -> list[StatsResponse]. StatsResponse is the same snake_case
// shape as the live STATS.{id} bus payload, plus controller_id (dtos/ai.py StatsResponse).
interface StatsResponse extends StatsDto {
  controller_id: number;
}

export function useStats(): { rows: StatsRow[]; isLoading: boolean } {
  const { lastStats } = useRealtime();
  const query = useQuery({
    queryKey: ['stats', 'all'],
    queryFn: () => apiGet<StatsResponse[]>('/controllers/stats'),
    refetchInterval: 5000, // REST fallback; live overlay below keeps it fresh between polls
  });

  const rows = useMemo<StatsRow[]>(() => {
    const seed = new Map<number, StatsRow>();
    for (const r of query.data ?? []) {
      seed.set(r.controller_id, toStatsRow(r.controller_id, r));
    }
    // Live overlay: bus stats win over the REST seed (same snake_case shape).
    for (const [loopId, dto] of lastStats) {
      seed.set(loopId, toStatsRow(loopId, dto));
    }
    return [...seed.values()].sort((a, b) => a.loopId - b.loopId);
  }, [query.data, lastStats]);

  return { rows, isLoading: query.isLoading };
}
