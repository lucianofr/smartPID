import type { SignalKey, Variable, WindowConfig } from './types';

/** Design-system §7.2: sliding window default ~600 pts / ~60 s. */
export const DEFAULT_WINDOW: WindowConfig = { maxPoints: 600, maxSeconds: 60 };

const TOKEN_BY_VARIABLE: Record<Variable, string> = {
  pv: '--trend-pv',
  sp: '--trend-sp',
  co: '--trend-co',
};

export function signalId(key: SignalKey): string {
  return `${key.loopId}:${key.variable}`;
}

export function parseSignalId(id: string): SignalKey {
  const [loop, variable] = id.split(':');
  return { loopId: Number(loop), variable: variable as Variable };
}

export interface SeriesColor {
  /** The CSS token var the series inherits (no new colors invented). */
  tokenVar: string;
  /**
   * Per-loop lightness offset (%) applied to the token base so loops are
   * tonally distinguishable (light→dark within the same hue), per §5.9.
   * Deterministic: loop 1 = 0, then ±step alternating, clamped.
   */
  lightnessPct: number;
}

/** CSS expression usable directly as a uPlot stroke. */
export function seriesStroke(color: SeriesColor): string {
  // color-mix keeps the theme token as the hue source; only lightness varies.
  const pct = color.lightnessPct;
  const towards = pct >= 0 ? 'white' : 'black';
  return `color-mix(in oklch, var(${color.tokenVar}), ${towards} ${Math.abs(pct)}%)`;
}

export function seriesColor(key: SignalKey): SeriesColor {
  const tokenVar = TOKEN_BY_VARIABLE[key.variable];
  // loop 1 → 0, loop 2 → -12, loop 3 → +12, loop 4 → -24, ... (clamped to ±48)
  const n = key.loopId - 1;
  const magnitude = Math.min(48, Math.ceil(n / 2) * 12);
  const sign = n % 2 === 1 ? -1 : 1;
  const lightnessPct = n === 0 ? 0 : sign * magnitude;
  return { tokenVar, lightnessPct };
}
