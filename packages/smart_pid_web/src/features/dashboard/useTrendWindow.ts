import { useEffect, useRef, useState } from 'react';
import type { TrendPenTip, TrendSeriesData } from '@/components/Trend';
import { statusTimestampToEpoch, type AiData, type StatusData } from '@/lib/envelope';
import { createWindowBuffer, type WindowBuffer } from '@/lib/windowBuffer';
import { useRealtime } from '@/realtime/useRealtime';

/** 1 Hz over the longest offered window (1 h) plus headroom for faster loops. */
const MAX_POINTS = 8000;
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
 * Sliding PV/SP/CO window for one loop, fed by the phase-3 realtime fan-out.
 * Window resizes re-seed from the retained samples so changing the control does
 * not blank a recorder that has been running for an hour.
 */
export function useTrendWindow(
  controllerId: number,
  maxSeconds: number,
  pxWidth: number,
): TrendWindow {
  const { subscribe: subscribeStatus } = useRealtime<StatusData>(controllerId, 'status');
  const { subscribe: subscribeAi } = useRealtime<AiData>(controllerId, 'ai');
  const bufferRef = useRef<WindowBuffer | null>(null);
  const [, setRevision] = useState(0);
  const [aiTicks, setAiTicks] = useState<number[]>([]);

  if (bufferRef.current === null) {
    bufferRef.current = createWindowBuffer(SERIES, { maxSeconds, maxPoints: MAX_POINTS });
  }

  useEffect(() => {
    const next = createWindowBuffer(SERIES, { maxSeconds, maxPoints: MAX_POINTS });
    seed(next, bufferRef.current);
    bufferRef.current = next;
    setRevision((r) => r + 1);
  }, [maxSeconds]);

  // Loop scope changed: the previous loop's trace must not bleed into this one.
  useEffect(() => {
    bufferRef.current?.clear();
    setAiTicks([]);
    setRevision((r) => r + 1);
  }, [controllerId]);

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
