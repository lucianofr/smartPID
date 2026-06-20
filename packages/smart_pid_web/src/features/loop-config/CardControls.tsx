import { useState } from 'react';
import {
  useModeMutation,
  useOptimizationMutation,
  useOutputMutation,
  useSetpointMutation,
} from './useCommands';
import { CONTROLLER_MODES, type ControllerMode } from './types';
import { validateOutput, validateSetpoint } from './validation';

export interface CardControlsProps {
  controllerId: number;
  mode: ControllerMode;
  optimizationEnabled: boolean;
  onOpenConfig: () => void;
}

/**
 * Flat ISA-101 per-loop controls. Inline-style blocks migrated to token utilities
 * (Task 8.2). The mode selector stays a NATIVE `<select>` — `CardControls.test.tsx`
 * reads it as an `HTMLSelectElement` via `getByLabelText(/mode/i)` — restyled flat
 * (no shadcn Select swap). Numeric inputs carry `numeric` (tabular numerals, §6).
 * Font sizes stay inline as `var(--text-*)` (no Tailwind type-scale mapping in the
 * `@theme inline` bridge — same precedent as AnalogBar/ControllerCard).
 */
const FIELD =
  'numeric w-[4.5rem] bg-field-bg text-text border border-border rounded-control px-1.5 py-0.5 ' +
  'focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-[var(--focus-ring)] ' +
  'disabled:text-text-disabled disabled:cursor-not-allowed';

const SELECT =
  'numeric w-auto bg-field-bg text-text border border-border rounded-control px-1.5 py-0.5 ' +
  'cursor-pointer focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-[var(--focus-ring)] ' +
  'disabled:text-text-disabled disabled:cursor-not-allowed';

const SET_BUTTON =
  'cursor-pointer bg-surface-container-high text-text border border-border rounded-control px-2 py-0.5 ' +
  'transition-colors duration-fast hover:bg-surface-container active:bg-field-bg ' +
  'focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-[var(--focus-ring)] ' +
  'disabled:text-text-disabled disabled:cursor-not-allowed disabled:hover:bg-surface-container-high';

const TOGGLE_BUTTON =
  'self-start cursor-pointer bg-surface-container-high text-text border border-border rounded-control px-2 py-0.5 ' +
  'transition-colors duration-fast hover:bg-surface-container active:bg-field-bg ' +
  'focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-[var(--focus-ring)] ' +
  'aria-pressed:bg-field-bg aria-pressed:border-border-strong ' +
  'disabled:text-text-disabled disabled:cursor-not-allowed disabled:hover:bg-surface-container-high';

const LABEL = 'w-10 flex-shrink-0 text-text-secondary';

function ErrorText({ message }: { message: string | null | undefined }) {
  if (!message) return null;
  return (
    <span role="alert" className="text-alarm-warning" style={{ fontSize: 'var(--text-2xs)' }}>
      {message}
    </span>
  );
}

export function CardControls({
  controllerId,
  mode,
  optimizationEnabled,
}: CardControlsProps) {
  const setpoint = useSetpointMutation();
  const modeCmd = useModeMutation();
  const output = useOutputMutation();
  const optimization = useOptimizationMutation();

  const [spInput, setSpInput] = useState('');
  const [coInput, setCoInput] = useState('');

  const spValue = Number(spInput);
  const coValue = Number(coInput);
  const spError = spInput === '' ? undefined : validateSetpoint(spValue);
  const coError = coInput === '' ? undefined : validateOutput(coValue);
  const isManual = mode === 'MAN';

  const handleSetSetpoint = () => {
    if (spInput === '' || spError) return;
    setpoint.mutate({ id: controllerId, value: spValue });
  };

  const handleSetOutput = () => {
    if (coInput === '' || coError) return;
    output.mutate({ id: controllerId, value: coValue });
  };

  const handleChangeMode = (next: ControllerMode) => {
    modeCmd.mutate({ id: controllerId, mode: next });
  };

  const handleToggleOptimization = () => {
    optimization.mutate({ id: controllerId, enabled: !optimizationEnabled });
  };

  return (
    <div
      className="flex flex-col gap-2 px-4 py-3 border-t border-border"
      style={{ fontSize: 'var(--text-2xs)' }}
    >
      <div className="flex items-center gap-2">
        <label htmlFor={`sp-${controllerId}`} className={LABEL}>
          Setpoint
        </label>
        <input
          id={`sp-${controllerId}`}
          className={FIELD}
          type="number"
          inputMode="decimal"
          value={spInput}
          onChange={(e) => setSpInput(e.target.value)}
          aria-invalid={Boolean(spError)}
        />
        <button
          type="button"
          aria-label="Set setpoint"
          onClick={handleSetSetpoint}
          disabled={setpoint.isPending || spInput === '' || Boolean(spError)}
          className={SET_BUTTON}
        >
          Set
        </button>
      </div>
      <ErrorText message={spError} />
      <ErrorText message={setpoint.error?.detail} />

      <div className="flex items-center gap-2">
        <label htmlFor={`mode-${controllerId}`} className={LABEL}>
          Mode
        </label>
        <select
          id={`mode-${controllerId}`}
          className={SELECT}
          value={mode}
          onChange={(e) => handleChangeMode(e.target.value as ControllerMode)}
          disabled={modeCmd.isPending}
        >
          {CONTROLLER_MODES.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
      </div>
      <ErrorText message={modeCmd.error?.detail} />

      <div className="flex items-center gap-2">
        <label htmlFor={`co-${controllerId}`} className={LABEL}>
          Output
        </label>
        <input
          id={`co-${controllerId}`}
          className={FIELD}
          type="number"
          inputMode="decimal"
          value={coInput}
          onChange={(e) => setCoInput(e.target.value)}
          disabled={!isManual}
          aria-invalid={Boolean(coError)}
        />
        <button
          type="button"
          aria-label="Set output"
          onClick={handleSetOutput}
          disabled={!isManual || output.isPending || coInput === '' || Boolean(coError)}
          className={SET_BUTTON}
        >
          Set
        </button>
      </div>
      <ErrorText message={coError} />
      <ErrorText message={output.error?.detail} />

      <button
        type="button"
        onClick={handleToggleOptimization}
        disabled={optimization.isPending}
        aria-pressed={optimizationEnabled}
        className={TOGGLE_BUTTON}
        style={{ fontSize: 'var(--text-xs)' }}
      >
        {optimizationEnabled ? 'Disable AI Optimization' : 'Enable AI Optimization'}
      </button>
      <ErrorText message={optimization.error?.detail} />
    </div>
  );
}
