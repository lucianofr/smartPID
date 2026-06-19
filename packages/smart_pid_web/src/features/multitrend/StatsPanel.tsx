import { formatMetric, formatVariabilityPct } from './format';
import type { StatsRow } from './types';
import './MultiTrend.css';

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
    return <p className="stats-panel__empty">No statistics available.</p>;
  }
  return (
    <div className="stats-panel">
      {rows.map((row) => (
        <section
          key={row.loopId}
          className="stats-panel__loop"
          aria-label={`Loop ${row.loopId} stats`}
        >
          <h3 className="stats-panel__title">Loop {row.loopId}</h3>
          <dl className="stats-panel__grid">
            {METRICS.map((m) => (
              <div key={m.label} className="stats-panel__cell">
                <dt>{m.label}</dt>
                <dd className="mono-tabular">{m.pick(row)}</dd>
              </div>
            ))}
          </dl>
        </section>
      ))}
    </div>
  );
}
