import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { endpoints } from '@/api/endpoints';
import { queryKeys } from '@/api/queryKeys';
import { ff, makeController, statusEnvelope } from '@/test/fixtures';
import { createFakeRealtime, createQueryClient, TestProviders } from '@/test/providers';
import { DashboardPage } from './DashboardPage';

const CONTROLLERS = [
  makeController({ id: 1, name: 'FIC-101', description: 'Flow' }),
  makeController({ id: 2, name: 'TIC-202', description: 'Temp' }),
];

function renderDashboard(controllers = CONTROLLERS, path = '/') {
  sessionStorage.setItem('smart-pid-token', 'jwt');
  vi.spyOn(endpoints, 'me').mockResolvedValue({ user_id: 1, username: 'admin', role: 'admin' });
  const queryClient = createQueryClient();
  queryClient.setQueryData(queryKeys.controllers, controllers);
  queryClient.setQueryData(queryKeys.alarmsActive, []);
  const realtime = createFakeRealtime();
  return {
    ...render(
      <TestProviders queryClient={queryClient} realtime={realtime.value} initialEntries={[path]}>
        <DashboardPage />
      </TestProviders>,
    ),
    realtime,
    queryClient,
  };
}

beforeEach(() => {
  sessionStorage.clear();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('DashboardPage', () => {
  it('renders one card per loop in a single non-wrapping scroller', () => {
    renderDashboard();
    const strip = within(screen.getByRole('region', { name: 'Malhas' })).getByRole('list');
    expect(strip.className).toContain('flex-nowrap');
    expect(strip.className).toContain('overflow-x-auto');
    expect(strip.className).not.toContain('flex-wrap');
    expect(within(strip).getAllByRole('listitem')).toHaveLength(2);
  });

  it('fans live status frames out to the right cards', () => {
    const { realtime } = renderDashboard();
    act(() => {
      // One burst, two loops: batching must not collapse them into one update.
      realtime.emit(statusEnvelope(1, 1, { pv: ff(11.5) }));
      realtime.emit(statusEnvelope(2, 2, { pv: ff(22.5) }));
    });
    const [first, second] = within(screen.getByRole('region', { name: 'Malhas' })).getAllByRole(
      'listitem',
    );
    expect(within(first).getByRole('meter', { name: 'PV' })).toHaveAttribute(
      'aria-valuenow',
      '11.5',
    );
    expect(within(second).getByRole('meter', { name: 'PV' })).toHaveAttribute(
      'aria-valuenow',
      '22.5',
    );
  });

  it('shows the first loop in the trend and faceplate, and follows the selection', () => {
    renderDashboard();
    expect(screen.getByRole('complementary', { name: 'Faceplate FIC-101' })).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: 'Abrir TIC-202' }));
    expect(screen.getByRole('complementary', { name: 'Faceplate TIC-202' })).toBeVisible();
    expect(screen.getByRole('img', { name: 'Tendência TIC-202' })).toBeInTheDocument();
  });

  it('preselects the loop named by ?loop= so a bad-actor row lands on it', () => {
    renderDashboard(CONTROLLERS, '/?loop=2');
    expect(screen.getByRole('complementary', { name: 'Faceplate TIC-202' })).toBeVisible();
  });

  it('ignores a ?loop= that names no configured loop', () => {
    renderDashboard(CONTROLLERS, '/?loop=nope');
    expect(screen.getByRole('complementary', { name: 'Faceplate FIC-101' })).toBeVisible();
  });

  it('stacks the faceplate under the trend below 1024 and splits them above', () => {
    renderDashboard();
    const detail = screen.getByTestId('dashboard-detail');
    expect(detail.className).toContain('flex-col');
    expect(detail.className).toContain('lg:flex-row');
    // ~320px faceplate only once the row layout applies.
    expect(screen.getByRole('complementary', { name: 'Faceplate FIC-101' }).className).toContain(
      'lg:w-80',
    );
  });

  it('keeps the alarm footer mounted with the loops', () => {
    renderDashboard();
    expect(screen.getByRole('contentinfo', { name: 'Alarm summary' })).toBeVisible();
    expect(screen.getByRole('button', { name: 'ACK ALL' })).toBeInTheDocument();
  });

  it('keeps the footer reachable when there are no loops at all', () => {
    renderDashboard([]);
    expect(screen.getByText('Nenhuma malha configurada.')).toBeVisible();
    expect(screen.getByRole('button', { name: 'ACK ALL' })).toBeInTheDocument();
  });

  it('stays silent about simulation while the twin is stopped', () => {
    renderDashboard();
    expect(screen.queryByRole('status', { name: 'Simulation mode' })).toBeNull();
  });

  it('tells the operator when the numbers on the Loops page come from a model', async () => {
    const { queryClient } = renderDashboard();
    queryClient.setQueryData(queryKeys.simulatorStatus, {
      enabled: true,
      running: true,
      controllers: {},
    });
    expect(await screen.findByRole('status', { name: 'Simulation mode' })).toBeVisible();
  });
});
