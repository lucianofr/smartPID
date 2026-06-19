import { useEffect, useMemo, useRef, useState } from 'react';
import { useRealtime } from '../../realtime/useRealtime';
import { selectSeries, valueAt, type AlignedSeries, type LoopBuffer } from './multiTrendData';
import { applyWindow, minMaxDecimate } from './decimate';
import { DEFAULT_WINDOW } from './signals';
import type { SignalKey, WindowConfig } from './types';

export interface MultiTrendModel {
  series: AlignedSeries;
  paused: boolean;
  setPaused: (p: boolean) => void;
  setSelection: (sel: ReadonlyArray<SignalKey>) => void;
  setWindow: (cfg: WindowConfig) => void;
  setPxWidth: (px: number) => void;
}

const HARD_BUFFER = 36_000; // safety ceiling per buffer (matches PySide6 1h@100ms)

/**
 * Derive epoch SECONDS from a STATUS frame's `timestamp`, tolerant of both
 * publish shapes (see realtime/envelope.ts):
 *   - number: monitor mode (monitor_worker) already publishes epoch seconds.
 *   - string: execute mode (pid_worker) publishes ISO-8601 -> Date.parse / 1000.
 * Returns NaN for unparseable input so callers can skip the frame.
 */
export function toEpochSeconds(ts: string | number): number {
  return typeof ts === 'number' ? ts : Date.parse(ts) / 1000;
}

/**
 * Accumulate per-loop ring buffers from the live `useRealtime().lastStatus`
 * map and expose a windowed + min/max-decimated `AlignedSeries` for uPlot.
 *
 * Time axis is epoch SECONDS (derived from `status.timestamp` via
 * `toEpochSeconds`), consistent with `applyWindow`/`DEFAULT_WINDOW.maxSeconds`.
 */
export function useMultiTrendModel(initial?: Partial<WindowConfig>): MultiTrendModel {
  const { lastStatus } = useRealtime();
  const [selection, setSelection] = useState<ReadonlyArray<SignalKey>>([]);
  const [windowCfg, setWindow] = useState<WindowConfig>({ ...DEFAULT_WINDOW, ...initial });
  const [paused, setPaused] = useState(false);
  const [pxWidth, setPxWidth] = useState(800);
  const buffers = useRef<Map<number, LoopBuffer>>(new Map());
  const [tick, setTick] = useState(0);

  // Append the newest frame of every loop that is currently selected.
  useEffect(() => {
    if (paused) return;
    const loops = new Set(selection.map((s) => s.loopId));
    let changed = false;
    for (const loopId of loops) {
      const status = lastStatus.get(loopId);
      if (!status) continue;
      // -> epoch seconds (matches applyWindow's unit); tolerant of ISO string
      // (execute mode) and numeric epoch (monitor mode).
      const t = toEpochSeconds(status.timestamp);
      if (Number.isNaN(t)) continue;
      let buf = buffers.current.get(loopId);
      if (!buf) {
        buf = { t: [], pv: [], sp: [], co: [] };
        buffers.current.set(loopId, buf);
      }
      if (buf.t.length > 0 && buf.t[buf.t.length - 1] === t) continue; // de-dupe coalesced frame
      buf.t.push(t);
      buf.pv.push(valueAt(status, 'pv'));
      buf.sp.push(valueAt(status, 'sp'));
      buf.co.push(valueAt(status, 'co'));
      if (buf.t.length > HARD_BUFFER) {
        const excess = buf.t.length - HARD_BUFFER;
        (['t', 'pv', 'sp', 'co'] as const).forEach((k) => buf![k].splice(0, excess));
      }
      changed = true;
    }
    if (changed) setTick((n) => n + 1);
  }, [lastStatus, selection, paused]);

  const series = useMemo(() => {
    const raw = selectSeries(buffers.current, selection);
    const windowed = applyWindow(raw, windowCfg);
    return minMaxDecimate(windowed, pxWidth);
    // tick forces recompute when buffers mutate in place
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selection, windowCfg, pxWidth, tick]);

  return { series, paused, setPaused, setSelection, setWindow, setPxWidth };
}
