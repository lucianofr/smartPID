import { useEffect, useMemo, useRef, useState } from 'react';
import uPlot from 'uplot';
import 'uplot/dist/uPlot.min.css';
import { buildUplotTheme, readTrendTokens, type UplotTheme } from '@/lib/uplotTheme';
import { cn } from '@/lib/utils';

export interface TrendSeriesData {
  /** Aligned columns: unix-second timestamps + one value column per series. */
  t: number[];
  pv: (number | null)[];
  sp: (number | null)[];
  co: (number | null)[];
}

export interface TrendAxisConfig {
  min?: number;
  max?: number;
  unit?: string;
}

export interface TrendPenTip {
  t: number;
  pv: number;
}

export interface TrendProps {
  data: TrendSeriesData;
  /** Accessible name — pt-BR at call sites (e.g. "Tendência FIC-101"). */
  ariaLabel: string;
  /** Left axis (PV/SP). Auto-range when min/max omitted. */
  pvAxis?: TrendAxisConfig;
  /** Right axis (CO). Defaults 0–100 (valve %). */
  coAxis?: TrendAxisConfig;
  /**
   * §6.7 pen tip: the TRUE latest sample — NOT the tail of the decimated series.
   * Phase 3's windowBuffer exposes the undecimated head; null/undefined hides the pen.
   * A static marker by construction — under prefers-reduced-motion nothing animates.
   */
  penTip?: TrendPenTip | null;
  /** AI intervention timestamps (unix seconds) ticked on the time axis (§6.7). */
  aiTicks?: readonly number[];
  /** Phosphor halo pass on PV (§6.7). Caller decides (phase 4: theme === 'phosphor'). */
  glow?: boolean;
  height?: number;
  className?: string;
}

const PEN_RADIUS_PX = 3.5;
const AI_TICK_PX = 6;

function drawPenTip(u: uPlot, tip: TrendPenTip, color: string): void {
  const x = u.valToPos(tip.t, 'x', true);
  const y = u.valToPos(tip.pv, 'y', true);
  const ctx = u.ctx;
  ctx.save();
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.arc(x, y, PEN_RADIUS_PX * uPlot.pxRatio, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
}

function drawAiTicks(u: uPlot, ticks: readonly number[], color: string): void {
  const ctx = u.ctx;
  const min = u.scales.x.min ?? Number.NEGATIVE_INFINITY;
  const max = u.scales.x.max ?? Number.POSITIVE_INFINITY;
  const y0 = u.bbox.top + u.bbox.height;
  ctx.save();
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.5 * uPlot.pxRatio;
  for (const t of ticks) {
    if (t < min || t > max) continue;
    const x = u.valToPos(t, 'x', true);
    ctx.beginPath();
    ctx.moveTo(x, y0);
    ctx.lineTo(x, y0 - AI_TICK_PX * uPlot.pxRatio);
    ctx.stroke();
  }
  ctx.restore();
}

/**
 * §6.7 Phosphor halo: re-stroke the PV path 2× wider at low alpha, then crisp
 * on top. ctx.shadowBlur is BANNED from the per-frame path (cost scales with
 * path length × radius at 60 fps) — never introduce it here.
 */
function drawHalo(u: uPlot, seriesIdx: number, theme: UplotTheme): void {
  const paths = (u.series[seriesIdx] as { _paths?: { stroke?: Path2D | null } })._paths;
  const stroke = paths?.stroke;
  if (!stroke) return;
  const ctx = u.ctx;
  const w = theme.series.pv.width * uPlot.pxRatio;
  ctx.save();
  ctx.strokeStyle = theme.series.pv.stroke;
  ctx.globalAlpha = 0.16;
  ctx.lineWidth = w * 3.5;
  ctx.stroke(stroke);
  ctx.globalAlpha = 0.3;
  ctx.lineWidth = w * 2;
  ctx.stroke(stroke);
  ctx.globalAlpha = 1;
  ctx.lineWidth = w;
  ctx.stroke(stroke);
  ctx.restore();
}

export function Trend({
  data,
  ariaLabel,
  pvAxis,
  coAxis,
  penTip,
  aiTicks,
  glow = false,
  height = 280,
  className,
}: TrendProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const plotRef = useRef<uPlot | null>(null);
  const [themeKey, setThemeKey] = useState(0);

  // Latest values readable from draw hooks without rebuilding the plot.
  const themeRef = useRef<UplotTheme | null>(null);
  const penTipRef = useRef<TrendPenTip | null>(penTip ?? null);
  const aiTicksRef = useRef<readonly number[]>(aiTicks ?? []);
  const glowRef = useRef(glow);
  penTipRef.current = penTip ?? null;
  aiTicksRef.current = aiTicks ?? [];
  glowRef.current = glow;

  const aligned = useMemo(
    () => [data.t, data.pv, data.sp, data.co] as uPlot.AlignedData,
    [data],
  );

  // uPlot bakes stroke colors at construction: rebuild on data-theme flips.
  useEffect(() => {
    const obs = new MutationObserver(() => setThemeKey((k) => k + 1));
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    return () => obs.disconnect();
  }, []);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const theme = buildUplotTheme(readTrendTokens(getComputedStyle(document.documentElement)));
    themeRef.current = theme;

    const opts: uPlot.Options = {
      width: el.clientWidth || 640,
      height,
      legend: { show: false },
      cursor: { x: true, y: true },
      scales: {
        x: { time: true },
        y:
          pvAxis?.min !== undefined && pvAxis?.max !== undefined
            ? { range: [pvAxis.min, pvAxis.max] }
            : {},
        co: { range: [coAxis?.min ?? 0, coAxis?.max ?? 100] },
      },
      axes: [
        {
          stroke: theme.axesStroke,
          font: theme.axisFont,
          grid: { stroke: theme.gridStroke, width: 1 },
          ticks: { stroke: theme.gridStroke, width: 1 },
        },
        {
          label: pvAxis?.unit,
          stroke: theme.axesStroke,
          font: theme.axisFont,
          grid: { stroke: theme.gridStroke, width: 1 },
          ticks: { stroke: theme.gridStroke, width: 1 },
        },
        {
          side: 1,
          scale: 'co',
          label: coAxis?.unit ?? '%',
          stroke: theme.axesStroke,
          font: theme.axisFont,
          grid: { show: false },
          ticks: { stroke: theme.gridStroke, width: 1 },
        },
      ],
      series: [
        {},
        { label: 'PV', stroke: theme.series.pv.stroke, width: theme.series.pv.width },
        { label: 'SP', stroke: theme.series.sp.stroke, width: theme.series.sp.width, dash: theme.series.sp.dash },
        { label: 'CO', stroke: theme.series.co.stroke, width: theme.series.co.width, scale: 'co' },
      ],
      hooks: {
        drawSeries: [
          (u, si) => {
            if (si === 1 && glowRef.current && themeRef.current) drawHalo(u, si, themeRef.current);
          },
        ],
        draw: [
          (u) => {
            const t = themeRef.current;
            if (!t) return;
            if (aiTicksRef.current.length > 0) drawAiTicks(u, aiTicksRef.current, t.accent);
            const tip = penTipRef.current;
            if (tip) drawPenTip(u, tip, t.series.pv.stroke);
          },
        ],
      },
    };

    try {
      plotRef.current = new uPlot(opts, aligned, el);
    } catch {
      /* jsdom has no canvas measure; ignore in tests */
    }

    const ro = new ResizeObserver(() => {
      const w = el.clientWidth;
      if (w > 0) plotRef.current?.setSize({ width: w, height });
    });
    ro.observe(el);

    return () => {
      ro.disconnect();
      plotRef.current?.destroy();
      plotRef.current = null;
    };
    // Rebuild on theme flips / geometry / axis config; data updates go through setData below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [themeKey, height, pvAxis?.min, pvAxis?.max, coAxis?.min, coAxis?.max]);

  useEffect(() => {
    plotRef.current?.setData(aligned);
  }, [aligned]);

  // Pen tip / AI ticks / glow changes need only a redraw, not a rebuild.
  useEffect(() => {
    plotRef.current?.redraw();
  }, [penTip, aiTicks, glow]);

  return (
    <div
      ref={containerRef}
      role="img"
      aria-label={ariaLabel}
      data-theme-key={themeKey}
      className={cn('w-full bg-trend-bg', className)}
      style={{ height }}
    />
  );
}