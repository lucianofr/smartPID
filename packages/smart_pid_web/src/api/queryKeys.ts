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
  aiStatus: (controllerId: number) => ['ai', 'status', controllerId] as const,
  opcuaStatus: ['opcua', 'status'] as const,
  simulatorStatus: ['simulator', 'status'] as const,
};