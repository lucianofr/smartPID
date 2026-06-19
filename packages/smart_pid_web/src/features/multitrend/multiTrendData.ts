import type { StatusData } from '../../realtime/envelope';
import type { SignalKey, Variable } from './types';

export interface LoopBuffer {
  t: number[];
  pv: number[];
  sp: number[];
  co: number[];
}

/** A column-oriented frame for uPlot: data[0] = x (time), data[1..] = each selected series. */
export interface AlignedSeries {
  keys: ReadonlyArray<SignalKey>; // order matches data[1..]
  data: number[][]; // uPlot AlignedData shape
}

/**
 * Read the numeric value of a variable from a live status frame. pv/sp/co arrive
 * as FFSignal objects on the wire (monitor_worker.py / pid_worker.py); the numeric
 * reading lives at `.value`.
 */
export function valueAt(status: StatusData, variable: Variable): number {
  return status[variable].value;
}

/** Keep the newest `k` samples; `k <= 0` yields []. Avoids slice(-0) returning all. */
function tail(arr: ReadonlyArray<number>, k: number): number[] {
  return k > 0 ? arr.slice(arr.length - k) : [];
}

/**
 * Build uPlot AlignedData from per-loop ring buffers for the selected signals.
 * The x axis is taken from the first selected loop's buffer (all loops share the
 * same scan cadence in this system); if nothing is selected, x comes from any
 * buffer so the chart still has a time axis.
 *
 * Per-loop ring buffers diverge in length whenever loops are selected at different
 * times (staggered checkboxes) or when frame coalescing skips one loop but not
 * another. uPlot mode-1 indexes EVERY series by position 0..data[0].length-1, so a
 * shorter row would be plotted against the wrong timestamps. To prevent that silent
 * misalignment, reconcile the x array and all selected rows to a common newest
 * window of length `n` (the min length across them). All loops share the same scan
 * cadence, so their NEWEST samples line up — dropping the OLDEST samples keeps the
 * rows aligned without introducing `null` padding (which would corrupt the numeric
 * min/max done downstream by minMaxDecimate / applyWindow).
 */
export function selectSeries(
  buffer: ReadonlyMap<number, LoopBuffer>,
  selection: ReadonlyArray<SignalKey>,
): AlignedSeries {
  const xSourceLoop = selection[0]?.loopId ?? buffer.keys().next().value;
  const xSource = xSourceLoop != null ? (buffer.get(xSourceLoop)?.t ?? []) : [];

  const rawRows: number[][] = [];
  const keys: SignalKey[] = [];
  for (const key of selection) {
    const buf = buffer.get(key.loopId);
    if (!buf) continue;
    rawRows.push(buf[key.variable]);
    keys.push(key);
  }

  const n =
    rawRows.length > 0
      ? Math.min(xSource.length, ...rawRows.map((r) => r.length))
      : xSource.length;

  const data: number[][] = [tail(xSource, n), ...rawRows.map((r) => tail(r, n))];
  return { keys, data };
}
