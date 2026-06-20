export interface TrendTokens {
  pv: string; sp: string; co: string;
  grid: string; axis: string; bg: string;
  /** Per-series line weights (CSS px), read from --trend-*-width tokens. */
  pvWidth: number; spWidth: number; coWidth: number;
  /** Axis label font shorthand, derived from --font-data. */
  font: string;
}

const DEFAULT_LINE_WIDTH = 1.5;
const AXIS_FONT_PX = 12;

function readWidth(style: CSSStyleDeclaration, name: string): number {
  const raw = Number.parseFloat(style.getPropertyValue(name));
  return Number.isFinite(raw) && raw > 0 ? raw : DEFAULT_LINE_WIDTH;
}

export function readTrendTokens(style: CSSStyleDeclaration): TrendTokens {
  const get = (n: string) => style.getPropertyValue(n).trim();
  const fontFamily = get('--font-data') || 'ui-monospace, monospace';
  return {
    pv: get('--trend-pv'), sp: get('--trend-sp'), co: get('--trend-co'),
    grid: get('--trend-grid'), axis: get('--trend-axis'), bg: get('--trend-bg'),
    pvWidth: readWidth(style, '--trend-pv-width'),
    spWidth: readWidth(style, '--trend-sp-width'),
    coWidth: readWidth(style, '--trend-co-width'),
    font: `${AXIS_FONT_PX}px ${fontFamily}`,
  };
}

export function buildUplotTheme(tokens: TrendTokens) {
  return {
    axesStroke: tokens.axis,
    gridStroke: tokens.grid,
    bg: tokens.bg,
    /** Axis label/tick font shorthand for uPlot `axes[*].font`. */
    axisFont: tokens.font,
    /** Thin crosshair on both axes (§6d). */
    cursor: { x: true, y: true } as const,
    series: {
      pv: { stroke: tokens.pv, width: tokens.pvWidth },
      sp: { stroke: tokens.sp, width: tokens.spWidth, dash: [6, 4] },
      co: { stroke: tokens.co, width: tokens.coWidth, scale: 'co' },
    },
  };
}
