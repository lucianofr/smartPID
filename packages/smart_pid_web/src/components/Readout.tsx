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

const VALUE_SIZE: Record<NonNullable<ReadoutProps['size']>, string> = {
  sm: 'text-sm',
  md: 'text-xl',
  lg: 'text-2xl',
};

/** Labeled numeric display. The label is Archivo (UI face); the value is ALWAYS
 *  Geist Mono via .numeric — a KPI figure is a metric (§6.2). */
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
      <span className="text-2xs font-medium uppercase tracking-wider text-text-soft">{label}</span>
      <span className="flex items-baseline gap-1">
        <span
          className={cn(
            'numeric font-medium',
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
