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
 * `normal` is only the fallback for an unrecognized label; every real PV/SP/CO
 * reading resolves its normal fill through `TRACE_FILL` instead (§6.4 — the
 * bar echoes the trend line's own color rather than a flat "ok" green).
 */
const ALARM_FILL: Record<AnalogBarAlarm, string> = {
  normal: 'var(--bar-fill)',
  warn: 'var(--alarm-warn)',
  crit: 'var(--alarm-crit)',
};

/** A stale bar drops to the disabled ink: not normal, not in alarm — unknown. */
const STALE_FILL = 'var(--text-disabled)';

/**
 * Normal-fill color per variable, keyed by the same PV/SP/CO label the cards
 * and faceplate already pass in. Matches the trend chart's own trace tokens
 * (`uplotTheme.ts`) so a bar and its line always read as the same signal.
 */
const TRACE_FILL: Record<string, string> = {
  PV: 'var(--trace-pv)',
  SP: 'var(--trace-sp)',
  CO: 'var(--trace-co)',
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

  const faceplate = size === 'faceplate';
  const normalFill = TRACE_FILL[label] ?? ALARM_FILL.normal;

  return (
    <div
      className={cn('flex items-center', faceplate ? 'gap-2.5' : 'gap-1.5', className)}
      data-stale={stale ? 'true' : undefined}
    >
      <span
        className={cn(
          'shrink-0 font-bold uppercase text-text-soft',
          faceplate ? 'w-6 text-xs' : 'w-4 text-2xs',
        )}
      >
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
          'relative min-w-16 grow overflow-hidden rounded-pill bg-bar-track',
          faceplate ? 'h-2.5' : 'h-1.5',
          // Diagonal hatch over the whole track: the classic "this reading is
          // not live" overlay, built from a contract token so the color guard
          // and every theme still hold.
          stale &&
            'after:pointer-events-none after:absolute after:inset-0 after:bg-[repeating-linear-gradient(135deg,transparent_0_3px,var(--text-disabled)_3px_4px)]',
        )}
      >
        <div
          data-testid="analog-bar-fill"
          className="absolute inset-y-0 left-0 rounded-pill"
          style={{ width: `${pct}%`, background: stale ? STALE_FILL : alarm === 'normal' ? normalFill : ALARM_FILL[alarm] }}
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
          'numeric shrink-0 text-right',
          // `leading-none` on the faceplate figures is load-bearing, not taste:
          // the rail is a fixed 320 px column that must never scroll, and the
          // default line box around a 30 px numeral spends ~6 px of that budget
          // on nothing. Digits have no descenders, so there is nothing to clip.
          faceplate ? 'w-16 text-lg font-semibold leading-none' : 'w-[34px] text-sm',
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
