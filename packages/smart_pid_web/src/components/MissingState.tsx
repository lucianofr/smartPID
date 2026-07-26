import type { ReactNode } from 'react';
import { Button } from '@/components/Button';
import { cn } from '@/lib/utils';

/**
 * Designed missing states (§11): loading and empty are states, not spinners
 * over blank space; 5xx/disconnect never renders blank. LoadingState is STATIC
 * (no shimmer/skeleton animation) — motion must not draw the operator's eye.
 */

const BAR_WIDTHS = ['w-2/3', 'w-1/2', 'w-3/4', 'w-2/5'] as const;

export interface LoadingStateProps {
  label: string;
  bars?: number;
  /** Greyed last-known value carried over while refreshing. */
  lastKnown?: ReactNode;
  className?: string;
}

export function LoadingState({ label, bars = 4, lastKnown, className }: LoadingStateProps) {
  return (
    <div aria-busy="true" aria-label={label} className={cn('flex flex-col gap-2 p-4', className)}>
      <span className="text-sm text-text-soft">{label}</span>
      {Array.from({ length: bars }, (_, i) => (
        <div
          key={i}
          data-slot="loading-bar"
          className={cn('h-2 bg-bar-track', BAR_WIDTHS[i % BAR_WIDTHS.length])}
        />
      ))}
      {lastKnown ? <div className="text-text-disabled">{lastKnown}</div> : null}
    </div>
  );
}

export interface EmptyStateProps {
  message: string;
  hint?: string;
  action?: ReactNode;
  className?: string;
}

export function EmptyState({ message, hint, action, className }: EmptyStateProps) {
  return (
    <div className={cn('flex flex-col items-center gap-2 p-8 text-center', className)}>
      <p className="text-sm font-medium text-text">{message}</p>
      {hint ? <p className="text-xs text-text-soft">{hint}</p> : null}
      {action}
    </div>
  );
}

export interface ErrorStateProps {
  message: string;
  onRetry?: () => void;
  retryLabel?: string;
  /** Stale last-known content shown greyed under the error. */
  stale?: ReactNode;
  className?: string;
}

export function ErrorState({
  message,
  onRetry,
  retryLabel = 'Tentar novamente',
  stale,
  className,
}: ErrorStateProps) {
  return (
    <div
      role="alert"
      className={cn('flex flex-col items-start gap-2 border border-rule-strong bg-surface-sunk p-4', className)}
    >
      <p className="text-sm font-medium text-text">{message}</p>
      {stale ? <div className="text-xs text-text-disabled">{stale}</div> : null}
      {onRetry ? (
        <Button variant="secondary" size="sm" onClick={onRetry}>
          {retryLabel}
        </Button>
      ) : null}
    </div>
  );
}