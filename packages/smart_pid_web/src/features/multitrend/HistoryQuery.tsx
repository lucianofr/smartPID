import { useState } from 'react';
import type { HistoryParams, TelemetryFrame } from './useHistory';
import { EmptyState, LoadingState } from '../../components/MissingState';

interface Props {
  controllerId: number;
  onQuery: (params: HistoryParams) => void;
  frames: TelemetryFrame[];
  count: number;
  isLoading: boolean;
  /** True once a query has been submitted — lets us distinguish "not yet run" from "ran, empty". */
  hasQueried?: boolean;
}

function toIso(localValue: string): string | undefined {
  if (!localValue) return undefined;
  return new Date(localValue).toISOString();
}

const fieldClass = 'flex flex-col gap-0.5 text-text-secondary';

export function HistoryQuery({
  controllerId,
  onQuery,
  frames,
  count,
  isLoading,
  hasQueried = false,
}: Props): JSX.Element {
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [limit, setLimit] = useState(1000);

  const submit = (): void => {
    onQuery({ controllerId, start: toIso(start), end: toIso(end), limit });
  };

  return (
    <section
      className="history-query flex flex-col gap-2 border border-border bg-surface-container p-3"
      aria-label="History query"
    >
      <div className="history-query__form flex flex-wrap items-end gap-2" style={{ fontSize: 'var(--text-xs)' }}>
        <label className={fieldClass}>
          Start
          <input type="datetime-local" value={start} onChange={(e) => setStart(e.target.value)} />
        </label>
        <label className={fieldClass}>
          End
          <input type="datetime-local" value={end} onChange={(e) => setEnd(e.target.value)} />
        </label>
        <label className={fieldClass}>
          Limit
          <input
            type="number"
            className="numeric"
            min={1}
            max={10000}
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
          />
        </label>
        <button type="button" onClick={submit}>
          Query
        </button>
      </div>
      <p className="history-query__count text-text-secondary" style={{ fontSize: 'var(--text-sm)' }}>
        {isLoading ? 'Loading…' : `${count} frame(s)`}
      </p>
      {isLoading && (
        <LoadingState testId="history-loading" label="Querying history…" bars={3} />
      )}
      {!isLoading && hasQueried && frames.length === 0 && (
        <EmptyState
          testId="history-empty"
          message="No history for this range."
          hint="Widen the start/end window or raise the limit."
        />
      )}
      {frames.length > 0 && (
        <table className="history-query__table numeric w-full border-collapse text-left" style={{ fontSize: 'var(--text-xs)' }}>
          <thead className="text-text-secondary">
            <tr>
              <th className="border-b border-border px-1 py-0.5">Time</th>
              <th className="border-b border-border px-1 py-0.5">PV</th>
              <th className="border-b border-border px-1 py-0.5">SP</th>
              <th className="border-b border-border px-1 py-0.5">CO</th>
              <th className="border-b border-border px-1 py-0.5">Mode</th>
              <th className="border-b border-border px-1 py-0.5">Status</th>
            </tr>
          </thead>
          <tbody className="text-text">
            {frames.slice(0, 200).map((f, i) => (
              <tr key={`${f.timestamp}-${i}`}>
                <td className="px-1 py-0.5">{f.timestamp}</td>
                <td className="px-1 py-0.5">{f.pv}</td>
                <td className="px-1 py-0.5">{f.sp}</td>
                <td className="px-1 py-0.5">{f.co}</td>
                <td className="px-1 py-0.5">{f.mode}</td>
                <td className="px-1 py-0.5">{f.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
