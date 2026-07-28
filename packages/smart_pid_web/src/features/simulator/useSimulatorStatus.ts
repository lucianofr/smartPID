import { useQuery } from '@tanstack/react-query';
import { ApiError } from '@/api/client';
import { queryKeys } from '@/api/queryKeys';
import type { SimulatorStatus } from '@/api/types';
import { useCan } from '@/auth/useCan';
import { simulatorApi } from './api';

export interface SimulatorStatusResult {
  /** Whole-twin snapshot; undefined until the admin poll lands. */
  data: SimulatorStatus | undefined;
  /** This session may not READ the twin's configuration — a designed state. */
  restricted: boolean;
  /** An allowed read is still in flight (always false when restricted). */
  isPending: boolean;
}

/** Same cadence as the OPC-UA poll — the twin moves, the snapshot must follow. */
const POLL_MS = 5_000;

/**
 * The twin snapshot behind every configuration control.
 *
 * GET `/simulator/status` is admin-only, so this NEVER fires without
 * `simulator.configure`: an unconditional call would hand a plain operator a
 * "sem permissão" toast plus a wasted `/auth/me` refetch (§11 side effects) on
 * every visit to the Sim page. A 403 that slips through anyway (role changed
 * mid-session) collapses into the same restricted state, and `retry: false`
 * keeps a permission wall from becoming a retry storm.
 */
export function useSimulatorStatus(): SimulatorStatusResult {
  const canConfigure = useCan('simulator.configure');
  const query = useQuery({
    queryKey: queryKeys.simulatorStatus,
    queryFn: () => simulatorApi.status(),
    enabled: canConfigure,
    retry: false,
    refetchInterval: POLL_MS,
  });

  const forbidden = query.error instanceof ApiError && query.error.kind === 'forbidden';
  return {
    data: query.data,
    restricted: !canConfigure || forbidden,
    isPending: canConfigure && query.isPending,
  };
}

/**
 * Ambient "is the plant being driven by a model?" read for surfaces outside the
 * Sim page. The §7 resync already primes `queryKeys.simulatorStatus` on every
 * (re)connect, so this subscribes to that cache entry (`enabled: false`) rather
 * than adding a second poll of an admin-only route to the dashboard.
 */
export function useTwinRunning(): boolean {
  const { data } = useQuery({
    queryKey: queryKeys.simulatorStatus,
    queryFn: () => simulatorApi.status(),
    enabled: false,
  });
  return data?.running === true;
}
