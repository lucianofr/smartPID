import type { AlignedSeries } from './multiTrendData';
import type { WindowConfig } from './types';

/**
 * Clamp the aligned series to the configured window (time first, then point cap),
 * dropping from the left so the newest samples are always retained.
 */
export function applyWindow(series: AlignedSeries, cfg: WindowConfig): AlignedSeries {
  const x = series.data[0] ?? [];
  if (x.length === 0) return series;

  const newest = x[x.length - 1];
  // earliest index whose timestamp is within the time window
  let start = 0;
  if (Number.isFinite(cfg.maxSeconds)) {
    const cutoff = newest - cfg.maxSeconds;
    while (start < x.length && x[start] < cutoff) start += 1;
  }
  // then enforce the hard point cap
  const kept = x.length - start;
  if (Number.isFinite(cfg.maxPoints) && kept > cfg.maxPoints) {
    start = x.length - cfg.maxPoints;
  }
  if (start === 0) return series;

  return {
    keys: series.keys,
    data: series.data.map((row) => row.slice(start)),
  };
}

/**
 * Min/max-per-pixel-column decimation (design-system §7.2): when point count
 * exceeds the pixel width, each output column keeps the min and the max of the
 * bucket so transients/peaks are preserved (critical for control trends).
 * Output length is at most `pxWidth * 2`.
 */
export function minMaxDecimate(series: AlignedSeries, pxWidth: number): AlignedSeries {
  const x = series.data[0] ?? [];
  const n = x.length;
  if (pxWidth <= 0 || n <= pxWidth) return series;

  const buckets = pxWidth;
  const perBucket = n / buckets;
  const outX: number[] = [];
  const outRows: number[][] = series.data.slice(1).map(() => []);

  for (let b = 0; b < buckets; b += 1) {
    const lo = Math.floor(b * perBucket);
    const hi = Math.min(n, Math.floor((b + 1) * perBucket));
    if (hi <= lo) continue;

    // Decimate each series row by min then max; pick representative x from the
    // bucket so the column carries two samples (min-sample, max-sample).
    for (let pass = 0; pass < 2; pass += 1) {
      let xi = lo;
      outRows.forEach((out, r) => {
        const row = series.data[r + 1];
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
      outX.push(x[xi]);
    }
  }

  // Re-sort by x so min/max columns stay monotonic for uPlot.
  const order = outX.map((_, i) => i).sort((a, c) => outX[a] - outX[c]);
  const data: number[][] = [order.map((i) => outX[i])];
  outRows.forEach((row) => data.push(order.map((i) => row[i])));
  return { keys: series.keys, data };
}
