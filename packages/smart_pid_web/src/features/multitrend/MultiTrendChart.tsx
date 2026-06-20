import { useEffect, useRef, useState } from 'react';
import uPlot from 'uplot';
import 'uplot/dist/uPlot.min.css';
import type { AlignedSeries } from './multiTrendData';
import { seriesColor, seriesStroke } from './signals';

function readToken(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || '#888';
}

interface Props {
  series: AlignedSeries;
  onPxWidth: (px: number) => void;
}

export function MultiTrendChart({ series, onPxWidth }: Props): JSX.Element {
  const ref = useRef<HTMLDivElement>(null);
  const plot = useRef<uPlot | null>(null);
  const [themeKey, setThemeKey] = useState(0);

  useEffect(() => {
    const obs = new MutationObserver(() => setThemeKey((k) => k + 1));
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    return () => obs.disconnect();
  }, []);

  useEffect(() => {
    if (!ref.current) return;
    const el = ref.current;
    const width = el.clientWidth || 800;
    const height = el.clientHeight || 360;
    onPxWidth(width);

    const uSeries: uPlot.Series[] = [
      {}, // x
      ...series.keys.map((k) => ({
        label: `L${k.loopId} ${k.variable.toUpperCase()}`,
        stroke: seriesStroke(seriesColor(k)),
        width: 1.5,
        dash: k.variable === 'sp' ? [6, 4] : undefined, // SP dashed (no color-only encoding)
        scale: k.variable === 'co' ? 'co' : 'pv',
        points: { show: false },
      })),
    ];

    const opts: uPlot.Options = {
      width,
      height,
      series: uSeries,
      scales: { x: { time: false }, pv: {}, co: { range: [0, 100] } },
      axes: [
        { stroke: readToken('--trend-axis'), grid: { stroke: readToken('--trend-grid') } },
        { scale: 'pv', stroke: readToken('--trend-axis'), grid: { stroke: readToken('--trend-grid') } },
        { scale: 'co', side: 1, stroke: readToken('--trend-axis'), grid: { show: false } },
      ],
      cursor: { drag: { x: true, y: false } },
      legend: { live: true },
    };

    try {
      plot.current = new uPlot(opts, series.data as uPlot.AlignedData, el);
    } catch {
      /* jsdom has no canvas measure; ignore in tests */
    }
    return () => {
      plot.current?.destroy();
      plot.current = null;
    };
    // Re-create on series-shape change OR theme change (themeKey); data updates handled below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [series.keys.map((k) => `${k.loopId}:${k.variable}`).join(','), themeKey]);

  useEffect(() => {
    plot.current?.setData(series.data as uPlot.AlignedData);
  }, [series.data]);

  return (
    <div
      ref={ref}
      data-testid="multitrend-chart"
      style={{ width: '100%', height: '100%', background: 'var(--trend-bg)' }}
    />
  );
}
