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

/**
 * Build uPlot AlignedData from per-loop ring buffers for the selected signals.
 * The x axis is taken from the first selected loop's buffer (all loops share the
 * same scan cadence in this system); if nothing is selected, x comes from any
 * buffer so the chart still has a time axis.
 */
export function selectSeries(
  buffer: ReadonlyMap<number, LoopBuffer>,
  selection: ReadonlyArray<SignalKey>,
): AlignedSeries {
  const xSourceLoop = selection[0]?.loopId ?? buffer.keys().next().value;
  const x = xSourceLoop != null ? (buffer.get(xSourceLoop)?.t ?? []) : [];
  const data: number[][] = [x.slice()];
  const keys: SignalKey[] = [];

  for (const key of selection) {
    const buf = buffer.get(key.loopId);
    if (!buf) continue;
    data.push(buf[key.variable].slice());
    keys.push(key);
  }
  return { keys, data };
}
