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
import { toast } from '@/components/Toast';
import type {
  ControllerResponse,
  OpcuaNode,
  ScaleConfigDto,
  TagBindingsDto,
} from '@/api/types';
import { cn } from '@/lib/utils';
import {
  EXECUTION_MODES,
  INTEGRAL_TYPES,
  PID_STRUCTURES,
  SHED_OPTIONS,
  type ExecutionMode,
  type LimitsForm,
  type PidParamsForm,
} from './types';
import {
  useCreateControllerMutation,
  useDeleteControllerMutation,
  useUpdateControllerMutation,
} from './useCommands';
import { hasErrors, validateLimits, validatePidParams } from './validation';
import {
  NODE_ID_FIELDS,
  NodeIdField,
  nodeIdLabel,
  TagPickerDialog,
  type NodeIdKey,
} from './TagPicker';

/**
 * Sections the DCS owns while the loop is SUPERVISORY. Smart PID only watches
 * that loop — showing tuning, scaling or shed here would invite a write that
 * the DCS immediately overrides. In DDC the PID runs here, so all of it applies.
 */
export const DDC_SECTIONS = [
  'PID Tuning',
  'Scaling & Limits',
  'Filters & IO',
  'Shed & Safety',
  'PID Structure',
  'Integral Type',
] as const;

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
  onChange(value: number): void;
}

function NumberField({ label, value, disabled, error, onChange }: NumberFieldProps) {
  const id = useId();
  return (
    <Field label={label} htmlFor={id} error={error}>
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
  onChange(value: string): void;
}

function TextField({ label, value, disabled, onChange }: TextFieldProps) {
  const id = useId();
  return (
    <Field label={label} htmlFor={id}>
      <Input id={id} value={value} disabled={disabled} onChange={(e) => onChange(e.target.value)} />
    </Field>
  );
}

interface SelectFieldProps {
  label: string;
  value: string;
  options: readonly string[];
  disabled: boolean;
  onChange(value: string): void;
}

function SelectField({ label, value, options, disabled, onChange }: SelectFieldProps) {
  const id = useId();
  return (
    <Field label={label} htmlFor={id}>
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
  bindings: Pick<TagBindingsDto, 'node_id_pv' | 'node_id_sp' | 'node_id_co' | 'node_id_ti'>;
  pid_structure: string;
  integral_type: string;
  shed_opt: string;
  shed_time_s: number;
  max_tuning_change_pct: number;
  low_cut: number;
  ff_gain: number;
};

function toDraft(c: ControllerResponse): Draft {
  const pid = c.pid_params ?? { gain: 1, reset: 10, rate: 0, alpha: 0.125, deadband: 0 };
  const pv = c.pv_scale ?? { eu_min: 0, eu_max: 100, unit: '' };
  const tags = c.tag_bindings;
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
    pv_scale: { ...pv },
    bindings: {
      node_id_pv: tags?.node_id_pv ?? '',
      node_id_sp: tags?.node_id_sp ?? '',
      node_id_co: tags?.node_id_co ?? '',
      node_id_ti: tags?.node_id_ti ?? '',
    },
    pid_structure: c.pid_structure ?? 'ISA',
    integral_type: c.integral_type ?? 'TIME_TI',
    shed_opt: c.shed_opt ?? 'MAN',
    shed_time_s: c.shed_time_s ?? 10,
    max_tuning_change_pct: c.max_tuning_change_pct ?? 10,
    low_cut: c.low_cut ?? 0,
    ff_gain: c.ff_gain ?? 1,
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

  const [draft, setDraft] = useState<Draft>(() => toDraft(controller));
  const [confirmDelete, setConfirmDelete] = useState(false);
  /** Which binding the open tag picker writes to; `null` = picker closed. */
  const [picking, setPicking] = useState<NodeIdKey | null>(null);

  const readOnly = !canManage;
  const isDdc = draft.execution_mode === 'DDC';
  const pidErrors = isDdc ? validatePidParams(draft.pid) : {};
  const limitErrors = isDdc ? validateLimits(draft.limits) : {};
  const blocked = hasErrors(pidErrors) || hasErrors(limitErrors) || draft.name.trim() === '';

  const patchPid = (key: keyof PidParamsForm, value: number): void =>
    setDraft((p) => ({ ...p, pid: { ...p.pid, [key]: value } }));
  const patchLimit = (key: keyof LimitsForm, value: number): void =>
    setDraft((p) => ({ ...p, limits: { ...p.limits, [key]: value } }));
  const patchBinding = (key: NodeIdKey, value: string): void =>
    setDraft((p) => ({ ...p, bindings: { ...p.bindings, [key]: value } }));

  /**
   * The picker never decides the target — `picking` is the field whose own
   * button opened it, so a browse started from CO can only ever land in CO.
   */
  const bindPickedNode = (node: OpcuaNode): void => {
    if (picking === null) return;
    patchBinding(picking, node.node_id);
    setPicking(null);
  };

  const save = (): void => {
    update.mutate(
      {
        id: controller.id,
        patch: {
          name: draft.name,
          description: draft.description,
          execution_mode: draft.execution_mode,
          scan_rate_s: draft.scan_rate_s,
          tag_bindings: { ...controller.tag_bindings, ...draft.bindings },
          ...(isDdc
            ? {
                pid_params: draft.pid,
                pid_structure: draft.pid_structure,
                integral_type: draft.integral_type,
                pv_scale: draft.pv_scale,
                shed_opt: draft.shed_opt,
                shed_time_s: draft.shed_time_s,
                max_tuning_change_pct: draft.max_tuning_change_pct,
                low_cut: draft.low_cut,
                ff_gain: draft.ff_gain,
                ...draft.limits,
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

        <div className="grid grid-cols-2 gap-2">
          <TextField
            label="Nome"
            value={draft.name}
            disabled={readOnly}
            onChange={(v) => setDraft((p) => ({ ...p, name: v }))}
          />
          <TextField
            label="Descrição"
            value={draft.description}
            disabled={readOnly}
            onChange={(v) => setDraft((p) => ({ ...p, description: v }))}
          />
          <SelectField
            label="Modo de execução"
            value={draft.execution_mode}
            options={EXECUTION_MODES}
            disabled={readOnly}
            onChange={(v) => setDraft((p) => ({ ...p, execution_mode: v as ExecutionMode }))}
          />
          <NumberField
            label="Taxa de varredura (s)"
            value={draft.scan_rate_s}
            disabled={readOnly}
            onChange={(v) => setDraft((p) => ({ ...p, scan_rate_s: v }))}
          />
          {NODE_ID_FIELDS.map(({ key, label }) => (
            <NodeIdField
              key={key}
              label={label}
              value={draft.bindings[key]}
              disabled={readOnly}
              onChange={(v) => patchBinding(key, v)}
              onBrowse={canManage ? () => setPicking(key) : undefined}
            />
          ))}
        </div>

        {isDdc ? (
          <>
            <Section label="PID Tuning">
              <NumberField
                label="Ganho (Kp)"
                value={draft.pid.gain}
                disabled={readOnly}
                error={pidErrors.gain}
                onChange={(v) => patchPid('gain', v)}
              />
              <NumberField
                label="Reset (Ti)"
                value={draft.pid.reset}
                disabled={readOnly}
                error={pidErrors.reset}
                onChange={(v) => patchPid('reset', v)}
              />
              <NumberField
                label="Rate (Td)"
                value={draft.pid.rate}
                disabled={readOnly}
                error={pidErrors.rate}
                onChange={(v) => patchPid('rate', v)}
              />
              <NumberField
                label="Filtro derivativo (alpha)"
                value={draft.pid.alpha}
                disabled={readOnly}
                error={pidErrors.alpha}
                onChange={(v) => patchPid('alpha', v)}
              />
              <NumberField
                label="Banda morta"
                value={draft.pid.deadband}
                disabled={readOnly}
                error={pidErrors.deadband}
                onChange={(v) => patchPid('deadband', v)}
              />
            </Section>

            <Section label="Scaling & Limits">
              <NumberField
                label="PV mín."
                value={draft.pv_scale.eu_min}
                disabled={readOnly}
                onChange={(v) => setDraft((p) => ({ ...p, pv_scale: { ...p.pv_scale, eu_min: v } }))}
              />
              <NumberField
                label="PV máx."
                value={draft.pv_scale.eu_max}
                disabled={readOnly}
                onChange={(v) => setDraft((p) => ({ ...p, pv_scale: { ...p.pv_scale, eu_max: v } }))}
              />
              <TextField
                label="Unidade PV"
                value={draft.pv_scale.unit}
                disabled={readOnly}
                onChange={(v) => setDraft((p) => ({ ...p, pv_scale: { ...p.pv_scale, unit: v } }))}
              />
              <NumberField
                label="Saída mín."
                value={draft.limits.out_lo_lim}
                disabled={readOnly}
                error={limitErrors.out_lo_lim}
                onChange={(v) => patchLimit('out_lo_lim', v)}
              />
              <NumberField
                label="Saída máx."
                value={draft.limits.out_hi_lim}
                disabled={readOnly}
                error={limitErrors.out_hi_lim}
                onChange={(v) => patchLimit('out_hi_lim', v)}
              />
              <NumberField
                label="ARW mín."
                value={draft.limits.arw_lo_lim}
                disabled={readOnly}
                error={limitErrors.arw_lo_lim}
                onChange={(v) => patchLimit('arw_lo_lim', v)}
              />
              <NumberField
                label="ARW máx."
                value={draft.limits.arw_hi_lim}
                disabled={readOnly}
                error={limitErrors.arw_hi_lim}
                onChange={(v) => patchLimit('arw_hi_lim', v)}
              />
              <NumberField
                label="SP mín."
                value={draft.limits.sp_lo_lim}
                disabled={readOnly}
                error={limitErrors.sp_lo_lim}
                onChange={(v) => patchLimit('sp_lo_lim', v)}
              />
              <NumberField
                label="SP máx."
                value={draft.limits.sp_hi_lim}
                disabled={readOnly}
                error={limitErrors.sp_hi_lim}
                onChange={(v) => patchLimit('sp_hi_lim', v)}
              />
            </Section>

            <Section label="Filters & IO">
              <NumberField
                label="Filtro PV (s)"
                value={draft.limits.pv_ftime}
                disabled={readOnly}
                error={limitErrors.pv_ftime}
                onChange={(v) => patchLimit('pv_ftime', v)}
              />
              <NumberField
                label="Filtro SP (s)"
                value={draft.limits.sp_ftime}
                disabled={readOnly}
                error={limitErrors.sp_ftime}
                onChange={(v) => patchLimit('sp_ftime', v)}
              />
              <NumberField
                label="Rampa SP subida"
                value={draft.limits.sp_rate_up}
                disabled={readOnly}
                error={limitErrors.sp_rate_up}
                onChange={(v) => patchLimit('sp_rate_up', v)}
              />
              <NumberField
                label="Rampa SP descida"
                value={draft.limits.sp_rate_dn}
                disabled={readOnly}
                error={limitErrors.sp_rate_dn}
                onChange={(v) => patchLimit('sp_rate_dn', v)}
              />
              <NumberField
                label="Corte baixo"
                value={draft.low_cut}
                disabled={readOnly}
                onChange={(v) => setDraft((p) => ({ ...p, low_cut: v }))}
              />
              <NumberField
                label="Ganho FF"
                value={draft.ff_gain}
                disabled={readOnly}
                onChange={(v) => setDraft((p) => ({ ...p, ff_gain: v }))}
              />
            </Section>

            <Section label="Shed & Safety">
              <SelectField
                label="Modo de shed"
                value={draft.shed_opt}
                options={SHED_OPTIONS}
                disabled={readOnly}
                onChange={(v) => setDraft((p) => ({ ...p, shed_opt: v }))}
              />
              <NumberField
                label="Tempo de shed (s)"
                value={draft.shed_time_s}
                disabled={readOnly}
                onChange={(v) => setDraft((p) => ({ ...p, shed_time_s: v }))}
              />
              <NumberField
                label="Mudança máx. de sintonia (%)"
                value={draft.max_tuning_change_pct}
                disabled={readOnly}
                onChange={(v) => setDraft((p) => ({ ...p, max_tuning_change_pct: v }))}
              />
            </Section>

            <Section label="PID Structure">
              <SelectField
                label="Estrutura"
                value={draft.pid_structure}
                options={PID_STRUCTURES}
                disabled={readOnly}
                onChange={(v) => setDraft((p) => ({ ...p, pid_structure: v }))}
              />
            </Section>

            <Section label="Integral Type">
              <SelectField
                label="Tipo integral"
                value={draft.integral_type}
                options={INTEGRAL_TYPES}
                disabled={readOnly}
                onChange={(v) => setDraft((p) => ({ ...p, integral_type: v }))}
              />
            </Section>
          </>
        ) : null}

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
            O restante da configuração fica disponível no [cfg] da malha criada.
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
