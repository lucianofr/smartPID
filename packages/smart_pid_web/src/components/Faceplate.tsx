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
import { Slider } from './ui/slider';
import type { Scale } from '../lib/scale';

export interface FaceplateProps {
  controllerId: number;
  tag: string;
  description?: string;
  scale: Scale;
  decimals?: number;
}

const CO_SCALE: Scale = { euMin: 0, euMax: 100, unit: '%' };

/*
 * ISA-101 faceplate (Task 3.1) — the design-system "vitrine".
 *
 * All static styling is expressed as token utilities (`bg-surface`, `border-border`,
 * `text-text*`, `rounded-*`, `--sp-*` spacing). Hierarchy is scale + weight + gray
 * only; flat per §design-quality (no shadow/lift/gradient). Font sizes stay inline
 * as `var(--text-*)` because the type scale has no Tailwind utility in the
 * `@theme inline` bridge — same sanctioned precedent as AnalogBar/ControllerCard.
 *
 * DOM-freeze (§3a) preserved exactly: root `<aside>` keeps `aria-label="Faceplate {tag}"`
 * (implicit `role="complementary"`); the 8 mode buttons keep their mode names + `aria-pressed`;
 * the numeric CO input keeps `aria-label="Manual CO"` and its MAN-only `disabled`; the
 * Setpoint input + `Set setpoint`/`Set output` buttons + apply-tuning button are unchanged.
 */

// Segmented mode switch (§5.3): flat tactile buttons, ≥44×44, no shadow.
// Inactive = high container + muted text; active = field surface + strong border.
const MODE_BUTTON_BASE =
  'flex min-h-[44px] min-w-[44px] items-center justify-center cursor-pointer numeric ' +
  'border border-border transition-colors duration-fast ' +
  'focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-[var(--focus-ring)]';
const MODE_BUTTON_INACTIVE =
  'bg-surface-container-high text-text-secondary hover:bg-surface-container hover:text-text';
const MODE_BUTTON_ACTIVE = 'bg-field-bg text-text border-2 border-border-strong';

const FIELD =
  'bg-field-bg text-text border border-border rounded-control numeric ' +
  'focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-[var(--focus-ring)] ' +
  'disabled:text-text-disabled disabled:cursor-not-allowed';

const ACTION_BUTTON =
  'min-h-[44px] cursor-pointer bg-surface-container-high text-text border border-border rounded-control ' +
  'transition-colors duration-fast hover:bg-surface-container ' +
  'focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-[var(--focus-ring)] ' +
  'disabled:text-text-disabled disabled:cursor-not-allowed';

// apply-tuning (§5.3): emphasis via a STRONG BORDER, never an alarm color.
const APPLY_BUTTON =
  'min-h-[44px] cursor-pointer bg-transparent text-text border-2 border-border-strong rounded-control ' +
  'transition-colors duration-fast hover:bg-surface-container-high ' +
  'focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-[var(--focus-ring)] ' +
  'disabled:text-text-disabled disabled:cursor-not-allowed';

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
    <div className="flex flex-col gap-1">
      <span
        className="text-text-secondary uppercase tracking-[0.05em]"
        style={{ fontSize: 'var(--text-2xs)' }}
      >
        {label}
      </span>
      <span
        className="numeric text-text tabular-nums"
        style={{
          fontSize: primary ? 'var(--text-3xl)' : 'var(--text-xl)',
          fontWeight: primary ? 500 : 600,
          lineHeight: 'var(--lh-tight)',
        }}
      >
        {value.toFixed(decimals)}
        <span className="text-text-secondary" style={{ fontSize: 'var(--text-sm)' }}>
          {' '}
          {unit}
        </span>
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
      <aside
        className="flex flex-col gap-4 p-4 bg-surface text-text border border-border rounded-card"
        style={{ minWidth: '22rem' }}
        aria-label={`Faceplate ${tag}`}
        aria-busy="true"
      >
        <header>
          <div
            className="numeric font-bold"
            style={{ fontSize: 'var(--text-3xl)', lineHeight: 1 }}
          >
            {tag}
          </div>
          {description ? (
            <div className="text-text-secondary" style={{ fontSize: 'var(--text-sm)' }}>
              {description}
            </div>
          ) : null}
        </header>
        <p className="text-text-secondary" style={{ fontSize: 'var(--text-sm)' }}>
          Waiting for data…
        </p>
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

  // Manual CO slider tracks the typed value while editing, else the live CO.
  const coSliderValue = coInput === '' || coError ? co : coValue;

  const handleSetSetpoint = () => {
    if (spInput === '' || spError) return;
    setpointCmd.mutate({ id: controllerId, value: spValue });
  };

  const handleSetOutput = () => {
    if (coInput === '' || coError) return;
    outputCmd.mutate({ id: controllerId, value: coValue });
  };

  const handleSliderCommit = (next: number) => {
    if (!isManual) return;
    outputCmd.mutate({ id: controllerId, value: next });
  };

  return (
    <aside
      className="flex flex-col gap-4 p-4 bg-surface text-text border border-border rounded-card"
      style={{ minWidth: '22rem' }}
      aria-label={`Faceplate ${tag}`}
    >
      <header>
        <div className="numeric font-bold" style={{ fontSize: 'var(--text-3xl)', lineHeight: 1 }}>
          {tag}
        </div>
        {description ? (
          <div className="text-text-secondary" style={{ fontSize: 'var(--text-sm)' }}>
            {description}
          </div>
        ) : null}
      </header>

      <div className="flex flex-wrap gap-4">
        <Readout label="PV" value={pv} unit={scale.unit} primary decimals={decimals} />
        <Readout label="SP" value={sp} unit={scale.unit} decimals={decimals} />
        <Readout label="CO" value={co} unit={CO_SCALE.unit} />
      </div>

      <div className="flex flex-col gap-2">
        <AnalogBar
          label="PV"
          value={pv}
          scale={scale}
          spValue={sp}
          size="faceplate"
          decimals={decimals}
        />
        <AnalogBar label="SP" value={sp} scale={scale} size="faceplate" decimals={decimals} />
        <AnalogBar label="CO" value={co} scale={CO_SCALE} size="faceplate" decimals={1} />
      </div>

      <div role="group" aria-label="Controller mode" className="grid grid-cols-4 gap-1">
        {CONTROLLER_MODES.map((m) => {
          const active = m === status.mode;
          return (
            <button
              key={m}
              type="button"
              aria-pressed={active}
              className={`${MODE_BUTTON_BASE} ${active ? MODE_BUTTON_ACTIVE : MODE_BUTTON_INACTIVE}`}
              style={{ fontSize: 'var(--text-xs)', fontWeight: 600 }}
              onClick={() => modeCmd.mutate({ id: controllerId, mode: m as ControllerMode })}
            >
              {m}
            </button>
          );
        })}
      </div>

      <div className="flex items-center gap-2">
        <label
          htmlFor={`fp-sp-${controllerId}`}
          className="text-text-secondary shrink-0"
          style={{ fontSize: 'var(--text-2xs)', width: '3rem' }}
        >
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
          className={FIELD}
          style={{ fontSize: 'var(--text-sm)', width: '6rem', padding: 'var(--sp-1) var(--sp-2)' }}
          aria-invalid={Boolean(spError)}
        />
        <button
          type="button"
          aria-label="Set setpoint"
          onClick={handleSetSetpoint}
          disabled={setpointCmd.isPending || spInput === '' || Boolean(spError)}
          className={ACTION_BUTTON}
          style={{ fontSize: 'var(--text-sm)', padding: 'var(--sp-1) var(--sp-3)' }}
        >
          Set
        </button>
      </div>
      {spError ? (
        <span role="alert" className="text-alarm-warning" style={{ fontSize: 'var(--text-2xs)' }}>
          {spError}
        </span>
      ) : null}
      {setpointCmd.error ? (
        <span className="text-alarm-warning" style={{ fontSize: 'var(--text-2xs)' }}>
          {setpointCmd.error.detail}
        </span>
      ) : null}

      <div className="flex items-center gap-2">
        <label
          htmlFor={`fp-co-${controllerId}`}
          className="text-text-secondary shrink-0"
          style={{ fontSize: 'var(--text-2xs)', width: '3rem' }}
        >
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
          className={FIELD}
          style={{ fontSize: 'var(--text-sm)', width: '6rem', padding: 'var(--sp-1) var(--sp-2)' }}
          aria-invalid={Boolean(coError)}
        />
        <button
          type="button"
          aria-label="Set output"
          onClick={handleSetOutput}
          disabled={!isManual || outputCmd.isPending || coInput === '' || Boolean(coError)}
          className={ACTION_BUTTON}
          style={{ fontSize: 'var(--text-sm)', padding: 'var(--sp-1) var(--sp-3)' }}
        >
          Set
        </button>
      </div>
      {/* Tactile MAN-only CO slider beside the numeric field. Distinct accessible name
          ("Manual CO slider") so getByLabelText('Manual CO') still resolves uniquely to
          the numeric input above. Shares the same MAN gate via `disabled`. */}
      <div className="flex items-center gap-2 min-h-[44px]">
        <span className="shrink-0" style={{ width: '3rem' }} aria-hidden />
        <Slider
          aria-label="Manual CO slider"
          min={CO_SCALE.euMin}
          max={CO_SCALE.euMax}
          step={1}
          value={[coSliderValue]}
          disabled={!isManual}
          onValueChange={(vals) => setCoInput(String(vals[0]))}
          onValueCommit={(vals) => handleSliderCommit(vals[0])}
        />
      </div>
      {coError ? (
        <span role="alert" className="text-alarm-warning" style={{ fontSize: 'var(--text-2xs)' }}>
          {coError}
        </span>
      ) : null}
      {outputCmd.error ? (
        <span className="text-alarm-warning" style={{ fontSize: 'var(--text-2xs)' }}>
          {outputCmd.error.detail}
        </span>
      ) : null}

      <button
        type="button"
        className={APPLY_BUTTON}
        style={{ fontSize: 'var(--text-sm)', fontWeight: 600, padding: 'var(--sp-2) var(--sp-3)' }}
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
