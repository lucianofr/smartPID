import { valueToFraction, type Scale } from '../lib/scale';

export type AlarmLevel = 'normal' | 'warning' | 'critical';

export interface AnalogBarProps {
  label: string;
  value: number | null | undefined;
  scale: Scale;
  spValue?: number;
  alarm?: AlarmLevel;
  size?: 'card' | 'faceplate';
  decimals?: number;
}

const ALARM_FILL: Record<AlarmLevel, string> = {
  normal: 'var(--bar-fill)',
  warning: 'var(--alarm-warning)',
  critical: 'var(--alarm-critical)',
};

export function AnalogBar({
  label,
  value,
  scale,
  spValue,
  alarm = 'normal',
  size = 'card',
  decimals = 1,
}: AnalogBarProps) {
  const finite = typeof value === 'number' && Number.isFinite(value);
  const pct = (finite ? valueToFraction(value, scale) * 100 : 0).toFixed(2);
  const spPct = spValue !== undefined ? (valueToFraction(spValue, scale) * 100).toFixed(2) : null;
  const trackHeight = size === 'faceplate' ? 14 : 8;
  const showSp = label === 'PV' && spPct !== null;
  const display = finite ? value.toFixed(decimals) : '—';

  return (
    <div
      className="analog-bar"
      data-size={size}
      style={{ display: 'flex', alignItems: 'center', gap: 8 }}
    >
      <span className="analog-bar__label" style={{ width: 24, color: 'var(--text-secondary)' }}>
        {label}
      </span>
      <div
        className="analog-bar__track"
        role="meter"
        aria-label={`${label} ${display} ${scale.unit}`}
        aria-valuemin={scale.euMin}
        aria-valuemax={scale.euMax}
        aria-valuenow={finite ? value : undefined}
        style={{
          position: 'relative',
          flex: 1,
          height: trackHeight,
          background: 'var(--bar-track)',
          borderRadius: 'var(--radius-pill, 0)',
          overflow: 'hidden',
        }}
      >
        <div
          data-testid="bar-fill"
          data-alarm={alarm}
          style={{
            position: 'absolute',
            left: 0,
            top: 0,
            bottom: 0,
            width: `${pct}%`,
            background: ALARM_FILL[alarm],
          }}
        />
        {showSp && (
          <span
            data-testid="sp-marker"
            aria-hidden
            style={{
              position: 'absolute',
              top: -3,
              left: `${spPct}%`,
              width: 0,
              height: 0,
              borderLeft: '4px solid transparent',
              borderRight: '4px solid transparent',
              borderTop: '5px solid var(--bar-marker)',
              transform: 'translateX(-50%)',
            }}
          />
        )}
      </div>
      <span
        data-testid="bar-value"
        className="analog-bar__value numeric"
        style={{
          minWidth: 64,
          textAlign: 'right',
          color: 'var(--text)',
          fontVariantNumeric: 'tabular-nums',
          fontWeight: alarm === 'normal' ? 400 : 600,
        }}
      >
        {display}{' '}
        <span style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-secondary)' }}>
          {scale.unit}
        </span>
      </span>
    </div>
  );
}
