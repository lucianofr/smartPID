import { useRealtime } from '../realtime/useRealtime';

/**
 * Realtime (WebSocket) disconnect indicator (Task 9.1 — §6a).
 *
 * The RealtimeProvider auto-reconnects with exponential backoff; this banner is
 * the operator-facing surface of that state. While `connected` is true it renders
 * nothing. On disconnect it shows an ISA-101-legal diagnostic treatment — the
 * desaturated `--alarm-diag` token (NOT critical red: a dropped live feed is a
 * diagnostic condition, the cached values on screen are still the last good ones),
 * a stale-data indicator (the on-screen telemetry is no longer live), and a
 * reconnect affordance that forces an immediate page reload to re-establish the
 * socket instead of waiting out the backoff timer.
 *
 * Flat, token-only, no animation (loading/diagnostic chrome must stay static).
 */
export function WsConnectionBanner(): JSX.Element | null {
  const { connected } = useRealtime();
  if (connected) return null;

  return (
    <div
      data-testid="ws-disconnected"
      role="alert"
      className="flex flex-wrap items-center gap-3 border-b border-alarm-diag bg-surface-container px-4 py-1.5 text-alarm-diag"
      style={{ fontSize: 'var(--text-sm)' }}
    >
      <span>Realtime feed disconnected — reconnecting…</span>
      <span data-testid="ws-stale" className="text-text-secondary">
        Showing stale data
      </span>
      <button
        type="button"
        onClick={() => window.location.reload()}
        className="ml-auto cursor-pointer rounded-control border border-alarm-diag bg-surface px-3 py-0.5 text-alarm-diag hover:border-border-strong"
      >
        Reconnect
      </button>
    </div>
  );
}
