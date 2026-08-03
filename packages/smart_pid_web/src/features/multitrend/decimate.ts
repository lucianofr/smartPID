import { createWindowBuffer } from '@/lib/windowBuffer';

/**
 * History decimation for display (§6.8).
 *
 * The min/max-per-pixel-column algorithm already lives in `windowBuffer.view`,
 * which is where live windows get it. A historical batch is not a live window
 * — it arrives whole, may repeat or reorder timestamps, and has no retention
 * bound — so it is fed through one transient unbounded buffer instead of
 * getting a second copy of the algorithm.
 *
 * On top of that: the exact FIRST and LATEST samples are pinned back. Bucket
 * extrema have no reason to land on the window edges, and those two readings
 * are precisely the ones an operator compares against the range they asked for.
 */
export function decimateHistory(
  t: readonly number[],
  rows: readonly (readonly number[])[],
  pxWidth: number,
): number[][] {
  if (rows.length === 0) return [t.slice()];
  if (pxWidth <= 0 || t.length <= pxWidth) {
    return [t.slice(), ...rows.map((r) => r.slice())];
  }

  // Ascending time is a precondition of the buffer's monotonic push, and the
  // historian's ordering is not part of any contract we control.
  const order = t.map((_, i) => i).sort((a, b) => t[a] - t[b]);
  const buffer = createWindowBuffer(rows.length, {
    maxSeconds: Number.POSITIVE_INFINITY,
    maxPoints: Number.POSITIVE_INFINITY,
  });
  const sample: number[] = new Array<number>(rows.length);
  for (const i of order) {
    for (let r = 0; r < rows.length; r += 1) sample[r] = rows[r][i];
    buffer.push(t[i], sample);
  }

  const data = buffer.view(pxWidth).data;
  const first = order[0];
  const last = order[order.length - 1];
  // The pin has to compare the VALUES, not just the timestamp. `view` places
  // each bucket's pair at the bucket's own first/last sample time, so an edge
  // column can carry the right x with a bucket extreme on it — true whenever
  // the edge bucket is non-monotonic. Matching x alone let that through and the
  // window edge reported a reading the historian never recorded.
  const carries = (col: number, src: number): boolean =>
    data[0][col] === t[src] && rows.every((r, i) => data[i + 1][col] === r[src]);
  const overwrite = (col: number, src: number): void => {
    data[0][col] = t[src];
    for (let r = 0; r < rows.length; r += 1) data[r + 1][col] = rows[r][src];
  };

  if (!carries(0, first)) {
    // Same x, wrong value: replace it. A different x means the edge sample is
    // genuinely absent, so prepend rather than displace a real column.
    if (data[0][0] === t[first]) overwrite(0, first);
    else {
      data[0].unshift(t[first]);
      for (let r = 0; r < rows.length; r += 1) data[r + 1].unshift(rows[r][first]);
    }
  }
  const tail = data[0].length - 1;
  if (!carries(tail, last)) {
    if (data[0][tail] === t[last]) overwrite(tail, last);
    else {
      data[0].push(t[last]);
      for (let r = 0; r < rows.length; r += 1) data[r + 1].push(rows[r][last]);
    }
  }
  return data;
}
