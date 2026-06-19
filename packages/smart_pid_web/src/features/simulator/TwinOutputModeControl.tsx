import { useState } from 'react';
import type { TwinMode } from './types';

interface Props {
  co: number;
  mode: TwinMode;
  onSetCo: (co: number) => void;
  onSetMode: (m: TwinMode) => void;
}

const clamp = (n: number) => Math.max(0, Math.min(100, n));

export function TwinOutputModeControl({ co, mode, onSetCo, onSetMode }: Props): JSX.Element {
  const [draft, setDraft] = useState(co);
  const auto = mode === 'AUTO';
  return (
    <fieldset>
      <legend>Twin output / mode</legend>
      <div role="group" aria-label="Twin mode">
        <button type="button" aria-pressed={!auto} onClick={() => onSetMode('MAN')}>
          MAN
        </button>
        <button type="button" aria-pressed={auto} onClick={() => onSetMode('AUTO')}>
          AUTO
        </button>
      </div>
      <label>
        <span>Output CO (%)</span>
        <input
          type="number"
          aria-label="Output CO"
          min={0}
          max={100}
          value={draft}
          disabled={auto}
          onChange={(e) => setDraft(Number(e.target.value))}
        />
      </label>
      <button type="button" disabled={auto} onClick={() => onSetCo(clamp(draft))}>
        Apply output
      </button>
    </fieldset>
  );
}
