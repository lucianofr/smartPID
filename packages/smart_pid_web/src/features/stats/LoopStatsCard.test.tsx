import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { makeController, makeStatus } from '@/test/fixtures';
import { LoopStatsCard } from './LoopStatsCard';
import type { LoopStatsRow } from './useLoopStats';

const BASE_ROW: LoopStatsRow = {
  controllerId: 1,
  iae: 1.234,
  ise: 2,
  itae: 3,
  mse: 4,
  std_dev: 5,
  total_variation: 6,
  variability_range: 0.1,
  variability_sp: 0.2,
  sample_count: 100,
  mean_abs_error: 0.5,
  osc: 0.1,
  osc_period_s: 12,
  osc_sample_count: 40,
  overshoot: 0.05,
  pk_pk_error: 3,
  recent_pk_pk_error: 2,
  recent_reversals: 4,
  reversals: 6,
  sp_pk_pk: 10,
  tv_per_sample: 0.02,
  zero_crossings: 8,
};

/** One label per field in `LoopStatsRow` — every indicator must be on screen. */
const METRIC_LABELS = [
  'IAE',
  'ISE',
  'ITAE',
  'MSE',
  'MAE',
  'σ',
  'TV',
  'TV/amostra',
  '2σ/SP',
  '2σ/Range',
  'Pico-pico erro',
  'Pico-pico erro (recente)',
  'Osc',
  'Período osc.',
  'Amostras osc.',
  'Reversões',
  'Reversões (recente)',
  'Cruzamentos por zero',
  'Pico-pico SP',
  'Overshoot',
  'Amostras',
];

describe('LoopStatsCard', () => {
  it('renders every metric label for a loop that has stats', () => {
    render(
      <LoopStatsCard
        controller={makeController({ id: 1, name: 'FIC-101' })}
        statsRow={BASE_ROW}
        status={undefined}
      />,
    );
    for (const label of METRIC_LABELS) {
      expect(screen.getByText(label)).toBeVisible();
    }
  });

  it('reflects the live realtime block mode, never the REST controller.mode field', () => {
    render(
      <LoopStatsCard
        controller={makeController({ id: 1, mode: 'MAN', mode_normal: 'MAN' })}
        statsRow={BASE_ROW}
        status={makeStatus({ mode: 'CAS' })}
      />,
    );
    expect(screen.getByText('CAS')).toBeVisible();
    expect(screen.queryByText('MAN')).not.toBeInTheDocument();
  });

  it('shows UNKNOWN before the first status frame, never falling back to the REST mode', () => {
    render(
      <LoopStatsCard
        controller={makeController({ id: 1, mode: 'AUTO' })}
        statsRow={BASE_ROW}
        status={undefined}
      />,
    );
    expect(screen.getByText('UNKNOWN')).toBeVisible();
    expect(screen.queryByText('AUTO')).not.toBeInTheDocument();
  });

  it('shows an em dash for a loop whose AI engine is NONE (opted out)', () => {
    render(
      <LoopStatsCard
        controller={makeController({ id: 1 })}
        statsRow={BASE_ROW}
        status={undefined}
      />,
    );
    expect(screen.getByText('—')).toBeVisible();
  });

  it('names the active AI engine when the optimizer is on', () => {
    render(
      <LoopStatsCard
        controller={makeController({
          id: 1,
          optimization_enabled: true,
          ai_config: {
            dead_time_l: 1,
            engine: 'FUZZY',
            limit_max: 100,
            limit_min: 0.1,
            objective: 'DISTURBANCE_REJECTION',
            rl_fallback_kd: 0.2,
            rl_fallback_kp: 0.6,
            rl_learning_rate: 0.0003,
            rl_train_interval: 32,
            sl_co_ramp_max_pct_min: 10,
            sl_error_small_pct: 5,
          },
        })}
        statsRow={BASE_ROW}
        status={undefined}
      />,
    );
    expect(screen.getByText('FUZZY')).toBeVisible();
  });

  it('renders with its badges and an explicit note when the loop has no stats row', () => {
    render(
      <LoopStatsCard
        controller={makeController({ id: 1, name: 'FIC-101' })}
        statsRow={undefined}
        status={makeStatus({ mode: 'AUTO' })}
      />,
    );
    expect(screen.getByText('AUTO')).toBeVisible();
    expect(screen.getByText('Sem estatísticas para esta malha.')).toBeVisible();
    expect(screen.queryByText('IAE')).not.toBeInTheDocument();
  });
});
