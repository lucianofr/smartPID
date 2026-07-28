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
  /** Returns false (and drops the sample) for non-finite or non-increasing t. */
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
      if (last !== undefined && t <= last) return false;
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
      const outX: number[] = [];
      const outRows: number[][] = rows.map(() => []);
      const perBucket = n / pxWidth;
      for (let b = 0; b < pxWidth; b += 1) {
        const lo = Math.floor(b * perBucket);
        const hi = Math.min(n, Math.floor((b + 1) * perBucket));
        if (hi <= lo) continue;
        for (let pass = 0; pass < 2; pass += 1) {
          let xi = lo;
          outRows.forEach((out, r) => {
            const row = rows[r];
            let bestIdx = lo;
            let best = row[lo];
            for (let i = lo + 1; i < hi; i += 1) {
              const v = row[i];
              if ((pass === 0 && v < best) || (pass === 1 && v > best)) {
                best = v;
                bestIdx = i;
              }
            }
            out.push(best);
            if (r === 0) xi = bestIdx;
          });
          outX.push(ts[xi]);
        }
      }
      // Re-sort by x so min/max columns stay monotonic for uPlot.
      const order = outX.map((_, i) => i).sort((a, c) => outX[a] - outX[c]);
      return {
        data: [
          order.map((i) => outX[i]),
          ...outRows.map((row) => order.map((i) => row[i])),
        ],
        decimated: true,
      };
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