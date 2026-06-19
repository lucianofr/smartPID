import './DynamicsSliders.css';

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

export function DynamicsSliders({ value, onCommit }: Props): JSX.Element {
  const change = (key: keyof Dynamics, raw: string) => onCommit({ ...value, [key]: Number(raw) });
  return (
    <div className="dyn-sliders">
      {FIELDS.map(({ key, label, min, max, step }) => {
        const v = value[key] ?? 0;
        return (
          <div key={key} className="dyn-sliders__row">
            <label className="dyn-sliders__label" htmlFor={`dyn-${key}`}>
              {label}
            </label>
            <input
              id={`dyn-${key}`}
              className="dyn-sliders__input"
              type="range"
              aria-label={label}
              min={min}
              max={max}
              step={step}
              value={v}
              onChange={(e) => change(key, e.target.value)}
            />
            <span className="numeric dyn-sliders__readout" data-testid={`readout-${key}`}>
              {v.toFixed(2)}
            </span>
          </div>
        );
      })}
    </div>
  );
}
