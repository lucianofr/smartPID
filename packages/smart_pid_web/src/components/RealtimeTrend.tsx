import { useEffect, useRef } from 'react';
import uPlot from 'uplot';
import 'uplot/dist/uPlot.min.css';

export type TrendData = [number[], number[], number[], number[]]; // [t, pv, sp, co]

function readToken(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || '#888';
}

export function RealtimeTrend({ data }: { data: TrendData }) {
  const ref = useRef<HTMLDivElement>(null);
  const plot = useRef<uPlot | null>(null);

  useEffect(() => {
    if (!ref.current) return;
    const opts: uPlot.Options = {
      width: ref.current.clientWidth || 600,
      height: 220,
      scales: { x: { time: false }, y: {}, co: { range: [0, 100] } },
      axes: [
        { stroke: readToken('--trend-axis'), grid: { stroke: readToken('--trend-grid') } },
        { stroke: readToken('--trend-axis'), grid: { stroke: readToken('--trend-grid') } },
        { side: 1, scale: 'co', stroke: readToken('--trend-axis'), grid: { show: false } },
      ],
      series: [
        {},
        { label: 'PV', stroke: readToken('--trend-pv'), width: 1.5 },
        { label: 'SP', stroke: readToken('--trend-sp'), width: 1.5, dash: [6, 4] },
        { label: 'CO', stroke: readToken('--trend-co'), width: 1.5, scale: 'co' },
      ],
    };
    try {
      plot.current = new uPlot(opts, data, ref.current);
    } catch {
      /* jsdom has no canvas measure; ignore in tests */
    }
    return () => plot.current?.destroy();
  }, []);

  useEffect(() => {
    plot.current?.setData(data);
  }, [data]);

  return <div ref={ref} style={{ width: '100%', background: 'var(--trend-bg)' }} />;
}
