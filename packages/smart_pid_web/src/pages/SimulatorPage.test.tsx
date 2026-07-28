import { act, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { endpoints } from '@/api/endpoints';
import { queryKeys } from '@/api/queryKeys';
import type { Role, SimulatorStatus } from '@/api/types';
import type { ControllerSimStatus } from '@/features/simulator/types';
import { makeController, statusEnvelope } from '@/test/fixtures';
import { createFakeRealtime, createQueryClient, TestProviders } from '@/test/providers';
import { SimulatorPage } from './SimulatorPage';

const SIM_CONTROLLER: ControllerSimStatus = {
  preset: 'FLOW',
  gain: 1.2,
  tau1: 3,
  tau2: null,
  dead_time: 1,
  step_active: false,
  step_amplitude: 0,
  noise_active: false,
  noise_amplitude: 0,
  pid_enabled: false,
  pid_kp: 1,
  pid_ti: 10,
  pid_td: 0,
  pid_mode: 0,
  pid_cv: 0,
  co: 40,
  sp: 50,
  pv: 50,
  error: 0,
  process_input: 0,
  process_output: 0,
  disturbance_output: 0,
  auto_sp: null,
  auto_disturbance: null,
};

function renderPage(options: { role?: Role; status?: SimulatorStatus } = {}) {
  const role = options.role ?? 'admin';
  sessionStorage.setItem('smart-pid-token', 'jwt');
  vi.spyOn(endpoints, 'me').mockResolvedValue({ user_id: 1, username: role, role });
  vi.spyOn(endpoints, 'simulatorStatus').mockResolvedValue(
    options.status ?? { enabled: true, running: true, controllers: { 1: SIM_CONTROLLER } },
  );
  const queryClient = createQueryClient();
  queryClient.setQueryData(queryKeys.controllers, [makeController({ id: 1, name: 'FIC-101' })]);
  const realtime = createFakeRealtime();
  return {
    realtime,
    ...render(
      <TestProviders queryClient={queryClient} realtime={realtime.value}>
        <SimulatorPage />
      </TestProviders>,
    ),
  };
}

beforeEach(() => sessionStorage.clear());
afterEach(() => vi.restoreAllMocks());

describe('SimulatorPage', () => {
  it('always fronts the page with the simulation-mode live region', async () => {
    renderPage({ status: { enabled: true, running: false, controllers: { 1: SIM_CONTROLLER } } });
    expect(screen.getByRole('status', { name: 'Simulation mode' })).toBeVisible();
    expect(screen.getByText('MODO SIMULAÇÃO')).toBeVisible();
    await waitFor(() => expect(screen.getByTestId('sim-running')).toHaveTextContent('Stopped'));
  });

  it('announces SIMULAÇÃO ATIVA once the twin is stepping', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText('SIMULAÇÃO ATIVA')).toBeVisible());
    expect(screen.getByTestId('sim-running')).toHaveTextContent('Running');
  });

  it('hides the loop selector for a single-controller twin', async () => {
    renderPage();
    await screen.findByRole('combobox', { name: 'Process preset' });
    expect(screen.queryByRole('combobox', { name: 'Simulator loop' })).toBeNull();
  });

  it('offers a loop selector once the twin holds more than one controller', async () => {
    renderPage({
      status: {
        enabled: true,
        running: true,
        controllers: { 1: SIM_CONTROLLER, 2: { ...SIM_CONTROLLER, preset: 'LEVEL' } },
      },
    });
    const selector = await screen.findByRole('combobox', { name: 'Simulator loop' });
    expect(selector).toHaveValue('1');
  });

  it('renders the twin trend and feeds it live frames', async () => {
    const { realtime } = renderPage();
    const trend = await screen.findByRole('region', { name: 'Twin response trend' });
    expect(trend).toBeInTheDocument();

    act(() => realtime.emit(statusEnvelope(1, 1, { timestamp: '2026-06-19T00:00:01.000Z' })));
    // makeStatus PV is 50 — the header readout follows the live frame.
    await waitFor(() => expect(screen.getByText('50.0')).toBeVisible());
  });

  it('keeps the page reachable for a user, falling back to the controller roster', async () => {
    const statusSpy = vi.spyOn(endpoints, 'simulatorStatus');
    renderPage({ role: 'user' });
    expect(await screen.findByText('Simulador gerenciado pelo administrador')).toBeVisible();
    expect(screen.getByRole('status', { name: 'Simulation mode' })).toBeVisible();
    // The twin loop id came from /controllers, not from the forbidden snapshot.
    expect(screen.getByRole('region', { name: 'Twin response trend' })).toBeInTheDocument();
    expect(statusSpy).not.toHaveBeenCalled();
  });
});
