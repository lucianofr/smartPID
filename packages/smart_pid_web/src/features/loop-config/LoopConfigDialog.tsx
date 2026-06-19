import { useState, type ReactNode } from 'react';
import { Dialog } from '../../components/ui/Dialog';
import { useUpdateControllerMutation } from './useCommands';
import { hasErrors, validateLimits, validatePidParams } from './validation';
import {
  AI_ENGINES,
  OBJECTIVES,
  type AiConfigForm,
  type AiEngine,
  type FieldErrors,
  type LimitsForm,
  type PidParamsForm,
  type PidStructure,
} from './types';

export interface LoopConfigDialogProps {
  controllerId: number;
  open: boolean;
  onClose: () => void;
  initial: {
    pid: PidParamsForm;
    limits: LimitsForm;
    pidStructure: PidStructure;
    ai: AiConfigForm;
  };
}

type Section = 'pid' | 'ai' | 'limits';
type SectionState = Record<Section, boolean>;

const PID_STRUCTURES: PidStructure[] = ['ISA', 'PARALLEL', 'SERIES'];

const rowStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 'var(--sp-3)',
};

const labelStyle: React.CSSProperties = {
  fontSize: 'var(--text-xs)',
  color: 'var(--text-secondary)',
  width: '9rem',
  flexShrink: 0,
};

const fieldStyle: React.CSSProperties = {
  background: 'var(--field-bg)',
  color: 'var(--text)',
  border: '1px solid var(--border)',
  borderRadius: 'var(--radius-control)',
  padding: '0.25rem 0.5rem',
  fontSize: 'var(--text-sm)',
  width: '8rem',
};

const errorStyle: React.CSSProperties = {
  fontSize: 'var(--text-2xs)',
  color: 'var(--alarm-warning, #d08a3a)',
};

const sectionHeaderStyle: React.CSSProperties = {
  background: 'transparent',
  border: 'none',
  borderBottom: '1px solid var(--border)',
  color: 'var(--text)',
  textAlign: 'left',
  padding: 'var(--sp-2) 0',
  fontSize: 'var(--text-base)',
  fontWeight: 'var(--fw-semibold)' as unknown as number,
  cursor: 'pointer',
  width: '100%',
};

function ErrorText({ message }: { message: string | null | undefined }) {
  if (!message) return null;
  return (
    <span role="alert" style={errorStyle}>
      {message}
    </span>
  );
}

interface NumberFieldProps {
  id: string;
  label: string;
  value: number;
  onChange: (value: number) => void;
  error?: string;
}

function NumberField({ id, label, value, onChange, error }: NumberFieldProps) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-1)' }}>
      <div style={rowStyle}>
        <label htmlFor={id} style={labelStyle}>
          {label}
        </label>
        <input
          id={id}
          className="numeric"
          type="number"
          inputMode="decimal"
          value={Number.isNaN(value) ? '' : value}
          onChange={(e) => onChange(Number(e.target.value))}
          style={fieldStyle}
          aria-invalid={Boolean(error)}
        />
      </div>
      <ErrorText message={error} />
    </div>
  );
}

interface CollapsibleProps {
  label: string;
  expanded: boolean;
  onToggle: () => void;
  children: ReactNode;
}

function Collapsible({ label, expanded, onToggle, children }: CollapsibleProps) {
  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-2)' }}>
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={expanded}
        style={sectionHeaderStyle}
      >
        {label}
      </button>
      {expanded ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-2)' }}>
          {children}
        </div>
      ) : null}
    </section>
  );
}

const finitePositive = (v: number): string | undefined =>
  Number.isFinite(v) && v >= 0 ? undefined : 'Must be a finite, non-negative number';

function validateAi(ai: AiConfigForm): FieldErrors {
  if (ai.engine === 'NONE') return {};
  const e: FieldErrors = {};
  e.dead_time_l = finitePositive(ai.dead_time_l);
  if (!Number.isFinite(ai.limit_min)) e.limit_min = 'Must be a number';
  if (!Number.isFinite(ai.limit_max)) e.limit_max = 'Must be a number';
  if (ai.engine === 'RL') {
    if (!Number.isFinite(ai.rl_fallback_kp)) e.rl_fallback_kp = 'Must be a number';
    if (!Number.isFinite(ai.rl_fallback_kd)) e.rl_fallback_kd = 'Must be a number';
    e.rl_learning_rate = finitePositive(ai.rl_learning_rate);
    e.rl_train_interval = finitePositive(ai.rl_train_interval);
  }
  return e;
}

export function LoopConfigDialog({
  controllerId,
  open,
  onClose,
  initial,
}: LoopConfigDialogProps) {
  const update = useUpdateControllerMutation();

  const [pid, setPid] = useState<PidParamsForm>(initial.pid);
  const [structure, setStructure] = useState<PidStructure>(initial.pidStructure);
  const [limits, setLimits] = useState<LimitsForm>(initial.limits);
  const [ai, setAi] = useState<AiConfigForm>(initial.ai);
  const [expanded, setExpanded] = useState<SectionState>({
    pid: true,
    ai: true,
    limits: true,
  });

  const pidErrors = validatePidParams(pid);
  const limitsErrors = validateLimits(limits);
  const aiErrors = validateAi(ai);
  const disabled =
    hasErrors(pidErrors) || hasErrors(limitsErrors) || hasErrors(aiErrors);

  const setPidField = (key: keyof PidParamsForm, value: number) =>
    setPid((prev) => ({ ...prev, [key]: value }));
  const setLimitField = (key: keyof LimitsForm, value: number) =>
    setLimits((prev) => ({ ...prev, [key]: value }));
  const setAiNumber = (key: keyof AiConfigForm, value: number) =>
    setAi((prev) => ({ ...prev, [key]: value }));

  const toggle = (next: Section) =>
    setExpanded((prev) => ({ ...prev, [next]: !prev[next] }));

  const handleSave = () => {
    if (disabled) return;
    update.mutate(
      {
        id: controllerId,
        patch: {
          pid_params: {
            gain: pid.gain,
            reset: pid.reset,
            rate: pid.rate,
            alpha: pid.alpha,
            deadband: pid.deadband,
          },
          pid_structure: structure,
          ai_config: {
            engine: ai.engine,
            objective: ai.objective,
            dead_time_l: ai.dead_time_l,
            limit_min: ai.limit_min,
            limit_max: ai.limit_max,
            rl_fallback_kp: ai.rl_fallback_kp,
            rl_fallback_kd: ai.rl_fallback_kd,
            rl_learning_rate: ai.rl_learning_rate,
            rl_train_interval: ai.rl_train_interval,
          },
          out_hi_lim: limits.out_hi_lim,
          out_lo_lim: limits.out_lo_lim,
          arw_hi_lim: limits.arw_hi_lim,
          arw_lo_lim: limits.arw_lo_lim,
          pv_ftime: limits.pv_ftime,
          sp_ftime: limits.sp_ftime,
        },
      },
      { onSuccess: () => onClose() },
    );
  };

  const footer = (
    <>
      <button type="button" onClick={onClose}>
        Cancelar
      </button>
      <button type="button" onClick={handleSave} disabled={disabled || update.isPending}>
        Salvar
      </button>
    </>
  );

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={`Configurar Loop #${controllerId}`}
      footer={footer}
    >
      <Collapsible label="PID" expanded={expanded.pid} onToggle={() => toggle('pid')}>
        <NumberField
          id="cfg-gain"
          label="Gain (Kp)"
          value={pid.gain}
          onChange={(v) => setPidField('gain', v)}
          error={pidErrors.gain}
        />
        <NumberField
          id="cfg-reset"
          label="Reset (Ti)"
          value={pid.reset}
          onChange={(v) => setPidField('reset', v)}
          error={pidErrors.reset}
        />
        <NumberField
          id="cfg-rate"
          label="Rate (Td)"
          value={pid.rate}
          onChange={(v) => setPidField('rate', v)}
          error={pidErrors.rate}
        />
        <NumberField
          id="cfg-alpha"
          label="Derivative filter (alpha)"
          value={pid.alpha}
          onChange={(v) => setPidField('alpha', v)}
          error={pidErrors.alpha}
        />
        <NumberField
          id="cfg-deadband"
          label="Deadband"
          value={pid.deadband}
          onChange={(v) => setPidField('deadband', v)}
          error={pidErrors.deadband}
        />
        <div style={rowStyle}>
          <label htmlFor="cfg-structure" style={labelStyle}>
            Structure
          </label>
          <select
            id="cfg-structure"
            value={structure}
            onChange={(e) => setStructure(e.target.value as PidStructure)}
            style={{ ...fieldStyle, width: 'auto' }}
          >
            {PID_STRUCTURES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
      </Collapsible>

      <Collapsible
        label="Otimização IA"
        expanded={expanded.ai}
        onToggle={() => toggle('ai')}
      >
        <fieldset style={{ border: 'none', padding: 0, margin: 0 }}>
          <legend style={{ ...labelStyle, width: 'auto' }}>Engine</legend>
          <div style={{ display: 'flex', gap: 'var(--sp-4)' }}>
            {AI_ENGINES.map((engine: AiEngine) => (
              <label
                key={engine}
                style={{ fontSize: 'var(--text-sm)', display: 'inline-flex', gap: 'var(--sp-1)' }}
              >
                <input
                  type="radio"
                  name="ai-engine"
                  value={engine}
                  checked={ai.engine === engine}
                  onChange={() => setAi((prev) => ({ ...prev, engine }))}
                />
                {engine}
              </label>
            ))}
          </div>
        </fieldset>

        {ai.engine !== 'NONE' ? (
          <>
            <div style={rowStyle}>
              <label htmlFor="cfg-objective" style={labelStyle}>
                Objective
              </label>
              <select
                id="cfg-objective"
                value={ai.objective}
                onChange={(e) => setAi((prev) => ({ ...prev, objective: e.target.value }))}
                style={{ ...fieldStyle, width: 'auto' }}
              >
                {OBJECTIVES.map((o) => (
                  <option key={o} value={o}>
                    {o}
                  </option>
                ))}
              </select>
            </div>
            <NumberField
              id="cfg-dead-time"
              label="Dead time L"
              value={ai.dead_time_l}
              onChange={(v) => setAiNumber('dead_time_l', v)}
              error={aiErrors.dead_time_l}
            />
            <NumberField
              id="cfg-limit-min"
              label="Ki limit min"
              value={ai.limit_min}
              onChange={(v) => setAiNumber('limit_min', v)}
              error={aiErrors.limit_min}
            />
            <NumberField
              id="cfg-limit-max"
              label="Ki limit max"
              value={ai.limit_max}
              onChange={(v) => setAiNumber('limit_max', v)}
              error={aiErrors.limit_max}
            />
          </>
        ) : null}

        {ai.engine === 'RL' ? (
          <>
            <NumberField
              id="cfg-rl-fallback-kp"
              label="RL fallback Kp"
              value={ai.rl_fallback_kp}
              onChange={(v) => setAiNumber('rl_fallback_kp', v)}
              error={aiErrors.rl_fallback_kp}
            />
            <NumberField
              id="cfg-rl-fallback-kd"
              label="RL fallback Kd"
              value={ai.rl_fallback_kd}
              onChange={(v) => setAiNumber('rl_fallback_kd', v)}
              error={aiErrors.rl_fallback_kd}
            />
            <NumberField
              id="cfg-rl-learning-rate"
              label="RL learning rate"
              value={ai.rl_learning_rate}
              onChange={(v) => setAiNumber('rl_learning_rate', v)}
              error={aiErrors.rl_learning_rate}
            />
            <NumberField
              id="cfg-rl-train-interval"
              label="RL train interval"
              value={ai.rl_train_interval}
              onChange={(v) => setAiNumber('rl_train_interval', v)}
              error={aiErrors.rl_train_interval}
            />
          </>
        ) : null}
      </Collapsible>

      <Collapsible
        label="Limites"
        expanded={expanded.limits}
        onToggle={() => toggle('limits')}
      >
        <NumberField
          id="cfg-out-hi"
          label="Output high limit"
          value={limits.out_hi_lim}
          onChange={(v) => setLimitField('out_hi_lim', v)}
          error={limitsErrors.out_hi_lim}
        />
        <NumberField
          id="cfg-out-lo"
          label="Output low limit"
          value={limits.out_lo_lim}
          onChange={(v) => setLimitField('out_lo_lim', v)}
          error={limitsErrors.out_lo_lim}
        />
        <NumberField
          id="cfg-arw-hi"
          label="ARW high limit"
          value={limits.arw_hi_lim}
          onChange={(v) => setLimitField('arw_hi_lim', v)}
          error={limitsErrors.arw_hi_lim}
        />
        <NumberField
          id="cfg-arw-lo"
          label="ARW low limit"
          value={limits.arw_lo_lim}
          onChange={(v) => setLimitField('arw_lo_lim', v)}
          error={limitsErrors.arw_lo_lim}
        />
        <NumberField
          id="cfg-pv-ftime"
          label="PV filter time"
          value={limits.pv_ftime}
          onChange={(v) => setLimitField('pv_ftime', v)}
          error={limitsErrors.pv_ftime}
        />
        <NumberField
          id="cfg-sp-ftime"
          label="SP filter time"
          value={limits.sp_ftime}
          onChange={(v) => setLimitField('sp_ftime', v)}
          error={limitsErrors.sp_ftime}
        />
      </Collapsible>
      <ErrorText message={update.error?.detail} />
    </Dialog>
  );
}
