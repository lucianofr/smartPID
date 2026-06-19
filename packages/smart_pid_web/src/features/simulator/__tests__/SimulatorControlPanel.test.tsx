import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import * as api from '../api';
import { SimulatorControlPanel } from '../SimulatorControlPanel';

vi.mock('../api');
vi.mock('../../../realtime/useRealtime', () => ({
  useRealtime: () => ({
    connected: true, lastStatus: new Map([[1, { pv: 50, sp: 50, co: 0, mode: 'MAN' }]]),
    lastStats: new Map(), subscribe: () => () => {}, onResync: () => () => {},
  }),
}));

const wrapper = ({ children }: { children: React.ReactNode }) => {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.getSimulatorStatus).mockResolvedValue({
    enabled: true, running: false,
    controllers: { 1: {
      preset: 'FLOW', gain: 1.2, tau1: 3, tau2: null, dead_time: 1,
      step_active: false, step_amplitude: 0, noise_active: false, noise_amplitude: 0,
      pid_mode: 0, co: 0, sp: 50, pv: 50, auto_sp: null, auto_disturbance: null,
    } as never },
  });
  vi.mocked(api.setPreset).mockResolvedValue({ ok: true });
  vi.mocked(api.injectDisturbance).mockResolvedValue({ ok: true });
});

describe('SimulatorControlPanel', () => {
  it('applies a preset change through the preset mutation', async () => {
    render(<SimulatorControlPanel controllerId={1} />, { wrapper });
    await waitFor(() => expect(screen.getByRole('combobox', { name: /process preset/i })).toBeInTheDocument());
    fireEvent.change(screen.getByRole('combobox', { name: /process preset/i }), { target: { value: 'LEVEL' } });
    await waitFor(() => expect(api.setPreset).toHaveBeenCalledWith({ controller_id: 1, preset: 'LEVEL' }));
  });
  it('injects a disturbance through the disturbance mutation', async () => {
    render(<SimulatorControlPanel controllerId={1} />, { wrapper });
    await waitFor(() => expect(screen.getByRole('button', { name: /inject/i })).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: /inject/i }));
    await waitFor(() => expect(api.injectDisturbance).toHaveBeenCalledWith(
      expect.objectContaining({ controller_id: 1, type: 'step' })));
  });
});

describe('SimulatorControlPanel — dynamics params debounce', () => {
  beforeEach(() => {
    vi.mocked(api.setParameters).mockResolvedValue({ ok: true });
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it('collapses several rapid dynamics commits into a single setParameters call', async () => {
    render(<SimulatorControlPanel controllerId={1} />, { wrapper });
    // Wait for the controller status to resolve and sliders to render.
    const gainSlider = await screen.findByRole('slider', { name: /gain/i });

    vi.useFakeTimers();
    // Several rapid slider drag ticks fire onCommit on each onChange.
    act(() => {
      fireEvent.change(gainSlider, { target: { value: '1.5' } });
      fireEvent.change(gainSlider, { target: { value: '2.0' } });
      fireEvent.change(gainSlider, { target: { value: '2.5' } });
    });

    // Before the debounce window elapses, no request is sent.
    expect(api.setParameters).not.toHaveBeenCalled();

    // Advance past the debounce trailing window; the async flush lets the
    // React Query mutation reach the (mocked) api.setParameters call.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(300);
    });

    expect(api.setParameters).toHaveBeenCalledTimes(1);
    expect(api.setParameters).toHaveBeenCalledWith(
      expect.objectContaining({ controller_id: 1, gain: 2.5 }),
    );
  });
});
