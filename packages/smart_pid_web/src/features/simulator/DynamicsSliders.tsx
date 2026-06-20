export interface Dynamics {
  gain: number;
  dead_time: number;
  tau1: number;
  tau2: number | null;
}

interface Props {
  value: Dynamics;
  onCommit: (v: Dynamics) => void;
}

const FIELDS: { key: keyof Dynamics; label: string; min: number; max: number; step: number }[] = [
  { key: 'gain', label: 'Gain', min: 0, max: 5, step: 0.1 },
  { key: 'dead_time', label: 'Dead time L', min: 0, max: 30, step: 0.1 },
  { key: 'tau1', label: 'Tau1', min: 0, max: 60, step: 0.1 },
  { key: 'tau2', label: 'Tau2', min: 0, max: 60, step: 0.1 },
];

/**
 * Process-dynamics sliders (Task 8.3 — CSS migrated to flat ISA-101 token
 * utilities). The control stays a NATIVE `<input type="range">` (restyled flat,
 * `accent-color` token), NOT the shadcn/Radix Slider: DynamicsSliders.test reads
 * each slider via `toHaveValue('1.2')` and drives it with `fireEvent.change(...,
 * { target: { value } })`, both of which only work on a native range input —
 * same frozen-binding precedent as the native `<select>` in CardControls. The
 * `readout-gain` testid and tabular `toFixed(2)` ('1.20') formatting are kept.
 */
export function DynamicsSliders({ value, onCommit }: Props): JSX.Element {
  const change = (key: keyof Dynamics, raw: string) => onCommit({ ...value, [key]: Number(raw) });
  return (
    <div className="flex flex-col gap-2">
      {FIELDS.map(({ key, label, min, max, step }) => {
        const v = value[key] ?? 0;
        return (
          <div key={key} className="flex items-center gap-3">
            <label
              className="w-24 flex-shrink-0 text-text-secondary"
              style={{ fontSize: 'var(--text-2xs)' }}
              htmlFor={`dyn-${key}`}
            >
              {label}
            </label>
            <input
              id={`dyn-${key}`}
              className="flex-1 accent-[var(--state-running)]"
              type="range"
              aria-label={label}
              min={min}
              max={max}
              step={step}
              value={v}
              onChange={(e) => change(key, e.target.value)}
            />
            <span
              className="numeric w-14 flex-shrink-0 text-right"
              style={{ fontSize: 'var(--text-xs)' }}
              data-testid={`readout-${key}`}
            >
              {v.toFixed(2)}
            </span>
          </div>
        );
      })}
    </div>
  );
}
