import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { endpoints } from '@/api/endpoints';
import type { Role, SimulatorStatus } from '@/api/types';
import { statusEnvelope } from '@/test/fixtures';
import { createFakeRealtime, createQueryClient, TestProviders } from '@/test/providers';
import { simulatorApi } from '../api';
import { SimulatorControlPanel } from '../SimulatorControlPanel';
import type { ControllerSimStatus } from '../types';

/**
 * The panel's contract is a permission split: reshaping the model is
 * `simulator.configure` (admin), driving twin SP/mode/CO is `loop.operate`
 * (everyone). Both halves are asserted here, plus the invalidate→refetch loop
 * that is the ONLY way a simulator write becomes visible.
 */

const CONFIG_CONTROLS = [
  'Start',
  'Stop',
  'Inject disturbance',
  'Remove',
  'Apply PID parameters',
] as const;

function controller(overrides: Partial<ControllerSimStatus> = {}): ControllerSimStatus {
  return {
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
    ...overrides,
  };
}

function snapshot(overrides: Partial<ControllerSimStatus> = {}, running = true): SimulatorStatus {
  return { enabled: true, running, controllers: { 1: controller(overrides) } };
}

function renderPanel(options: { role?: Role; status?: SimulatorStatus } = {}) {
  const role = options.role ?? 'admin';
  sessionStorage.setItem('smart-pid-token', 'jwt');
  vi.spyOn(endpoints, 'me').mockResolvedValue({ user_id: 1, username: role, role });
  const statusSpy = vi
    .spyOn(endpoints, 'simulatorStatus')
    .mockResolvedValue(options.status ?? snapshot());
  const realtime = createFakeRealtime();
  const view = render(
    <TestProviders queryClient={createQueryClient()} realtime={realtime.value}>
      <SimulatorControlPanel controllerId={1} />
    </TestProviders>,
  );
  return { ...view, statusSpy, realtime };
}

beforeEach(() => {
  sessionStorage.clear();
  vi.spyOn(simulatorApi, 'start').mockResolvedValue({ ok: true });
  vi.spyOn(simulatorApi, 'preset').mockResolvedValue({ ok: true });
  vi.spyOn(simulatorApi, 'parameters').mockResolvedValue({ ok: true });
  vi.spyOn(simulatorApi, 'injectDisturbance').mockResolvedValue({ ok: true });
  vi.spyOn(simulatorApi, 'clearDisturbance').mockResolvedValue({ ok: true });
  vi.spyOn(simulatorApi, 'setCo').mockResolvedValue({ ok: true });
  vi.spyOn(simulatorApi, 'setSp').mockResolvedValue({ ok: true });
  vi.spyOn(simulatorApi, 'setMode').mockResolvedValue({ ok: true });
  vi.spyOn(simulatorApi, 'setAutoSp').mockResolvedValue(controller());
  vi.spyOn(simulatorApi, 'enablePid').mockResolvedValue({ ok: true });
  vi.spyOn(simulatorApi, 'setPidParams').mockResolvedValue({ ok: true });
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe('SimulatorControlPanel — permission split', () => {
  it('gives an administrator the whole configuration region', async () => {
    renderPanel();
    for (const name of CONFIG_CONTROLS) {
      expect(await screen.findByRole('button', { name })).toBeInTheDocument();
    }
    expect(screen.getByRole('combobox', { name: 'Process preset' })).toBeInTheDocument();
    expect(screen.getByRole('slider', { name: 'Gain' })).toBeInTheDocument();
    expect(screen.getByRole('switch', { name: 'Auto-SP' })).toBeInTheDocument();
    expect(screen.getByRole('switch', { name: 'Enable PID' })).toBeInTheDocument();
  });

  it('shows a user the designed restricted state instead of the configuration region', async () => {
    const { statusSpy } = renderPanel({ role: 'user' });
    expect(await screen.findByText('Simulador gerenciado pelo administrador')).toBeVisible();
    for (const name of CONFIG_CONTROLS) {
      expect(screen.queryByRole('button', { name })).toBeNull();
    }
    expect(screen.queryByRole('combobox', { name: 'Process preset' })).toBeNull();
    expect(screen.queryByRole('switch', { name: 'Auto-SP' })).toBeNull();
    expect(screen.queryByRole('switch', { name: 'Enable PID' })).toBeNull();
    expect(statusSpy).not.toHaveBeenCalled();
  });

  it('still lets a user drive twin SP/mode/CO off the live frame', async () => {
    const { realtime } = renderPanel({ role: 'user' });
    await screen.findByText('Simulador gerenciado pelo administrador');

    // No REST snapshot is readable, so the operate region waits for a frame.
    expect(screen.queryByRole('group', { name: 'Twin mode' })).toBeNull();
    act(() => realtime.emit(statusEnvelope(1, 1, { mode: 'MAN' })));

    expect(screen.getByRole('group', { name: 'Twin mode' })).toBeInTheDocument();
    // makeStatus: sp 55, co 42 — the operate fields seed from the live frame.
    expect(screen.getByRole('spinbutton', { name: 'Setpoint SP' })).toHaveValue(55);
    fireEvent.click(screen.getByRole('button', { name: 'Apply output' }));
    await waitFor(() => expect(simulatorApi.setCo).toHaveBeenCalledWith(1, 42));
  });
});

describe('SimulatorControlPanel — server-owned state', () => {
  it('refetches the snapshot after every write so the panel shows the server, not the click', async () => {
    const { statusSpy } = renderPanel();
    await screen.findByRole('button', { name: 'Start' });
    const before = statusSpy.mock.calls.length;

    fireEvent.change(screen.getByRole('combobox', { name: 'Process preset' }), {
      target: { value: 'TEMPERATURE' },
    });

    await waitFor(() => expect(simulatorApi.preset).toHaveBeenCalledWith({
      controller_id: 1,
      preset: 'TEMPERATURE',
    }));
    await waitFor(() => expect(statusSpy.mock.calls.length).toBeGreaterThan(before));
  });

  it('arms Remove from the server flags, never from the click that injected', async () => {
    const { statusSpy } = renderPanel();
    const remove = await screen.findByRole('button', { name: 'Remove' });
    expect(remove).toBeDisabled();

    statusSpy.mockResolvedValue(snapshot({ step_active: true }));
    fireEvent.change(screen.getByRole('spinbutton', { name: 'Amplitude' }), {
      target: { value: '20' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Inject disturbance' }));

    await waitFor(() =>
      expect(simulatorApi.injectDisturbance).toHaveBeenCalledWith({
        controller_id: 1,
        type: 'step',
        amplitude: 20,
      }),
    );
    await waitFor(() => expect(screen.getByRole('button', { name: 'Remove' })).toBeEnabled());
  });

  it('closes manual injection while Auto-disturbance owns the disturbance', async () => {
    renderPanel({
      status: snapshot({ auto_disturbance: { enabled: true, max_amplitude_pct: 20, period_s: 30 } }),
    });
    expect(await screen.findByRole('button', { name: 'Inject disturbance' })).toBeDisabled();
    expect(screen.getByRole('combobox', { name: 'Disturbance type' })).toBeDisabled();
    expect(screen.getByRole('spinbutton', { name: 'Amplitude' })).toBeDisabled();
    expect(screen.getByText(/Auto-disturbance está ativo/)).toBeVisible();
  });

  it('treats a noise disturbance as active too', async () => {
    renderPanel({ status: snapshot({ noise_active: true }) });
    await waitFor(() => expect(screen.getByRole('button', { name: 'Remove' })).toBeEnabled());
  });

  it('collapses a slider drag into ONE parameters PUT', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    renderPanel();
    const gain = await screen.findByRole('slider', { name: 'Gain' });

    // Radix moves the thumb one `step` per arrow key — three ticks, one gesture.
    for (let i = 0; i < 3; i += 1) fireEvent.keyDown(gain, { key: 'ArrowRight' });
    await act(async () => {
      vi.advanceTimersByTime(300);
    });

    expect(simulatorApi.parameters).toHaveBeenCalledTimes(1);
    expect(simulatorApi.parameters).toHaveBeenCalledWith(
      expect.objectContaining({ controller_id: 1, tau1: 3, tau2: null, dead_time: 1 }),
    );
  });

  it('closes the CO path in AUTO — the PID owns the output there', async () => {
    renderPanel({ status: snapshot({ pid_mode: 1 }) });
    await waitFor(() => expect(screen.getByRole('spinbutton', { name: 'Output CO' })).toBeDisabled());
    expect(screen.getByRole('button', { name: 'Apply output' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'AUTO' })).toHaveAttribute('aria-pressed', 'true');
    // SP stays writable in AUTO — that is the whole point of AUTO.
    expect(screen.getByRole('spinbutton', { name: 'Setpoint SP' })).toBeEnabled();
  });

  it('sends the automation band the server already holds when re-enabling', async () => {
    renderPanel({
      status: snapshot({ auto_sp: { enabled: false, sp_min_pct: 10, sp_max_pct: 90, period_s: 30 } }),
    });
    fireEvent.click(await screen.findByRole('switch', { name: 'Auto-SP' }));
    await waitFor(() =>
      expect(simulatorApi.setAutoSp).toHaveBeenCalledWith(1, {
        enabled: true,
        sp_min_pct: 10,
        sp_max_pct: 90,
        period_s: 30,
      }),
    );
  });

  it('toggling Enable PID calls simulatorApi.enablePid', async () => {
    renderPanel();
    fireEvent.click(await screen.findByRole('switch', { name: 'Enable PID' }));
    await waitFor(() => expect(simulatorApi.enablePid).toHaveBeenCalledWith(1, true));
  });

  it('seeds Kp/Ti/Td from the server and applies edited values', async () => {
    renderPanel({
      status: snapshot({ pid_enabled: true, pid_kp: 2.5, pid_ti: 8, pid_td: 1.2 }),
    });
    expect(await screen.findByRole('spinbutton', { name: 'Kp' })).toHaveValue(2.5);
    expect(screen.getByRole('spinbutton', { name: 'Ti' })).toHaveValue(8);
    expect(screen.getByRole('spinbutton', { name: 'Td' })).toHaveValue(1.2);

    fireEvent.change(screen.getByRole('spinbutton', { name: 'Kp' }), { target: { value: '3' } });
    fireEvent.change(screen.getByRole('spinbutton', { name: 'Ti' }), { target: { value: '12' } });
    fireEvent.change(screen.getByRole('spinbutton', { name: 'Td' }), { target: { value: '0.5' } });
    fireEvent.click(screen.getByRole('button', { name: 'Apply PID parameters' }));

    await waitFor(() =>
      expect(simulatorApi.setPidParams).toHaveBeenCalledWith(1, { kp: 3, ti: 12, td: 0.5 }),
    );
  });

  it('resets the Kp/Ti/Td drafts instead of applying the previous loop\'s values (key={controllerId})', async () => {
    sessionStorage.setItem('smart-pid-token', 'jwt');
    vi.spyOn(endpoints, 'me').mockResolvedValue({ user_id: 1, username: 'admin', role: 'admin' });
    vi.spyOn(endpoints, 'simulatorStatus').mockResolvedValue({
      enabled: true,
      running: true,
      controllers: {
        1: controller({ pid_enabled: true, pid_kp: 1, pid_ti: 10, pid_td: 0 }),
        2: controller({ pid_enabled: true, pid_kp: 7, pid_ti: 20, pid_td: 3 }),
      },
    });
    const realtime = createFakeRealtime();
    const queryClient = createQueryClient();
    const { rerender } = render(
      <TestProviders queryClient={queryClient} realtime={realtime.value}>
        <SimulatorControlPanel controllerId={1} />
      </TestProviders>,
    );

    expect(await screen.findByRole('spinbutton', { name: 'Kp' })).toHaveValue(1);
    // Edit the draft without clicking Apply — a stale draft must not leak onto the next loop.
    fireEvent.change(screen.getByRole('spinbutton', { name: 'Kp' }), { target: { value: '99' } });
    expect(screen.getByRole('spinbutton', { name: 'Kp' })).toHaveValue(99);

    rerender(
      <TestProviders queryClient={queryClient} realtime={realtime.value}>
        <SimulatorControlPanel controllerId={2} />
      </TestProviders>,
    );

    await waitFor(() => expect(screen.getByRole('spinbutton', { name: 'Kp' })).toHaveValue(7));
    expect(screen.getByRole('spinbutton', { name: 'Ti' })).toHaveValue(20);
    expect(screen.getByRole('spinbutton', { name: 'Td' })).toHaveValue(3);
  });

  it('keeps Kp/Ti/Td and Apply editable while the PID is off — staging values before arming it', async () => {
    renderPanel({ status: snapshot({ pid_enabled: false, pid_kp: 1, pid_ti: 10, pid_td: 0 }) });
    expect(await screen.findByRole('spinbutton', { name: 'Kp' })).toBeEnabled();
    expect(screen.getByRole('spinbutton', { name: 'Ti' })).toBeEnabled();
    expect(screen.getByRole('spinbutton', { name: 'Td' })).toBeEnabled();
    expect(screen.getByRole('button', { name: 'Apply PID parameters' })).toBeEnabled();

    fireEvent.change(screen.getByRole('spinbutton', { name: 'Kp' }), { target: { value: '4' } });
    fireEvent.click(screen.getByRole('button', { name: 'Apply PID parameters' }));
    await waitFor(() =>
      expect(simulatorApi.setPidParams).toHaveBeenCalledWith(1, { kp: 4, ti: 10, td: 0 }),
    );
  });

  it('refuses to offer controls for a simulator the server has switched off', async () => {
    renderPanel({ status: { enabled: false, running: false, controllers: {} } });
    expect(await screen.findByText('Simulador desabilitado no servidor')).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Start' })).toBeNull();
  });
});
