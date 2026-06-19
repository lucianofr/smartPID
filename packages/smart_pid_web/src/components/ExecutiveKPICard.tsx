import './ExecutiveKPICard.css';

export interface ExecutiveKPICardProps {
  label: string;
  value: string;
  delta?: { dir: 'up' | 'down'; value: string; outOfTarget: boolean };
  rangeBar?: { ratio: number };
  testId?: string;
}

export function ExecutiveKPICard({
  label,
  value,
  delta,
  rangeBar,
  testId,
}: ExecutiveKPICardProps): JSX.Element {
  return (
    <article className="exec-kpi-card" data-testid={testId}>
      <span className="exec-kpi-value numeric">{value}</span>
      <span className="exec-kpi-label">{label}</span>
      {delta && (
        <span
          className="exec-kpi-delta"
          data-testid={testId ? `${testId}-delta` : undefined}
          data-out-of-target={delta.outOfTarget}
        >
          {delta.dir === 'up' ? '▲' : '▼'} {delta.value}
        </span>
      )}
      {rangeBar && (
        <div className="exec-kpi-rangebar" aria-hidden>
          <div
            className="exec-kpi-rangefill"
            style={{ width: `${Math.max(0, Math.min(1, rangeBar.ratio)) * 100}%` }}
          />
        </div>
      )}
    </article>
  );
}
