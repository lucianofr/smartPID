import { useId } from 'react';
import { cn } from '@/lib/utils';
import { PRESET_NAMES, type ProcessPresetName } from './types';

export interface PresetSelectorProps {
  value: ProcessPresetName;
  onChange: (preset: ProcessPresetName) => void;
}

/** Shared with DisturbanceControls — the flat instrument look for a native select. */
export const NATIVE_SELECT_CLASS = cn(
  'min-h-11 w-full rounded-control border border-rule-strong bg-surface-sunk px-2 text-sm text-text',
  'outline-none focus-visible:ring-2 focus-visible:ring-focus-ring',
);

/**
 * Process model behind the twin. Deliberately a NATIVE `<select>`, not the
 * Radix `Select`: the value is server-owned (the POST invalidates the status
 * snapshot and the refetch decides what is selected), and e2e/simulator drives
 * it with `selectOption`, which only speaks to a real `<select>`.
 */
export function PresetSelector({ value, onChange }: PresetSelectorProps) {
  const id = useId();
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-2xs font-medium uppercase tracking-wider text-text-soft">
        Process preset
      </label>
      <select
        id={id}
        className={NATIVE_SELECT_CLASS}
        value={value}
        onChange={(e) => onChange(e.target.value as ProcessPresetName)}
      >
        {PRESET_NAMES.map((preset) => (
          <option key={preset} value={preset}>
            {preset}
          </option>
        ))}
      </select>
    </div>
  );
}
