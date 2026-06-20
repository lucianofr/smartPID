import { useEffect, useRef, useState } from 'react';
import uPlot from 'uplot';
import 'uplot/dist/uPlot.min.css';
import { buildUplotTheme, readTrendTokens } from '../lib/uplotTheme';

export type TrendData = [number[], number[], number[], number[]]; // [t, pv, sp, co]

interface Readout {
  pv: number | null;
  sp: number | null;
  co: number | null;
}

const EMPTY_READOUT: Readout = { pv: null, sp: null, co: null };

function fmt(value: number | null): string {
  return value == null ? '—' : value.toFixed(2);
}

export function RealtimeTrend({ data }: { data: TrendData }) {
  const ref = useRef<HTMLDivElement>(null);
  const plot = useRef<uPlot | null>(null);
  const [themeKey, setThemeKey] = useState(0);
  const [readout, setReadout] = useState<Readout>(EMPTY_READOUT);

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
      cursor: theme.cursor,
      axes: [
        { stroke: theme.axesStroke, font: theme.axisFont, grid: { stroke: theme.gridStroke } },
        { stroke: theme.axesStroke, font: theme.axisFont, grid: { stroke: theme.gridStroke } },
        { side: 1, scale: 'co', stroke: theme.axesStroke, font: theme.axisFont, grid: { show: false } },
      ],
      series: [
        {},
        { label: 'PV', ...theme.series.pv },
        { label: 'SP', ...theme.series.sp },
        { label: 'CO', ...theme.series.co },
      ],
      hooks: {
        setCursor: [
          (u) => {
            const idx = u.cursor.idx;
            if (idx == null) {
              setReadout(EMPTY_READOUT);
              return;
            }
            setReadout({
              pv: u.data[1]?.[idx] ?? null,
              sp: u.data[2]?.[idx] ?? null,
              co: u.data[3]?.[idx] ?? null,
            });
          },
        ],
      },
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

  return (
    <div className="bg-surface border border-border">
      <div ref={ref} className="w-full" style={{ background: 'var(--trend-bg)' }} />
      <dl
        data-testid="trend-readout"
        aria-label="Trend cursor readout"
        className="numeric grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 border-t border-border px-3 py-1.5 text-text-secondary"
        style={{ fontSize: 'var(--text-xs)' }}
      >
        <dt>PV</dt>
        <dd className="text-right text-text">{fmt(readout.pv)}</dd>
        <dt>SP</dt>
        <dd className="text-right text-text">{fmt(readout.sp)}</dd>
        <dt>CO</dt>
        <dd className="text-right text-text">{fmt(readout.co)}</dd>
      </dl>
    </div>
  );
}
