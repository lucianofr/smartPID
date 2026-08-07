import { fireEvent, render, screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import { queryKeys } from '@/api/queryKeys';
import type { StatsResponse } from '@/api/types';
import { makeController } from '@/test/fixtures';
import { createFakeRealtime, createQueryClient, TestProviders } from '@/test/providers';
import { MultiTrendPage, reconcilableRoster } from './MultiTrendPage';

describe('reconcilableRoster', () => {
  it('is null while the stats query is pending', () => {
    expect(reconcilableRoster({ isPending: true, isError: false, loops: [] })).toBeNull();
  });

  it('is null when the stats query errored, even with a stale-empty loops array', () => {
    // React Query settles isPending=false as soon as the query lands in an
    // error state (after its retry budget), leaving `loops` at its `[]`
    // default. That must never be read as "the roster really is empty" —
    // reconciling against it would permanently wipe a saved trend layout for
    // a transient backend hiccup.
    expect(reconcilableRoster({ isPending: false, isError: true, loops: [] })).toBeNull();
  });

  it('passes the real roster through once the query has resolved successfully', () => {
    expect(reconcilableRoster({ isPending: false, isError: false, loops: [1, 2] })).toEqual([
      1, 2,
    ]);
  });
});

/** Every field `StatsResponse` needs beyond `controller_id`; values are inert. */
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

/**
 * Renders the real `MultiTrendPage`, so the assertions below exercise the
 * actual `loopLabel` closure (id→tag join over `useControllers`), not a
 * test-stubbed prop. Loop 2 is on the stats roster but absent from the
 * controller roster — the fallback branch the sibling `SeriesSelector` unit
 * test cannot reach on its own.
 */
function renderPage() {
  const queryClient = createQueryClient();
  queryClient.setQueryData(queryKeys.controllers, [makeController({ id: 1, name: 'FIC-101' })]);
  queryClient.setQueryData(queryKeys.allStats, [statsRow(1), statsRow(2)]);
  queryClient.setQueryData(queryKeys.alarmsActive, []);
  const realtime = createFakeRealtime();
  return render(
    <TestProviders queryClient={queryClient} realtime={realtime.value}>
      <MultiTrendPage />
    </TestProviders>,
  );
}

describe('MultiTrendPage — loop titles (§9.3)', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('titles the selector row `#{id} · {tag}`, falling back to `Loop {id}`', () => {
    renderPage();
    const selector = screen.getByRole('group', { name: 'Séries' });
    expect(within(selector).getByText('#1 · FIC-101')).toBeVisible();
    expect(within(selector).getByText('Loop 2')).toBeVisible();
    // The checkbox accessible name is untouched by the title change.
    expect(within(selector).getByLabelText('Loop 1 · PV')).toBeInTheDocument();
    expect(within(selector).getByLabelText('Loop 2 · CO')).toBeInTheDocument();
  });

  it('titles the chart cell header and its aria-label the same way once occupied', () => {
    renderPage();
    fireEvent.click(screen.getByLabelText('Loop 1 · PV'));
    fireEvent.click(screen.getByLabelText('Loop 2 · PV'));

    const chart = screen.getByTestId('multitrend-chart');
    expect(within(chart).getByText('#1 · FIC-101')).toBeVisible();
    expect(within(chart).getByText('Loop 2')).toBeVisible();
    expect(screen.getByRole('region', { name: 'Tendência #1 · FIC-101' })).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Tendência Loop 2' })).toBeInTheDocument();
  });
});
