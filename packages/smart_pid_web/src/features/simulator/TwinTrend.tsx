import { useEffect, useId, useRef, useState } from 'react';
import { Readout } from '@/components/Readout';
import { Input } from '@/components/Field';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/Select';
import { Switch } from '@/components/Switch';
import { Trend } from '@/components/Trend';
import {
  ScaleRange,
  UNIT_LABEL,
  UNIT_SECONDS,
  UNIT_SHORT,
  windowSeconds,
  type TrendWindowUnit,
} from '@/features/dashboard/TrendPanel';
import { useTrendWindow } from '@/features/dashboard/useTrendWindow';
import { formatNumber, formatTimestamp } from '@/lib/format';
import type { StatusData } from '@/lib/envelope';
import { useRealtime } from '@/realtime/useRealtime';
import { useGlowTrace } from '@/theme/useGlowTrace';
import { toTwinPoint, TWIN_WINDOW_SECONDS } from './twinTrend';

export interface TwinTrendProps {
  controllerId: number;
}

const PLOT_HEIGHT = 210;

/** Twin PV/SP/CO are all percentages, so both scale pairs default to 0–100 %. */
const TWIN_SCALE_MIN = 0;
const TWIN_SCALE_MAX = 100;

const CONTROL_LABEL = 'shrink-0 text-2xs uppercase tracking-caps text-text-soft';
const NUMBER_INPUT = 'numeric w-14 px-2 text-sm';

/**
 * Live twin response.
 *
 * The twin publishes on the ordinary STATUS topic, so this reuses the recorder
 * window rather than growing a second buffer: same decimation, same undecimated
 * pen tip, same AI tick marks when a worker intervenes on the model.
 *
 * The header carries the last sample's wall clock on purpose — a dead simulator
 * looks exactly like a settled one on a plot, and the clock is what tells them
 * apart. Time-window and Y-scale controls mirror the dashboard's TrendPanel so
 * an engineer can zoom the same way on both screens.
 */
export function TwinTrend({ controllerId }: TwinTrendProps) {
  const glow = useGlowTrace();
  const plotRef = useRef<HTMLDivElement>(null);
  const [pxWidth, setPxWidth] = useState(800);

  const windowId = useId();
  const unitId = useId();
  const autoId = useId();
  const pvMinId = useId();
  const pvMaxId = useId();
  const coMinId = useId();
  const coMaxId = useId();

  const [unit, setUnit] = useState<TrendWindowUnit>('minuto');
  const [count, setCount] = useState(TWIN_WINDOW_SECONDS / UNIT_SECONDS.minuto);
  const [autoScale, setAutoScale] = useState(true);
  const [pvMin, setPvMin] = useState(TWIN_SCALE_MIN);
  const [pvMax, setPvMax] = useState(TWIN_SCALE_MAX);
  const [coMin, setCoMin] = useState(TWIN_SCALE_MIN);
  const [coMax, setCoMax] = useState(TWIN_SCALE_MAX);

  useEffect(() => {
    const el = plotRef.current;
    if (el === null) return;
    const ro = new ResizeObserver(() => {
      if (el.clientWidth > 0) setPxWidth(el.clientWidth);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const { data, penTip, aiTicks } = useTrendWindow(controllerId, windowSeconds(count, unit), pxWidth);
  const frame = useRealtime<StatusData>(controllerId, 'status').last?.data;
  const point = frame === undefined ? null : toTwinPoint(frame);

  return (
    <section
      aria-label="Twin response trend"
      className="flex min-w-0 flex-col rounded-card border border-rule bg-surface"
    >
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 border-b border-rule px-3 py-2">
        <div className="flex items-center gap-1.5">
          <span aria-hidden="true" className="mb-0.5 inline-block h-0.5 w-2.5 shrink-0 bg-trace-pv" />
          <Readout label="PV" value={point?.pv} unit="%" size="sm" />
        </div>
        <div className="flex items-center gap-1.5">
          <span
            aria-hidden="true"
            className="mb-0.5 inline-block h-0 w-2.5 shrink-0 border-t-2 border-dashed border-trace-sp"
          />
          <Readout label="SP" value={point?.sp} unit="%" size="sm" />
        </div>
        <div className="flex items-center gap-1.5">
          <span aria-hidden="true" className="mb-0.5 inline-block h-0.5 w-2.5 shrink-0 bg-trace-co" />
          <Readout label="CO" value={point?.co} unit="%" size="sm" />
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-2xs font-medium uppercase tracking-wider text-text-soft">
            Última amostra
          </span>
          <span className="numeric text-sm text-text">
            {point === null ? '—' : formatTimestamp(point.x)}
          </span>
        </div>

        <div className="ml-auto flex items-center gap-1.5">
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
          <div className="flex w-full flex-wrap items-center gap-1.5">
            <ScaleRange
              variable="PV"
              minId={pvMinId}
              maxId={pvMaxId}
              min={pvMin}
              max={pvMax}
              onMinChange={setPvMin}
              onMaxChange={setPvMax}
            />
            <ScaleRange
              variable="CO"
              minId={coMinId}
              maxId={coMaxId}
              min={coMin}
              max={coMax}
              onMinChange={setCoMin}
              onMaxChange={setCoMax}
            />
          </div>
        )}
      </div>

      <div ref={plotRef} className="min-w-0 p-3">
        <Trend
          data={data}
          ariaLabel={`Resposta do gêmeo digital — malha ${controllerId}`}
          pvAxis={
            autoScale
              ? { unit: '%', name: 'PV / SP' }
              : { unit: '%', name: 'PV / SP', min: pvMin, max: pvMax }
          }
          coAxis={autoScale ? { unit: '%', name: 'CO' } : { unit: '%', name: 'CO', min: coMin, max: coMax }}
          penTip={penTip}
          aiTicks={aiTicks}
          glow={glow}
          height={PLOT_HEIGHT}
          labels={{
            yTop: autoScale ? undefined : `${formatNumber(pvMax, 1)} %`,
            yBottom: autoScale ? undefined : `${formatNumber(pvMin, 1)} %`,
            time: `−${count} ${UNIT_SHORT[unit]} → agora`,
          }}
        />
      </div>
    </section>
  );
}
