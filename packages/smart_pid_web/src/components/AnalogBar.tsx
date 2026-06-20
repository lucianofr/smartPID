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

/**
 * Fill color per alarm level. These are CSS-variable references (theme contract
 * tokens), not raw color literals — and they are runtime-selected, so the fill
 * background MUST stay an inline style (mandated by the DOM-freeze §3a + §6
 * inventory: the test reads `bar-fill.style.width`, and the fill is one of the
 * two sanctioned dynamic inline styles).
 */
const ALARM_FILL: Record<AlarmLevel, string> = {
  normal: 'var(--bar-fill)',
  warning: 'var(--alarm-warning)',
  critical: 'var(--alarm-critical)',
};

const TRACK_HEIGHT: Record<NonNullable<AnalogBarProps['size']>, number> = {
  card: 8,
  faceplate: 14,
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
  const showSp = label === 'PV' && spPct !== null;
  const display = finite ? value.toFixed(decimals) : '—';

  return (
    <div className="analog-bar flex items-center gap-2" data-size={size}>
      <span className="analog-bar__label w-6 text-text-secondary">{label}</span>
      <div
        className="analog-bar__track relative flex-1 bg-bar-track overflow-hidden rounded-pill"
        data-size={size}
        role="meter"
        aria-label={`${label} ${display} ${scale.unit}`}
        aria-valuemin={scale.euMin}
        aria-valuemax={scale.euMax}
        aria-valuenow={finite ? value : undefined}
        style={{ height: TRACK_HEIGHT[size] }}
      >
        <div
          data-testid="bar-fill"
          data-alarm={alarm}
          className="absolute inset-y-0 left-0"
          // §3a / §6: dynamic width + runtime-selected fill color stay inline —
          // Tailwind cannot express a runtime `%` width nor the per-alarm token swap.
          style={{ width: `${pct}%`, background: ALARM_FILL[alarm] }}
        />
        {showSp && (
          <span
            data-testid="sp-marker"
            aria-hidden
            className="analog-bar__sp-marker absolute top-0 h-0 w-0"
            // §3a / §6: marker position is a runtime `%` (stays inline). The
            // triangle borders use a theme token color, so they stay inline too.
            style={{
              left: `${spPct}%`,
              top: -3,
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
        className="analog-bar__value numeric font-data tabular-nums text-right text-text"
        style={{
          minWidth: 64,
          fontWeight: alarm === 'normal' ? 400 : 600,
        }}
      >
        {display}{' '}
        <span className="text-text-secondary" style={{ fontSize: 'var(--text-2xs)' }}>
          {scale.unit}
        </span>
      </span>
    </div>
  );
}
