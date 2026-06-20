import { useState, type ReactNode } from 'react';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/dialog';
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

/**
 * Flat ISA-101 loop-config form bodies. Inline-style blocks migrated to token
 * utilities (Task 8.2). The dialog shell is the shadcn Dialog (Task 8.1). The
 * NONE/FUZZY/RL engine radios stay NATIVE (`getByLabelText('RL')` is frozen) and
 * the Structure/Objective selectors stay native `<select>`s, all restyled flat.
 * Numeric inputs carry `numeric` (tabular numerals, §6). Font sizes stay inline as
 * `var(--text-*)` (no Tailwind type-scale mapping in the `@theme inline` bridge).
 */
const LABEL = 'w-36 flex-shrink-0 text-text-secondary';

const FIELD =
  'numeric w-32 bg-field-bg text-text border border-border rounded-control px-2 py-1 ' +
  'focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-[var(--focus-ring)] ' +
  'aria-[invalid=true]:border-border-strong';

const SELECT =
  'numeric w-auto bg-field-bg text-text border border-border rounded-control px-2 py-1 cursor-pointer ' +
  'focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-[var(--focus-ring)]';

const SECTION_HEADER =
  'w-full cursor-pointer bg-transparent border-0 border-b border-border text-left text-text py-2 font-semibold ' +
  'focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-[var(--focus-ring)]';

const FOOTER_BUTTON =
  'cursor-pointer bg-surface-container-high text-text border border-border rounded-control px-3 py-1 ' +
  'transition-colors duration-fast hover:bg-surface-container active:bg-field-bg ' +
  'focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-[var(--focus-ring)] ' +
  'disabled:text-text-disabled disabled:cursor-not-allowed disabled:hover:bg-surface-container-high';

function ErrorText({ message }: { message: string | null | undefined }) {
  if (!message) return null;
  return (
    <span role="alert" className="text-alarm-warning" style={{ fontSize: 'var(--text-2xs)' }}>
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
    <div className="flex flex-col gap-1">
      <div className="flex items-center gap-3">
        <label htmlFor={id} className={LABEL} style={{ fontSize: 'var(--text-xs)' }}>
          {label}
        </label>
        <input
          id={id}
          className={FIELD}
          type="number"
          inputMode="decimal"
          value={Number.isNaN(value) ? '' : value}
          onChange={(e) => onChange(Number(e.target.value))}
          style={{ fontSize: 'var(--text-sm)' }}
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
    <section className="flex flex-col gap-2">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={expanded}
        className={SECTION_HEADER}
        style={{ fontSize: 'var(--text-base)' }}
      >
        {label}
      </button>
      {expanded ? <div className="flex flex-col gap-2">{children}</div> : null}
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

  return (
    <Dialog open={open} onOpenChange={(next) => { if (!next) onClose(); }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Configurar Loop #{controllerId}</DialogTitle>
        </DialogHeader>
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
        <div className="flex items-center gap-3">
          <label htmlFor="cfg-structure" className={LABEL} style={{ fontSize: 'var(--text-xs)' }}>
            Structure
          </label>
          <select
            id="cfg-structure"
            value={structure}
            onChange={(e) => setStructure(e.target.value as PidStructure)}
            className={SELECT}
            style={{ fontSize: 'var(--text-sm)' }}
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
        <fieldset className="border-0 m-0 p-0">
          <legend className="text-text-secondary" style={{ fontSize: 'var(--text-xs)' }}>
            Engine
          </legend>
          <div className="flex gap-4">
            {AI_ENGINES.map((engine: AiEngine) => (
              <label
                key={engine}
                className="inline-flex items-center gap-1"
                style={{ fontSize: 'var(--text-sm)' }}
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
            <div className="flex items-center gap-3">
              <label htmlFor="cfg-objective" className={LABEL} style={{ fontSize: 'var(--text-xs)' }}>
                Objective
              </label>
              <select
                id="cfg-objective"
                value={ai.objective}
                onChange={(e) => setAi((prev) => ({ ...prev, objective: e.target.value }))}
                className={SELECT}
                style={{ fontSize: 'var(--text-sm)' }}
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
        <DialogFooter>
          <button type="button" onClick={onClose} className={FOOTER_BUTTON}>
            Cancelar
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={disabled || update.isPending}
            className={FOOTER_BUTTON}
          >
            Salvar
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
