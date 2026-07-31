import { useEffect, useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { endpoints } from '@/api/endpoints';
import { queryKeys } from '@/api/queryKeys';
import type { ControllerMode } from '@/api/types';
import { AnalogBar } from '@/components/AnalogBar';
import { Button } from '@/components/Button';
import { toast } from '@/components/Toast';
import { AiPanel } from '@/features/loop-config/AiPanel';
import { CardControls } from '@/features/loop-config/CardControls';
import type { Range } from '@/features/loop-config/types';
import { formatNumber, formatPercent } from '@/lib/format';
import type { Scale } from '@/lib/scale';
import type { StatsData, StatusData } from '@/lib/envelope';
import { useConnectionStatus } from '@/realtime/useConnectionStatus';
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
 * Short-viewport density switches. Written as literals because Tailwind's JIT
 * only sees complete class names; grouped here so the arbitrary media variant
 * appears once per role instead of scattered through the JSX.
 *
 * `stackToRow` folds a caption-over-value cell into one baseline-aligned line —
 * the 1a composition at ≥820px, 13px shorter below it.
 */
const SHORT_VIEWPORT = {
  railGap: '[@media(max-height:820px)]:gap-1.5',
  railPad: '[@media(max-height:820px)]:p-2',
  stackToRow:
    '[@media(max-height:820px)]:flex [@media(max-height:820px)]:items-baseline [@media(max-height:820px)]:justify-center [@media(max-height:820px)]:gap-1',
} as const;

/** 1a segment geometry. `min-h-11` is the §8.3 44px floor, above the mock's 34px. */
const SEGMENT_BASE = 'min-h-11 flex-1 rounded-control border border-rule px-1 py-2 text-base font-bold';
const SEGMENT_IDLE = 'bg-transparent text-text-soft hover:bg-surface-sunk hover:text-text';

/**
 * Selected-mode fills. AUTO takes brand navy, but its ink is
 * `--brand-accent-soft`, NOT the mock's white / `--on-accent`: under
 * optimizer-dark `--on-accent` IS `--brand-ink` (#0D1F38), so that pair renders
 * navy on navy — the same trap AppShell documents on the avatar chip.
 */
const MODE_ACTIVE: Record<string, string> = {
  AUTO: 'bg-brand-ink text-brand-accent-soft hover:bg-brand-ink',
  MAN: 'bg-alarm-warn text-on-alarm hover:bg-alarm-warn',
};

/**
 * The four §6.7 loop metrics, in the 1a 4-up grid. `IAE` and `2σ/Range` are
 * literal e2e anchors — do not reword them.
 */
interface Metric {
  readonly label: string;
  readonly value: string;
}

function metrics(stats: StatsData | null): readonly Metric[] {
  return [
    { label: 'IAE', value: formatNumber(stats?.iae ?? null, 1) },
    { label: '2σ/SP', value: formatPercent(stats?.variability_sp ?? null) },
    { label: '2σ/Range', value: formatPercent(stats?.variability_range ?? null) },
    { label: 'TV', value: formatNumber(stats?.total_variation ?? null, 1) },
  ];
}

/**
 * Loop faceplate rail (§6.9), direction 1a: a single surface card holding the
 * tag, the PV/SP/CO bars, the operator entries, the mode and optimizer
 * segments, the live gains and the AI box.
 *
 * The rail is fixed at `lg:w-80` (320px), NOT the mock's 372px — 320 ± 8 is a
 * hard e2e assertion (e2e/responsive.spec.ts) and the trend's ≥65% share of
 * 1440 is budgeted against it.
 *
 * SP/CO entry is `CardControls`, mounted here rather than restated: the loop
 * must not offer the same operator two setpoint boxes on one screen. Both roles
 * keep AUTO/MAN, setpoint and manual output; only an admin gets the AI panel
 * (and the `Apply tuning` it owns). The backend re-enforces all of it.
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
  const link = useConnectionStatus();
  const queryClient = useQueryClient();

  const [coDraft, setCoDraft] = useState(0);

  const data = status.last?.data ?? null;
  const mode = data?.mode ?? '—';

  // The manual output field tracks the live CO until the operator edits it,
  // and goes back to tracking whenever the loop leaves MAN.
  const [coTouched, setCoTouched] = useState(false);
  useEffect(() => {
    if (!coTouched && data !== null) setCoDraft(data.co.value);
  }, [coTouched, data]);
  useEffect(() => {
    if (mode !== 'MAN') setCoTouched(false);
  }, [mode]);

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

  const gains: readonly Metric[] = [
    { label: 'Kp', value: formatNumber(data?.kp ?? null, 2) },
    { label: 'Ti', value: formatNumber(data?.ti ?? null, 2) },
    { label: 'Td', value: formatNumber(data?.td ?? null, 2) },
  ];

  return (
    <aside
      aria-label={`Faceplate ${tag}`}
      className={cn(
        // Direction 1a floats the faceplate as a card rather than butting it
        // against the viewport edge as a rail: white surface, hairline on all
        // four sides, 10px corners, sitting in the workspace gutter.
        'flex w-full shrink-0 flex-col gap-2 border border-rule bg-surface p-3',
        'lg:order-first lg:min-h-0 lg:w-80 lg:overflow-y-auto lg:rounded-card',
        'lg:my-3 lg:ml-3',
        // Height-aware density (§4.3). The rail must not scroll, and what it
        // gets is the viewport minus the app bar, the KPI band and the alarm
        // footer — roughly 600px at a 768px screen, against ~700px at 900px.
        // Compacting only below 820px buys that difference back without
        // touching the 1a spacing at any height the design was drawn for.
        SHORT_VIEWPORT.railGap,
        SHORT_VIEWPORT.railPad,
      )}
    >
      <header className="flex items-start justify-between gap-2">
        <div className="min-w-0 leading-tight">
          <p className="numeric truncate text-xl font-bold text-text">{tag}</p>
          {description !== undefined ? (
            <p className="truncate text-sm text-text-soft">{description}</p>
          ) : null}
        </div>
        {/* The link dot, not a mode chip: the mode is legible in the segment
            below, and what the header cannot otherwise say is whether these
            numbers are current (E2E-047). */}
        <span
          aria-hidden="true"
          className={cn(
            'mt-1.5 h-[9px] w-[9px] shrink-0 rounded-pill',
            link.stale ? 'bg-state-error' : 'bg-live',
          )}
        />
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

      <div className="flex flex-col gap-1.5">
        <CardControls
          controllerId={controllerId}
          mode={mode}
          spRange={spRange}
          controls={['setpoint']}
        />
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

      <div className="flex flex-col gap-1.5">
        <span className="text-2xs font-bold uppercase tracking-caps text-text-soft">Modo PID</span>
        <div role="group" aria-label="Modo do controlador" className="flex gap-1.5">
          {OPERATOR_MODES.map((m) => (
            <Button
              key={m}
              aria-pressed={mode === m}
              className={cn(SEGMENT_BASE, mode === m ? MODE_ACTIVE[m] : SEGMENT_IDLE)}
              disabled={modeCmd.isPending}
              onClick={() => modeCmd.mutate(m)}
            >
              {/* Mode codes are data, not prose — and the numeric face is what
                  keeps AUTO and MAN the same width in both segments. */}
              <span className="numeric">{m}</span>
            </Button>
          ))}
        </div>
      </div>

      <div aria-hidden="true" className="h-px shrink-0 bg-rule" />

      <div className="flex gap-2">
        {gains.map((gain) => (
          <div
            key={gain.label}
            className={cn('flex-1 text-center leading-tight', SHORT_VIEWPORT.stackToRow)}
          >
            <div className="text-2xs uppercase text-text-soft">{gain.label}</div>
            <div className="numeric text-base font-semibold text-text">{gain.value}</div>
          </div>
        ))}
      </div>

      <AiPanel controllerId={controllerId} tag={tag} />

      {/* No `uppercase` here on purpose: it would fold σ to Σ and print the
          variability metrics as `2Σ/RANGE`, which is a different quantity. */}
      <div className="grid shrink-0 grid-cols-4 gap-x-1.5 gap-y-2.5">
        {metrics(stats.last?.data ?? null).map((metric) => (
          <div
            key={metric.label}
            className={cn('text-center leading-tight', SHORT_VIEWPORT.stackToRow)}
          >
            <div className="text-[9px] text-text-soft">{metric.label}</div>
            <div
              className={cn(
                'numeric text-sm font-semibold',
                stats.stale ? 'text-text-disabled' : 'text-text',
              )}
            >
              {metric.value}
            </div>
          </div>
        ))}
      </div>
    </aside>
  );
}
