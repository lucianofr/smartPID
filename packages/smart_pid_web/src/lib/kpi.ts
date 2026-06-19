import type { StatsData } from '../realtime/envelope';

export interface StatsResponseLike {
  controller_id: number;
  iae: number; itae: number; ise: number; mse: number;
  std_dev: number; total_variation: number;
  variability_sp: number; variability_range: number;
  sample_count: number;
}

export interface LoopKpis {
  controllerId: number;
  iae: number; itae: number; ise: number; mse: number;
  sigma: number;
  tv: number;
  variabilitySp: number;
  variabilityRange: number;
  sampleCount: number;
}

export interface AggregateKpis {
  loopCount: number;
  avgVariabilityRange: number;
  totalTv: number;
  avgIae: number;
  autoPct: number;
}

const AUTO_MODES = new Set(['AUTO', 'CAS', 'RCAS']);
const DEFAULT_VARIABILITY_TARGET = 0.05; // 5% of RANGE

export function fromRestStats(r: StatsResponseLike): LoopKpis {
  return {
    controllerId: r.controller_id,
    iae: r.iae, itae: r.itae, ise: r.ise, mse: r.mse,
    sigma: r.std_dev,
    tv: r.total_variation,
    variabilitySp: r.variability_sp,
    variabilityRange: r.variability_range,
    sampleCount: r.sample_count,
  };
}

export function fromWsStats(controllerId: number, s: StatsData): LoopKpis {
  return {
    controllerId,
    iae: s.iae, itae: s.itae, ise: s.ise, mse: s.mse,
    sigma: s.std_dev,
    tv: s.total_variation,
    variabilitySp: s.variability_sp,
    variabilityRange: s.variability_range,
    sampleCount: 0,
  };
}

export function isAutoMode(mode: string): boolean {
  return AUTO_MODES.has(mode);
}

export function aggregate(
  loops: ReadonlyArray<LoopKpis>,
  modesById: ReadonlyMap<number, string>,
): AggregateKpis {
  const n = loops.length;
  if (n === 0) {
    return { loopCount: 0, avgVariabilityRange: 0, totalTv: 0, avgIae: 0, autoPct: 0 };
  }
  const totalTv = loops.reduce((s, l) => s + l.tv, 0);
  const sumVar = loops.reduce((s, l) => s + l.variabilityRange, 0);
  const sumIae = loops.reduce((s, l) => s + l.iae, 0);
  const autoCount = loops.reduce(
    (c, l) => c + (isAutoMode(modesById.get(l.controllerId) ?? '') ? 1 : 0),
    0,
  );
  return {
    loopCount: n,
    avgVariabilityRange: sumVar / n,
    totalTv,
    avgIae: sumIae / n,
    autoPct: (autoCount / n) * 100,
  };
}

export function formatKpi(value: number, kind: 'pct' | 'index' | 'count'): string {
  switch (kind) {
    case 'pct':
      return `${(value * 100).toFixed(1)}%`;
    case 'index':
      return value.toFixed(2);
    case 'count':
      return Math.round(value).toString();
  }
}

export function variabilityOutOfTarget(
  variabilityRange: number,
  targetPct: number = DEFAULT_VARIABILITY_TARGET,
): boolean {
  return variabilityRange > targetPct;
}
