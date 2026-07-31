import { Slider } from '@/components/Slider';
import type { Dynamics } from './types';

export interface DynamicsSlidersProps {
  value: Dynamics;
  /** Fires on every tick — the panel debounces it into one PUT per gesture. */
  onCommit: (next: Dynamics) => void;
}

/**
 * Process-model bounds, carried over verbatim from the pre-rewrite panel: a
 * gain above 5 or a lag above a minute stops being a plausible loop and starts
 * being a way to make the twin diverge.
 */
const FIELDS: readonly {
  key: keyof Dynamics;
  label: string;
  min: number;
  max: number;
  step: number;
  unit: string;
}[] = [
  { key: 'gain', label: 'Gain', min: 0, max: 5, step: 0.1, unit: '' },
  { key: 'dead_time', label: 'Dead time L', min: 0, max: 30, step: 0.1, unit: 's' },
  { key: 'tau1', label: 'Tau1', min: 0, max: 60, step: 0.1, unit: 's' },
  { key: 'tau2', label: 'Tau2', min: 0, max: 60, step: 0.1, unit: 's' },
];

export function DynamicsSliders({ value, onCommit }: DynamicsSlidersProps) {
  return (
    <div className="grid grid-cols-1 gap-x-4 gap-y-1.5 @min-[26rem]:grid-cols-2">
      {FIELDS.map(({ key, label, min, max, step, unit }) => {
        // `tau2` is null for a first-order model; the slider shows it as 0 and
        // only writes a number once the operator actually moves THAT slider.
        const current = value[key] ?? 0;
        return (
          <div key={key} className="flex items-center gap-2">
            <span className="w-20 shrink-0 text-2xs font-medium uppercase tracking-wider text-text-soft">
              {label}
            </span>
            <Slider
              className="flex-1"
              thumbLabel={label}
              min={min}
              max={max}
              step={step}
              value={[current]}
              onValueChange={([next]) => onCommit({ ...value, [key]: next })}
            />
            <span
              data-testid={`readout-${key}`}
              className="numeric w-16 shrink-0 text-right text-xs text-text"
            >
              {current.toFixed(2)}
              {unit}
            </span>
          </div>
        );
      })}
    </div>
  );
}
