import { formatNumber } from '../lib/format';

export interface AnalogBarProps {
  label: string;
  value: number | null | undefined;
  min: number;
  max: number;
  unit: string;
  decimals: number;
  state?: 'normal' | 'critical' | 'warning';
}

export function AnalogBar({ label, value, min, max, unit, decimals, state = 'normal' }: AnalogBarProps) {
  const pct =
    value === null || value === undefined || Number.isNaN(value)
      ? 0
      : Math.max(0, Math.min(1, (value - min) / (max - min)));
  const fill =
    state === 'critical' ? 'var(--alarm-critical)' : state === 'warning' ? 'var(--alarm-warning)' : 'var(--bar-fill)';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-2)', fontSize: 'var(--text-xs)' }}>
      <span style={{ width: 24, color: 'var(--text-secondary)' }}>{label}</span>
      <div
        role="meter"
        aria-label={`${label} ${formatNumber(value, decimals)} ${unit}`}
        aria-valuemin={min}
        aria-valuemax={max}
        aria-valuenow={value ?? undefined}
        style={{ position: 'relative', flex: 1, height: 8, background: 'var(--bar-track)', overflow: 'hidden' }}
      >
        <div
          style={{
            position: 'absolute', inset: 0, background: fill,
            transform: `scaleX(${pct})`, transformOrigin: 'left',
            transition: 'transform var(--dur-fast) linear',
          }}
        />
      </div>
      <span className="numeric" style={{ minWidth: 64, textAlign: 'right', color: 'var(--text)', fontWeight: state === 'normal' ? 400 : 600 }}>
        {formatNumber(value, decimals)}
        <span style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-secondary)', marginLeft: 2 }}>{unit}</span>
      </span>
    </div>
  );
}
