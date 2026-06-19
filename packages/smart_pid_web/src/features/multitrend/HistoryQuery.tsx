import { useState } from 'react';
import type { HistoryParams, TelemetryFrame } from './useHistory';

interface Props {
  controllerId: number;
  onQuery: (params: HistoryParams) => void;
  frames: TelemetryFrame[];
  count: number;
  isLoading: boolean;
}

function toIso(localValue: string): string | undefined {
  if (!localValue) return undefined;
  return new Date(localValue).toISOString();
}

export function HistoryQuery({ controllerId, onQuery, frames, count, isLoading }: Props): JSX.Element {
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [limit, setLimit] = useState(1000);

  const submit = (): void => {
    onQuery({ controllerId, start: toIso(start), end: toIso(end), limit });
  };

  return (
    <section className="history-query" aria-label="History query">
      <div className="history-query__form">
        <label>
          Start
          <input type="datetime-local" value={start} onChange={(e) => setStart(e.target.value)} />
        </label>
        <label>
          End
          <input type="datetime-local" value={end} onChange={(e) => setEnd(e.target.value)} />
        </label>
        <label>
          Limit
          <input
            type="number"
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
      <p className="history-query__count">{isLoading ? 'Loading…' : `${count} frame(s)`}</p>
      {frames.length > 0 && (
        <table className="history-query__table numeric">
          <thead>
            <tr>
              <th>Time</th>
              <th>PV</th>
              <th>SP</th>
              <th>CO</th>
              <th>Mode</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {frames.slice(0, 200).map((f, i) => (
              <tr key={`${f.timestamp}-${i}`}>
                <td>{f.timestamp}</td>
                <td>{f.pv}</td>
                <td>{f.sp}</td>
                <td>{f.co}</td>
                <td>{f.mode}</td>
                <td>{f.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
