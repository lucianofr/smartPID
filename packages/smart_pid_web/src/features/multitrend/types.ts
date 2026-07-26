/**
 * Multi-trend vocabulary (§6.8). The page owns FOUR slots — the 2×2 grid is
 * the hard ceiling on how many controllers may be plotted at once — and each
 * slot independently enables PV, SP and CO.
 */

export type Signal = 'pv' | 'sp' | 'co';

/** Row order inside a slot's aligned columns, and the selector's column order. */
export const SIGNALS: readonly Signal[] = ['pv', 'sp', 'co'];

/** Hard ceiling: four controllers, one per cell of the 2×2 grid. */
export const MAX_SLOTS = 4;

export interface TrendSlot {
  /** null = free cell. */
  controllerId: number | null;
  series: Record<Signal, boolean>;
}

/** One plotted line: a (loop, signal) pair. */
export interface SignalKey {
  loopId: number;
  signal: Signal;
}

/** uPlot AlignedData plus the key of every value row: data[0] = t, data[1..] = keys[0..]. */
export interface AlignedSeries {
  keys: readonly SignalKey[];
  data: number[][];
}

/** Legend/readout name for a line — frozen by the multitrend E2E ("L1 PV"). */
export function signalLabel(key: SignalKey): string {
  return `L${key.loopId} ${key.signal.toUpperCase()}`;
}

export function freeSlot(): TrendSlot {
  return { controllerId: null, series: { pv: false, sp: false, co: false } };
}
