import type { ReactNode } from 'react';

/**
 * Mandated missing states (Task 9.1 — §6a), ISA-101-legal.
 *
 * Three flat, token-only surfaces shared across the migrated screens:
 *  - <LoadingState>  static placeholder bars + greyed last-known value + `aria-busy`.
 *                    NO shimmer / skeleton animation (ISA-101: motion must not draw
 *                    the operator's eye; a loading screen has nothing actionable).
 *  - <EmptyState>    an explicit, per-surface "nothing here" message.
 *  - <ErrorState>    desaturated `--alarm-diag` token treatment (via the
 *                    `text-alarm-diag`/`border-alarm-diag` utilities — never the
 *                    critical-red token) + a retry/reconnect affordance.
 *
 * All three are pure presentational; callers own the data branching. No raw
 * colors, no box-shadow/gradient, no `animate-*` — the static bars are plain
 * token-filled rectangles so the file stays inside the ISA-101 source-guard.
 */

const BAR = 'h-2 rounded-control bg-bar-track';

/** Static (non-animated) placeholder bars. Widths vary only to read as "rows". */
const BAR_WIDTHS = ['w-2/3', 'w-1/2', 'w-3/4', 'w-2/5'] as const;

interface LoadingStateProps {
  /** Stable hook the surface test asserts `aria-busy` on. */
  testId: string;
  label: string;
  /** Number of static placeholder bars (default 4). */
  bars?: number;
  /** Optional greyed last-known value carried over while refreshing. */
  lastKnown?: ReactNode;
}

export function LoadingState({ testId, label, bars = 4, lastKnown }: LoadingStateProps): JSX.Element {
  const count = Math.max(1, bars);
  return (
    <div
      data-testid={testId}
      role="status"
      aria-busy="true"
      aria-live="polite"
      className="flex flex-col gap-2 p-4"
    >
      <span className="text-text-secondary" style={{ fontSize: 'var(--text-sm)' }}>
        {label}
      </span>
      {lastKnown != null && (
        <span
          data-testid="loading-last-known"
          className="text-text-disabled"
          style={{ fontSize: 'var(--text-sm)' }}
        >
          {lastKnown}
        </span>
      )}
      <div className="flex flex-col gap-2" aria-hidden="true">
        {Array.from({ length: count }, (_, i) => (
          <span
            key={i}
            data-testid="loading-bar"
            className={`${BAR} ${BAR_WIDTHS[i % BAR_WIDTHS.length]}`}
          />
        ))}
      </div>
    </div>
  );
}

interface EmptyStateProps {
  testId: string;
  message: string;
  hint?: string;
}

export function EmptyState({ testId, message, hint }: EmptyStateProps): JSX.Element {
  return (
    <div
      data-testid={testId}
      role="status"
      className="flex flex-col items-center gap-1 p-6 text-center text-text-secondary"
    >
      <span style={{ fontSize: 'var(--text-base)' }}>{message}</span>
      {hint != null && (
        <span className="text-text-disabled" style={{ fontSize: 'var(--text-sm)' }}>
          {hint}
        </span>
      )}
    </div>
  );
}

interface ErrorStateProps {
  testId: string;
  message: string;
  /** Retry/reconnect affordance label + handler. */
  actionLabel: string;
  onAction: () => void;
  /** Optional stale-data indication rendered alongside the message. */
  stale?: ReactNode;
}

export function ErrorState({
  testId,
  message,
  actionLabel,
  onAction,
  stale,
}: ErrorStateProps): JSX.Element {
  return (
    <div
      data-testid={testId}
      role="alert"
      className="flex flex-wrap items-center gap-3 border border-alarm-diag p-3 text-alarm-diag"
      style={{ fontSize: 'var(--text-sm)' }}
    >
      <span>{message}</span>
      {stale != null && (
        <span data-testid="error-stale" className="text-text-secondary">
          {stale}
        </span>
      )}
      <button
        type="button"
        onClick={onAction}
        className="ml-auto cursor-pointer rounded-control border border-alarm-diag bg-surface px-3 py-1 text-alarm-diag hover:border-border-strong"
      >
        {actionLabel}
      </button>
    </div>
  );
}
