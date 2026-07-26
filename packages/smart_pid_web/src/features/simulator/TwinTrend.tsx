import { useEffect, useRef, useState } from 'react';
import { Readout } from '@/components/Readout';
import { Trend } from '@/components/Trend';
import { useTrendWindow } from '@/features/dashboard/useTrendWindow';
import { formatTimestamp } from '@/lib/format';
import type { StatusData } from '@/lib/envelope';
import { useRealtime } from '@/realtime/useRealtime';
import { useTheme } from '@/theme/ThemeProvider';
import { toTwinPoint, TWIN_WINDOW_SECONDS } from './twinTrend';

export interface TwinTrendProps {
  controllerId: number;
}

const PLOT_HEIGHT = 320;

/**
 * Live twin response.
 *
 * The twin publishes on the ordinary STATUS topic, so this reuses the recorder
 * window rather than growing a second buffer: same decimation, same undecimated
 * pen tip, same AI tick marks when a worker intervenes on the model.
 *
 * The header carries the last sample's wall clock on purpose — a dead simulator
 * looks exactly like a settled one on a plot, and the clock is what tells them
 * apart.
 */
export function TwinTrend({ controllerId }: TwinTrendProps) {
  const { theme } = useTheme();
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

  const { data, penTip, aiTicks } = useTrendWindow(controllerId, TWIN_WINDOW_SECONDS, pxWidth);
  const frame = useRealtime<StatusData>(controllerId, 'status').last?.data;
  const point = frame === undefined ? null : toTwinPoint(frame);

  return (
    <section
      aria-label="Twin response trend"
      className="flex min-w-0 flex-col rounded-card border border-rule bg-surface"
    >
      <header className="flex flex-wrap items-end gap-x-6 gap-y-2 border-b border-rule px-3 py-2">
        <Readout label="PV" value={point?.pv} unit="%" size="sm" />
        <Readout label="SP" value={point?.sp} unit="%" size="sm" />
        <Readout label="CO" value={point?.co} unit="%" size="sm" />
        <div className="ml-auto flex flex-col gap-0.5">
          <span className="text-2xs font-medium uppercase tracking-wider text-text-soft">
            Última amostra
          </span>
          <span className="numeric text-sm text-text">
            {point === null ? '—' : formatTimestamp(point.x)}
          </span>
        </div>
      </header>
      <div ref={plotRef} className="min-w-0 p-3">
        <Trend
          data={data}
          ariaLabel={`Resposta do gêmeo digital — malha ${controllerId}`}
          pvAxis={{ unit: '%' }}
          coAxis={{ unit: '%' }}
          penTip={penTip}
          aiTicks={aiTicks}
          glow={theme === 'phosphor'}
          height={PLOT_HEIGHT}
        />
      </div>
    </section>
  );
}
