import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { useRealtime } from '../realtime/useRealtime';
import { CONTROLLER_MODES, type ControllerMode } from '../features/loop-config/types';
import {
  useModeMutation,
  useOutputMutation,
  useSetpointMutation,
} from '../features/loop-config/useCommands';
import { useTuningRecommendation } from '../features/loop-config/useAiControls';
import { applyTuning } from '../features/loop-config/commandApi';
import { ConfirmApplyTuningDialog } from '../features/loop-config/ConfirmApplyTuningDialog';
import { validateOutput, validateSetpoint } from '../features/loop-config/validation';
import type { ApiError } from '../api/client';
import { AnalogBar } from './AnalogBar';
import type { Scale } from '../lib/scale';

export interface FaceplateProps {
  controllerId: number;
  tag: string;
  description?: string;
  scale: Scale;
  decimals?: number;
}

const CO_SCALE: Scale = { euMin: 0, euMax: 100, unit: '%' };

const rootStyle: React.CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: 'var(--sp-4)',
  padding: 'var(--sp-4)',
  background: 'var(--surface)',
  color: 'var(--text)',
  border: '1px solid var(--border)',
  borderRadius: 'var(--radius-card)',
  minWidth: '22rem',
};

const tagStyle: React.CSSProperties = {
  fontFamily: 'var(--font-data)',
  fontSize: 'var(--text-3xl)',
  fontWeight: 'var(--fw-bold)' as unknown as number,
  lineHeight: 1,
};

const descStyle: React.CSSProperties = {
  fontSize: 'var(--text-sm)',
  color: 'var(--text-secondary)',
};

const readoutRowStyle: React.CSSProperties = {
  display: 'flex',
  gap: 'var(--sp-4)',
  flexWrap: 'wrap',
};

const readoutStyle: React.CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: 'var(--sp-1)',
};

const readoutLabelStyle: React.CSSProperties = {
  fontSize: 'var(--text-2xs)',
  color: 'var(--text-secondary)',
  textTransform: 'uppercase',
  letterSpacing: '0.05em',
};

const readoutValueStyle: React.CSSProperties = {
  fontFamily: 'var(--font-data)',
  fontSize: 'var(--text-xl)',
  fontWeight: 'var(--fw-semibold)' as unknown as number,
};

// Design §5.3: the PV is the dominant reading in the faceplate hierarchy.
const readoutValuePrimaryStyle: React.CSSProperties = {
  ...readoutValueStyle,
  fontSize: 'var(--text-3xl)',
};

const barsStyle: React.CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: 'var(--sp-2)',
};

const modeGridStyle: React.CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'repeat(4, 1fr)',
  gap: 'var(--sp-1)',
};

const modeButtonStyle = (active: boolean): React.CSSProperties => ({
  background: active ? 'var(--text)' : 'var(--field-bg)',
  color: active ? 'var(--surface)' : 'var(--text)',
  border: `1px solid ${active ? 'var(--border-strong)' : 'var(--border)'}`,
  borderRadius: 'var(--radius-control)',
  padding: 'var(--sp-1) var(--sp-2)',
  fontFamily: 'var(--font-data)',
  fontSize: 'var(--text-xs)',
  fontWeight: 'var(--fw-semibold)' as unknown as number,
  cursor: 'pointer',
});

const controlRowStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 'var(--sp-2)',
};

const controlLabelStyle: React.CSSProperties = {
  fontSize: 'var(--text-2xs)',
  color: 'var(--text-secondary)',
  width: '3rem',
  flexShrink: 0,
};

const fieldStyle: React.CSSProperties = {
  background: 'var(--field-bg)',
  color: 'var(--text)',
  border: '1px solid var(--border)',
  borderRadius: 'var(--radius-control)',
  padding: 'var(--sp-1) var(--sp-2)',
  fontSize: 'var(--text-sm)',
  width: '6rem',
};

const errorStyle: React.CSSProperties = {
  fontSize: 'var(--text-2xs)',
  color: 'var(--alarm-warning, #d08a3a)',
};

const applyButtonStyle: React.CSSProperties = {
  border: '1px solid var(--border-strong)',
  background: 'transparent',
  color: 'var(--text)',
  borderRadius: 'var(--radius-control)',
  fontWeight: 'var(--fw-semibold)' as unknown as number,
  padding: 'var(--sp-2) var(--sp-3)',
  cursor: 'pointer',
};

function Readout({
  label,
  value,
  unit,
  primary = false,
  decimals = 1,
}: {
  label: string;
  value: number;
  unit: string;
  primary?: boolean;
  decimals?: number;
}) {
  return (
    <div style={readoutStyle}>
      <span style={readoutLabelStyle}>{label}</span>
      <span style={primary ? readoutValuePrimaryStyle : readoutValueStyle}>
        {value.toFixed(decimals)}
        <span style={descStyle}> {unit}</span>
      </span>
    </div>
  );
}

export function Faceplate({ controllerId, tag, description, scale, decimals = 1 }: FaceplateProps) {
  const { lastStatus } = useRealtime();
  const status = lastStatus.get(controllerId);

  const setpointCmd = useSetpointMutation();
  const modeCmd = useModeMutation();
  const outputCmd = useOutputMutation();

  const recommendation = useTuningRecommendation(controllerId);
  const rec = recommendation.data;
  const canApply = rec?.status === 'pending';

  const [confirmOpen, setConfirmOpen] = useState(false);
  const [spInput, setSpInput] = useState('');
  const [coInput, setCoInput] = useState('');

  // Reuse the Fatia 2 apply-tuning flow exactly: a local mutation around the shared
  // applyTuning command so a rejected write surfaces to the operator instead of
  // being swallowed. No mutation logic is duplicated.
  const applyMut = useMutation<unknown, ApiError, void>({
    mutationFn: () => applyTuning(controllerId),
    onSuccess: () => setConfirmOpen(false),
  });

  if (!status) {
    return (
      <aside style={rootStyle} aria-label={`Faceplate ${tag}`}>
        <header>
          <div style={tagStyle}>{tag}</div>
          {description ? <div style={descStyle}>{description}</div> : null}
        </header>
        <p style={descStyle}>Waiting for data…</p>
      </aside>
    );
  }

  const pv = status.pv.value;
  const sp = status.sp.value;
  const co = status.co.value;
  const isManual = status.mode === 'MAN';

  const spValue = Number(spInput);
  const coValue = Number(coInput);
  const spError = spInput === '' ? undefined : validateSetpoint(spValue);
  const coError = coInput === '' ? undefined : validateOutput(coValue);

  const handleSetSetpoint = () => {
    if (spInput === '' || spError) return;
    setpointCmd.mutate({ id: controllerId, value: spValue });
  };

  const handleSetOutput = () => {
    if (coInput === '' || coError) return;
    outputCmd.mutate({ id: controllerId, value: coValue });
  };

  return (
    <aside style={rootStyle} aria-label={`Faceplate ${tag}`}>
      <header>
        <div style={tagStyle}>{tag}</div>
        {description ? <div style={descStyle}>{description}</div> : null}
      </header>

      <div style={readoutRowStyle}>
        <Readout label="PV" value={pv} unit={scale.unit} primary decimals={decimals} />
        <Readout label="SP" value={sp} unit={scale.unit} decimals={decimals} />
        <Readout label="CO" value={co} unit={CO_SCALE.unit} />
      </div>

      <div style={barsStyle}>
        <AnalogBar label="PV" value={pv} scale={scale} spValue={sp} size="faceplate" decimals={decimals} />
        <AnalogBar label="SP" value={sp} scale={scale} size="faceplate" decimals={decimals} />
        <AnalogBar label="CO" value={co} scale={CO_SCALE} size="faceplate" decimals={1} />
      </div>

      <div role="group" aria-label="Controller mode" style={modeGridStyle}>
        {CONTROLLER_MODES.map((m) => (
          <button
            key={m}
            type="button"
            aria-pressed={m === status.mode}
            style={modeButtonStyle(m === status.mode)}
            onClick={() => modeCmd.mutate({ id: controllerId, mode: m as ControllerMode })}
          >
            {m}
          </button>
        ))}
      </div>

      <div style={controlRowStyle}>
        <label htmlFor={`fp-sp-${controllerId}`} style={controlLabelStyle}>
          SP
        </label>
        <input
          id={`fp-sp-${controllerId}`}
          type="number"
          inputMode="decimal"
          aria-label="Setpoint"
          value={spInput}
          onChange={(e) => setSpInput(e.target.value)}
          onBlur={handleSetSetpoint}
          style={fieldStyle}
          aria-invalid={Boolean(spError)}
        />
        <button
          type="button"
          aria-label="Set setpoint"
          onClick={handleSetSetpoint}
          disabled={setpointCmd.isPending || spInput === '' || Boolean(spError)}
        >
          Set
        </button>
      </div>
      {spError ? (
        <span role="alert" style={errorStyle}>
          {spError}
        </span>
      ) : null}
      {setpointCmd.error ? <span style={errorStyle}>{setpointCmd.error.detail}</span> : null}

      <div style={controlRowStyle}>
        <label htmlFor={`fp-co-${controllerId}`} style={controlLabelStyle}>
          CO
        </label>
        <input
          id={`fp-co-${controllerId}`}
          type="number"
          inputMode="decimal"
          aria-label="Manual CO"
          value={coInput}
          onChange={(e) => setCoInput(e.target.value)}
          onBlur={handleSetOutput}
          disabled={!isManual}
          style={fieldStyle}
          aria-invalid={Boolean(coError)}
        />
        <button
          type="button"
          aria-label="Set output"
          onClick={handleSetOutput}
          disabled={!isManual || outputCmd.isPending || coInput === '' || Boolean(coError)}
        >
          Set
        </button>
      </div>
      {coError ? (
        <span role="alert" style={errorStyle}>
          {coError}
        </span>
      ) : null}
      {outputCmd.error ? <span style={errorStyle}>{outputCmd.error.detail}</span> : null}

      <button
        type="button"
        style={applyButtonStyle}
        disabled={!canApply}
        onClick={() => setConfirmOpen(true)}
      >
        Apply tuning…
      </button>

      {rec ? (
        <ConfirmApplyTuningDialog
          controllerId={controllerId}
          recommendation={rec}
          open={confirmOpen}
          onConfirm={() => applyMut.mutate()}
          onCancel={() => {
            applyMut.reset();
            setConfirmOpen(false);
          }}
          error={applyMut.error?.detail}
        />
      ) : null}
    </aside>
  );
}
