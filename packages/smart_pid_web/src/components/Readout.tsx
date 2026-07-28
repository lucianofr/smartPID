import { formatNumber } from '@/lib/format';
import { cn } from '@/lib/utils';

export interface ReadoutProps {
  label: string;
  value: number | null | undefined;
  unit?: string;
  decimals?: number;
  size?: 'sm' | 'md' | 'lg';
  /** Last value seen, not the current one — the bus went quiet (E2E-047). */
  stale?: boolean;
  className?: string;
}

/** Three rungs of the §6.2 numeric scale: inline stat, panel stat, hero figure. */
const VALUE_SIZE: Record<NonNullable<ReadoutProps['size']>, string> = {
  sm: 'text-sm',
  md: 'text-lg',
  lg: 'text-3xl',
};

/** Labeled numeric display. The label is the UI face; the value is ALWAYS the
 *  data face via .numeric — a KPI figure is a metric (§6.2). */
export function Readout({
  label,
  value,
  unit,
  decimals = 1,
  size = 'md',
  stale = false,
  className,
}: ReadoutProps) {
  const finite = typeof value === 'number' && Number.isFinite(value);
  return (
    <div className={cn('flex flex-col gap-0.5', className)} data-stale={stale ? 'true' : undefined}>
      <span className="text-2xs uppercase tracking-caps text-text-soft">{label}</span>
      <span className="flex items-baseline gap-1">
        <span
          className={cn(
            'numeric font-semibold',
            VALUE_SIZE[size],
            stale ? 'text-text-disabled' : 'text-text',
          )}
        >
          {stale && finite ? <span aria-hidden="true">*</span> : null}
          {formatNumber(value, decimals)}
        </span>
        {/* Real text, not aria-label: a plain <span> is role=generic, where
            aria-label is not reliably exposed. The dimmed ink and the `*` are
            the sighted cues; this is the same fact for a screen reader, which
            would otherwise read a frozen number as a live one. */}
        {stale && finite ? <span className="sr-only">desatualizado</span> : null}
        {unit ? <span className="text-xs text-text-soft">{unit}</span> : null}
      </span>
    </div>
  );
}
