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
import { CO_SCALE, useControllers } from './useControllers';
import { useTrendWindow } from './useTrendWindow';

export interface TrendPanelProps {
  controllerId: number;
  scale: Scale;
}

export type TrendWindowUnit = 'segundo' | 'minuto' | 'hora';

const UNIT_SECONDS: Record<TrendWindowUnit, number> = { segundo: 1, minuto: 60, hora: 3600 };
const UNIT_LABEL: Record<TrendWindowUnit, string> = {
  segundo: 'segundos',
  minuto: 'minutos',
  hora: 'horas',
};
/** Ruler abbreviations — the well label is mono and has ~10 px of band to live in. */
const UNIT_SHORT: Record<TrendWindowUnit, string> = { segundo: 's', minuto: 'min', hora: 'h' };

export function windowSeconds(count: number, unit: TrendWindowUnit): number {
  return Math.max(1, count) * UNIT_SECONDS[unit];
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

/**
 * Floor for the canvas. It exists for two reasons, neither cosmetic: uPlot with
 * a zero height produces a zero-sized canvas, and the E2E readiness probe
 * (`trendCanvasPainted`) waits forever on one. Kept deliberately low so a
 * cramped column clips a little rather than a lot — the dashboard's vertical
 * budget is dominated by the loop-card strip above, not by this panel.
 */
const MIN_PLOT_HEIGHT = 140;

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

  const [count, setCount] = useState(30);
  const [unit, setUnit] = useState<TrendWindowUnit>('minuto');
  const [autoScale, setAutoScale] = useState(true);
  const [pvMin, setPvMin] = useState(scale.euMin);
  const [pvMax, setPvMax] = useState(scale.euMax);
  const [coMin, setCoMin] = useState(CO_SCALE.euMin);
  const [coMax, setCoMax] = useState(CO_SCALE.euMax);

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
              onChange={(e) => setCount(Number(e.target.value))}
            />
            <Select value={unit} onValueChange={(v) => setUnit(v as TrendWindowUnit)}>
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
            <Switch id={autoId} checked={autoScale} onCheckedChange={setAutoScale} />
          </div>

          {autoScale ? null : (
            <div className="flex flex-wrap items-center gap-2">
              <ScaleInput id={pvMinId} label="PV mínimo" value={pvMin} onChange={setPvMin} />
              <ScaleInput id={pvMaxId} label="PV máximo" value={pvMax} onChange={setPvMax} />
              <ScaleInput id={coMinId} label="CO mínimo" value={coMin} onChange={setCoMin} />
              <ScaleInput id={coMaxId} label="CO máximo" value={coMax} onChange={setCoMax} />
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
          pvAxis={autoScale ? { unit: scale.unit } : { min: pvMin, max: pvMax, unit: scale.unit }}
          coAxis={autoScale ? { unit: CO_SCALE.unit } : { min: coMin, max: coMax, unit: CO_SCALE.unit }}
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

function ScaleInput({
  id,
  label,
  value,
  onChange,
}: {
  id: string;
  label: string;
  value: number;
  onChange: (n: number) => void;
}) {
  return (
    <span className="flex items-center gap-1">
      <label htmlFor={id} className={CONTROL_LABEL}>
        {label}
      </label>
      <Input
        id={id}
        type="number"
        className={cn(NUMBER_INPUT)}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    </span>
  );
}
