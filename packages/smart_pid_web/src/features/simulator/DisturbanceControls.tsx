import { useId, useState } from 'react';
import { Button } from '@/components/Button';
import { Input } from '@/components/Field';
import { NATIVE_SELECT_CLASS } from './PresetSelector';
import type { DisturbanceType } from './types';

export interface DisturbanceControlsProps {
  /** A step OR noise disturbance is currently loaded on the model. */
  active: boolean;
  /** Auto-disturbance re-injects a random amplitude on its own cycle — while
   * it owns the disturbance, a manual injection would be overridden within
   * seconds without any indication, so the path is closed rather than left
   * to silently lose the race (same reasoning as CO staying closed in AUTO). */
  autoDisturbanceEnabled: boolean;
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
export function DisturbanceControls({
  active,
  autoDisturbanceEnabled,
  onInject,
  onRemove,
}: DisturbanceControlsProps) {
  const typeId = useId();
  const amplitudeId = useId();
  const [type, setType] = useState<DisturbanceType>('step');
  const [amplitude, setAmplitude] = useState(DEFAULT_AMPLITUDE);

  return (
    <fieldset className="flex flex-col gap-1.5 border-t border-rule pt-1.5">
      <legend className="text-2xs font-medium uppercase tracking-wider text-text-soft">
        Disturbance
      </legend>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
        <div className="flex min-w-40 flex-1 items-center gap-1.5">
          <label htmlFor={typeId} className="shrink-0 text-2xs text-text-soft">
            Disturbance type
          </label>
          <div className="min-w-0 flex-1">
            <select
              id={typeId}
              className={NATIVE_SELECT_CLASS}
              value={type}
              disabled={autoDisturbanceEnabled}
              onChange={(e) => setType(e.target.value as DisturbanceType)}
            >
              <option value="step">step</option>
              <option value="noise">noise</option>
            </select>
          </div>
        </div>
        <div className="flex min-w-32 flex-1 items-center gap-1.5">
          <label htmlFor={amplitudeId} className="shrink-0 text-2xs text-text-soft">
            Amplitude
          </label>
          <div className="min-w-0 flex-1">
            <Input
              id={amplitudeId}
              type="number"
              value={amplitude}
              disabled={autoDisturbanceEnabled}
              onChange={(e) => setAmplitude(Number(e.target.value))}
            />
          </div>
        </div>
      </div>
      {autoDisturbanceEnabled ? (
        <p className="text-2xs text-text-soft">
          Auto-disturbance está ativo e reinjeta uma amplitude aleatória periodicamente — desative-o
          em Automation para injetar manualmente.
        </p>
      ) : null}
      <div className="flex flex-wrap gap-2">
        <Button size="sm" disabled={autoDisturbanceEnabled} onClick={() => onInject(type, amplitude)}>
          Inject disturbance
        </Button>
        <Button size="sm" variant="ghost" disabled={!active} onClick={onRemove}>
          Remove
        </Button>
      </div>
    </fieldset>
  );
}
