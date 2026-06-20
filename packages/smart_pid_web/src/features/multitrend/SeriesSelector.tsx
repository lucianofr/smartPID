import type { SignalKey, Variable } from './types';
import { seriesColor, seriesStroke, signalId } from './signals';

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
    <fieldset className="series-selector flex flex-col gap-2 border border-border bg-surface-container p-3">
      <legend className="px-1 text-text-secondary" style={{ fontSize: 'var(--text-sm)' }}>
        Séries
      </legend>
      {loops.map((loopId) => (
        <div key={loopId} className="series-selector__loop flex flex-wrap gap-3">
          {VARIABLES.map((variable) => {
            const key: SignalKey = { loopId, variable };
            const label = `Loop ${loopId} · ${variable.toUpperCase()}`;
            return (
              <label
                key={signalId(key)}
                className="series-selector__item inline-flex cursor-pointer items-center gap-1 text-text"
                style={{ fontSize: 'var(--text-sm)' }}
              >
                <input
                  type="checkbox"
                  aria-label={label}
                  checked={selectedIds.has(signalId(key))}
                  onChange={() => toggle(key)}
                />
                <span
                  className="series-selector__swatch inline-block h-3 w-3"
                  style={{ background: seriesStroke(seriesColor(key)), borderRadius: 'var(--radius-pill)' }}
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
