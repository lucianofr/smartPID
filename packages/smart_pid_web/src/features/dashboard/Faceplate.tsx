import { useEffect, useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { endpoints } from '@/api/endpoints';
import { queryKeys } from '@/api/queryKeys';
import type { ControllerMode } from '@/api/types';
import { AnalogBar } from '@/components/AnalogBar';
import { Badge } from '@/components/Badge';
import { Button } from '@/components/Button';
import { Readout } from '@/components/Readout';
import { Slider } from '@/components/Slider';
import { toast } from '@/components/Toast';
import { AiPanel } from '@/features/loop-config/AiPanel';
import { CardControls } from '@/features/loop-config/CardControls';
import type { Range } from '@/features/loop-config/types';
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
  /** Loop SP limits (`sp_lo_lim`/`sp_hi_lim`); omit to check finiteness only. */
  spRange?: Range;
}

/** Operator modes offered on the faceplate; the rest of the enum is config-only. */
const OPERATOR_MODES: readonly ControllerMode[] = ['AUTO', 'MAN'];

/**
 * Fixed ~320 px loop faceplate (§6.9). Both roles keep AUTO/MAN, setpoint and
 * manual output; only an admin gets the AI panel (and the `Apply tuning` it
 * owns) — the shorter variant is a designed state, not a hole. The backend
 * re-enforces all of it.
 *
 * SP/CO entry is `CardControls`, mounted here rather than restated: the loop
 * must not offer the same operator two setpoint boxes on one screen.
 */
export function Faceplate({
  controllerId,
  tag,
  description,
  scale,
  decimals = 1,
  spRange,
}: FaceplateProps) {
  const status = useRealtime<StatusData>(controllerId, 'status');
  const stats = useRealtime<StatsData>(controllerId, 'stats');
  const queryClient = useQueryClient();

  const [coDraft, setCoDraft] = useState(0);

  const data = status.last?.data ?? null;
  const mode = data?.mode ?? '—';
  const isManual = mode === 'MAN';

  // The manual slider tracks the live CO until the operator grabs it, and goes
  // back to tracking whenever the loop leaves MAN.
  const [coTouched, setCoTouched] = useState(false);
  useEffect(() => {
    if (!coTouched && data !== null) setCoDraft(data.co.value);
  }, [coTouched, data]);
  useEffect(() => {
    if (!isManual) setCoTouched(false);
  }, [isManual]);

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

  return (
    <aside
      aria-label={`Faceplate ${tag}`}
      className="flex w-full shrink-0 flex-col gap-3 border-rule bg-surface p-3 lg:w-80 lg:overflow-y-auto lg:border-l"
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
          stale={status.stale}
        />
        <AnalogBar
          label="SP"
          value={data?.sp.value ?? null}
          scale={scale}
          size="faceplate"
          decimals={decimals}
          stale={status.stale}
        />
        <AnalogBar
          label="CO"
          value={data?.co.value ?? null}
          scale={CO_SCALE}
          size="faceplate"
          decimals={decimals}
          stale={status.stale}
        />
      </div>

      <div className="flex items-end justify-between gap-2 border-t border-rule pt-2">
        <Readout
          label="IAE"
          value={stats.last?.data.iae ?? null}
          decimals={1}
          size="sm"
          stale={stats.stale}
        />
        <div className="flex flex-col gap-0.5">
          <span className="text-2xs font-medium uppercase tracking-wider text-text-soft">
            2σ/Range
          </span>
          <span
            className={cn(
              'numeric text-sm font-medium',
              stats.stale ? 'text-text-disabled' : 'text-text',
            )}
          >
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

      <CardControls
        controllerId={controllerId}
        mode={mode}
        spRange={spRange}
        controls={['setpoint']}
      />

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
        {/* Numeric twin of the slider: same draft, one `Set output` write. */}
        <CardControls
          controllerId={controllerId}
          mode={mode}
          controls={['output']}
          outputValue={coDraft}
          onOutputValueChange={(v) => {
            setCoTouched(true);
            setCoDraft(v);
          }}
        />
      </div>

      <AiPanel controllerId={controllerId} tag={tag} />
    </aside>
  );
}
