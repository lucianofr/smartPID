import { PRESET_NAMES, type ProcessPresetName } from './types';

interface Props {
  value: ProcessPresetName;
  onChange: (p: ProcessPresetName) => void;
}

export function PresetSelector({ value, onChange }: Props): JSX.Element {
  return (
    <label htmlFor="simulator-preset">
      <span>Process preset</span>
      <select
        id="simulator-preset"
        aria-label="Process preset"
        value={value}
        onChange={(e) => onChange(e.target.value as ProcessPresetName)}
      >
        {PRESET_NAMES.map((p) => (
          <option key={p} value={p}>
            {p}
          </option>
        ))}
      </select>
    </label>
  );
}
