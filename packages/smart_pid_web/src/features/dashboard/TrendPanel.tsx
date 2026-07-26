import { useCallback, useEffect, useId, useRef, useState } from 'react';
import { Button } from '@/components/Button';
import { Input } from '@/components/Field';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/Select';
import { Switch } from '@/components/Switch';
import { Trend, type TrendSeriesData } from '@/components/Trend';
import { useTheme } from '@/theme/ThemeProvider';
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

const NUMBER_INPUT = 'w-20 px-2 py-1 text-xs';

/**
 * Recorder strip for the selected loop (§6.7/§6.9): live window, pen tip at the
 * true latest sample, AI ticks in `--accent`, and the Phosphor halo pass. The
 * `ctx.shadowBlur` path stays banned — the halo lives in `Trend`.
 */
export function TrendPanel({ controllerId, scale }: TrendPanelProps) {
  const { theme } = useTheme();
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

  const plotRef = useRef<HTMLDivElement>(null);
  const [pxWidth, setPxWidth] = useState(800);
  useEffect(() => {
    const el = plotRef.current;
    if (el === null) return;
    const ro = new ResizeObserver(() => {
      if (el.clientWidth > 0) setPxWidth(el.clientWidth);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const { data, penTip, aiTicks } = useTrendWindow(
    controllerId,
    windowSeconds(count, unit),
    pxWidth,
  );

  const exportCsv = useCallback(() => {
    downloadCsv(`${tag}-tendencia.csv`, buildTrendCsv(data, scale));
  }, [data, scale, tag]);

  return (
    <section
      aria-label={`Painel de tendência ${tag}`}
      // Stacked (<1024) the pane keeps its natural height and the page scrolls;
      // shrinking it would let the fixed-height plot overlap the faceplate.
      className="flex min-w-0 flex-col max-lg:shrink-0 lg:min-h-0 lg:flex-1"
    >
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-rule px-3 py-2">
        <div className="flex items-center gap-2">
          <label htmlFor={windowId} className="text-2xs font-medium uppercase tracking-wider text-text-soft">
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
            <SelectTrigger id={unitId} aria-label="Unidade da janela" className="w-32">
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

        <div className="flex items-center gap-2">
          <label htmlFor={autoId} className="text-2xs font-medium uppercase tracking-wider text-text-soft">
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

        <Button size="sm" className="ml-auto" onClick={exportCsv}>
          Exportar CSV
        </Button>
      </div>

      <div ref={plotRef} className="min-h-0 flex-1 p-3">
        <Trend
          data={data}
          ariaLabel={`Tendência ${tag}`}
          pvAxis={autoScale ? { unit: scale.unit } : { min: pvMin, max: pvMax, unit: scale.unit }}
          coAxis={autoScale ? { unit: CO_SCALE.unit } : { min: coMin, max: coMax, unit: CO_SCALE.unit }}
          penTip={penTip}
          aiTicks={aiTicks}
          glow={theme === 'phosphor'}
          height={280}
        />
      </div>
    </section>
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
      <label htmlFor={id} className="text-2xs uppercase tracking-wider text-text-soft">
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
