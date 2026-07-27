import { cn } from '@/lib/utils';
import { SIGNALS, type Signal } from './types';

/**
 * Flat (loop × signal) checkbox grid over the four-slot model.
 *
 * The checkbox accessible name `Loop {id} · {SIGNAL}` is FROZEN by the
 * multitrend E2E and by this file's own suite; only the row title changes to
 * `#3 · TIC-E2E` so the selector and the grid map onto each other by sight.
 * The visible signal text is the short tag, which the accessible name contains
 * (WCAG 2.5.3).
 *
 * A loop that holds no slot when the grid is already full is disabled rather
 * than silently ignored — the ceiling has to be visible, not surprising.
 */

const SWATCH: Record<Signal, string> = {
  pv: 'bg-trace-pv',
  sp: 'bg-trace-sp',
  co: 'bg-trace-co',
};

export interface SeriesSelectorProps {
  /** Controller ids offered, ascending. */
  loops: readonly number[];
  /** Row title, `#3 · TIC-E2E`; the caller falls back to `Loop {id}`. */
  loopLabel(loopId: number): string;
  isSelected(loopId: number, signal: Signal): boolean;
  /** Every slot taken — loops outside `occupiedLoops` can no longer be added. */
  isFull: boolean;
  occupiedLoops: readonly number[];
  onToggle(loopId: number, signal: Signal): void;
}

export function SeriesSelector({
  loops,
  loopLabel,
  isSelected,
  isFull,
  occupiedLoops,
  onToggle,
}: SeriesSelectorProps) {
  return (
    <fieldset className="flex min-w-0 flex-col gap-2 border border-rule bg-surface-sunk p-3">
      <legend className="px-1 text-2xs uppercase tracking-wider text-text-soft">Séries</legend>
      {loops.length === 0 ? (
        <p className="text-sm text-text-soft">Nenhuma malha disponível.</p>
      ) : (
        loops.map((loopId) => {
          const locked = isFull && !occupiedLoops.includes(loopId);
          return (
            <div key={loopId} className="flex flex-wrap items-center gap-3">
              <span
                className={cn(
                  // w-28 fits `#3 · TIC-E2E`; w-16 clipped it.
                  'numeric w-28 shrink-0 truncate text-xs',
                  locked ? 'text-text-disabled' : 'text-text-soft',
                )}
              >
                {loopLabel(loopId)}
              </span>
              {SIGNALS.map((signal) => (
                <label
                  key={signal}
                  className={cn(
                    'inline-flex min-h-11 items-center gap-1.5 text-xs',
                    locked ? 'text-text-disabled' : 'cursor-pointer text-text',
                  )}
                >
                  <input
                    type="checkbox"
                    aria-label={`Loop ${loopId} · ${signal.toUpperCase()}`}
                    checked={isSelected(loopId, signal)}
                    disabled={locked}
                    onChange={() => onToggle(loopId, signal)}
                    className="accent-accent focus-visible:ring-2 focus-visible:ring-focus-ring"
                  />
                  <span
                    aria-hidden="true"
                    className={cn('inline-block h-2.5 w-2.5 rounded-pill', SWATCH[signal])}
                  />
                  {signal.toUpperCase()}
                </label>
              ))}
            </div>
          );
        })
      )}
      {isFull ? <p className="text-2xs text-text-soft">Limite de 4 malhas atingido.</p> : null}
    </fieldset>
  );
}
