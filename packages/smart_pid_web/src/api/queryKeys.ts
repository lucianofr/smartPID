/**
 * Canonical TanStack Query keys. The §7 resync runner primes these entries via
 * setQueryData; feature hooks in phases 4-10 MUST reuse the same keys or the
 * resync becomes invisible to them.
 */
export const queryKeys = {
  controllers: ['controllers'] as const,
  alarmsActive: ['alarms', 'active'] as const,
  /** Gap-window history rows fetched by resync (alarms since last_seen_ts). */
  alarmsResyncHistory: ['alarms', 'resync-history'] as const,
  /** Operator-driven history window — keyed by the whole filter (phase 6). */
  alarmsHistory: (filter: Record<string, unknown>) => ['alarms', 'history', filter] as const,
  /** Per-loop threshold set behind the admin-only config form (phase 6). */
  alarmConfig: (controllerId: number) => ['alarms', 'config', controllerId] as const,
  aiStatus: (controllerId: number) => ['ai', 'status', controllerId] as const,
  opcuaStatus: ['opcua', 'status'] as const,
  simulatorStatus: ['simulator', 'status'] as const,
  /** Loop performance metrics for every controller (phase 7 multitrend). */
  allStats: ['controllers', 'stats'] as const,
  /** Operator-driven telemetry replay — keyed by the whole window (phase 7). */
  history: (window: object) => ['history', window] as const,
  /** One export job's poll cursor (phase 7). */
  exportJob: (exportId: string) => ['export', exportId] as const,
};
