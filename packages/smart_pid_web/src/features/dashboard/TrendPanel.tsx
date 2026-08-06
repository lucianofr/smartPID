import { useCallback, useEffect, useId, useRef, useState, type ReactNode } from 'react';
import { Download } from 'lucide-react';
import { Input } from '@/components/Field';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/Select';
import { Switch } from '@/components/Switch';
import { Trend, TREND_WELL_INSET_PX, type TrendSeriesData } from '@/components/Trend';
import { useGlowTrace } from '@/theme/useGlowTrace';
import { formatNumber } from '@/lib/format';
import type { StatusData } from '@/lib/envelope';
import { useRealtime } from '@/realtime/useRealtime';
import type { Scale } from '@/lib/scale';
import { cn } from '@/lib/utils';
import { TREND_WINDOW_MAX_S } from '@/features/settings/settingsTypes';
import { CO_SCALE, useControllers } from './useControllers';
import { useTrendWindow } from './useTrendWindow';
import { readTrendView, writeTrendView, type TrendViewConfig } from './trendViewStore';

export interface TrendPanelProps {
  controllerId: number;
  scale: Scale;
}

export type TrendWindowUnit = 'segundo' | 'minuto' | 'hora';

export const UNIT_SECONDS: Record<TrendWindowUnit, number> = { segundo: 1, minuto: 60, hora: 3600 };
export const UNIT_LABEL: Record<TrendWindowUnit, string> = {
  segundo: 'segundos',
  minuto: 'minutos',
  hora: 'horas',
};
/** Ruler abbreviations — the well label is mono and has ~10 px of band to live in. */
export const UNIT_SHORT: Record<TrendWindowUnit, string> = { segundo: 's', minuto: 'min', hora: 'h' };

/**
 * Window control to seconds, clamped to `TREND_WINDOW_MAX_S`: `count` is a free
 * numeric input, and a span wider than a chart can retain would paint a shorter
 * trace than its own axis claims.
 */
export function windowSeconds(count: number, unit: TrendWindowUnit): number {
  return Math.min(Math.max(1, count) * UNIT_SECONDS[unit], TREND_WINDOW_MAX_S);
}

/**
 * Framing an unconfigured loop opens with: half an hour of context, autoscale
 * on, and — the reason this is a function of `scale` — the loop's OWN
 * engineering range as the pinned PV bounds, not a hardcoded 0-100.
 */
export function panelDefaults(scale: Scale): TrendViewConfig {
  return {
    count: 30,
    unit: 'minuto',
    autoScale: true,
    pvMin: scale.euMin,
    pvMax: scale.euMax,
    coMin: CO_SCALE.euMin,
    coMax: CO_SCALE.euMax,
  };
}

/** Exactly the plotted rows — the export must match what the operator sees. */
export function buildTrendCsv(data: TrendSeriesData, scale: Scale): string {
  const cell = (v: number | null): string => (v === null || !Number.isFinite(v) ? '' : String(v));
  const header = `timestamp,pv_${scale.unit},sp_${scale.unit},co_${CO_SCALE.unit}`;
  const rows = data.t.map(
    (t, i) =>
      `${new Date(t * 1000).toISOString()},${cell(data.pv[i])},${cell(data.sp[i])},${cell(data.co[i])}`,
  );
  return [header, ...rows].join('\n');
}

function downloadCsv(filename: string, csv: string): void {
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

const NUMBER_INPUT = 'numeric w-14 px-2 text-sm';
const CONTROL_LABEL = 'shrink-0 text-2xs uppercase tracking-caps text-text-soft';
const SCALE_INPUT = 'numeric w-12 px-1.5 text-xs';

/**
 * Paint guard for the canvas — NOT a design minimum, and the distinction is the
 * whole point. uPlot with a zero height produces a zero-sized canvas and the E2E
 * readiness probe (`trendCanvasPainted`) waits forever on one, so the height
 * handed to `Trend` must stay positive even when the measured remainder goes to
 * zero or negative.
 *
 * It must NOT exceed what the tightest supported layout can grant, because the
 * well is `TREND_WELL_INSET_PX` taller than the canvas: a floor that outbids the
 * remainder makes the well taller than its own container, and that overflow
 * escapes the card entirely (see the `max-h-full` note in `Trend`). The old
 * value of 140 did exactly that — the dashboard's vertical budget is dominated
 * by the ~413px loop-card strip above, which leaves this panel a ~114px plot box
 * at 1440x900, so 140 + 28 overshot by 54px and the clip ate the time ruler.
 *
 * Invariant, pinned by "the trend well never outgrows its plot box" in
 * e2e/responsive.spec.ts: MIN_PLOT_HEIGHT + TREND_WELL_INSET_PX must fit the
 * plot box at every supported desktop viewport. 72 leaves uPlot its ~30px x-axis
 * plus ~40px of plot area, and stays clear of the ~86px the tightest of them
 * affords. Raising it is what that E2E assertion is there to catch.
 */
const MIN_PLOT_HEIGHT = 72;

/**
 * Recorder strip for the selected loop (§6.7/§6.9): live window, pen tip at the
 * true latest sample, AI ticks in `--accent`, and the halo pass on PV whenever
 * `--glow-trace` is non-zero (§10.5). The `ctx.shadowBlur` path stays banned —
 * the halo lives in `Trend`.
 */
export function TrendPanel({ controllerId, scale }: TrendPanelProps) {
  const glow = useGlowTrace();
  const controllers = useControllers();
  const tag = controllers.data?.find((c) => c.id === controllerId)?.name ?? `#${controllerId}`;

  const windowId = useId();
  const unitId = useId();
  const autoId = useId();
  const pvMinId = useId();
  const pvMaxId = useId();
  const coMinId = useId();
  const coMaxId = useId();

  /**
   * View state (window + scale) is persisted per loop (§9.1), so a framing an
   * engineer set on FIC-101 survives navigation and reload and does not follow
   * them onto the next loop.
   *
   * `loop` travels INSIDE the state on purpose: the loop id and the values it
   * describes must change in the same commit, otherwise the save effect fires
   * once with the new id and the previous loop's numbers and overwrites the
   * stored framing of the loop just opened.
   */
  const [view, setView] = useState(() => ({
    loop: controllerId,
    config: readTrendView('panel', controllerId, panelDefaults(scale)),
  }));
  if (view.loop !== controllerId) {
    setView({ loop: controllerId, config: readTrendView('panel', controllerId, panelDefaults(scale)) });
  }
  const { count, unit, autoScale, pvMin, pvMax, coMin, coMax } = view.config;
  const patch = useCallback(
    (next: Partial<TrendViewConfig>) =>
      setView((v) => ({ loop: v.loop, config: { ...v.config, ...next } })),
    [],
  );
  useEffect(() => {
    writeTrendView('panel', view.loop, view.config);
  }, [view]);

  /**
   * The plot is sized from its own column rather than pinned: the well is the
   * flex remainder of the card, so a fixed canvas height would leave a dead
   * sunken band under the trace at tall viewports. `TREND_WELL_INSET_PX` is the
   * well's own padding, which the caller must not pay twice.
   */
  const plotRef = useRef<HTMLDivElement>(null);
  const [plotBox, setPlotBox] = useState({ width: 800, height: 280 });
  useEffect(() => {
    const el = plotRef.current;
    if (el === null) return;
    const ro = new ResizeObserver(() => {
      const width = el.clientWidth - TREND_WELL_INSET_PX;
      const height = Math.max(MIN_PLOT_HEIGHT, el.clientHeight - TREND_WELL_INSET_PX);
      if (width <= 0) return;
      setPlotBox((prev) => (prev.width === width && prev.height === height ? prev : { width, height }));
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const { data, penTip, aiTicks } = useTrendWindow(
    controllerId,
    windowSeconds(count, unit),
    plotBox.width,
  );

  // Legend figures come from the status envelope, not the decimated tail: the
  // header states what the loop is doing right now, and decimation may have
  // dropped the newest sample of SP or CO from the plotted columns.
  const status = useRealtime<StatusData>(controllerId, 'status');
  const frame = status.last?.data;

  const exportCsv = useCallback(() => {
    downloadCsv(`${tag}-tendencia.csv`, buildTrendCsv(data, scale));
  }, [data, scale, tag]);

  return (
    <section
      aria-label={`Painel de tendência ${tag}`}
      // Stacked (<1024) the pane keeps its natural height and the page scrolls;
      // shrinking it would let the fixed-height plot overlap the faceplate.
      className={cn(
        'm-3 flex min-w-0 flex-col gap-3 rounded-card border border-rule bg-surface p-4.5',
        'max-lg:shrink-0 lg:min-h-0 lg:flex-1',
      )}
    >
      <div className="flex flex-wrap items-center justify-between gap-2.5">
        <div className="flex min-w-0 flex-wrap items-center gap-x-4 gap-y-1.5">
          <h2 className="type-display text-xl font-semibold text-text">Tendência — {tag}</h2>
          <div className="flex flex-wrap items-center gap-x-3.5 gap-y-1 text-sm text-text-soft">
            <LegendItem
              swatch={<span className="inline-block h-0.5 w-2.5 bg-trace-pv" />}
              name="PV"
              value={formatNumber(frame?.pv.value ?? null, 1)}
              stale={status.stale}
            />
            <LegendItem
              swatch={
                <span className="inline-block h-0 w-2.5 border-t-2 border-dashed border-trace-sp" />
              }
              name="SP"
              value={formatNumber(frame?.sp.value ?? null, 1)}
              stale={status.stale}
            />
            <LegendItem
              swatch={<span className="inline-block h-0.5 w-2.5 bg-trace-co" />}
              name="CO"
              value={formatNumber(frame?.co.value ?? null, 1)}
              stale={status.stale}
            />
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1.5">
          <div className="flex items-center gap-1.5">
            <label htmlFor={windowId} className={CONTROL_LABEL}>
              Janela de tempo
            </label>
            <Input
              id={windowId}
              type="number"
              min={1}
              className={NUMBER_INPUT}
              value={count}
              onChange={(e) => patch({ count: Number(e.target.value) })}
            />
            <Select value={unit} onValueChange={(v) => patch({ unit: v as TrendWindowUnit })}>
              <SelectTrigger id={unitId} aria-label="Unidade da janela" className="w-28">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {(Object.keys(UNIT_SECONDS) as TrendWindowUnit[]).map((u) => (
                  <SelectItem key={u} value={u}>
                    {UNIT_LABEL[u]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="flex items-center gap-1.5">
            <label htmlFor={autoId} className={CONTROL_LABEL}>
              Autoescala
            </label>
            <Switch id={autoId} checked={autoScale} onCheckedChange={(v) => patch({ autoScale: v })} />
          </div>

          {autoScale ? null : (
            <div className="flex flex-wrap items-center gap-1.5">
              <ScaleRange
                variable="PV"
                minId={pvMinId}
                maxId={pvMaxId}
                min={pvMin}
                max={pvMax}
                onMinChange={(v) => patch({ pvMin: v })}
                onMaxChange={(v) => patch({ pvMax: v })}
              />
              <ScaleRange
                variable="CO"
                minId={coMinId}
                maxId={coMaxId}
                min={coMin}
                max={coMax}
                onMinChange={(v) => patch({ coMin: v })}
                onMaxChange={(v) => patch({ coMax: v })}
              />
            </div>
          )}

          {/*
            The visible affordance is the design's 32 px brand pill; the button
            itself keeps the 44 px pointer floor (§8.3) as transparent padding
            around it, so the target is honestly 44 px without inflating the
            chrome.
          */}
          <button
            type="button"
            onClick={exportCsv}
            className={cn(
              'group inline-flex min-h-11 min-w-11 shrink-0 items-center justify-center',
              'rounded-control outline-none focus-visible:ring-2 focus-visible:ring-focus-ring',
            )}
          >
            <span
              className={cn(
                // 1a paints this pill in brand navy. That works on a light
                // workspace and disappears on a dark one: --brand-ink is navy in
                // every theme, and under optimizer-dark so is --surface AND
                // --on-accent, so the mock's pairing renders navy-on-navy twice
                // over. The interactive accent is the token that is guaranteed
                // to read as "act on this" against the current surface in all
                // six palettes, so the pill takes that instead.
                'inline-flex h-8 items-center gap-1.5 rounded-control bg-accent px-3.5',
                'text-sm font-semibold text-on-accent transition-colors',
                'group-hover:bg-accent-hover group-active:bg-accent-sunk',
              )}
            >
              <Download className="h-3.5 w-3.5" aria-hidden="true" />
              Exportar CSV
            </span>
          </button>
        </div>
      </div>

      <div ref={plotRef} className="min-h-0 flex-1">
        <Trend
          data={data}
          ariaLabel={`Tendência ${tag}`}
          pvAxis={
            autoScale
              ? { unit: scale.unit, name: 'PV / SP' }
              : { min: pvMin, max: pvMax, unit: scale.unit, name: 'PV / SP' }
          }
          coAxis={
            autoScale
              ? { unit: CO_SCALE.unit, name: 'CO' }
              : { min: coMin, max: coMax, unit: CO_SCALE.unit, name: 'CO' }
          }
          penTip={penTip}
          aiTicks={aiTicks}
          glow={glow}
          height={plotBox.height}
          // Bounds are printed only when the operator pinned them. Under
          // auto-scale the plotted range is uPlot's, not `scale`'s, and a
          // number the axis does not agree with is worse than no number.
          labels={{
            yTop: autoScale ? undefined : `${formatNumber(pvMax, 1)} ${scale.unit}`,
            yBottom: autoScale ? undefined : `${formatNumber(pvMin, 1)} ${scale.unit}`,
            time: `−${count} ${UNIT_SHORT[unit]} → agora`,
          }}
        />
      </div>
    </section>
  );
}

function LegendItem({
  swatch,
  name,
  value,
  stale,
}: {
  swatch: ReactNode;
  name: string;
  value: string;
  stale: boolean;
}) {
  return (
    <span className="flex items-center gap-1.5">
      <span aria-hidden="true" className="flex w-2.5 shrink-0 items-center">
        {swatch}
      </span>
      {name}
      <b className={cn('numeric font-semibold', stale ? 'text-text-disabled' : 'text-text')}>
        {value}
      </b>
    </span>
  );
}

/**
 * Min/max pair for one variable, under a single shared "PV"/"CO" glyph
 * instead of two full "PV mínimo"/"PV máximo" labels — the accessible names
 * stay exactly those strings (via `aria-label`, not visible text), so the
 * pair fits the toolbar's one line without shrinking what a screen reader
 * announces.
 */
export function ScaleRange({
  variable,
  minId,
  maxId,
  min,
  max,
  onMinChange,
  onMaxChange,
}: {
  variable: string;
  minId: string;
  maxId: string;
  min: number;
  max: number;
  onMinChange: (n: number) => void;
  onMaxChange: (n: number) => void;
}) {
  return (
    <span className="flex items-center gap-1">
      <span aria-hidden="true" className={CONTROL_LABEL}>
        {variable}
      </span>
      <Input
        id={minId}
        type="number"
        aria-label={`${variable} mínimo`}
        className={cn(SCALE_INPUT)}
        value={min}
        onChange={(e) => onMinChange(Number(e.target.value))}
      />
      <span aria-hidden="true" className="text-text-soft">
        –
      </span>
      <Input
        id={maxId}
        type="number"
        aria-label={`${variable} máximo`}
        className={cn(SCALE_INPUT)}
        value={max}
        onChange={(e) => onMaxChange(Number(e.target.value))}
      />
    </span>
  );
}
