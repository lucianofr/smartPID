/**
 * uPlot token bridge (§7, retained pattern re-pointed at the §6.4 names:
 * --trace-* for series, --trend-* for chart chrome). uPlot bakes stroke colors
 * at construction — Trend pairs this with themeKey re-instantiation.
 */
export interface TrendTokens {
  pv: string;
  sp: string;
  co: string;
  grid: string;
  axis: string;
  bg: string;
  /** --accent: AI intervention ticks (§6.7) — interactive chrome, never a trace/alarm color. */
  accent: string;
  /** Per-series line weights (CSS px) from --trend-*-width ('2px' → 2). */
  pvWidth: number;
  spWidth: number;
  coWidth: number;
  /**
   * SP dash pattern from --trend-sp-dash. §6.3 gives Recorder/Phosphor a dashed
   * graphite SP ('6 4') while ISA-101 keeps a SOLID blue SP ('none' → []).
   */
  spDash: number[];
  /** Axis label font shorthand, derived from --font-data. */
  font: string;
}

const DEFAULT_LINE_WIDTH = 1.5;
const AXIS_FONT_PX = 12;

function readWidth(style: CSSStyleDeclaration, name: string): number {
  const raw = Number.parseFloat(style.getPropertyValue(name));
  return Number.isFinite(raw) && raw > 0 ? raw : DEFAULT_LINE_WIDTH;
}

/** '6 4' → [6, 4]; 'none' / '' / garbage → [] (uPlot renders a solid stroke). */
function readDash(style: CSSStyleDeclaration, name: string): number[] {
  const raw = style.getPropertyValue(name).trim();
  if (raw === '' || raw === 'none') return [];
  const parts = raw.split(/[\s,]+/).map(Number);
  return parts.every((n) => Number.isFinite(n) && n > 0) ? parts : [];
}

export function readTrendTokens(style: CSSStyleDeclaration): TrendTokens {
  const get = (n: string) => style.getPropertyValue(n).trim();
  const fontFamily = get('--font-data') || 'ui-monospace, monospace';
  return {
    pv: get('--trace-pv'),
    sp: get('--trace-sp'),
    co: get('--trace-co'),
    grid: get('--trend-grid'),
    axis: get('--trend-axis'),
    bg: get('--trend-bg'),
    accent: get('--accent'),
    pvWidth: readWidth(style, '--trend-pv-width'),
    spWidth: readWidth(style, '--trend-sp-width'),
    coWidth: readWidth(style, '--trend-co-width'),
    spDash: readDash(style, '--trend-sp-dash'),
    font: `${AXIS_FONT_PX}px ${fontFamily}`,
  };
}

export interface UplotTheme {
  axesStroke: string;
  gridStroke: string;
  bg: string;
  accent: string;
  axisFont: string;
  series: {
    pv: { stroke: string; width: number };
    sp: { stroke: string; width: number; dash: number[] };
    co: { stroke: string; width: number; scale: 'co' };
  };
}

export function buildUplotTheme(tokens: TrendTokens): UplotTheme {
  return {
    axesStroke: tokens.axis,
    gridStroke: tokens.grid,
    bg: tokens.bg,
    accent: tokens.accent,
    axisFont: tokens.font,
    series: {
      pv: { stroke: tokens.pv, width: tokens.pvWidth },
      sp: { stroke: tokens.sp, width: tokens.spWidth, dash: tokens.spDash },
      co: { stroke: tokens.co, width: tokens.coWidth, scale: 'co' },
    },
  };
}