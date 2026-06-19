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

const fieldStyle: React.CSSProperties = {
  background: 'var(--field-bg)',
  color: 'var(--text)',
  border: '1px solid var(--border)',
  borderRadius: 'var(--radius-control)',
  padding: '0.125rem 0.375rem',
  fontSize: 'var(--text-xs)',
  width: '4.5rem',
};

const rowStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 'var(--sp-2)',
};

const labelStyle: React.CSSProperties = {
  fontSize: 'var(--text-2xs)',
  color: 'var(--text-secondary)',
  width: '2.5rem',
  flexShrink: 0,
};

const errorStyle: React.CSSProperties = {
  fontSize: 'var(--text-2xs)',
  color: 'var(--alarm-hi, #d08a3a)',
};

function ErrorText({ message }: { message: string | null | undefined }) {
  if (!message) return null;
  return (
    <span role="alert" style={errorStyle}>
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
      style={{
        padding: 'var(--sp-3) var(--sp-4)',
        borderTop: '1px solid var(--border)',
        display: 'flex',
        flexDirection: 'column',
        gap: 'var(--sp-2)',
      }}
    >
      <div style={rowStyle}>
        <label htmlFor={`sp-${controllerId}`} style={labelStyle}>
          Setpoint
        </label>
        <input
          id={`sp-${controllerId}`}
          className="numeric"
          type="number"
          inputMode="decimal"
          value={spInput}
          onChange={(e) => setSpInput(e.target.value)}
          style={fieldStyle}
          aria-invalid={Boolean(spError)}
        />
        <button
          type="button"
          aria-label="Set setpoint"
          onClick={handleSetSetpoint}
          disabled={setpoint.isPending || spInput === '' || Boolean(spError)}
        >
          Set
        </button>
      </div>
      <ErrorText message={spError} />
      <ErrorText message={setpoint.error?.detail} />

      <div style={rowStyle}>
        <label htmlFor={`mode-${controllerId}`} style={labelStyle}>
          Mode
        </label>
        <select
          id={`mode-${controllerId}`}
          className="numeric"
          value={mode}
          onChange={(e) => handleChangeMode(e.target.value as ControllerMode)}
          disabled={modeCmd.isPending}
          style={{ ...fieldStyle, width: 'auto' }}
        >
          {CONTROLLER_MODES.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
      </div>
      <ErrorText message={modeCmd.error?.detail} />

      <div style={rowStyle}>
        <label htmlFor={`co-${controllerId}`} style={labelStyle}>
          Output
        </label>
        <input
          id={`co-${controllerId}`}
          className="numeric"
          type="number"
          inputMode="decimal"
          value={coInput}
          onChange={(e) => setCoInput(e.target.value)}
          disabled={!isManual}
          style={fieldStyle}
          aria-invalid={Boolean(coError)}
        />
        <button
          type="button"
          aria-label="Set output"
          onClick={handleSetOutput}
          disabled={!isManual || output.isPending || coInput === '' || Boolean(coError)}
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
        style={{ alignSelf: 'flex-start', fontSize: 'var(--text-xs)' }}
      >
        {optimizationEnabled ? 'Disable AI Optimization' : 'Enable AI Optimization'}
      </button>
      <ErrorText message={optimization.error?.detail} />
    </div>
  );
}
