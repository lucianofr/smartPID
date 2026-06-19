import { useState } from 'react';
import type { DisturbanceType } from './types';

interface Props {
  active: boolean;
  onInject: (type: DisturbanceType, amplitude: number) => void;
  onRemove: () => void;
}

export function DisturbanceControls({ active, onInject, onRemove }: Props): JSX.Element {
  const [type, setType] = useState<DisturbanceType>('step');
  const [amplitude, setAmplitude] = useState(10);
  return (
    <fieldset>
      <legend>Disturbance</legend>
      <label>
        <span>Type</span>
        <select
          aria-label="Disturbance type"
          value={type}
          onChange={(e) => setType(e.target.value as DisturbanceType)}
        >
          <option value="step">step</option>
          <option value="noise">noise</option>
        </select>
      </label>
      <label>
        <span>Amplitude</span>
        <input
          type="number"
          aria-label="Amplitude"
          value={amplitude}
          onChange={(e) => setAmplitude(Number(e.target.value))}
        />
      </label>
      <button type="button" onClick={() => onInject(type, amplitude)}>
        Inject disturbance
      </button>
      <button type="button" disabled={!active} onClick={onRemove}>
        Remove
      </button>
    </fieldset>
  );
}
