import { useEffect, useMemo, useRef, useState } from 'react';
import uPlot from 'uplot';
import 'uplot/dist/uPlot.min.css';
import { buildUplotTheme, readTrendTokens, type UplotTheme } from '@/lib/uplotTheme';
import { cn } from '@/lib/utils';
import type { TimeSync } from './timeSync';
import { signalLabel, type AlignedSeries, type Signal } from './types';

/**
 * One cell of the multi-trend grid: a single loop's enabled signals over the
 * shared time axis. Every row comes from the same window buffer, so the series
 * cannot drift off the x column.
 *
 * Scale pinning: an untouched chart auto-follows the live window. The first
 * drag-zoom pins it, which (a) publishes the range to the siblings and (b)
 * stops `setData` from resetting scales — live samples must never yank a view
 * the operator just framed. uPlot's dblclick reset releases the pin.
 */

const JSDOM = /jsdom/i;
const CO_SCALE = 'co';
const PV_SCALE = 'pv';

export interface MultiTrendChartProps {
  /** Stable sync identity, e.g. `slot-0`. */
  id: string;
  series: AlignedSeries;
  ariaLabel: string;
  sync?: TimeSync;
  /** Reports the drawable width so the caller can size decimation buckets. */
  onPxWidth?(px: number): void;
  height?: number;
  testId?: string;
  className?: string;
}

function seriesOptions(key: { signal: Signal }, theme: UplotTheme): uPlot.Series {
  if (key.signal === 'sp') {
    return {
      stroke: theme.series.sp.stroke,
      width: theme.series.sp.width,
      dash: theme.series.sp.dash,
      scale: PV_SCALE,
    };
  }
  if (key.signal === 'co') {
    return { stroke: theme.series.co.stroke, width: theme.series.co.width, scale: CO_SCALE };
  }
  return { stroke: theme.series.pv.stroke, width: theme.series.pv.width, scale: PV_SCALE };
}

export function MultiTrendChart({
  id,
  series,
  ariaLabel,
  sync,
  onPxWidth,
  height = 240,
  testId,
  className,
}: MultiTrendChartProps) {
  const hostRef = useRef<HTMLDivElement>(null);
  const plotRef = useRef<uPlot | null>(null);
  const [themeKey, setThemeKey] = useState(0);

  // Read from uPlot hooks without rebuilding the plot when they change.
  const syncRef = useRef(sync);
  syncRef.current = sync;
  const pxRef = useRef(onPxWidth);
  pxRef.current = onPxWidth;
  const pinnedRef = useRef(false);

  const shape = series.keys.map((k) => `${k.loopId}:${k.signal}`).join(',');
  const aligned = useMemo(() => series.data as uPlot.AlignedData, [series.data]);

  useEffect(() => {
    const obs = new MutationObserver(() => setThemeKey((k) => k + 1));
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    return () => obs.disconnect();
  }, []);

  useEffect(() => {
    const el = hostRef.current;
    if (!el || (typeof window !== 'undefined' && JSDOM.test(window.navigator.userAgent))) return;
    const theme = buildUplotTheme(readTrendTokens(getComputedStyle(document.documentElement)));
    const width = el.clientWidth || 640;
    pxRef.current?.(width);

    const axis = {
      stroke: theme.axesStroke,
      font: theme.axisFont,
      grid: { stroke: theme.gridStroke, width: 1 },
      ticks: { stroke: theme.gridStroke, width: 1 },
    };

    const opts: uPlot.Options = {
      width,
      height,
      legend: { show: true, live: true },
      cursor: { x: true, y: true, drag: { x: true, y: false } },
      scales: { x: { time: true }, [PV_SCALE]: {}, [CO_SCALE]: { range: [0, 100] } },
      axes: [
        axis,
        { ...axis, scale: PV_SCALE },
        { ...axis, scale: CO_SCALE, side: 1, grid: { show: false } },
      ],
      series: [
        {},
        ...series.keys.map((key) => ({ label: signalLabel(key), ...seriesOptions(key, theme) })),
      ],
      hooks: {
        // A drag-zoom is the only thing that pins the view; live auto-follow
        // must not publish, or two live charts would fight over the x range.
        setSelect: [() => { pinnedRef.current = true; }],
        setScale: [
          (u, key) => {
            if (key !== 'x' || !pinnedRef.current) return;
            const { min, max } = u.scales.x;
            if (min === undefined || max === undefined) return;
            syncRef.current?.publish(id, { min, max });
          },
        ],
      },
    };

    try {
      plotRef.current = new uPlot(opts, aligned, el);
    } catch {
      /* jsdom has no canvas measure; ignore in tests */
    }

    const release = () => {
      pinnedRef.current = false;
    };
    el.addEventListener('dblclick', release);

    const ro = new ResizeObserver(() => {
      const w = el.clientWidth;
      if (w <= 0) return;
      plotRef.current?.setSize({ width: w, height });
      pxRef.current?.(w);
    });
    ro.observe(el);

    return () => {
      el.removeEventListener('dblclick', release);
      ro.disconnect();
      plotRef.current?.destroy();
      plotRef.current = null;
    };
    // Series COUNT and labels are baked at construction; data flows through setData.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shape, themeKey, height, id]);

  useEffect(() => {
    plotRef.current?.setData(aligned, !pinnedRef.current);
  }, [aligned]);

  useEffect(() => {
    if (!sync) return;
    return sync.register({
      id,
      setX: (range) => {
        pinnedRef.current = true;
        plotRef.current?.setScale('x', { min: range.min, max: range.max });
      },
    });
  }, [sync, id]);

  return (
    <section
      aria-label={ariaLabel}
      data-testid={testId}
      className={cn('flex min-w-0 flex-col border border-rule bg-trend-bg', className)}
    >
      <div ref={hostRef} className="w-full min-w-0" style={{ height }} />
    </section>
  );
}
