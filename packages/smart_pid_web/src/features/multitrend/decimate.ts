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
  if (data[0][0] !== t[first]) {
    data[0].unshift(t[first]);
    for (let r = 0; r < rows.length; r += 1) data[r + 1].unshift(rows[r][first]);
  }
  if (data[0][data[0].length - 1] !== t[last]) {
    data[0].push(t[last]);
    for (let r = 0; r < rows.length; r += 1) data[r + 1].push(rows[r][last]);
  }
  return data;
}
