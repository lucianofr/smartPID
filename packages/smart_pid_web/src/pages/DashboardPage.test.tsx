import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { endpoints } from '@/api/endpoints';
import { queryKeys } from '@/api/queryKeys';
import type { MeResponse } from '@/api/types';
import { FEEDBACK_PROMPT } from '@/features/feedback/FeedbackBanner';
import { ff, makeController, statusEnvelope } from '@/test/fixtures';
import { createFakeRealtime, createQueryClient, TestProviders } from '@/test/providers';
import { DashboardPage } from './DashboardPage';

const CONTROLLERS = [
  makeController({ id: 1, name: 'FIC-101', description: 'Flow' }),
  makeController({ id: 2, name: 'TIC-202', description: 'Temp' }),
];

function renderDashboard(
  controllers = CONTROLLERS,
  path = '/',
  realtime = createFakeRealtime(),
  me: MeResponse = { user_id: 1, username: 'admin', role: 'admin' },
) {
  localStorage.setItem('smart-pid-token', 'jwt');
  vi.spyOn(endpoints, 'me').mockResolvedValue(me);
  const queryClient = createQueryClient();
  queryClient.setQueryData(queryKeys.controllers, controllers);
  queryClient.setQueryData(queryKeys.alarmsActive, []);
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
  localStorage.clear();
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
    fireEvent.click(screen.getByRole('button', { name: 'TIC-202' }));
    expect(screen.getByRole('complementary', { name: 'Faceplate TIC-202' })).toBeVisible();
    expect(screen.getByRole('img', { name: 'Tendência TIC-202' })).toBeInTheDocument();
  });

  it('resets the faceplate drafts when the selection changes loop', async () => {
    // The faceplate is keyed by the selected loop: an un-submitted tuning
    // draft typed on one loop must not survive the switch, or ENTER on the
    // next loop would write it to the wrong controller.
    renderDashboard();
    const kp = await screen.findByLabelText('Escrever Kp');
    fireEvent.change(kp, { target: { value: '2.2' } });
    fireEvent.click(screen.getByRole('button', { name: 'TIC-202' }));
    expect(screen.getByLabelText('Escrever Kp')).toHaveValue(null);
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

  /**
   * E2E-047 — the whole defect in one assertion: the last frame is still on
   * screen (blanking it would be worse), but nothing about it may read as the
   * plant's current state.
   */
  it('marks every card reading as not current once the bus goes quiet', () => {
    const frozen = createFakeRealtime({ stale: true, staleSince: Date.now() - 30_000 });
    renderDashboard(CONTROLLERS, '/', frozen);
    act(() => {
      frozen.emit(statusEnvelope(1, 1, { pv: ff(11.5) }));
    });
    const [first] = within(screen.getByRole('region', { name: 'Malhas' })).getAllByRole('listitem');
    const pv = within(first).getByRole('meter', { name: 'PV' });
    expect(pv).toHaveAttribute('aria-valuenow', '11.5');
    expect(pv).toHaveAttribute('aria-valuetext', expect.stringContaining('desatualizado'));
  });

  it('offers the demo account a line to the developer', async () => {
    renderDashboard(CONTROLLERS, '/', createFakeRealtime(), {
      user_id: 3,
      username: 'demo',
      role: 'user',
    });
    expect(await screen.findByText(FEEDBACK_PROMPT)).toBeVisible();
  });

  it('keeps the developer invitation off a real operator page', async () => {
    renderDashboard();
    await waitFor(() => expect(endpoints.me).toHaveBeenCalled());
    expect(screen.queryByText(FEEDBACK_PROMPT)).toBeNull();
  });
});
