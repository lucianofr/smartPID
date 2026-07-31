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
  /** What the axis measures, e.g. "PV / SP" or "CO" — rendered alongside `unit`. */
  name?: string;
}

/** Combines `name` + `unit` into one uPlot axis label, e.g. "PV / SP (%)". */
function axisLabel(cfg: TrendAxisConfig | undefined): string | undefined {
  if (cfg?.name && cfg?.unit) return `${cfg.name} (${cfg.unit})`;
  return cfg?.name ?? cfg?.unit;
}

export interface TrendPenTip {
  t: number;
  pv: number;
}

/** Micro-labels in the well's padding band (§6.9), all optional. */
export interface TrendWellLabels {
  /** Upper y bound, top-left. Omit when the plot is auto-scaled — an unknown
   *  bound printed as a number is a lie the operator cannot audit. */
  yTop?: string;
  /** Lower y bound, bottom-left. */
  yBottom?: string;
  /** Time ruler, bottom-right (e.g. "30 min → agora"). */
  time?: string;
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
  /** Static halo pass on PV (§6.7). Caller decides from `--glow-trace` (§10.5). */
  glow?: boolean;
  /** Canvas height in CSS px. The well adds `TREND_WELL_CHROME_PX` around it. */
  height?: number;
  labels?: TrendWellLabels;
  className?: string;
}

const PEN_RADIUS_PX = 3.5;
const AI_TICK_PX = 6;

/**
 * Padding the sunken well adds around the canvas — `p-3.5` is uniform, so the
 * same number applies on both axes. Exported so a caller sizing the plot from a
 * measured container subtracts the real inset instead of hard-coding a
 * duplicate of this class that silently drifts when the padding changes.
 */
export const TREND_WELL_INSET_PX = 28;

/**
 * §6.9 PV area fade. The stops are the RESOLVED `--trace-pv` value with an
 * 8-digit alpha suffix appended, so no color ever enters this file — the token
 * remains the single source. Themes author the traces as 6-digit hex; anything
 * else (a future wide-gamut theme) skips the fill rather than guessing at a
 * conversion, which is why this returns a falsy fill style instead of throwing.
 */
const AREA_ALPHA_TOP = '33'; // ≈20%
const AREA_ALPHA_BOTTOM = '00'; // fully transparent
const SIX_DIGIT_HEX = /^#[0-9a-f]{6}$/i;

function withAlpha(color: string, alphaSuffix: string): string | null {
  const trimmed = color.trim();
  return SIX_DIGIT_HEX.test(trimmed) ? `${trimmed}${alphaSuffix}` : null;
}

function pvAreaFill(u: uPlot, pvStroke: string): CanvasGradient | string {
  const top = withAlpha(pvStroke, AREA_ALPHA_TOP);
  const bottom = withAlpha(pvStroke, AREA_ALPHA_BOTTOM);
  if (top === null || bottom === null) return '';
  // uPlot's context works in device pixels, and bbox is already scaled.
  const gradient = u.ctx.createLinearGradient(0, u.bbox.top, 0, u.bbox.top + u.bbox.height);
  gradient.addColorStop(0, top);
  gradient.addColorStop(1, bottom);
  return gradient;
}

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
 * §6.7 halo: re-stroke the PV path 2× wider at low alpha, then crisp
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

const WELL_LABEL = 'numeric pointer-events-none absolute text-2xs leading-none text-text-soft';

export function Trend({
  data,
  ariaLabel,
  pvAxis,
  coAxis,
  penTip,
  aiTicks,
  glow = false,
  height = 280,
  labels,
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
    if (!el || (typeof window !== 'undefined' && /jsdom/i.test(window.navigator.userAgent))) return;
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
          label: axisLabel(pvAxis),
          stroke: theme.axesStroke,
          font: theme.axisFont,
          grid: { stroke: theme.gridStroke, width: 1 },
          ticks: { stroke: theme.gridStroke, width: 1 },
        },
        {
          side: 1,
          scale: 'co',
          label: axisLabel(coAxis) ?? '%',
          stroke: theme.axesStroke,
          font: theme.axisFont,
          grid: { show: false },
          ticks: { stroke: theme.gridStroke, width: 1 },
        },
      ],
      series: [
        {},
        {
          label: 'PV',
          stroke: theme.series.pv.stroke,
          width: theme.series.pv.width,
          // Re-read per draw so a resize re-derives the gradient geometry.
          fill: (u) => pvAreaFill(u, theme.series.pv.stroke),
        },
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

  /**
   * Pen tip / AI ticks / glow are painted by the `draw` hook, so a bare repaint
   * is all they need — and it MUST be `redraw(false)`.
   *
   * `redraw()` (rebuildPaths defaulted on) synchronously re-issues
   * `setScale('x', scales.x.min, scales.x.max)`, which overwrites the x range
   * `setData` queued one effect earlier (uPlot commits on a microtask, so the
   * good range is still pending when this effect runs). The plot is built
   * before the first realtime frame, so that pending-clobbering range is
   * `[null, null]` — and uPlot's `snapTimeX` maps a null range straight back to
   * `[null, null]`, so the x scale can never re-acquire one. Every
   * `valToPosX()` then returns NaN and the canvas paints nothing at all.
   */
  useEffect(() => {
    plotRef.current?.redraw(false);
  }, [penTip, aiTicks, glow]);

  return (
    <div
      role="img"
      aria-label={ariaLabel}
      data-theme-key={themeKey}
      data-glow={glow ? 'on' : 'off'}
      // The §6.9 sunken well. The micro-labels live in the padding band, not
      // over the plot: uPlot draws real axes inside the canvas and an overlay
      // there would collide with its own tick labels.
      //
      // `max-h-full` is load-bearing, not defensive tidying. The well's height
      // is content-driven (`TREND_WELL_INSET_PX` + the canvas), so a caller
      // whose canvas height exceeds the box it measured — any floor that
      // outbids a cramped flex remainder — used to render a well TALLER than
      // its container. That overflow escaped the card's content box, painted
      // its `bg-surface-sunk` straight over the card's own bottom border (a
      // descendant background paints after an ancestor's border), and was
      // finally cut by the nearest `overflow-hidden` ancestor — which took the
      // bottom-anchored micro-labels with it. Clamping here keeps the padding
      // band, and therefore every label in it, inside the box the layout
      // actually granted; the pre-existing `overflow-hidden` then absorbs the
      // squeeze on the canvas, which is the one part that degrades gracefully.
      className={cn(
        'relative max-h-full w-full overflow-hidden rounded-well bg-surface-sunk p-3.5',
        className,
      )}
    >
      {labels?.yTop ? <span className={cn(WELL_LABEL, 'left-3.5 top-1')}>{labels.yTop}</span> : null}
      {labels?.yBottom ? (
        <span className={cn(WELL_LABEL, 'bottom-1 left-3.5')}>{labels.yBottom}</span>
      ) : null}
      {labels?.time ? (
        <span className={cn(WELL_LABEL, 'bottom-1 right-3.5')}>{labels.time}</span>
      ) : null}
      <div ref={containerRef} className="w-full bg-trend-bg" style={{ height }} />
    </div>
  );
}
