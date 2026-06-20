import { useEffect, useRef, useState } from 'react';
import uPlot from 'uplot';
import 'uplot/dist/uPlot.min.css';
import { buildUplotTheme, readTrendTokens } from '../lib/uplotTheme';

export type TrendData = [number[], number[], number[], number[]]; // [t, pv, sp, co]

export function RealtimeTrend({ data }: { data: TrendData }) {
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
    const theme = buildUplotTheme(readTrendTokens(getComputedStyle(document.documentElement)));
    const opts: uPlot.Options = {
      width: ref.current.clientWidth || 600,
      height: 220,
      scales: { x: { time: false }, y: {}, co: { range: [0, 100] } },
      axes: [
        { stroke: theme.axesStroke, grid: { stroke: theme.gridStroke } },
        { stroke: theme.axesStroke, grid: { stroke: theme.gridStroke } },
        { side: 1, scale: 'co', stroke: theme.axesStroke, grid: { show: false } },
      ],
      series: [
        {},
        { label: 'PV', ...theme.series.pv },
        { label: 'SP', ...theme.series.sp },
        { label: 'CO', ...theme.series.co },
      ],
    };
    try {
      plot.current = new uPlot(opts, data, ref.current);
    } catch {
      /* jsdom has no canvas measure; ignore in tests */
    }
    return () => plot.current?.destroy();
    // init: create plot on mount + on theme change (themeKey); data updates handled by setData effect below
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [themeKey]);

  useEffect(() => {
    plot.current?.setData(data);
  }, [data]);

  return <div ref={ref} style={{ width: '100%', background: 'var(--trend-bg)' }} />;
}
