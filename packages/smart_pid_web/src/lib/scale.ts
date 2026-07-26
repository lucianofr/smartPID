/**
 * Value→fraction, clamping and tick generation for AnalogBar (§7 pure module).
 * Phase 3 may extend (valueToPercent, clampToScale) but NEVER changes these
 * signatures — pinned with the phase-3 plan.
 */
export interface Scale {
  euMin: number;
  euMax: number;
  unit: string;
}

/** Clamped 0..1 fraction of value within the scale span; 0 when span <= 0. */
export function valueToFraction(value: number, scale: Scale): number {
  const span = scale.euMax - scale.euMin;
  if (span <= 0) return 0;
  const f = (value - scale.euMin) / span;
  return f < 0 ? 0 : f > 1 ? 1 : f;
}

/** Evenly spaced tick VALUES from euMin to euMax inclusive (count >= 2, default 5). */
export function ticks(scale: Scale, count = 5): number[] {
  const n = Math.max(2, Math.floor(count));
  const span = scale.euMax - scale.euMin;
  if (span <= 0) return [scale.euMin, scale.euMin];
  return Array.from({ length: n }, (_, i) => scale.euMin + (span * i) / (n - 1));
}

/** Percent position on the scale span, clamped 0..100 (phase-3 extension). */
export function valueToPercent(value: number, scale: Scale): number {
  return valueToFraction(value, scale) * 100;
}

/** Clamp a raw EU value into [euMin, euMax]; degenerate span collapses to euMin. */
export function clampToScale(value: number, scale: Scale): number {
  if (scale.euMax <= scale.euMin) return scale.euMin;
  return Math.min(Math.max(value, scale.euMin), scale.euMax);
}