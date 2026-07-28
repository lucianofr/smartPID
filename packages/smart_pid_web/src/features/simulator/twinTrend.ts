import { statusTimestampToEpoch, type StatusData } from '@/lib/envelope';

/** One twin sample on the recorder's time base: x in epoch SECONDS. */
export interface TwinPoint {
  x: number;
  pv: number;
  sp: number;
  co: number;
}

/**
 * How much twin response the Sim page keeps on screen. Long enough to watch a
 * step settle on the slowest preset (TEMPERATURE), short enough that the plot
 * still shows the dead time.
 */
export const TWIN_WINDOW_SECONDS = 300;

/**
 * STATUS frame → plotted twin sample.
 *
 * The twin publishes on the same STATUS topic as a real loop, so pv/sp/co
 * arrive as FFSignal objects and `timestamp` is either an ISO-8601 string
 * (execute mode) or float epoch seconds (monitor mode). A frame whose timestamp
 * cannot be read has no place on a time axis — it yields null rather than a
 * guessed x that would shear the trace.
 */
export function toTwinPoint(status: StatusData): TwinPoint | null {
  const x = statusTimestampToEpoch(status.timestamp);
  if (x === null) return null;
  return { x, pv: status.pv.value, sp: status.sp.value, co: status.co.value };
}
