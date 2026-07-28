import { useId, useState } from 'react';
import { useCan } from '@/auth/useCan';
import { Button } from '@/components/Button';
import { Input } from '@/components/Field';
import { toast } from '@/components/Toast';
import { cn } from '@/lib/utils';
import { CONTROLLER_MODES, type ControllerMode, type Range } from './types';
import { useModeMutation, useOutputMutation, useSetpointMutation } from './useCommands';
import { validateOutput, validateSetpoint } from './validation';

/**
 * The operator command cluster for one loop: setpoint entry, block mode and
 * manual output. Split across two mount points so no control is duplicated on
 * screen — the card strip carries the quick mode switch, the faceplate carries
 * the numeric entry beside its bars and CO slider.
 */
export type CardControl = 'setpoint' | 'mode' | 'output';

const ALL_CONTROLS: readonly CardControl[] = ['setpoint', 'mode', 'output'];

export interface CardControlsProps {
  controllerId: number;
  /** Live block mode; manual output stays locked outside MAN. */
  mode: string;
  /** Loop SP limits — omit to check finiteness only. */
  spRange?: Range;
  controls?: readonly CardControl[];
  /** Controlled CO draft, so a slider elsewhere on the surface stays in sync. */
  outputValue?: number;
  onOutputValueChange?(value: number): void;
  className?: string;
}

const SELECT_CLASS = cn(
  'numeric min-h-11 w-full rounded-control border border-rule-strong bg-surface-sunk px-2 py-1',
  'text-sm text-text outline-none focus-visible:ring-2 focus-visible:ring-focus-ring',
  'disabled:cursor-not-allowed disabled:text-text-disabled',
);

/**
 * Direction 1a entry row: label left, right-aligned mono field, write button.
 * `Field` is not used here — its stacked label/control is the wrong axis for
 * this row, and the 320px rail has no budget for the extra line. The `<label
 * htmlFor>` binding, the `${id}-err` alert id and the accessible names are
 * reproduced verbatim, so `getByLabel('Setpoint')` / `getByLabel('Saída')` and
 * the aria-describedby wiring are unchanged.
 *
 * The mock draws a 30px field; `min-h-11` (44px) from `Input` stands, because
 * these are real operator inputs under the §8.3 target-size floor.
 */
const ENTRY_LABEL = 'shrink-0 text-sm text-text-soft';
const ENTRY_INPUT = cn(
  'numeric min-w-0 max-w-[110px] flex-1 px-2 py-1 text-right text-base',
);
const ENTRY_ERROR = 'text-xs font-medium text-alarm-crit';

export function CardControls({
  controllerId,
  mode,
  spRange,
  controls = ALL_CONTROLS,
  outputValue,
  onOutputValueChange,
  className,
}: CardControlsProps) {
  const canOperate = useCan('loop.operate');
  const spId = useId();
  const coId = useId();
  const modeId = useId();

  const [spDraft, setSpDraft] = useState('');
  const [coDraft, setCoDraft] = useState(0);

  const setpointCmd = useSetpointMutation();
  const modeCmd = useModeMutation();
  const outputCmd = useOutputMutation();

  if (!canOperate) return null;

  const onRejected = (): void => {
    toast({ title: 'Comando recusado', description: `Malha #${controllerId}`, tone: 'crit' });
  };

  const co = outputValue ?? coDraft;
  const setCo = (value: number): void => {
    if (onOutputValueChange !== undefined) onOutputValueChange(value);
    else setCoDraft(value);
  };

  const spValue = Number(spDraft);
  const spError = spDraft.trim() === '' ? undefined : validateSetpoint(spValue, spRange);
  const coError = validateOutput(co);
  // Same precedence `Field` applied: local validation first, then the rejection
  // the backend sent back for this control.
  const spMessage = spError ?? setpointCmd.error?.detail;
  const coMessage = coError ?? outputCmd.error?.detail;
  const isManual = mode === 'MAN';

  const show = (control: CardControl): boolean => controls.includes(control);

  return (
    <div data-testid="card-controls" className={cn('flex flex-col gap-2', className)}>
      {show('setpoint') ? (
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2">
            <label htmlFor={spId} className={ENTRY_LABEL}>
              Setpoint
            </label>
            <Input
              id={spId}
              type="number"
              inputMode="decimal"
              className={ENTRY_INPUT}
              value={spDraft}
              invalid={spError !== undefined}
              aria-describedby={spError !== undefined ? `${spId}-err` : undefined}
              onChange={(e) => setSpDraft(e.target.value)}
            />
            <Button
              className="shrink-0 px-2.5"
              disabled={spDraft.trim() === '' || spError !== undefined || setpointCmd.isPending}
              onClick={() =>
                setpointCmd.mutate({ id: controllerId, value: spValue }, { onError: onRejected })
              }
            >
              Set setpoint
            </Button>
          </div>
          {spMessage !== undefined ? (
            <p id={`${spId}-err`} role="alert" className={ENTRY_ERROR}>
              {spMessage}
            </p>
          ) : null}
        </div>
      ) : null}

      {show('mode') ? (
        <div className="flex flex-col gap-1">
          <label
            htmlFor={modeId}
            className="text-2xs font-medium uppercase tracking-wider text-text-soft"
          >
            Modo
          </label>
          {/* Native on purpose: the block enum has nine members and the retained
              command e2e drives it with selectOption(). */}
          <select
            id={modeId}
            aria-label="Mode"
            className={SELECT_CLASS}
            value={mode}
            disabled={modeCmd.isPending}
            onChange={(e) =>
              modeCmd.mutate(
                { id: controllerId, mode: e.target.value as ControllerMode },
                { onError: onRejected },
              )
            }
          >
            {CONTROLLER_MODES.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </div>
      ) : null}

      {show('output') ? (
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2">
            <label htmlFor={coId} className={ENTRY_LABEL}>
              Saída
            </label>
            <Input
              id={coId}
              type="number"
              inputMode="decimal"
              className={ENTRY_INPUT}
              value={Number.isFinite(co) ? co : ''}
              disabled={!isManual}
              invalid={coError !== undefined}
              aria-describedby={coError !== undefined ? `${coId}-err` : undefined}
              onChange={(e) => setCo(Number(e.target.value))}
            />
            <Button
              className="shrink-0 px-2.5"
              disabled={!isManual || coError !== undefined || outputCmd.isPending}
              onClick={() =>
                outputCmd.mutate({ id: controllerId, value: co }, { onError: onRejected })
              }
            >
              Set output
            </Button>
          </div>
          {coMessage !== undefined ? (
            <p id={`${coId}-err`} role="alert" className={ENTRY_ERROR}>
              {coMessage}
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
