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
  /** Per-loop tuning log behind the faceplate optimizer panel. */
  aiHistory: (controllerId: number) => ['ai', 'history', controllerId] as const,
  /** One loop's fuzzy inference trace — the fuzzy screen's poll key. */
  fuzzyTrace: (controllerId: number) => ['ai', 'fuzzy', controllerId] as const,
  opcuaStatus: ['opcua', 'status'] as const,
  simulatorStatus: ['simulator', 'status'] as const,
  /** Loop performance metrics for every controller (phase 7 multitrend). */
  allStats: ['controllers', 'stats'] as const,
  /** Operator-driven telemetry replay — keyed by the whole window (phase 7). */
  history: (window: object) => ['history', window] as const,
  /** One export job's poll cursor (phase 7). */
  exportJob: (exportId: string) => ['export', exportId] as const,
  /** One expanded OPC-UA folder's children (phase 10). */
  opcuaBrowse: (nodeId: string) => ['opcua', 'browse', nodeId] as const,
  /** Tag-search hits, keyed by the query string (phase 10). */
  opcuaSearch: (query: string) => ['opcua', 'search', query] as const,
  /** Portable `.spid` roster — every project mutation invalidates it (phase 10). */
  projects: ['projects', 'list'] as const,
  /** The active project behind the header label (§header, /project/current). */
  projectCurrent: ['projects', 'current'] as const,
  /** Admin-only user roster (phase 10). */
  users: ['users'] as const,
  /** Sessions connected right now, behind the settings security panel. */
  authSessions: ['auth', 'sessions'] as const,
  /** Platform sign-in history — keyed by the row cap it was fetched with. */
  accessLog: (limit: number) => ['auth', 'access-log', limit] as const,
  /** Backend health snapshot behind the executive dashboard (phase 9). */
  systemStatus: ['system', 'status'] as const,
  /** AI tuning log — keyed by the whole executive window (phase 9). */
  aiTuningHistory: (window: object) => ['ai', 'tuning-history', window] as const,
};
