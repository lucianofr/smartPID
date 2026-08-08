import type { ReactNode } from 'react';
import { renderHook, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '@/api/client';
import { endpoints } from '@/api/endpoints';
import type { FuzzyTraceResponse } from '@/api/types';
import { createQueryClient, TestProviders } from '@/test/providers';
import { toFuzzyView, useFuzzyTrace } from './useFuzzyTrace';

function traceDto(overrides: Partial<FuzzyTraceResponse> = {}): FuzzyTraceResponse {
  return {
    controller_id: 7,
    objective: 'DISTURBANCE_REJECTION',
    timestamp: 1,
    delta_ti: -0.25,
    inputs: [
      {
        name: 'iae',
        value: 4,
        domain_min: 0,
        domain_max: 8,
        functions: [{ label: 'HIGH', kind: 'trapezoid', params: [2, 4, 8, 8], degree: 0.6 }],
      },
    ],
    rules: [
      { index: 1, conditions: { iae: 'HIGH' }, output: 'R', strength: 0.6, fired: true },
    ],
    outputs: [{ label: 'R', center: -0.15, strength: 0.6 }],
    ...overrides,
  };
}

function setup(controllerId: number | null, queryClient = createQueryClient()) {
  const wrapper = ({ children }: { children: ReactNode }) => (
    <TestProviders queryClient={queryClient}>{children}</TestProviders>
  );
  return renderHook(() => useFuzzyTrace(controllerId), { wrapper });
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe('toFuzzyView (pure)', () => {
  it('maps domain_min/domain_max to domainMin/domainMax and preserves rule identity fields', () => {
    const view = toFuzzyView(traceDto());
    expect(view.inputs[0]).toMatchObject({ domainMin: 0, domainMax: 8 });
    expect(view.rules[0]).toMatchObject({ index: 1, fired: true, strength: 0.6 });
    expect(view.deltaTi).toBe(-0.25);
  });
});

describe('useFuzzyTrace', () => {
  it('stays disabled and issues no request while no loop is selected', () => {
    const spy = vi.spyOn(endpoints, 'fuzzyTrace');
    const { result } = setup(null);
    expect(spy).not.toHaveBeenCalled();
    // TanStack keeps a disabled, never-fetched query's status 'pending' — the
    // page never reaches this state itself (selectedId is only null when the
    // roster has no FUZZY loop, which short-circuits to its own empty state
    // before the trace section renders).
    expect(result.current.isPending).toBe(true);
    expect(result.current.view).toBeUndefined();
  });

  it('maps a successful trace to the view model', async () => {
    vi.spyOn(endpoints, 'fuzzyTrace').mockResolvedValue(traceDto());
    const { result } = setup(7);
    await waitFor(() => expect(result.current.view).toBeDefined());
    expect(result.current.view?.controllerId).toBe(7);
    expect(result.current.isError).toBe(false);
    expect(result.current.notRun).toBe(false);
  });

  it('surfaces a 404 as notRun, not as an error, and does not retry it', async () => {
    const spy = vi
      .spyOn(endpoints, 'fuzzyTrace')
      .mockRejectedValue(new ApiError(404, 'not-found', 'No fuzzy inference recorded'));
    const { result } = setup(7);
    await waitFor(() => expect(result.current.notRun).toBe(true));
    expect(result.current.isError).toBe(false);
    expect(result.current.view).toBeUndefined();
    expect(spy).toHaveBeenCalledTimes(1);
  });

  it('surfaces a genuine server failure as isError, distinct from notRun', async () => {
    vi.spyOn(endpoints, 'fuzzyTrace').mockRejectedValue(new ApiError(500, 'server', 'boom'));
    const { result } = setup(7);
    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.notRun).toBe(false);
  });
});
