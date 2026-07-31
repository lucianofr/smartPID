import { useId } from 'react';
import type { OpcuaNode, TagBindingsDto } from '@/api/types';
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
import { TagBrowser } from '@/features/connection/TagBrowser';

/**
 * OPC-UA NodeID binding row (§6.10) — a typed field plus the address-space
 * picker behind it.
 *
 * The field stays a plain text input: E2E-009 binds a loop by pasting an id,
 * and an operator with the id in hand must never be forced through a tree.
 * The picker is the discovery path, not a replacement for typing.
 */

/** The bindings the dialog owns, and the one place label/tooltip ↔ key is decided. */
export const NODE_ID_FIELDS = [
  {
    key: 'node_id_pv',
    label: 'NodeID PV',
    tooltip: 'Endereço OPC-UA de onde a Variável de Processo (PV) é lida.',
  },
  {
    key: 'node_id_sp',
    label: 'NodeID SP',
    tooltip: 'Endereço OPC-UA de onde o Setpoint (SP) é lido ou escrito.',
  },
  {
    key: 'node_id_co',
    label: 'NodeID CO',
    tooltip: 'Endereço OPC-UA de onde a Saída de Controle (CO) é lida ou escrita.',
  },
  {
    key: 'node_id_ti',
    label: 'NodeID Ti',
    tooltip:
      'Endereço OPC-UA usado para leitura/escrita do parâmetro de tempo integral (Ti), quando aplicável.',
  },
  {
    key: 'node_id_mode_actual',
    label: 'NodeID Modo (leitura)',
    tooltip:
      'Endereço OPC-UA de onde o modo REAL do bloco PID é lido no CLP/DCS. Usado para saber em que modo a malha está operando de fato.',
  },
  {
    key: 'node_id_mode_target',
    label: 'NodeID Modo (escrita)',
    tooltip:
      'Endereço OPC-UA para onde o modo COMANDADO é escrito no CLP/DCS. Usado quando o operador troca o modo pela interface.',
  },
  {
    key: 'node_id_enabled',
    label: 'NodeID PID em uso',
    tooltip:
      'Endereço OPC-UA do booleano do CLP que indica se o processo desta malha está em operação (1) ou parado (0) — tipicamente a tag PID_[MALHA]_ENABLED, por exemplo Process_Running. Em branco, o otimizador roda sem esse bloqueio.',
  },
] as const satisfies readonly { key: keyof TagBindingsDto; label: string; tooltip: string }[];

export type NodeIdKey = (typeof NODE_ID_FIELDS)[number]['key'];

export function nodeIdLabel(key: NodeIdKey | null): string | null {
  if (key === null) return null;
  return NODE_ID_FIELDS.find((field) => field.key === key)?.label ?? null;
}

export interface NodeIdFieldProps {
  label: string;
  value: string;
  disabled: boolean;
  onChange(value: string): void;
  /** Omitted when the session cannot write — the picker is a write affordance. */
  onBrowse?: () => void;
  tooltip?: string;
}

export function NodeIdField({
  label,
  value,
  disabled,
  onChange,
  onBrowse,
  tooltip,
}: NodeIdFieldProps) {
  const id = useId();
  return (
    <Field label={label} htmlFor={id} tooltip={tooltip}>
      <div className="flex items-center gap-2">
        <Input
          id={id}
          value={value}
          disabled={disabled}
          onChange={(e) => onChange(e.target.value)}
        />
        {onBrowse ? (
          <Button
            variant="secondary"
            aria-label={`Procurar ${label}`}
            title={`Procurar ${label}`}
            className="shrink-0 px-3"
            onClick={onBrowse}
          >
            <span aria-hidden="true" className="numeric text-xs">
              [tag]
            </span>
          </Button>
        ) : null}
      </div>
    </Field>
  );
}

export interface TagPickerDialogProps {
  /** Label of the field being bound; `null` closes the picker. */
  field: string | null;
  onSelect(node: OpcuaNode): void;
  onClose(): void;
}

/**
 * Nested picker. Which field the chosen node lands in is decided by the caller
 * that opened it, never by this dialog — the title only echoes that decision
 * back so the operator can see what they are about to overwrite.
 */
export function TagPickerDialog({ field, onSelect, onClose }: TagPickerDialogProps) {
  return (
    <Dialog
      open={field !== null}
      onOpenChange={(next) => {
        if (!next) onClose();
      }}
    >
      <DialogContent className="max-h-[85vh] max-w-xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Selecionar tag para {field}</DialogTitle>
          <DialogDescription>
            Navegue pelo espaço de endereços ou busque pelo nome. O NodeID da tag escolhida vai para{' '}
            {field}.
          </DialogDescription>
        </DialogHeader>

        <TagBrowser showNodeId onSelect={onSelect} />

        <DialogFooter>
          <Button variant="secondary" onClick={onClose}>
            Cancelar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
