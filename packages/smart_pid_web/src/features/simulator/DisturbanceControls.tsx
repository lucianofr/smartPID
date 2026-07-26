import { useId, useState } from 'react';
import { Button } from '@/components/Button';
import { Input } from '@/components/Field';
import { NATIVE_SELECT_CLASS } from './PresetSelector';
import type { DisturbanceType } from './types';

export interface DisturbanceControlsProps {
  /** A step OR noise disturbance is currently loaded on the model. */
  active: boolean;
  onInject: (type: DisturbanceType, amplitude: number) => void;
  onRemove: () => void;
}

/** Pre-rewrite default: big enough to see on a trend, small enough not to trip. */
const DEFAULT_AMPLITUDE = 10;

/**
 * Load disturbance on the process model. `Remove` is driven by the SERVER's
 * `step_active || noise_active`, never by local optimism — a Remove that looks
 * armed while the model is clean is how an operator concludes the twin is stuck.
 */
export function DisturbanceControls({ active, onInject, onRemove }: DisturbanceControlsProps) {
  const typeId = useId();
  const amplitudeId = useId();
  const [type, setType] = useState<DisturbanceType>('step');
  const [amplitude, setAmplitude] = useState(DEFAULT_AMPLITUDE);

  return (
    <fieldset className="flex flex-col gap-2 border-t border-rule pt-3">
      <legend className="text-2xs font-medium uppercase tracking-wider text-text-soft">
        Disturbance
      </legend>
      <div className="flex flex-wrap items-end gap-2">
        <div className="flex min-w-28 flex-1 flex-col gap-1">
          <label htmlFor={typeId} className="text-2xs text-text-soft">
            Disturbance type
          </label>
          <select
            id={typeId}
            className={NATIVE_SELECT_CLASS}
            value={type}
            onChange={(e) => setType(e.target.value as DisturbanceType)}
          >
            <option value="step">step</option>
            <option value="noise">noise</option>
          </select>
        </div>
        <div className="flex min-w-24 flex-1 flex-col gap-1">
          <label htmlFor={amplitudeId} className="text-2xs text-text-soft">
            Amplitude
          </label>
          <Input
            id={amplitudeId}
            type="number"
            value={amplitude}
            onChange={(e) => setAmplitude(Number(e.target.value))}
          />
        </div>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button size="sm" onClick={() => onInject(type, amplitude)}>
          Inject disturbance
        </Button>
        <Button size="sm" variant="ghost" disabled={!active} onClick={onRemove}>
          Remove
        </Button>
      </div>
    </fieldset>
  );
}
