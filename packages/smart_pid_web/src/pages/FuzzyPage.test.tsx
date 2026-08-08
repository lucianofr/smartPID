import { fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '@/api/client';
import { endpoints } from '@/api/endpoints';
import { queryKeys } from '@/api/queryKeys';
import type { ControllerResponse, FuzzyTraceResponse } from '@/api/types';
import { makeController } from '@/test/fixtures';
import { createQueryClient, TestProviders } from '@/test/providers';
import { FuzzyPage } from './FuzzyPage';

function aiConfig(engine: string): ControllerResponse['ai_config'] {
  return {
    dead_time_l: 1,
    engine,
    limit_max: 100,
    limit_min: 0.1,
    objective: 'DISTURBANCE_REJECTION',
    rl_fallback_kd: 0.2,
    rl_fallback_kp: 0.6,
    rl_learning_rate: 0.0003,
    rl_train_interval: 32,
    sl_co_ramp_max_pct_min: 10,
    sl_error_small_pct: 5,
  };
}

// An RL loop, a NONE (opted-out) loop, and a FUZZY-configured loop whose
// optimizer is switched off — none of the three is an active FUZZY loop.
const RL_LOOP = makeController({
  id: 1,
  name: 'RL-101',
  optimization_enabled: true,
  ai_config: aiConfig('RL'),
});
const NONE_LOOP = makeController({
  id: 2,
  name: 'NONE-101',
  optimization_enabled: true,
  ai_config: aiConfig('NONE'),
});
const DISABLED_FUZZY_LOOP = makeController({
  id: 3,
  name: 'OFF-101',
  optimization_enabled: false,
  ai_config: aiConfig('FUZZY'),
});
const FUZZY_LOOP_A = makeController({
  id: 4,
  name: 'FIC-401',
  optimization_enabled: true,
  ai_config: aiConfig('FUZZY'),
});
const FUZZY_LOOP_B = makeController({
  id: 5,
  name: 'FIC-402',
  optimization_enabled: true,
  ai_config: aiConfig('FUZZY'),
});

function twoInputTrace(controllerId: number): FuzzyTraceResponse {
  return {
    controller_id: controllerId,
    objective: 'DISTURBANCE_REJECTION',
    timestamp: 1700000000,
    delta_ti: -0.42,
    inputs: [
      {
        name: 'iae',
        value: 3,
        domain_min: 0,
        domain_max: 6,
        functions: [{ label: 'HIGH', kind: 'trapezoid', params: [2, 4, 6, 6], degree: 0.5 }],
      },
      {
        name: 'osc',
        value: 1,
        domain_min: 0,
        domain_max: 2,
        functions: [{ label: 'STABLE', kind: 'triangle', params: [0, 0, 1], degree: 0.9 }],
      },
    ],
    rules: [
      { index: 1, conditions: { iae: 'HIGH', osc: 'STABLE' }, output: 'R', strength: 0.5, fired: true },
      { index: 2, conditions: { iae: 'LOW', osc: 'STABLE' }, output: 'M', strength: 0, fired: false },
    ],
    outputs: [
      { label: 'R', center: -0.1, strength: 0.5 },
      { label: 'M', center: 0, strength: 0 },
    ],
  };
}

function oneInputTrace(controllerId: number, inputName: string): FuzzyTraceResponse {
  return {
    controller_id: controllerId,
    objective: 'DISTURBANCE_REJECTION',
    timestamp: 1700000100,
    delta_ti: 0.1,
    inputs: [
      {
        name: inputName,
        value: 2,
        domain_min: 0,
        domain_max: 4,
        functions: [{ label: 'LOW', kind: 'trapezoid', params: [0, 0, 2, 4], degree: 0.3 }],
      },
    ],
    rules: [{ index: 1, conditions: { [inputName]: 'LOW' }, output: 'M', strength: 0.3, fired: true }],
    outputs: [{ label: 'M', center: 0, strength: 0.3 }],
  };
}

function renderFuzzy(
  controllers: ControllerResponse[],
  preseed: ReadonlyArray<readonly [number, FuzzyTraceResponse]> = [],
) {
  const queryClient = createQueryClient();
  queryClient.setQueryData(queryKeys.controllers, controllers);
  for (const [id, dto] of preseed) {
    queryClient.setQueryData(queryKeys.fuzzyTrace(id), dto);
  }
  return {
    ...render(
      <TestProviders queryClient={queryClient}>
        <FuzzyPage />
      </TestProviders>,
    ),
    queryClient,
  };
}

function openLoopSelect() {
  fireEvent.keyDown(screen.getByRole('combobox', { name: 'Malha' }), { key: 'Enter' });
  return screen.findByRole('listbox');
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe('FuzzyPage', () => {
  it('lists only loops whose active engine is FUZZY — RL, NONE, and a disabled-optimizer FUZZY loop are excluded', async () => {
    renderFuzzy(
      [RL_LOOP, NONE_LOOP, DISABLED_FUZZY_LOOP, FUZZY_LOOP_A],
      [[FUZZY_LOOP_A.id, oneInputTrace(FUZZY_LOOP_A.id, 'iae')]],
    );
    const listbox = await openLoopSelect();
    expect(within(listbox).getAllByRole('option').map((o) => o.textContent)).toEqual(['FIC-401']);
  });

  it('renders one membership-function plot per input and the full rule table, and swaps on selection', async () => {
    // Mocked by id, not preseeded: the second loop's query is unobserved
    // until it is picked, and `createQueryClient()`'s `gcTime: 0` evicts an
    // unobserved cache entry almost immediately — switching to it must
    // genuinely refetch, exactly like the real page does.
    vi.spyOn(endpoints, 'fuzzyTrace').mockImplementation((controllerId) =>
      Promise.resolve(
        controllerId === FUZZY_LOOP_A.id
          ? twoInputTrace(controllerId)
          : oneInputTrace(controllerId, 'error'),
      ),
    );
    renderFuzzy([FUZZY_LOOP_A, FUZZY_LOOP_B]);
    expect(await screen.findByRole('img', { name: 'Funções de pertinência de iae' })).toBeVisible();
    expect(screen.getByRole('img', { name: 'Funções de pertinência de osc' })).toBeVisible();
    expect(screen.getByText('Base de regras fuzzy')).toBeVisible();
    expect(screen.getByTestId('rule-row-1')).toBeInTheDocument();
    expect(screen.getByTestId('rule-row-2')).toBeInTheDocument();

    const listbox = await openLoopSelect();
    fireEvent.click(within(listbox).getByRole('option', { name: 'FIC-402' }));

    expect(await screen.findByRole('img', { name: 'Funções de pertinência de error' })).toBeVisible();
    expect(screen.queryByRole('img', { name: 'Funções de pertinência de iae' })).not.toBeInTheDocument();
  });

  it('falls back to the first FUZZY loop when the picked one leaves the fuzzy set', async () => {
    vi.spyOn(endpoints, 'fuzzyTrace').mockImplementation((controllerId) =>
      Promise.resolve(oneInputTrace(controllerId, 'iae')),
    );
    const { queryClient } = renderFuzzy([FUZZY_LOOP_A, FUZZY_LOOP_B]);
    const listbox = await openLoopSelect();
    fireEvent.click(within(listbox).getByRole('option', { name: 'FIC-402' }));
    expect(await screen.findByRole('combobox', { name: 'Malha' })).toHaveTextContent('FIC-402');

    // The operator switches FIC-402's optimizer off from another surface: it
    // is no longer an active FUZZY loop, so the selection cannot stay on it.
    queryClient.setQueryData(queryKeys.controllers, [
      FUZZY_LOOP_A,
      { ...FUZZY_LOOP_B, optimization_enabled: false },
    ]);

    expect(await screen.findByRole('combobox', { name: 'Malha' })).toHaveTextContent('FIC-401');
    const reopened = await openLoopSelect();
    expect(within(reopened).getAllByRole('option').map((o) => o.textContent)).toEqual(['FIC-401']);
  });

  it('renders the "no execution yet" empty state on a 404, never an error state', async () => {
    vi.spyOn(endpoints, 'fuzzyTrace').mockRejectedValue(
      new ApiError(404, 'not-found', 'No fuzzy inference recorded'),
    );
    renderFuzzy([FUZZY_LOOP_A]);
    expect(
      await screen.findByText('Nenhuma execução fuzzy registrada para esta malha ainda.'),
    ).toBeVisible();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('shows the "no fuzzy loop configured" empty state and issues no request when no loop runs FUZZY', () => {
    const spy = vi.spyOn(endpoints, 'fuzzyTrace');
    renderFuzzy([RL_LOOP, NONE_LOOP, DISABLED_FUZZY_LOOP]);
    expect(screen.getByText('Nenhuma malha usa o motor fuzzy.')).toBeVisible();
    expect(spy).not.toHaveBeenCalled();
  });

  it('renders the legend, scoped to the terms the current trace puts on screen', async () => {
    renderFuzzy(
      [FUZZY_LOOP_A],
      [[FUZZY_LOOP_A.id, oneInputTrace(FUZZY_LOOP_A.id, 'iae')]],
    );
    expect(await screen.findByText('Legenda')).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'iae' })).toBeInTheDocument();
  });

  it('shows no legend on the "no execution yet" empty state — no terms are on screen to explain', async () => {
    vi.spyOn(endpoints, 'fuzzyTrace').mockRejectedValue(
      new ApiError(404, 'not-found', 'No fuzzy inference recorded'),
    );
    renderFuzzy([FUZZY_LOOP_A]);
    await screen.findByText('Nenhuma execução fuzzy registrada para esta malha ainda.');
    expect(screen.queryByText('Legenda')).not.toBeInTheDocument();
  });
});
