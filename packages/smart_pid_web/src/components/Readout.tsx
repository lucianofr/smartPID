import { formatNumber } from '@/lib/format';
import { cn } from '@/lib/utils';

export interface ReadoutProps {
  label: string;
  value: number | null | undefined;
  unit?: string;
  decimals?: number;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

const VALUE_SIZE: Record<NonNullable<ReadoutProps['size']>, string> = {
  sm: 'text-sm',
  md: 'text-xl',
  lg: 'text-2xl',
};

/** Labeled numeric display. The label is Archivo (UI face); the value is ALWAYS
 *  Geist Mono via .numeric — a KPI figure is a metric (§6.2). */
export function Readout({ label, value, unit, decimals = 1, size = 'md', className }: ReadoutProps) {
  return (
    <div className={cn('flex flex-col gap-0.5', className)}>
      <span className="text-2xs font-medium uppercase tracking-wider text-text-soft">{label}</span>
      <span className="flex items-baseline gap-1">
        <span className={cn('numeric font-medium text-text', VALUE_SIZE[size])}>
          {formatNumber(value, decimals)}
        </span>
        {unit ? <span className="text-xs text-text-soft">{unit}</span> : null}
      </span>
    </div>
  );
}