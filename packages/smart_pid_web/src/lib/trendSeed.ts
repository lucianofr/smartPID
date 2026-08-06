/**
 * Shared seed loader for trend charts.
 *
 * Every trend chart (dashboard panel, simulator twin, multitrend cells) pulls
 * the operator's chosen time window from the backend ring on mount, then keeps
 * appending realtime frames. This module is the "pull the window" half: it
 * fetches `/trend/{id}` and maps the wire `TelemetryFrame` list into the
 * `(epoch seconds, [pv, sp, co])` samples `WindowBuffer.push` consumes.
 *
 * The ring stores one sample per second over 72 h, so the response is bounded
 * by the requested window rather than by the ring — a 30 min panel pulls
 * ~1 800 frames. The request is clamped to `TREND_WINDOW_MAX_S` because that
 * is the widest window any chart can actually retain.
 *
 * The merge-with-live half lives in each chart hook: the realtime handler keeps
 * pushing to the buffer while the fetch is in flight, and the hook reconciles
 * (seed ∪ live, deduped by timestamp) once the fetch resolves — so a frame
 * that arrives during the fetch is never lost and never duplicated.
 */
import { endpoints } from '@/api/endpoints';
import { TREND_WINDOW_MAX_S } from '@/features/settings/settingsTypes';
import type { WindowBuffer } from '@/lib/windowBuffer';

export interface SeedSample {
  t: number;
  values: readonly [number, number, number];
}

/** Pull the last `seconds` of the ring for a loop, ascending by timestamp. */
export async function loadTrendSeed(
  controllerId: number,
  seconds: number,
): Promise<SeedSample[]> {
  const res = await endpoints.trend(controllerId, Math.min(seconds, TREND_WINDOW_MAX_S));
  const samples: SeedSample[] = [];
  for (const frame of res.frames) {
    const ms = Date.parse(frame.timestamp);
    if (Number.isNaN(ms)) continue;
    samples.push({ t: ms / 1000, values: [frame.pv, frame.sp, frame.co] });
  }
  samples.sort((a, b) => a.t - b.t);
  return samples;
}

/**
 * Fold a backend seed into whatever the live subscription already pushed.
 *
 * The realtime handler never stops writing to the buffer while the seed is in
 * flight, so a plain `clear() + push(seed)` would drop those frames — and
 * pushing the seed on top would be rejected outright, because `push` refuses a
 * timestamp older than the buffer head. Rebuilding from the union keeps both
 * halves; a repeated `t` is one sample, not two.
 */
export function mergeSeed(buffer: WindowBuffer, seeds: readonly SeedSample[]): void {
  const [t, pv, sp, co] = buffer.view(Number.POSITIVE_INFINITY).data;
  const byT = new Map<number, readonly number[]>();
  for (const s of seeds) byT.set(s.t, s.values);
  // Live frames win a tie: they are what the operator just watched being drawn.
  for (let i = 0; i < t.length; i += 1) byT.set(t[i], [pv[i], sp[i], co[i]]);
  const ordered = [...byT.entries()].sort((a, b) => a[0] - b[0]);
  buffer.clear();
  for (const [ts, values] of ordered) buffer.push(ts, values);
}
