import { formatNumber } from '@/lib/format';
import { valueToFraction, type Scale } from '@/lib/scale';
import { cn } from '@/lib/utils';

export type AnalogBarAlarm = 'normal' | 'warn' | 'crit';

export interface AnalogBarProps {
  label: string;
  value: number | null | undefined;
  scale: Scale;
  spValue?: number;
  alarm?: AnalogBarAlarm;
  decimals?: number;
  size?: 'card' | 'faceplate';
  /**
   * The bus stopped delivering: this is the last value seen, not the current
   * one (E2E-047). Overrides `alarm` — a frozen reading cannot testify to the
   * plant being normal OR in alarm.
   */
  stale?: boolean;
  className?: string;
}

/**
 * Fill color per alarm level — token var() references selected at runtime
 * (one of the two sanctioned dynamic inline styles; the other is the width %).
 * Normal fill is gray (--bar-fill): green never means "ok" (§6.4).
 */
const ALARM_FILL: Record<AnalogBarAlarm, string> = {
  normal: 'var(--bar-fill)',
  warn: 'var(--alarm-warn)',
  crit: 'var(--alarm-crit)',
};

/** A stale bar drops to the disabled ink: not normal, not in alarm — unknown. */
const STALE_FILL = 'var(--text-disabled)';

const TRACK_HEIGHT: Record<NonNullable<AnalogBarProps['size']>, string> = {
  card: 'h-2',
  faceplate: 'h-3.5',
};

export function AnalogBar({
  label,
  value,
  scale,
  spValue,
  alarm = 'normal',
  decimals = 1,
  size = 'card',
  stale = false,
  className,
}: AnalogBarProps) {
  const finite = typeof value === 'number' && Number.isFinite(value);
  const pct = (finite ? valueToFraction(value, scale) * 100 : 0).toFixed(2);
  const spPct = spValue !== undefined ? (valueToFraction(spValue, scale) * 100).toFixed(2) : null;
  const reading = finite ? `${formatNumber(value, decimals)} ${scale.unit}` : 'sem dados';

  return (
    <div className={cn('flex items-center gap-2', className)} data-stale={stale ? 'true' : undefined}>
      <span className="w-8 shrink-0 text-2xs font-medium uppercase tracking-wider text-text-soft">
        {label}
      </span>
      <div
        role="meter"
        aria-label={label}
        aria-valuemin={scale.euMin}
        aria-valuemax={scale.euMax}
        aria-valuenow={finite ? value : undefined}
        // Screen readers get the same warning the sighted operator gets from
        // the dimmed ink — the number alone would read as current.
        aria-valuetext={stale && finite ? `${reading} (desatualizado)` : reading}
        className={cn(
          'relative min-w-16 grow overflow-hidden bg-bar-track',
          TRACK_HEIGHT[size],
          // Diagonal hatch over the whole track: the classic "this reading is
          // not live" overlay, built from a contract token so the color guard
          // and every theme still hold.
          stale &&
            'after:pointer-events-none after:absolute after:inset-0 after:bg-[repeating-linear-gradient(135deg,transparent_0_3px,var(--text-disabled)_3px_4px)]',
        )}
      >
        <div
          data-testid="analog-bar-fill"
          className="absolute inset-y-0 left-0"
          style={{ width: `${pct}%`, background: stale ? STALE_FILL : ALARM_FILL[alarm] }}
        />
        {spPct !== null ? (
          <div
            data-testid="analog-bar-sp"
            aria-hidden="true"
            className="absolute inset-y-0 w-0.5 -translate-x-1/2 bg-bar-marker"
            style={{ left: `${spPct}%` }}
          />
        ) : null}
      </div>
      <span
        className={cn(
          'numeric w-16 shrink-0 text-right text-sm',
          stale ? 'text-text-disabled' : 'text-text',
        )}
      >
        {/* The DCS bad-quality mark, in the mono column so digits stay aligned. */}
        {stale && finite ? <span aria-hidden="true">*</span> : null}
        {formatNumber(value, decimals)}
      </span>
    </div>
  );
}
