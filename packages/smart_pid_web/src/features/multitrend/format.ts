import type { StatsRow } from './types';

// Real wire shape (snake_case) shared by BOTH stats sources:
//   - WS STATS.{id} payload (stats_worker.py:86 get_current_stats)
//   - REST GET /controllers/stats -> StatsResponse (smart_pid_domain/dtos/ai.py StatsResponse)
// Only the 8 fields the multi-trend row needs are declared here.
export interface StatsDto {
  iae: number;
  itae: number;
  ise: number;
  mse: number;
  std_dev: number;
  total_variation: number;
  variability_range: number;
  variability_sp: number;
}

export function toStatsRow(loopId: number, dto: StatsDto): StatsRow {
  return {
    loopId,
    iae: dto.iae,
    itae: dto.itae,
    ise: dto.ise,
    mse: dto.mse,
    sigma: dto.std_dev,
    tv: dto.total_variation,
    varRange: dto.variability_range,
    varSp: dto.variability_sp,
  };
}

export function formatMetric(value: number): string {
  if (!Number.isFinite(value)) return '—';
  return value.toFixed(3);
}

export function formatVariabilityPct(ratio: number): string {
  if (!Number.isFinite(ratio)) return '—';
  return `${(ratio * 100).toFixed(1)}%`;
}
