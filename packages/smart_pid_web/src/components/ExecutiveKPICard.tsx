export interface ExecutiveKPICardProps {
  label: string;
  value: string;
  delta?: { dir: 'up' | 'down'; value: string; outOfTarget: boolean };
  rangeBar?: { ratio: number };
  testId?: string;
}

/**
 * Executive KPI hero card (§6b latitude — one of two non-operator screens).
 * Flat ISA-101: token colors only, NO shadow/gradient/bevel. The latitude is
 * expressed through TYPOGRAPHY and HIERARCHY — a large tabular big-number hero
 * (the one sanctioned big-number pattern) over a quiet secondary label.
 *
 * Color never asserts process state: a within-target delta renders in the gray
 * secondary token; only an off-target delta promotes to the warning token plus a
 * heavier weight. `data-out-of-target` drives that token emphasis (weight/color),
 * never color alone (DOM-freeze §3a + §6 inventory require the attribute itself).
 *
 * One restrained motion affordance: a compositor-only entrance fade/rise
 * (opacity + transform) that honors `prefers-reduced-motion` via `motion-reduce`.
 */
export function ExecutiveKPICard({
  label,
  value,
  delta,
  rangeBar,
  testId,
}: ExecutiveKPICardProps): JSX.Element {
  return (
    <article
      className="exec-kpi-enter flex flex-col gap-2 border border-border bg-surface-container-high px-5 py-4 rounded-card"
      data-testid={testId}
    >
      <span
        className="numeric text-text"
        style={{ fontSize: 'var(--text-2xl)', lineHeight: 'var(--lh-tight)' }}
      >
        {value}
      </span>
      <span
        className="text-text-secondary"
        style={{ fontSize: 'var(--text-sm)' }}
      >
        {label}
      </span>
      {delta && (
        <span
          className={
            delta.outOfTarget
              ? 'numeric text-alarm-warning'
              : 'numeric text-text-secondary'
          }
          data-testid={testId ? `${testId}-delta` : undefined}
          data-out-of-target={delta.outOfTarget}
          style={{
            fontSize: 'var(--text-sm)',
            fontWeight: delta.outOfTarget ? 'var(--fw-semibold)' : 'var(--fw-regular)',
          }}
        >
          {delta.dir === 'up' ? '▲' : '▼'} {delta.value}
        </span>
      )}
      {rangeBar && (
        <div className="h-1 bg-surface-container overflow-hidden" aria-hidden>
          <div
            className="h-full bg-text-secondary"
            style={{ width: `${Math.max(0, Math.min(1, rangeBar.ratio)) * 100}%` }}
          />
        </div>
      )}
    </article>
  );
}
