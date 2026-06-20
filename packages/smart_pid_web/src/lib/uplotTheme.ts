export interface TrendTokens {
  pv: string; sp: string; co: string;
  grid: string; axis: string; bg: string;
}

export function readTrendTokens(style: CSSStyleDeclaration): TrendTokens {
  const get = (n: string) => style.getPropertyValue(n).trim();
  return {
    pv: get('--trend-pv'), sp: get('--trend-sp'), co: get('--trend-co'),
    grid: get('--trend-grid'), axis: get('--trend-axis'), bg: get('--trend-bg'),
  };
}

export function buildUplotTheme(tokens: TrendTokens) {
  return {
    axesStroke: tokens.axis,
    gridStroke: tokens.grid,
    bg: tokens.bg,
    series: {
      pv: { stroke: tokens.pv, width: 1.5 },
      sp: { stroke: tokens.sp, width: 1.5, dash: [6, 4] },
      co: { stroke: tokens.co, width: 1.5, scale: 'co' },
    },
  };
}
