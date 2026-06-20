export interface Scale {
  euMin: number;
  euMax: number;
  unit: string;
}

export function valueToFraction(value: number, scale: Scale): number {
  const span = scale.euMax - scale.euMin;
  if (span <= 0) return 0;
  const f = (value - scale.euMin) / span;
  return f < 0 ? 0 : f > 1 ? 1 : f;
}
