import { formatMetric, formatVariabilityPct } from './format';
import type { StatsRow } from './types';

interface Props {
  rows: StatsRow[];
}

const METRICS: ReadonlyArray<{ label: string; pick: (r: StatsRow) => string }> = [
  { label: 'IAE', pick: (r) => formatMetric(r.iae) },
  { label: 'ITAE', pick: (r) => formatMetric(r.itae) },
  { label: 'ISE', pick: (r) => formatMetric(r.ise) },
  { label: 'MSE', pick: (r) => formatMetric(r.mse) },
  { label: 'σ', pick: (r) => formatMetric(r.sigma) },
  { label: 'TV', pick: (r) => formatMetric(r.tv) },
  { label: '2σ/RANGE', pick: (r) => formatVariabilityPct(r.varRange) },
  { label: '2σ/SP', pick: (r) => formatVariabilityPct(r.varSp) },
];

export function StatsPanel({ rows }: Props): JSX.Element {
  if (rows.length === 0) {
    return (
      <p className="stats-panel__empty text-text-secondary" style={{ fontSize: 'var(--text-sm)' }}>
        No statistics available.
      </p>
    );
  }
  return (
    <div className="stats-panel flex flex-col gap-3">
      {rows.map((row) => (
        <section
          key={row.loopId}
          className="stats-panel__loop border border-border bg-surface-container p-3"
          aria-label={`Loop ${row.loopId} stats`}
        >
          <h3 className="stats-panel__title m-0 mb-2 text-text" style={{ fontSize: 'var(--text-base)' }}>
            Loop {row.loopId}
          </h3>
          <dl className="stats-panel__grid m-0 grid gap-2 grid-cols-[repeat(auto-fit,minmax(96px,1fr))]">
            {METRICS.map((m) => (
              <div key={m.label} className="stats-panel__cell flex flex-col gap-0.5">
                <dt className="text-text-secondary" style={{ fontSize: 'var(--text-xs)' }}>
                  {m.label}
                </dt>
                <dd className="numeric m-0 text-text" style={{ fontSize: 'var(--text-sm)' }}>
                  {m.pick(row)}
                </dd>
              </div>
            ))}
          </dl>
        </section>
      ))}
    </div>
  );
}
