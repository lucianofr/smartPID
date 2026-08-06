/**
 * Bounded sliding window with explicit min/max decimation — pure module (spec §7).
 *
 * Replaces the deleted client's ad-hoc pair (immutable append with ring cap in
 * features/simulator/twinTrend.ts + min/max column decimation in
 * features/multitrend/decimate.ts) with one buffer that ALSO exposes the
 * undecimated newest sample: the Recorder pen tip marks valToPos() of the TRUE
 * latest sample, not the tail of the decimated series (spec §6.7).
 */

export interface WindowBufferConfig {
  /** Time window in seconds; Infinity disables the time bound. */
  maxSeconds: number;
  /** Hard point cap applied after the time window; Infinity disables it. */
  maxPoints: number;
  /**
   * Minimum spacing between retained samples, in seconds; omitted disables the
   * thinning. A long window cannot hold a 10 Hz feed inside `maxPoints`, and
   * the point cap would drop from the LEFT — eroding the span of an axis that
   * still claims the full window. Thinning the feed keeps the span honest.
   */
  minStep?: number;
}

export interface WindowSample {
  t: number;
  values: readonly number[];
}

export interface WindowView {
  /** uPlot AlignedData shape: data[0] = ascending t, then one row per series. */
  data: number[][];
  decimated: boolean;
}

export interface WindowBuffer {
  /**
   * Returns false (and drops the sample) for a non-finite t, a non-increasing
   * t, or a t closer than `minStep` to the last retained sample. The last is
   * routine thinning, not an error — callers that re-render on `true` simply
   * skip the frame.
   */
  push(t: number, values: readonly number[]): boolean;
  /** Undecimated head — the §6.7 pen tip. */
  latest(): WindowSample | null;
  /** Window contents; min/max-per-pixel-column decimated when length > pxWidth. */
  view(pxWidth: number): WindowView;
  length(): number;
  clear(): void;
}

export function createWindowBuffer(
  seriesCount: number,
  cfg: WindowBufferConfig,
): WindowBuffer {
  if (!Number.isInteger(seriesCount) || seriesCount < 1) {
    throw new RangeError(`seriesCount must be a positive integer, got ${seriesCount}`);
  }
  let ts: number[] = [];
  let rows: number[][] = Array.from({ length: seriesCount }, () => []);

  const trim = (): void => {
    const n = ts.length;
    if (n === 0) return;
    let start = 0;
    if (Number.isFinite(cfg.maxSeconds)) {
      const cutoff = ts[n - 1] - cfg.maxSeconds;
      while (start < n && ts[start] < cutoff) start += 1;
    }
    if (Number.isFinite(cfg.maxPoints) && n - start > cfg.maxPoints) {
      start = n - cfg.maxPoints;
    }
    if (start > 0) {
      ts = ts.slice(start);
      rows = rows.map((r) => r.slice(start));
    }
  };

  return {
    push(t, values) {
      if (values.length !== seriesCount) {
        throw new RangeError(
          `expected ${seriesCount} series values, got ${values.length}`,
        );
      }
      if (!Number.isFinite(t)) return false;
      const last = ts[ts.length - 1];
      if (last !== undefined) {
        if (t <= last) return false;
        if (cfg.minStep !== undefined && t - last < cfg.minStep) return false;
      }
      ts.push(t);
      for (let i = 0; i < seriesCount; i += 1) rows[i].push(values[i]);
      trim();
      return true;
    },

    latest() {
      const n = ts.length;
      if (n === 0) return null;
      return { t: ts[n - 1], values: rows.map((r) => r[n - 1]) };
    },

    view(pxWidth) {
      const n = ts.length;
      if (pxWidth <= 0 || n <= pxWidth) {
        return { data: [ts.slice(), ...rows.map((r) => r.slice())], decimated: false };
      }
      // Min/max per pixel column: each bucket contributes its min-sample and its
      // max-sample so transients and peaks survive (critical for control trends).
      //
      // THREE rules make the envelope honest and STABLE:
      //
      // 1. Bucket boundaries are a grid on ABSOLUTE TIME, never on array
      //    indices. Index-anchored buckets (`n / pxWidth`) shift by one sample
      //    on every push and again on every trim, so each column recomputed its
      //    min/max over a different set of samples on every frame: a point
      //    ALREADY on screen jumped in Y as the window slid, and the trace drew
      //    values the historian never recorded. Measured over 30 renders of a
      //    sliding 10-min window on a real ring, worst case per series: CO moved
      //    35.5 EU, SP 16.5 EU. On a time grid a sample's column is a pure
      //    function of its timestamp, so history is immobile — only the newest
      //    bucket (still filling) and the oldest (being trimmed) can change,
      //    which is exactly what those two are supposed to do.
      // 2. The pair sits at the bucket's own first/last sample time, shared by
      //    all series. Taking x from series 0's argmin/argmax stamped SP and CO
      //    extremes with PV's timing.
      // 3. Each series orders its own pair by when ITS extremes occurred, so a
      //    bucket where the series fell renders falling. Ordering every series by
      //    series 0's direction inverted the fine structure of every series that
      //    disagreed with PV — for CO, anti-correlated with PV by construction,
      //    that was 775 injected direction reversals with 29 EU peaks: the
      //    sawtooth.
      //
      // The grid width is fixed by the window and the canvas, NOT by how much
      // data has arrived — that is what keeps it stable. A window still filling
      // up therefore draws fewer, wider columns than its pixel budget allows;
      // the envelope is intact, only the vertex spacing is coarser, and it
      // sharpens to one pair per pixel once the window is full.
      const windowSpan = Number.isFinite(cfg.maxSeconds)
        ? cfg.maxSeconds
        : ts[n - 1] - ts[0];
      const width = windowSpan / pxWidth;
      if (!(width > 0)) {
        return { data: [ts.slice(), ...rows.map((r) => r.slice())], decimated: false };
      }
      const outX: number[] = [];
      const outRows: number[][] = rows.map(() => []);
      let lo = 0;
      while (lo < n) {
        const key = Math.floor(ts[lo] / width);
        let hi = lo + 1;
        while (hi < n && Math.floor(ts[hi] / width) === key) hi += 1;
        // A single-sample bucket has no envelope to draw; emitting it twice
        // would repeat an x value, which uPlot reads as a vertical segment.
        if (hi - lo === 1) {
          outX.push(ts[lo]);
          for (let r = 0; r < outRows.length; r += 1) outRows[r].push(rows[r][lo]);
          lo = hi;
          continue;
        }
        outX.push(ts[lo], ts[hi - 1]);
        for (let r = 0; r < outRows.length; r += 1) {
          const row = rows[r];
          let minIdx = lo;
          let maxIdx = lo;
          for (let i = lo + 1; i < hi; i += 1) {
            if (row[i] < row[minIdx]) minIdx = i;
            if (row[i] > row[maxIdx]) maxIdx = i;
          }
          if (minIdx <= maxIdx) outRows[r].push(row[minIdx], row[maxIdx]);
          else outRows[r].push(row[maxIdx], row[minIdx]);
        }
        lo = hi;
      }
      return { data: [outX, ...outRows], decimated: true };
    },

    length() {
      return ts.length;
    },

    clear() {
      ts = [];
      rows = rows.map(() => []);
    },
  };
}