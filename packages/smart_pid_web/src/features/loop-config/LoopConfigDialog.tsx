import { useId, useState, type ReactNode } from 'react';
import { useCan } from '@/auth/useCan';
import { Button } from '@/components/Button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/Dialog';
import { Field, Input } from '@/components/Field';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/Tabs';
import { toast } from '@/components/Toast';
import type {
  AiConfigDto,
  ControllerResponse,
  OpcuaNode,
  ScaleConfigDto,
  TagBindingsDto,
} from '@/api/types';
import { cn } from '@/lib/utils';
import {
  CONTROLLER_MODES,
  EXECUTION_MODES,
  INTEGRAL_TYPE_OPTIONS,
  PID_STRUCTURES,
  SHED_OPTIONS,
  type AiEngine,
  type ControlObjective,
  type ControllerMode,
  type ExecutionMode,
  type IntegralType,
  type LimitsForm,
  type PidParamsForm,
  type ProcessSpeed,
} from './types';
import {
  useCreateControllerMutation,
  useDeleteControllerMutation,
  useUpdateControllerMutation,
} from './useCommands';
import {
  hasErrors,
  validateAiConfig,
  validateEngineeringLimits,
  validateLimits,
  validatePidParams,
} from './validation';
import {
  NODE_ID_FIELDS,
  NodeIdField,
  nodeIdLabel,
  TagPickerDialog,
  type NodeIdKey,
} from './TagPicker';
import { AiConfigSection } from './AiConfigSection';

/**
 * Tabs the DCS owns while the loop is SUPERVISORY. Smart PID only watches that
 * loop — showing tuning or shed here would invite a write that the DCS
 * immediately overrides. In DDC the PID runs here, so all of it applies.
 */
export const DDC_TABS = ['Sintonia', 'Avançado'] as const;

export interface LoopConfigDialogProps {
  controller: ControllerResponse;
  open: boolean;
  onClose(): void;
}

const SELECT_CLASS = cn(
  'numeric min-h-11 w-full rounded-control border border-rule-strong bg-surface-sunk px-3 py-2',
  'text-sm text-text outline-none focus-visible:ring-2 focus-visible:ring-focus-ring',
  'disabled:cursor-not-allowed disabled:text-text-disabled',
);

function Section({ label, children }: { label: string; children: ReactNode }) {
  return (
    <section aria-label={label} className="flex flex-col gap-2 border-t border-rule pt-3">
      <h3 className="text-2xs font-medium uppercase tracking-wider text-text-soft">{label}</h3>
      <div className="grid grid-cols-2 gap-2">{children}</div>
    </section>
  );
}

interface NumberFieldProps {
  label: string;
  value: number;
  disabled: boolean;
  error?: string;
  tooltip?: string;
  onChange(value: number): void;
}

function NumberField({ label, value, disabled, error, tooltip, onChange }: NumberFieldProps) {
  const id = useId();
  return (
    <Field label={label} htmlFor={id} error={error} tooltip={tooltip}>
      <Input
        id={id}
        type="number"
        inputMode="decimal"
        className="numeric"
        value={Number.isFinite(value) ? value : ''}
        disabled={disabled}
        invalid={error !== undefined}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    </Field>
  );
}

interface TextFieldProps {
  label: string;
  value: string;
  disabled: boolean;
  tooltip?: string;
  onChange(value: string): void;
}

function TextField({ label, value, disabled, tooltip, onChange }: TextFieldProps) {
  const id = useId();
  return (
    <Field label={label} htmlFor={id} tooltip={tooltip}>
      <Input id={id} value={value} disabled={disabled} onChange={(e) => onChange(e.target.value)} />
    </Field>
  );
}

interface SelectFieldProps {
  label: string;
  value: string;
  options: readonly string[];
  disabled: boolean;
  tooltip?: string;
  onChange(value: string): void;
}

function SelectField({ label, value, options, disabled, tooltip, onChange }: SelectFieldProps) {
  const id = useId();
  return (
    <Field label={label} htmlFor={id} tooltip={tooltip}>
      <select
        id={id}
        className={SELECT_CLASS}
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
      >
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </Field>
  );
}

interface RadioGroupFieldProps {
  legend: string;
  value: string;
  options: readonly { value: string; label: string }[];
  disabled: boolean;
  onChange(value: string): void;
}

/**
 * Two-or-three-way exclusive choice rendered as real radios rather than a
 * `<select>`: every alternative stays on screen, which is what an operator
 * needs when the wrong pick silently inverts the sign of a tuning write.
 */
function RadioGroupField({ legend, value, options, disabled, onChange }: RadioGroupFieldProps) {
  const name = useId();
  return (
    <fieldset className="col-span-2 flex flex-col gap-2">
      <legend className="text-xs font-medium text-text-soft">{legend}</legend>
      {options.map((option) => (
        <label key={option.value} className="flex items-center gap-2 text-sm text-text">
          <input
            type="radio"
            name={name}
            value={option.value}
            checked={value === option.value}
            disabled={disabled}
            className="size-4 accent-accent disabled:cursor-not-allowed"
            onChange={() => onChange(option.value)}
          />
          {option.label}
        </label>
      ))}
    </fieldset>
  );
}

interface ModeMapFieldProps {
  mode: ControllerMode;
  value: string;
  disabled: boolean;
  onChange(value: string): void;
}

/**
 * One row of the mode/value map: the integer the raw tag carries when the
 * loop is in `mode`. Blank means "not used by this loop" — 0 is a legitimate
 * code (e.g. MAN=0), so it cannot double as unset.
 */
function ModeMapField({ mode, value, disabled, onChange }: ModeMapFieldProps) {
  const id = useId();
  return (
    <Field
      label={mode}
      htmlFor={id}
      tooltip={`Valor inteiro que a tag de modo assume quando a malha está em ${mode}. Deixe em branco se este modo não é usado nesta malha.`}
    >
      <Input
        id={id}
        type="number"
        inputMode="numeric"
        step={1}
        className="numeric"
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
      />
    </Field>
  );
}

/** Type-the-tag gate. A misclick must never be able to delete a live loop. */
function DeleteConfirm({
  tag,
  open,
  pending,
  onConfirm,
  onCancel,
}: {
  tag: string;
  open: boolean;
  pending: boolean;
  onConfirm(): void;
  onCancel(): void;
}) {
  const id = useId();
  const [typed, setTyped] = useState('');

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) onCancel();
      }}
    >
      <DialogContent role="alertdialog">
        <DialogHeader>
          <DialogTitle>Excluir {tag}?</DialogTitle>
          <DialogDescription>
            A malha, seu histórico de sintonia e seus alarmes são removidos. Não há desfazer.
          </DialogDescription>
        </DialogHeader>
        <Field label={`Digite ${tag} para confirmar`} htmlFor={id}>
          <Input id={id} value={typed} onChange={(e) => setTyped(e.target.value)} />
        </Field>
        <DialogFooter>
          <Button variant="secondary" onClick={onCancel}>
            Cancelar
          </Button>
          <Button variant="destructive" disabled={typed !== tag || pending} onClick={onConfirm}>
            Excluir definitivamente
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

type Draft = {
  name: string;
  description: string;
  execution_mode: ExecutionMode;
  scan_rate_s: number;
  pid: PidParamsForm;
  limits: LimitsForm;
  pv_scale: ScaleConfigDto;
  /** CO engineering scale (`out_scale` on the wire), symmetric with `pv_scale`. */
  co_scale: ScaleConfigDto;
  bindings: Pick<
    TagBindingsDto,
    | 'node_id_pv'
    | 'node_id_sp'
    | 'node_id_co'
    | 'node_id_kp'
    | 'node_id_ti'
    | 'node_id_td'
    | 'node_id_mode_actual'
    | 'node_id_mode_target'
    | 'node_id_enabled'
  >;
  /** Raw per-field text so a blank box means "not mapped", never the digit 0. */
  modeIntMap: Record<ControllerMode, string>;
  pid_structure: string;
  integral_type: string;
  /** Blank = inherit the daemon-wide band; a number = this loop's override. */
  stability_band_pct: string;
  shed_opt: string;
  shed_time_s: number;
  max_tuning_change_pct: number;
  low_cut: number;
  ff_gain: number;
  process_speed: ProcessSpeed;
  ai: {
    engine: AiEngine;
    objective: ControlObjective;
    dead_time_l: number;
    limit_min: number;
    limit_max: number;
    sl_band_lo_pct: number | null;
    sl_band_hi_pct: number | null;
    sl_error_small_pct: number;
    sl_co_ramp_max_pct_min: number;
  };
};

function toDraft(c: ControllerResponse): Draft {
  const pid = c.pid_params ?? { gain: 1, reset: 10, rate: 0, alpha: 0.125, deadband: 0 };
  const pv = c.pv_scale ?? { eu_min: 0, eu_max: 100, unit: '%' };
  const co = c.out_scale ?? { eu_min: 0, eu_max: 100, unit: '%' };
  const tags = c.tag_bindings;
  const ai = c.ai_config as Partial<AiConfigDto> | undefined;
  const modeIntMap = {} as Record<ControllerMode, string>;
  for (const mode of CONTROLLER_MODES) {
    const code = tags?.mode_int_map?.[mode];
    modeIntMap[mode] = code === undefined ? '' : String(code);
  }
  return {
    name: c.name,
    description: c.description ?? '',
    execution_mode: (c.execution_mode as ExecutionMode | undefined) ?? 'SUPERVISORY',
    scan_rate_s: c.scan_rate_s ?? 1,
    pid: { ...pid },
    limits: {
      out_hi_lim: c.out_hi_lim ?? 100,
      out_lo_lim: c.out_lo_lim ?? 0,
      arw_hi_lim: c.arw_hi_lim ?? 100,
      arw_lo_lim: c.arw_lo_lim ?? 0,
      sp_hi_lim: c.sp_hi_lim ?? 100,
      sp_lo_lim: c.sp_lo_lim ?? 0,
      pv_ftime: c.pv_ftime ?? 0,
      sp_ftime: c.sp_ftime ?? 0,
      sp_rate_up: c.sp_rate_up ?? 0,
      sp_rate_dn: c.sp_rate_dn ?? 0,
    },
    // A legacy blank unit coerces to `%`: the dialog now always writes a unit,
    // and a blank box invites saving one back.
    pv_scale: { ...pv, unit: pv.unit || '%' },
    co_scale: { ...co, unit: co.unit || '%' },
    bindings: {
      node_id_pv: tags?.node_id_pv ?? '',
      node_id_sp: tags?.node_id_sp ?? '',
      node_id_co: tags?.node_id_co ?? '',
      node_id_kp: tags?.node_id_kp ?? '',
      node_id_ti: tags?.node_id_ti ?? '',
      node_id_td: tags?.node_id_td ?? '',
      node_id_mode_actual: tags?.node_id_mode_actual ?? '',
      node_id_mode_target: tags?.node_id_mode_target ?? '',
      node_id_enabled: tags?.node_id_enabled ?? '',
    },
    modeIntMap,
    pid_structure: c.pid_structure ?? 'ISA',
    integral_type: c.integral_type ?? 'TIME_TI',
    stability_band_pct:
      c.stability_band_pct === null || c.stability_band_pct === undefined
        ? ''
        : String(c.stability_band_pct),
    shed_opt: c.shed_opt ?? 'MAN',
    shed_time_s: c.shed_time_s ?? 10,
    max_tuning_change_pct: c.max_tuning_change_pct ?? 10,
    low_cut: c.low_cut ?? 0,
    ff_gain: c.ff_gain ?? 1,
    process_speed: (c.process_speed as ProcessSpeed | undefined) ?? 'MEDIUM',
    ai: {
      engine: (ai?.engine as AiEngine | undefined) ?? 'NONE',
      objective: (ai?.objective as ControlObjective | undefined) ?? 'DISTURBANCE_REJECTION',
      dead_time_l: ai?.dead_time_l ?? 1,
      limit_min: ai?.limit_min ?? 1,
      limit_max: ai?.limit_max ?? 10,
      sl_band_lo_pct: ai?.sl_band_lo_pct ?? null,
      sl_band_hi_pct: ai?.sl_band_hi_pct ?? null,
      sl_error_small_pct: ai?.sl_error_small_pct ?? 5,
      sl_co_ramp_max_pct_min: ai?.sl_co_ramp_max_pct_min ?? 10,
    },
  };
}

/**
 * Controller configuration (§6.10). Identification, execution mode, scan rate
 * and the OPC-UA bindings are always editable; everything the DCS owns appears
 * only for a DDC loop. `controllers.manage` gates the writes — a user still
 * gets the read-only view, because "you cannot see it" is not the same promise
 * as "you cannot change it", and the backend enforces the second one.
 */
export function LoopConfigDialog({ controller, open, onClose }: LoopConfigDialogProps) {
  const canManage = useCan('controllers.manage');
  const update = useUpdateControllerMutation();
  const remove = useDeleteControllerMutation();
  const stabilityBandId = useId();

  const [draft, setDraft] = useState<Draft>(() => toDraft(controller));
  const [confirmDelete, setConfirmDelete] = useState(false);
  /** Which binding the open tag picker writes to; `null` = picker closed. */
  const [picking, setPicking] = useState<NodeIdKey | null>(null);

  const readOnly = !canManage;
  const isDdc = draft.execution_mode === 'DDC';
  const pidErrors = isDdc ? validatePidParams(draft.pid) : {};
  const limitErrors = isDdc ? validateLimits(draft.limits) : {};
  // Never DDC-gated: the PV/CO scales and the SP band are display and
  // operator-entry contracts, and a SUPERVISORY loop needs both.
  const scaleErrors = validateEngineeringLimits({
    pv_eu_min: draft.pv_scale.eu_min,
    pv_eu_max: draft.pv_scale.eu_max,
    co_eu_min: draft.co_scale.eu_min,
    co_eu_max: draft.co_scale.eu_max,
    sp_lo_lim: draft.limits.sp_lo_lim,
    sp_hi_lim: draft.limits.sp_hi_lim,
  });
  const aiErrors = validateAiConfig({
    engine: draft.ai.engine,
    objective: draft.ai.objective,
    dead_time_l: draft.ai.dead_time_l,
    limit_min: draft.ai.limit_min,
    limit_max: draft.ai.limit_max,
    sl_band_lo_pct: draft.ai.sl_band_lo_pct,
    sl_band_hi_pct: draft.ai.sl_band_hi_pct,
    sl_error_small_pct: draft.ai.sl_error_small_pct,
    sl_co_ramp_max_pct_min: draft.ai.sl_co_ramp_max_pct_min,
  });
  const blocked =
    hasErrors(pidErrors) ||
    hasErrors(limitErrors) ||
    hasErrors(scaleErrors) ||
    hasErrors(aiErrors) ||
    draft.name.trim() === '';

  const patchPid = (key: keyof PidParamsForm, value: number): void =>
    setDraft((p) => ({ ...p, pid: { ...p.pid, [key]: value } }));
  const patchLimit = (key: keyof LimitsForm, value: number): void =>
    setDraft((p) => ({ ...p, limits: { ...p.limits, [key]: value } }));
  const patchBinding = (key: NodeIdKey, value: string): void =>
    setDraft((p) => ({ ...p, bindings: { ...p.bindings, [key]: value } }));
  const patchModeMap = (mode: ControllerMode, value: string): void =>
    setDraft((p) => ({ ...p, modeIntMap: { ...p.modeIntMap, [mode]: value } }));

  /**
   * The picker never decides the target — `picking` is the field whose own
   * button opened it, so a browse started from CO can only ever land in CO.
   */
  const bindPickedNode = (node: OpcuaNode): void => {
    if (picking === null) return;
    patchBinding(picking, node.node_id);
    setPicking(null);
  };

  /** Blank fields are omitted, never sent as the digit 0 (see `ModeMapField`). */
  const modeIntMapPayload = (): Record<string, number> => {
    const result: Record<string, number> = {};
    for (const mode of CONTROLLER_MODES) {
      const raw = draft.modeIntMap[mode].trim();
      if (raw === '') continue;
      const n = Number(raw);
      if (Number.isFinite(n)) result[mode] = n;
    }
    return result;
  };

  /**
   * Blank box = "inherit the daemon-wide band", sent as null. The backend
   * PUT ignores nulls, so a loop that already carries an override keeps it
   * until a number replaces it — clearing one is a backend concern, not a
   * silent client-side reset.
   */
  const stabilityBandPayload = (): number | null => {
    const raw = draft.stability_band_pct.trim();
    if (raw === '') return null;
    const n = Number(raw);
    return Number.isFinite(n) ? n : null;
  };

  const save = (): void => {
    // sp_* ride the always-sent block below; the DDC spread must not restate
    // them or the two copies could disagree.
    const { sp_hi_lim, sp_lo_lim, ...ddcLimits } = draft.limits;
    update.mutate(
      {
        id: controller.id,
        patch: {
          name: draft.name,
          description: draft.description,
          execution_mode: draft.execution_mode,
          scan_rate_s: draft.scan_rate_s,
          tag_bindings: {
            ...controller.tag_bindings,
            ...draft.bindings,
            mode_int_map: modeIntMapPayload(),
          },
          process_speed: draft.process_speed,
          // Not DDC-gated: `integral_type` decides the SIGN of every integral
          // adjustment the optimizer computes, and it rides the ACTION.AI
          // write-back that only happens for a SUPERVISORY loop. Hiding it
          // there would strand the field exactly where it matters most.
          integral_type: draft.integral_type,
          stability_band_pct: stabilityBandPayload(),
          // Engineering scales and the SP band persist in every execution
          // mode — the Limites tab is not DDC-gated.
          pv_scale: draft.pv_scale,
          out_scale: draft.co_scale,
          sp_hi_lim,
          sp_lo_lim,
          ai_config: {
            engine: draft.ai.engine,
            objective: draft.ai.objective,
            dead_time_l: draft.ai.dead_time_l,
            limit_min: draft.ai.limit_min,
            limit_max: draft.ai.limit_max,
            sl_band_lo_pct: draft.ai.sl_band_lo_pct,
            sl_band_hi_pct: draft.ai.sl_band_hi_pct,
            sl_error_small_pct: draft.ai.sl_error_small_pct,
            sl_co_ramp_max_pct_min: draft.ai.sl_co_ramp_max_pct_min,
          },
          ...(isDdc
            ? {
                pid_params: draft.pid,
                pid_structure: draft.pid_structure,
                shed_opt: draft.shed_opt,
                shed_time_s: draft.shed_time_s,
                max_tuning_change_pct: draft.max_tuning_change_pct,
                low_cut: draft.low_cut,
                ff_gain: draft.ff_gain,
                ...ddcLimits,
              }
            : {}),
        },
      },
      { onSuccess: () => onClose() },
    );
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) onClose();
      }}
    >
      <DialogContent className="max-h-[85vh] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Configurar {controller.name}</DialogTitle>
          <DialogDescription>
            Malha #{controller.id}. Campos de sintonia aparecem apenas em DDC.
          </DialogDescription>
        </DialogHeader>

        <Tabs defaultValue="geral">
          <TabsList aria-label="Seções da configuração">
            <TabsTrigger value="geral">Geral</TabsTrigger>
            <TabsTrigger value="tags">Tags</TabsTrigger>
            <TabsTrigger value="limites">Limites</TabsTrigger>
            {/* The execution-mode select lives on Geral, the default tab, so
                switching to SUPERVISORY can never pull the tab out from under
                the operator who is standing on it. */}
            {isDdc ? <TabsTrigger value="sintonia">Sintonia</TabsTrigger> : null}
            {isDdc ? <TabsTrigger value="avancado">Avançado</TabsTrigger> : null}
            <TabsTrigger value="ia">IA</TabsTrigger>
          </TabsList>

          <TabsContent value="geral">
            <div className="grid grid-cols-2 gap-2">
              <TextField
                label="Nome"
                tooltip="Nome de identificação da malha (tag), exibido nos cards e no faceplate."
                value={draft.name}
                disabled={readOnly}
                onChange={(v) => setDraft((p) => ({ ...p, name: v }))}
              />
              <TextField
                label="Descrição"
                tooltip="Texto livre descrevendo o processo controlado por esta malha."
                value={draft.description}
                disabled={readOnly}
                onChange={(v) => setDraft((p) => ({ ...p, description: v }))}
              />
              <SelectField
                label="Modo de execução"
                tooltip="SUPERVISORY: o PID roda no CLP/DCS e o SmartPID só monitora. DDC: o PID roda dentro do SmartPID, que escreve a saída diretamente."
                value={draft.execution_mode}
                options={EXECUTION_MODES}
                disabled={readOnly}
                onChange={(v) => setDraft((p) => ({ ...p, execution_mode: v as ExecutionMode }))}
              />
              <NumberField
                label="Taxa de varredura (s)"
                tooltip="Intervalo, em segundos, entre execuções do algoritmo PID quando a malha está em DDC."
                value={draft.scan_rate_s}
                disabled={readOnly}
                onChange={(v) => setDraft((p) => ({ ...p, scan_rate_s: v }))}
              />
            </div>
          </TabsContent>

          <TabsContent value="tags" className="flex flex-col gap-3">
            <div className="grid grid-cols-2 gap-2">
              {NODE_ID_FIELDS.map(({ key, label, tooltip }) => (
                <NodeIdField
                  key={key}
                  label={label}
                  tooltip={tooltip}
                  value={draft.bindings[key]}
                  disabled={readOnly}
                  onChange={(v) => patchBinding(key, v)}
                  onBrowse={canManage ? () => setPicking(key) : undefined}
                />
              ))}
            </div>

            <Section label="Mapeamento de Modo">
              {CONTROLLER_MODES.map((mode) => (
                <ModeMapField
                  key={mode}
                  mode={mode}
                  value={draft.modeIntMap[mode]}
                  disabled={readOnly}
                  onChange={(v) => patchModeMap(mode, v)}
                />
              ))}
            </Section>
          </TabsContent>

          {/* Not DDC-gated: these are the display and operator-entry ranges.
              A SUPERVISORY loop still draws bars and still takes a setpoint. */}
          <TabsContent value="limites" className="flex flex-col gap-3">
            <Section label="PV">
              <NumberField
                label="PV mín."
                tooltip="Limite inferior da escala de engenharia da PV, usado para converter o sinal bruto e desenhar a barra e o gráfico."
                value={draft.pv_scale.eu_min}
                disabled={readOnly}
                error={scaleErrors.pv_eu_min}
                onChange={(v) => setDraft((p) => ({ ...p, pv_scale: { ...p.pv_scale, eu_min: v } }))}
              />
              <NumberField
                label="PV máx."
                tooltip="Limite superior da escala de engenharia da PV, usado para converter o sinal bruto e desenhar a barra e o gráfico."
                value={draft.pv_scale.eu_max}
                disabled={readOnly}
                error={scaleErrors.pv_eu_max}
                onChange={(v) => setDraft((p) => ({ ...p, pv_scale: { ...p.pv_scale, eu_max: v } }))}
              />
              <TextField
                label="Unidade PV"
                tooltip="Unidade de engenharia exibida junto ao valor da PV (ex.: °C, bar, m³/h)."
                value={draft.pv_scale.unit}
                disabled={readOnly}
                onChange={(v) => setDraft((p) => ({ ...p, pv_scale: { ...p.pv_scale, unit: v } }))}
              />
            </Section>

            <Section label="SP">
              <NumberField
                label="SP mín."
                tooltip="Limite inferior permitido para o setpoint digitado pelo operador."
                value={draft.limits.sp_lo_lim}
                disabled={readOnly}
                error={scaleErrors.sp_lo_lim}
                onChange={(v) => patchLimit('sp_lo_lim', v)}
              />
              <NumberField
                label="SP máx."
                tooltip="Limite superior permitido para o setpoint digitado pelo operador."
                value={draft.limits.sp_hi_lim}
                disabled={readOnly}
                error={scaleErrors.sp_hi_lim}
                onChange={(v) => patchLimit('sp_hi_lim', v)}
              />
              {/* The SP shares the PV's engineering scale, so it cannot carry a
                  unit of its own — shown read-only rather than hidden, because
                  "which unit is this box in?" is the operator's first question. */}
              <TextField
                label="Unidade SP"
                tooltip="Herdada da unidade da PV — SP compartilha a escala da PV."
                value={draft.pv_scale.unit}
                disabled
                onChange={() => undefined}
              />
            </Section>

            <Section label="CO">
              <NumberField
                label="CO mín."
                tooltip="Limite inferior da escala de engenharia do CO, usado para exibir a saída de controle."
                value={draft.co_scale.eu_min}
                disabled={readOnly}
                error={scaleErrors.co_eu_min}
                onChange={(v) => setDraft((p) => ({ ...p, co_scale: { ...p.co_scale, eu_min: v } }))}
              />
              <NumberField
                label="CO máx."
                tooltip="Limite superior da escala de engenharia do CO, usado para exibir a saída de controle."
                value={draft.co_scale.eu_max}
                disabled={readOnly}
                error={scaleErrors.co_eu_max}
                onChange={(v) => setDraft((p) => ({ ...p, co_scale: { ...p.co_scale, eu_max: v } }))}
              />
              <TextField
                label="Unidade CO"
                tooltip="Unidade de engenharia exibida junto ao valor do CO (ex.: %, kPa)."
                value={draft.co_scale.unit}
                disabled={readOnly}
                onChange={(v) => setDraft((p) => ({ ...p, co_scale: { ...p.co_scale, unit: v } }))}
              />
            </Section>
          </TabsContent>

          {isDdc ? (
            <TabsContent value="sintonia" className="flex flex-col gap-3">
              <Section label="PID Tuning">
                <NumberField
                  label="Ganho (Kp)"
                  tooltip="Ganho proporcional do controlador PID."
                  value={draft.pid.gain}
                  disabled={readOnly}
                  error={pidErrors.gain}
                  onChange={(v) => patchPid('gain', v)}
                />
                <NumberField
                  label="Reset (Ti)"
                  tooltip="Tempo integral (reset), em segundos por repetição — quanto menor, mais rápida a ação integral."
                  value={draft.pid.reset}
                  disabled={readOnly}
                  error={pidErrors.reset}
                  onChange={(v) => patchPid('reset', v)}
                />
                <NumberField
                  label="Rate (Td)"
                  tooltip="Tempo derivativo — antecipa a tendência do erro. Zero desativa a ação derivativa (controlador PI)."
                  value={draft.pid.rate}
                  disabled={readOnly}
                  error={pidErrors.rate}
                  onChange={(v) => patchPid('rate', v)}
                />
                <NumberField
                  label="Filtro derivativo (alpha)"
                  tooltip="Fator de filtro do termo derivativo (0–1), reduz ruído amplificado pela derivada."
                  value={draft.pid.alpha}
                  disabled={readOnly}
                  error={pidErrors.alpha}
                  onChange={(v) => patchPid('alpha', v)}
                />
                <NumberField
                  label="Banda morta"
                  tooltip="Faixa de erro, em unidades de engenharia, dentro da qual o controlador não atua."
                  value={draft.pid.deadband}
                  disabled={readOnly}
                  error={pidErrors.deadband}
                  onChange={(v) => patchPid('deadband', v)}
                />
              </Section>

              <Section label="PID Structure">
                <SelectField
                  label="Estrutura"
                  tooltip="Forma matemática do algoritmo PID: ISA (interativa), Paralela ou Série."
                  value={draft.pid_structure}
                  options={PID_STRUCTURES}
                  disabled={readOnly}
                  onChange={(v) => setDraft((p) => ({ ...p, pid_structure: v }))}
                />
              </Section>

              {/* Actuation clamps, not the CO display scale (that is the CO
                  section on Limites): these bound what the DDC PID may write. */}
              <Section label="Saída & ARW">
                <NumberField
                  label="Saída mín."
                  tooltip="Limite inferior permitido para a saída de controle (CO), em %."
                  value={draft.limits.out_lo_lim}
                  disabled={readOnly}
                  error={limitErrors.out_lo_lim}
                  onChange={(v) => patchLimit('out_lo_lim', v)}
                />
                <NumberField
                  label="Saída máx."
                  tooltip="Limite superior permitido para a saída de controle (CO), em %."
                  value={draft.limits.out_hi_lim}
                  disabled={readOnly}
                  error={limitErrors.out_hi_lim}
                  onChange={(v) => patchLimit('out_hi_lim', v)}
                />
                <NumberField
                  label="ARW mín."
                  tooltip="Limite inferior de anti-windup do termo integral — impede que o integrador acumule além da faixa útil da saída."
                  value={draft.limits.arw_lo_lim}
                  disabled={readOnly}
                  error={limitErrors.arw_lo_lim}
                  onChange={(v) => patchLimit('arw_lo_lim', v)}
                />
                <NumberField
                  label="ARW máx."
                  tooltip="Limite superior de anti-windup do termo integral — impede que o integrador acumule além da faixa útil da saída."
                  value={draft.limits.arw_hi_lim}
                  disabled={readOnly}
                  error={limitErrors.arw_hi_lim}
                  onChange={(v) => patchLimit('arw_hi_lim', v)}
                />
              </Section>
            </TabsContent>
          ) : null}

          {isDdc ? (
            <TabsContent value="avancado" className="flex flex-col gap-3">
              <Section label="Filters & IO">
                <NumberField
                  label="Filtro PV (s)"
                  tooltip="Constante de tempo do filtro de primeira ordem aplicado à leitura da PV."
                  value={draft.limits.pv_ftime}
                  disabled={readOnly}
                  error={limitErrors.pv_ftime}
                  onChange={(v) => patchLimit('pv_ftime', v)}
                />
                <NumberField
                  label="Filtro SP (s)"
                  tooltip="Constante de tempo do filtro de primeira ordem aplicado ao setpoint."
                  value={draft.limits.sp_ftime}
                  disabled={readOnly}
                  error={limitErrors.sp_ftime}
                  onChange={(v) => patchLimit('sp_ftime', v)}
                />
                <NumberField
                  label="Rampa SP subida"
                  tooltip="Taxa máxima de variação do setpoint por segundo, ao subir, antes de chegar ao valor digitado."
                  value={draft.limits.sp_rate_up}
                  disabled={readOnly}
                  error={limitErrors.sp_rate_up}
                  onChange={(v) => patchLimit('sp_rate_up', v)}
                />
                <NumberField
                  label="Rampa SP descida"
                  tooltip="Taxa máxima de variação do setpoint por segundo, ao descer, antes de chegar ao valor digitado."
                  value={draft.limits.sp_rate_dn}
                  disabled={readOnly}
                  error={limitErrors.sp_rate_dn}
                  onChange={(v) => patchLimit('sp_rate_dn', v)}
                />
                <NumberField
                  label="Corte baixo"
                  tooltip="Valor de PV abaixo do qual o sinal é tratado como corte de baixa escala (low cut)."
                  value={draft.low_cut}
                  disabled={readOnly}
                  onChange={(v) => setDraft((p) => ({ ...p, low_cut: v }))}
                />
                <NumberField
                  label="Ganho FF"
                  tooltip="Ganho aplicado ao sinal de feedforward somado à saída do PID."
                  value={draft.ff_gain}
                  disabled={readOnly}
                  onChange={(v) => setDraft((p) => ({ ...p, ff_gain: v }))}
                />
              </Section>

              <Section label="Shed & Safety">
                <SelectField
                  label="Modo de shed"
                  tooltip="Modo para o qual a malha muda automaticamente quando o link de I/O é perdido."
                  value={draft.shed_opt}
                  options={SHED_OPTIONS}
                  disabled={readOnly}
                  onChange={(v) => setDraft((p) => ({ ...p, shed_opt: v }))}
                />
                <NumberField
                  label="Tempo de shed (s)"
                  tooltip="Tempo, em segundos, sem comunicação de I/O antes de aplicar o modo de shed."
                  value={draft.shed_time_s}
                  disabled={readOnly}
                  onChange={(v) => setDraft((p) => ({ ...p, shed_time_s: v }))}
                />
                <NumberField
                  label="Mudança máx. de sintonia (%)"
                  tooltip="Variação percentual máxima permitida em um único ajuste de sintonia enviado pela IA."
                  value={draft.max_tuning_change_pct}
                  disabled={readOnly}
                  onChange={(v) => setDraft((p) => ({ ...p, max_tuning_change_pct: v }))}
                />
              </Section>
            </TabsContent>
          ) : null}

          {/* Not DDC-gated: these fields are what SETS the optimizer state, and
              the optimizer runs for a SUPERVISORY loop too. `integral_type` in
              particular decides the sign of every integral adjustment and rides
              the ACTION.AI write-back that only a SUPERVISORY loop performs. */}
          <TabsContent value="ia" className="flex flex-col gap-3">
            <Section label="Integral Type">
              <RadioGroupField
                legend="Tipo integral"
                value={draft.integral_type}
                options={INTEGRAL_TYPE_OPTIONS}
                disabled={readOnly}
                onChange={(v) => setDraft((p) => ({ ...p, integral_type: v }))}
              />
            </Section>

            <Section label="AI Optimization">
              <AiConfigSection
                value={{
                  ...draft.ai,
                  speed: draft.process_speed,
                  integral_type: draft.integral_type as IntegralType,
                }}
                errors={aiErrors}
                disabled={readOnly}
                onChange={(patch) =>
                  setDraft((p) => {
                    const { speed, ...ai } = patch;
                    return {
                      ...p,
                      process_speed: speed ?? p.process_speed,
                      ai: { ...p.ai, ...ai },
                    };
                  })
                }
              />
            </Section>

            <Section label="Optimizer Guardrail">
              <Field
                label="Banda de estabilidade (% do SP)"
                htmlFor={stabilityBandId}
                tooltip="Enquanto |PV - SP| ficar dentro desta faixa a malha é considerada em regime e o otimizador não altera Ki/Ti. Em branco, usa o padrão global do daemon (2%)."
              >
                <Input
                  id={stabilityBandId}
                  type="number"
                  inputMode="decimal"
                  step={0.1}
                  min={0}
                  className="numeric"
                  placeholder="global"
                  value={draft.stability_band_pct}
                  disabled={readOnly}
                  onChange={(e) => setDraft((p) => ({ ...p, stability_band_pct: e.target.value }))}
                />
              </Field>
            </Section>
          </TabsContent>
        </Tabs>

        {update.error !== null ? (
          <p role="alert" className="text-sm font-medium text-alarm-crit">
            {update.error.detail}
          </p>
        ) : null}

        <DialogFooter>
          {canManage ? (
            <Button
              variant="destructive"
              className="mr-auto"
              disabled={remove.isPending}
              onClick={() => setConfirmDelete(true)}
            >
              Excluir
            </Button>
          ) : null}
          <Button variant="secondary" onClick={onClose}>
            Cancelar
          </Button>
          {canManage ? (
            <Button variant="primary" disabled={blocked || update.isPending} onClick={save}>
              Salvar
            </Button>
          ) : null}
        </DialogFooter>
      </DialogContent>

      {canManage ? (
        <TagPickerDialog
          field={nodeIdLabel(picking)}
          onSelect={bindPickedNode}
          onClose={() => setPicking(null)}
        />
      ) : null}

      {canManage ? (
        <DeleteConfirm
          tag={controller.name}
          open={confirmDelete}
          pending={remove.isPending}
          onCancel={() => setConfirmDelete(false)}
          onConfirm={() =>
            remove.mutate(controller.id, {
              onSuccess: () => {
                setConfirmDelete(false);
                toast({ title: 'Malha excluída', description: controller.name });
                onClose();
              },
            })
          }
        />
      ) : null}
    </Dialog>
  );
}

export interface NewLoopDialogProps {
  open: boolean;
  onClose(): void;
  onCreated?(controller: ControllerResponse): void;
}

/**
 * Create is deliberately thin: `ControllerCreate` defaults every field but the
 * name, so the operator names the loop here and tunes it in the dialog above
 * rather than facing forty inputs before the row even exists.
 */
export function NewLoopDialog({ open, onClose, onCreated }: NewLoopDialogProps) {
  const create = useCreateControllerMutation();
  const nameId = useId();
  const descriptionId = useId();
  const modeId = useId();

  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [executionMode, setExecutionMode] = useState<ExecutionMode>('SUPERVISORY');

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) onClose();
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Nova malha</DialogTitle>
          <DialogDescription>
            O restante da configuração fica disponível em Configurar na malha criada.
          </DialogDescription>
        </DialogHeader>

        <Field label="Nome" htmlFor={nameId}>
          <Input id={nameId} value={name} onChange={(e) => setName(e.target.value)} />
        </Field>
        <Field label="Descrição" htmlFor={descriptionId}>
          <Input
            id={descriptionId}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </Field>
        <Field label="Modo de execução" htmlFor={modeId}>
          <select
            id={modeId}
            className={SELECT_CLASS}
            value={executionMode}
            onChange={(e) => setExecutionMode(e.target.value as ExecutionMode)}
          >
            {EXECUTION_MODES.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </Field>

        {create.error !== null ? (
          <p role="alert" className="text-sm font-medium text-alarm-crit">
            {create.error.detail}
          </p>
        ) : null}

        <DialogFooter>
          <Button variant="secondary" onClick={onClose}>
            Cancelar
          </Button>
          <Button
            variant="primary"
            disabled={name.trim() === '' || create.isPending}
            onClick={() =>
              create.mutate(
                { name: name.trim(), description, execution_mode: executionMode },
                {
                  onSuccess: (controller) => {
                    toast({ title: 'Malha criada', description: controller.name });
                    onCreated?.(controller);
                    onClose();
                  },
                },
              )
            }
          >
            Criar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
