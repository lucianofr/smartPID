import type { SignalKey, Variable } from './types';
import { seriesColor, seriesStroke, signalId } from './signals';
import './MultiTrend.css';

const VARIABLES: Variable[] = ['pv', 'sp', 'co'];

interface Props {
  loops: number[];
  selected: SignalKey[];
  onChange: (sel: SignalKey[]) => void;
}

export function SeriesSelector({ loops, selected, onChange }: Props): JSX.Element {
  const selectedIds = new Set(selected.map(signalId));

  const toggle = (key: SignalKey): void => {
    const id = signalId(key);
    const next = selectedIds.has(id)
      ? selected.filter((s) => signalId(s) !== id)
      : [...selected, key];
    onChange(next);
  };

  return (
    <fieldset className="series-selector">
      <legend>Séries</legend>
      {loops.map((loopId) => (
        <div key={loopId} className="series-selector__loop">
          {VARIABLES.map((variable) => {
            const key: SignalKey = { loopId, variable };
            const label = `Loop ${loopId} · ${variable.toUpperCase()}`;
            return (
              <label key={signalId(key)} className="series-selector__item">
                <input
                  type="checkbox"
                  aria-label={label}
                  checked={selectedIds.has(signalId(key))}
                  onChange={() => toggle(key)}
                />
                <span
                  className="series-selector__swatch"
                  style={{ background: seriesStroke(seriesColor(key)) }}
                  aria-hidden
                />
                {label}
              </label>
            );
          })}
        </div>
      ))}
    </fieldset>
  );
}
