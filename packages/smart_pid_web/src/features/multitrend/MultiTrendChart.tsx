import { useEffect, useRef, useState } from 'react';
import uPlot from 'uplot';
import 'uplot/dist/uPlot.min.css';
import type { AlignedSeries } from './multiTrendData';
import { seriesColor, seriesStroke } from './signals';
import { buildUplotTheme, readTrendTokens } from '../../lib/uplotTheme';

interface Props {
  series: AlignedSeries;
  onPxWidth: (px: number) => void;
}

interface ReadoutCell {
  label: string;
  value: string;
}

function fmt(value: number | null | undefined): string {
  return value == null ? '—' : value.toFixed(2);
}

export function MultiTrendChart({ series, onPxWidth }: Props): JSX.Element {
  const ref = useRef<HTMLDivElement>(null);
  const plot = useRef<uPlot | null>(null);
  const [themeKey, setThemeKey] = useState(0);
  const [readout, setReadout] = useState<ReadoutCell[]>([]);

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

    const theme = buildUplotTheme(readTrendTokens(getComputedStyle(document.documentElement)));
    const labels = series.keys.map((k) => `L${k.loopId} ${k.variable.toUpperCase()}`);
    const weightFor = (variable: string): number =>
      variable === 'sp' ? theme.series.sp.width : variable === 'co' ? theme.series.co.width : theme.series.pv.width;

    const uSeries: uPlot.Series[] = [
      {}, // x
      ...series.keys.map((k, i) => ({
        label: labels[i],
        stroke: seriesStroke(seriesColor(k)),
        width: weightFor(k.variable),
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
        { stroke: theme.axesStroke, font: theme.axisFont, grid: { stroke: theme.gridStroke } },
        { scale: 'pv', stroke: theme.axesStroke, font: theme.axisFont, grid: { stroke: theme.gridStroke } },
        { scale: 'co', side: 1, stroke: theme.axesStroke, font: theme.axisFont, grid: { show: false } },
      ],
      cursor: { ...theme.cursor, drag: { x: true, y: false } },
      legend: { live: true },
      hooks: {
        setCursor: [
          (u) => {
            const idx = u.cursor.idx;
            if (idx == null) {
              setReadout([]);
              return;
            }
            setReadout(labels.map((label, i) => ({ label, value: fmt(u.data[i + 1]?.[idx]) })));
          },
        ],
      },
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
    <div className="flex h-full w-full flex-col bg-surface border border-border">
      <div
        ref={ref}
        data-testid="multitrend-chart"
        className="min-h-0 w-full flex-1"
        style={{ background: 'var(--trend-bg)' }}
      />
      <dl
        data-testid="multitrend-readout"
        aria-label="Trend cursor readout"
        className="numeric flex flex-wrap gap-x-4 gap-y-0.5 border-t border-border px-3 py-1.5 text-text-secondary"
        style={{ fontSize: 'var(--text-xs)' }}
      >
        {readout.length === 0 ? (
          <span className="text-text-secondary">Hover to read values</span>
        ) : (
          readout.map((cell) => (
            <span key={cell.label} className="inline-flex gap-1.5">
              <dt>{cell.label}</dt>
              <dd className="text-text">{cell.value}</dd>
            </span>
          ))
        )}
      </dl>
    </div>
  );
}
