import { PERIOD_OPTIONS, type PeriodKey } from '../lib/period';

export interface PeriodSelectorProps {
  value: PeriodKey;
  onChange: (k: PeriodKey) => void;
}

export function PeriodSelector({ value, onChange }: PeriodSelectorProps) {
  return (
    <label>
      <select
        aria-label="Aggregation period"
        value={value}
        onChange={(e) => onChange(e.target.value as PeriodKey)}
      >
        {PERIOD_OPTIONS.map((o) => (
          <option key={o.key} value={o.key}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}
