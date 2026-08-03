import { useEffect, useRef, useState } from 'react';
import type { TrendPenTip, TrendSeriesData } from '@/components/Trend';
import { statusTimestampToEpoch, type AiData, type StatusData } from '@/lib/envelope';
import { loadTrendSeed, mergeSeed } from '@/lib/trendSeed';
import { createWindowBuffer, type WindowBuffer } from '@/lib/windowBuffer';
import { useRealtime } from '@/realtime/useRealtime';

/**
 * Point cap for the retained window, matched to the backend ring's own
 * `MAX_SAMPLES_PER_LOOP` so the buffer keeps everything `GET /trend` can serve.
 *
 * The feed is the IO scan, NOT 1 Hz: `scan_interval_s` / `simulator_interval_ms`
 * default to 100 ms, so an hour is ~36 000 samples. The previous 8 000 was sized
 * for 1 Hz and silently clipped every window past ~13 min — asking for 30 min
 * painted 13 min of trace, and the x axis agreed with it, so nothing on screen
 * said the window had been cut.
 *
 * Cost of the larger cap, measured on a full 40 000-sample buffer: 0.48 ms per
 * push (the window trim) and 4.3 ms per `view(1400)`. At a 10 Hz feed that is
 * ~5 % of one core — the price of a chart whose axis means what it says.
 */
const MAX_POINTS = 40_000;
const SERIES = 3; // pv, sp, co

export interface TrendWindow {
  /** Decimated columns for uPlot. */
  data: TrendSeriesData;
  /** §6.7: the TRUE latest sample, never the decimated tail. */
  penTip: TrendPenTip | null;
  /** ACTION.AI timestamps inside the window (epoch seconds). */
  aiTicks: number[];
  /** Undecimated sample count currently held. */
  sampleCount: number;
}

function seed(next: WindowBuffer, previous: WindowBuffer | null): void {
  if (previous === null) return;
  const [t, pv, sp, co] = previous.view(Number.POSITIVE_INFINITY).data;
  for (let i = 0; i < t.length; i += 1) next.push(t[i], [pv[i], sp[i], co[i]]);
}


/**
 * Sliding PV/SP/CO window for one loop, fed by the phase-3 realtime fan-out and
 * SEEDED from the backend 1-hour ring (`GET /trend/{id}`).
 *
 * Without the seed a freshly mounted recorder was blank and stayed blank until
 * it had accumulated the window live — an operator asking for the last hour got
 * an empty plot for an hour. The seed paints the chosen window immediately and
 * realtime frames extend it from there.
 *
 * Window resizes re-seed from the retained samples first (instant continuity,
 * no flash) and then reconcile against the ring, so widening the window pulls in
 * history the previous, narrower buffer had already evicted.
 */
export function useTrendWindow(
  controllerId: number,
  maxSeconds: number,
  pxWidth: number,
): TrendWindow {
  const { subscribe: subscribeStatus } = useRealtime<StatusData>(controllerId, 'status');
  const { subscribe: subscribeAi } = useRealtime<AiData>(controllerId, 'ai');
  const bufferRef = useRef<WindowBuffer | null>(null);
  /** Loop the current buffer belongs to — a resize may reuse it, a loop change may not. */
  const sameLoopRef = useRef(controllerId);
  const [, setRevision] = useState(0);
  const [aiTicks, setAiTicks] = useState<number[]>([]);

  if (bufferRef.current === null) {
    bufferRef.current = createWindowBuffer(SERIES, { maxSeconds, maxPoints: MAX_POINTS });
  }

  // Loop scope or window changed: rebuild the buffer, then refill it from the
  // backend ring. A loop change starts from nothing (the previous loop's trace
  // must not bleed in); a resize starts from the retained samples so the plot
  // never blanks while the fetch is in flight.
  useEffect(() => {
    const next = createWindowBuffer(SERIES, { maxSeconds, maxPoints: MAX_POINTS });
    seed(next, sameLoopRef.current === controllerId ? bufferRef.current : null);
    sameLoopRef.current = controllerId;
    bufferRef.current = next;
    setAiTicks([]);
    setRevision((r) => r + 1);

    let cancelled = false;
    loadTrendSeed(controllerId, maxSeconds)
      .then((seeds) => {
        if (cancelled || seeds.length === 0) return;
        mergeSeed(next, seeds);
        setRevision((r) => r + 1);
      })
      .catch(() => {
        // No ring (older backend, network blip): live-only, exactly as before.
      });
    return () => {
      cancelled = true;
    };
  }, [controllerId, maxSeconds]);

  useEffect(
    () =>
      subscribeStatus((env) => {
        const t = statusTimestampToEpoch(env.data.timestamp) ?? env.ts;
        const pushed = bufferRef.current?.push(t, [
          env.data.pv.value,
          env.data.sp.value,
          env.data.co.value,
        ]);
        if (pushed === true) setRevision((r) => r + 1);
      }),
    [subscribeStatus],
  );

  useEffect(
    () =>
      subscribeAi((env) => {
        const t = statusTimestampToEpoch(env.data.timestamp) ?? env.ts;
        setAiTicks((prev) => [...prev, t]);
      }),
    [subscribeAi],
  );

  const buffer = bufferRef.current;
  const [t, pv, sp, co] = buffer.view(pxWidth).data;
  const head = buffer.latest();
  const oldest = t.length > 0 ? t[0] : Number.NEGATIVE_INFINITY;

  return {
    data: { t, pv, sp, co },
    penTip: head === null ? null : { t: head.t, pv: head.values[0] },
    aiTicks: aiTicks.filter((tick) => tick >= oldest),
    sampleCount: buffer.length(),
  };
}
