import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, fireEvent } from '@testing-library/react';
import type { ReactElement } from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { Faceplate } from './Faceplate';
import type { StatusData, FFSignal } from '../realtime/envelope';

// Faceplate reuses the Fatia 2 apply-tuning flow via a real useMutation (mirroring AiPanel),
// so renders need a QueryClient — the same canonical test harness AiPanel's own test uses.
// This wraps, it does not stub: the mutation logic is the production code, untouched.
function renderFaceplate(ui: ReactElement) {
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

// FFSignal-shaped factory: the numeric reading lives at `.value` (matches the wire dicts
// produced by monitor_worker.py / pid_worker.py and decoded by RealtimeProvider).
const sig = (v: number): FFSignal => ({
  value: v,
  severity: 'GOOD',
  limit_bits: 'NONE',
  sub_status: 'NON_SPECIFIC',
});

const statusMap = new Map<number, StatusData>();

// Top-level mutation spies so assertions can inspect the payloads passed to the
// Fatia 2 command hooks (no mutation logic is duplicated — the hooks are mocked).
const setMode = vi.fn();
const setSetpoint = vi.fn();
const setOutput = vi.fn();

vi.mock('../realtime/useRealtime', () => ({
  useRealtime: () => ({
    connected: true,
    lastStatus: statusMap,
    lastStats: new Map(),
    subscribe: () => () => {},
    onResync: () => () => {},
  }),
}));

vi.mock('../features/loop-config/useCommands', () => ({
  useModeMutation: () => ({ mutate: setMode, isPending: false }),
  useSetpointMutation: () => ({ mutate: setSetpoint, isPending: false }),
  useOutputMutation: () => ({ mutate: setOutput, isPending: false }),
}));

// No pending recommendation -> Apply tuning disabled, dialog not rendered, no QueryClient needed.
vi.mock('../features/loop-config/useAiControls', () => ({
  useTuningRecommendation: () => ({ data: undefined }),
}));

const scale = { euMin: 0, euMax: 200, unit: '°C' };

function seedAuto() {
  statusMap.clear();
  statusMap.set(5, {
    pv: sig(150.2),
    sp: sig(152.0),
    co: sig(64.0),
    bkcal_in: sig(0),
    bkcal_out: sig(0),
    mode: 'AUTO',
    kp: 1,
    ti: 30,
    td: 0,
    integral_val: 0,
    timestamp: 0,
  });
}

describe('Faceplate', () => {
  beforeEach(() => {
    setMode.mockClear();
    setSetpoint.mockClear();
    setOutput.mockClear();
    seedAuto();
  });

  it('renders the tag and live PV/SP/CO readouts', () => {
    renderFaceplate(<Faceplate controllerId={5} tag="TIC-101" scale={scale} />);
    expect(screen.getByText('TIC-101')).toBeInTheDocument();
    // PV/SP/CO each surface in both the headline readout and the AnalogBar, so >=1 match.
    expect(screen.getAllByText(/150\.2/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/152\.0/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/64\.0/).length).toBeGreaterThan(0);
  });

  it('renders the 8 standard mode buttons with the active mode pressed', () => {
    renderFaceplate(<Faceplate controllerId={5} tag="TIC-101" scale={scale} />);
    for (const m of ['OOS', 'IMAN', 'LO', 'MAN', 'AUTO', 'CAS', 'RCAS', 'ROUT']) {
      expect(screen.getByRole('button', { name: m })).toBeInTheDocument();
    }
    expect(screen.getByRole('button', { name: 'AUTO' })).toHaveAttribute('aria-pressed', 'true');
  });

  it('issues a mode command with the Fatia 2 payload shape when a mode is clicked', () => {
    renderFaceplate(<Faceplate controllerId={5} tag="TIC-101" scale={scale} />);
    fireEvent.click(screen.getByRole('button', { name: 'MAN' }));
    expect(setMode).toHaveBeenCalledWith({ id: 5, mode: 'MAN' });
  });

  it('gates the manual CO control on MAN mode', () => {
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    const { rerender } = render(
      <QueryClientProvider client={client}>
        <Faceplate controllerId={5} tag="TIC-101" scale={scale} />
      </QueryClientProvider>,
    );
    expect(screen.getByLabelText('Manual CO')).toBeDisabled();

    statusMap.set(5, { ...statusMap.get(5)!, mode: 'MAN' });
    rerender(
      <QueryClientProvider client={client}>
        <Faceplate controllerId={5} tag="TIC-101" scale={scale} />
      </QueryClientProvider>,
    );
    expect(screen.getByLabelText('Manual CO')).not.toBeDisabled();
  });

  it('exposes PV on the first faceplate meter via aria-valuenow', () => {
    renderFaceplate(<Faceplate controllerId={5} tag="TIC-101" scale={scale} />);
    expect(screen.getAllByRole('meter')[0]).toHaveAttribute('aria-valuenow', '150.2');
  });

  it('commits a setpoint command with the Fatia 2 payload shape', () => {
    renderFaceplate(<Faceplate controllerId={5} tag="TIC-101" scale={scale} />);
    const sp = screen.getByLabelText('Setpoint');
    fireEvent.change(sp, { target: { value: '160' } });
    fireEvent.blur(sp);
    expect(setSetpoint).toHaveBeenCalledWith({ id: 5, value: 160 });
  });

  it('disables Apply tuning when there is no pending recommendation', () => {
    renderFaceplate(<Faceplate controllerId={5} tag="TIC-101" scale={scale} />);
    expect(screen.getByRole('button', { name: /apply tuning/i })).toBeDisabled();
  });

  it('shows a waiting state when no status frame has arrived', () => {
    statusMap.clear();
    renderFaceplate(<Faceplate controllerId={5} tag="TIC-101" scale={scale} />);
    expect(screen.getByText('TIC-101')).toBeInTheDocument();
    expect(screen.getByText(/no data|aguardando|waiting/i)).toBeInTheDocument();
  });
});
