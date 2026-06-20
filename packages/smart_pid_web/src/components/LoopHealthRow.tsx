export type LoopHealth = 'running' | 'stopped' | 'error';
export interface LoopHealthRowProps {
  name: string;
  health: LoopHealth;
  opc: 'OFFLINE' | 'CONNECTING' | 'ONLINE' | 'RECONNECTING';
  mode: string;
}

/**
 * Flat ISA-101 health row. Static styling only (token utilities): a single
 * border-bottom divider, 4px-rhythm gap/padding, and gray hierarchy — the tag is
 * the dominant text, state/opc are secondary. Process-style values use the
 * `numeric` (tabular-nums) class. No color-coded status, no shadow/lift.
 */
export function LoopHealthRow({ name, health, opc, mode }: LoopHealthRowProps) {
  return (
    <div
      data-testid={`health-${name}`}
      data-health={health}
      data-opc={opc}
      className="flex items-baseline gap-3 border-b border-divider px-3 py-2 text-text-secondary"
      style={{ fontSize: 'var(--text-sm)' }}
    >
      <span className="numeric flex-1 text-text">{name}</span>
      <span className="numeric">{mode}</span>
      <span data-testid={`health-${name}-state`} className="numeric">
        {health}
      </span>
      <span data-testid={`health-${name}-opc`} className="numeric">
        {opc}
      </span>
    </div>
  );
}
