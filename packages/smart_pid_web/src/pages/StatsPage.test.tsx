import { act, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { queryKeys } from '@/api/queryKeys';
import type { StatsResponse } from '@/api/types';
import { statusEnvelope, ff, makeController } from '@/test/fixtures';
import { createFakeRealtime, createQueryClient, TestProviders } from '@/test/providers';
import { StatsPage } from './StatsPage';

const CONTROLLERS = [
  makeController({ id: 1, name: 'FIC-101', description: 'Flow' }),
  makeController({ id: 2, name: 'TIC-202', description: 'Temp' }),
];

const BASE_METRICS: Omit<StatsResponse, 'controller_id'> = {
  iae: 1,
  ise: 2,
  itae: 3,
  mse: 4,
  std_dev: 5,
  total_variation: 6,
  variability_range: 0.1,
  variability_sp: 0.2,
  sample_count: 100,
  mean_abs_error: 0,
  osc: 0,
  osc_period_s: 0,
  osc_sample_count: 0,
  overshoot: 0,
  pk_pk_error: 0,
  recent_pk_pk_error: 0,
  recent_reversals: 0,
  reversals: 0,
  sp_pk_pk: 0,
  tv_per_sample: 0,
  zero_crossings: 0,
};

function statsRow(controllerId: number): StatsResponse {
  return { ...BASE_METRICS, controller_id: controllerId };
}

function renderStats(controllers = CONTROLLERS, stats: StatsResponse[] = [statsRow(1), statsRow(2)]) {
  const realtime = createFakeRealtime();
  const queryClient = createQueryClient();
  queryClient.setQueryData(queryKeys.controllers, controllers);
  queryClient.setQueryData(queryKeys.allStats, stats);
  return {
    ...render(
      <TestProviders queryClient={queryClient} realtime={realtime.value}>
        <StatsPage />
      </TestProviders>,
    ),
    realtime,
    queryClient,
  };
}

beforeEach(() => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => [] }),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('StatsPage', () => {
  it('renders one card per configured loop', () => {
    renderStats();
    const region = screen.getByRole('region', { name: 'Estatísticas das malhas' });
    expect(within(region).getByText('FIC-101')).toBeVisible();
    expect(within(region).getByText('TIC-202')).toBeVisible();
  });

  it('shows every metric label for a loop that has stats', () => {
    renderStats();
    expect(screen.getAllByText('IAE')).toHaveLength(2);
    expect(screen.getAllByText('Overshoot')).toHaveLength(2);
    expect(screen.getAllByText('Cruzamentos por zero')).toHaveLength(2);
  });

  it('reflects a live STATUS frame in the block-mode badge, not the REST mode field', () => {
    const { realtime } = renderStats([makeController({ id: 1, name: 'FIC-101', mode: 'MAN' })], [
      statsRow(1),
    ]);
    // No live frame yet: the REST `mode` field must never leak into the badge.
    expect(screen.getByText('UNKNOWN')).toBeVisible();
    expect(screen.queryByText('MAN')).not.toBeInTheDocument();

    act(() => realtime.emit(statusEnvelope(1, 1, { pv: ff(10), mode: 'CAS' })));

    expect(screen.getByText('CAS')).toBeVisible();
    expect(screen.queryByText('UNKNOWN')).not.toBeInTheDocument();
  });

  it('shows an em dash for a loop whose AI engine opted out (NONE)', () => {
    renderStats([makeController({ id: 1, name: 'FIC-101' })], [statsRow(1)]);
    expect(screen.getByText('—')).toBeVisible();
  });

  it('still renders a card with its badges when a loop has no stats row', () => {
    renderStats(
      [
        makeController({ id: 1, name: 'FIC-101' }),
        makeController({ id: 2, name: 'TIC-202' }),
      ],
      [statsRow(1)],
    );
    const cards = screen.getAllByText('SUPERVISORY');
    expect(cards).toHaveLength(2);
    expect(screen.getByText('Sem estatísticas para esta malha.')).toBeVisible();
  });

  it('shows an empty state when no loops are configured', () => {
    renderStats([], []);
    expect(screen.getByText('Nenhuma malha configurada.')).toBeVisible();
  });
});
