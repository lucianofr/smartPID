import { useEffect, useId, useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { endpoints } from '@/api/endpoints';
import { queryKeys } from '@/api/queryKeys';
import type { ControllerMode } from '@/api/types';
import { AnalogBar } from '@/components/AnalogBar';
import { Badge } from '@/components/Badge';
import { Button } from '@/components/Button';
import { Input } from '@/components/Field';
import { Readout } from '@/components/Readout';
import { Slider } from '@/components/Slider';
import { toast } from '@/components/Toast';
import { useCan } from '@/auth/useCan';
import { formatPercent } from '@/lib/format';
import type { Scale } from '@/lib/scale';
import type { StatsData, StatusData } from '@/lib/envelope';
import { useRealtime } from '@/realtime/useRealtime';
import { cn } from '@/lib/utils';
import { CO_SCALE } from './useControllers';

export interface FaceplateProps {
  controllerId: number;
  tag: string;
  description?: string;
  scale: Scale;
  decimals?: number;
}

/** Operator modes offered on the faceplate; the rest of the enum is config-only. */
const OPERATOR_MODES: readonly ControllerMode[] = ['AUTO', 'MAN'];

/**
 * Fixed ~320 px loop faceplate (§6.9). Both roles keep AUTO/MAN, setpoint and
 * manual output; only `tuning.edit` sees `Apply tuning` — the shorter variant
 * is a designed state, not a hole. The backend re-enforces all of it.
 */
export function Faceplate({ controllerId, tag, description, scale, decimals = 1 }: FaceplateProps) {
  const status = useRealtime<StatusData>(controllerId, 'status');
  const stats = useRealtime<StatsData>(controllerId, 'stats');
  const canTune = useCan('tuning.edit');
  const queryClient = useQueryClient();

  const spId = useId();
  const [spDraft, setSpDraft] = useState('');
  const [coDraft, setCoDraft] = useState(0);

  const data = status.last?.data ?? null;
  const mode = data?.mode ?? '—';
  const isManual = mode === 'MAN';

  // The manual slider tracks the live CO until the operator grabs it.
  const [coTouched, setCoTouched] = useState(false);
  useEffect(() => {
    if (!coTouched && data !== null) setCoDraft(data.co.value);
  }, [coTouched, data]);

  const invalidate = (): void => {
    void queryClient.invalidateQueries({ queryKey: queryKeys.controllers });
  };
  const onCommandError = (): void => {
    toast({ title: 'Comando recusado', description: `Malha ${tag}`, tone: 'crit' });
  };

  const modeCmd = useMutation({
    mutationFn: (next: ControllerMode) => endpoints.setMode(controllerId, next),
    onSuccess: invalidate,
    onError: onCommandError,
  });
  const spCmd = useMutation({
    mutationFn: (value: number) => endpoints.setSetpoint(controllerId, value),
    onSuccess: invalidate,
    onError: onCommandError,
  });
  const coCmd = useMutation({
    mutationFn: (value: number) => endpoints.setOutput(controllerId, value),
    onSuccess: () => {
      setCoTouched(false);
      invalidate();
    },
    onError: onCommandError,
  });
  const tuningCmd = useMutation({
    mutationFn: () => endpoints.applyTuning(controllerId),
    onSuccess: () => {
      toast({ title: 'Sintonia aplicada', description: `Malha ${tag}` });
      invalidate();
    },
    onError: onCommandError,
  });

  const spValue = Number(spDraft);
  const spValid = spDraft.trim() !== '' && Number.isFinite(spValue);

  return (
    <aside
      aria-label={`Faceplate ${tag}`}
      className="flex w-full shrink-0 flex-col gap-3 border-rule bg-surface p-3 lg:w-80 lg:border-l"
    >
      <header className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="numeric truncate text-sm font-medium text-text">{tag}</p>
          {description !== undefined ? (
            <p className="truncate text-2xs text-text-soft">{description}</p>
          ) : null}
        </div>
        <Badge tone={mode === 'MAN' ? 'warn' : 'accent'} className="numeric shrink-0">
          {mode}
        </Badge>
      </header>

      {/* §6.9 shows one line per variable: label, bar, value. AnalogBar already
          carries the numeric, so a parallel Readout row would print it twice. */}
      <div className="flex flex-col gap-1.5">
        <AnalogBar
          label="PV"
          value={data?.pv.value ?? null}
          spValue={data?.sp.value}
          scale={scale}
          size="faceplate"
          decimals={decimals}
        />
        <AnalogBar
          label="SP"
          value={data?.sp.value ?? null}
          scale={scale}
          size="faceplate"
          decimals={decimals}
        />
        <AnalogBar
          label="CO"
          value={data?.co.value ?? null}
          scale={CO_SCALE}
          size="faceplate"
          decimals={decimals}
        />
      </div>

      <div className="flex items-end justify-between gap-2 border-t border-rule pt-2">
        <Readout label="IAE" value={stats.last?.data.iae ?? null} decimals={1} size="sm" />
        <div className="flex flex-col gap-0.5">
          <span className="text-2xs font-medium uppercase tracking-wider text-text-soft">
            2σ/Range
          </span>
          <span className="numeric text-sm font-medium text-text">
            {formatPercent(stats.last?.data.variability_range ?? null)}
          </span>
        </div>
      </div>

      <div role="group" aria-label="Modo do controlador" className="flex gap-2">
        {OPERATOR_MODES.map((m) => (
          <Button
            key={m}
            variant={mode === m ? 'primary' : 'secondary'}
            className="flex-1"
            aria-pressed={mode === m}
            disabled={modeCmd.isPending}
            onClick={() => modeCmd.mutate(m)}
          >
            {m}
          </Button>
        ))}
      </div>

      <div className="flex items-end gap-2">
        <span className="flex min-w-0 flex-1 flex-col gap-1">
          <label htmlFor={spId} className="text-2xs font-medium uppercase tracking-wider text-text-soft">
            Setpoint
          </label>
          <Input
            id={spId}
            type="number"
            className="px-2 py-1 text-sm"
            placeholder={String(data?.sp.value ?? '')}
            value={spDraft}
            onChange={(e) => setSpDraft(e.target.value)}
          />
        </span>
        <Button disabled={!spValid || spCmd.isPending} onClick={() => spCmd.mutate(spValue)}>
          Set setpoint
        </Button>
      </div>

      <div className="flex flex-col gap-1">
        <span className="flex items-baseline justify-between">
          <span className="text-2xs font-medium uppercase tracking-wider text-text-soft">
            Manual CO
          </span>
          <span className={cn('numeric text-sm', isManual ? 'text-text' : 'text-text-disabled')}>
            {coDraft.toFixed(decimals)}
          </span>
        </span>
        <Slider
          thumbLabel="Manual CO"
          data-testid="manual-co-slider"
          min={CO_SCALE.euMin}
          max={CO_SCALE.euMax}
          step={0.5}
          value={[coDraft]}
          disabled={!isManual}
          onValueChange={([v]) => {
            setCoTouched(true);
            setCoDraft(v);
          }}
        />
        <Button
          className="self-end"
          disabled={!isManual || coCmd.isPending}
          onClick={() => coCmd.mutate(coDraft)}
        >
          Set output
        </Button>
      </div>

      {canTune ? (
        <Button
          variant="secondary"
          disabled={tuningCmd.isPending}
          onClick={() => tuningCmd.mutate()}
        >
          Apply tuning
        </Button>
      ) : null}
    </aside>
  );
}
