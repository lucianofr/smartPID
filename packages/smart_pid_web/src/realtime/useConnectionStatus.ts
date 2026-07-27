import { useContext } from 'react';
import { RealtimeContext, type ConnectionPhase } from './RealtimeProvider';

export interface ConnectionStatus {
  phase: ConnectionPhase;
  /** Socket authenticated (live or resyncing). */
  connected: boolean;
  /** Resync complete — the bus is rendering current frames (§8). */
  live: boolean;
  /** Frames on screen are older than the liveness deadline (E2E-047). */
  stale: boolean;
  /** Epoch ms of the newest frame received before the link went quiet. */
  staleSince: number | null;
}

/**
 * The link state, without subscribing to any envelope type.
 *
 * `useRealtime` already carries these fields, but every one of its callers pays
 * for a per-type subscription and a `last` re-render it does not want here. The
 * shell banner and the loop strip only need to know whether what they are
 * showing is current.
 */
export function useConnectionStatus(): ConnectionStatus {
  const ctx = useContext(RealtimeContext);
  if (!ctx) throw new Error('useConnectionStatus must be used within RealtimeProvider');
  // The provider already memoizes `ctx`; narrowing it structurally keeps that
  // identity, so this is safe in a dependency array.
  return ctx;
}
