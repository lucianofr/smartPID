import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { ReactElement } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AiPanel } from '../AiPanel';
import { ApiError } from '../../../api/client';
import type { AiStatus, TuningRecommendation } from '../commandApi';
import type { AiData, RealtimeEnvelope, RealtimeType } from '../../../realtime/envelope';

const aiActionMutate = vi.fn();
const applyTuningMock = vi.fn();

let aiStatus: { data: AiStatus | undefined } = { data: undefined };
let tuningRec: { data: TuningRecommendation | undefined } = { data: undefined };

vi.mock('../useAiControls', () => ({
  useAiStatus: () => aiStatus,
  useTuningRecommendation: () => tuningRec,
  useAiAction: () => ({ mutate: aiActionMutate, error: null }),
}));

vi.mock('../commandApi', () => ({
  applyTuning: (...args: unknown[]) => applyTuningMock(...args),
}));

// Capture the handler registered for the 'ai' realtime type so tests can drive frames.
let aiHandler: ((env: RealtimeEnvelope<AiData>) => void) | null = null;
const unsubscribe = vi.fn();

vi.mock('../../../realtime/useRealtime', () => ({
  useRealtime: () => ({
    subscribe: (type: RealtimeType, handler: (env: RealtimeEnvelope<AiData>) => void) => {
      if (type === 'ai') aiHandler = handler;
      return unsubscribe;
    },
  }),
}));

function makeStatus(overrides: Partial<AiStatus> = {}): AiStatus {
  return {
    controller_id: 7,
    engine: 'fuzzy',
    objective: 'sp_tracking',
    speed: 'medium',
    current_ki: 0.5,
    last_gamma: 0.12,
    enabled: true,
    ...overrides,
  };
}

function aiFrame(loopId: number, data: AiData): RealtimeEnvelope<AiData> {
  return { type: 'ai', loop_id: loopId, seq: 1, ts: 0, data };
}

function renderWithClient(ui: ReactElement) {
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

const pendingRec: TuningRecommendation = {
  controller_id: 7,
  current_kp: 1.5,
  current_ti: 30,
  current_td: 2,
  recommended_kp: 1.8,
  recommended_ti: 25,
  recommended_td: 1.5,
  reason: 'IAE improvement',
  timestamp: 1,
  status: 'pending',
  source: 'fuzzy',
};

describe('AiPanel', () => {
  beforeEach(() => {
    aiStatus = { data: makeStatus() };
    tuningRec = { data: undefined };
    aiHandler = null;
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('renders status fields from useAiStatus', () => {
    renderWithClient(<AiPanel controllerId={7} />);
    const text = screen.getByTestId('ai-panel').textContent ?? '';
    expect(text).toContain('fuzzy');
    expect(text).toContain('sp_tracking');
    expect(text).toContain('0.5');
    expect(text).toContain('0.12');
  });

  it.each(['start', 'stop', 'pause'] as const)(
    '%s button calls useAiAction mutate with the action',
    (action) => {
      renderWithClient(<AiPanel controllerId={7} />);
      fireEvent.click(screen.getByRole('button', { name: new RegExp(action, 'i') }));
      expect(aiActionMutate).toHaveBeenCalledWith({ id: 7, action });
    },
  );

  it('updates the displayed strategy from an incoming ai frame for the matching loop', () => {
    renderWithClient(<AiPanel controllerId={7} />);
    expect(aiHandler).not.toBeNull();

    // Drive a frame for the matching loop.
    act(() => {
      aiHandler?.(aiFrame(7, { gamma: -0.4, ki: 0.7, strategy: 'disturbance' }));
    });
    expect(screen.getByText(/disturbance/i)).toBeInTheDocument();
  });

  it('ignores an ai frame for a different loop', () => {
    renderWithClient(<AiPanel controllerId={7} />);
    act(() => {
      aiHandler?.(aiFrame(99, { gamma: -0.4, ki: 0.7, strategy: 'other-loop-strategy' }));
    });
    expect(screen.queryByText(/other-loop-strategy/i)).toBeNull();
  });

  it('apply-tuning button is disabled without a pending recommendation', () => {
    renderWithClient(<AiPanel controllerId={7} />);
    expect(screen.getByRole('button', { name: /apply tuning/i })).toBeDisabled();
  });

  it('apply-tuning flow: enabled with pending rec, opens confirm, confirm calls applyTuning', async () => {
    tuningRec = { data: pendingRec };
    applyTuningMock.mockResolvedValue({ ok: true });
    renderWithClient(<AiPanel controllerId={7} />);

    const applyBtn = screen.getByRole('button', { name: /apply tuning/i });
    expect(applyBtn).toBeEnabled();
    expect(applyTuningMock).not.toHaveBeenCalled();

    fireEvent.click(applyBtn);
    // confirm dialog open, but applyTuning must not have fired yet
    expect(applyTuningMock).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: /confirm write/i }));
    await waitFor(() => expect(applyTuningMock).toHaveBeenCalledWith(7));
  });

  it('keeps the confirm dialog open and surfaces the error when apply-tuning is rejected', async () => {
    tuningRec = { data: pendingRec };
    applyTuningMock.mockRejectedValue(new ApiError(409, 'External PID is in MAN mode'));
    renderWithClient(<AiPanel controllerId={7} />);

    fireEvent.click(screen.getByRole('button', { name: /apply tuning/i }));
    fireEvent.click(screen.getByRole('button', { name: /confirm write/i }));

    // Error surfaced to the operator.
    expect(await screen.findByText(/External PID is in MAN mode/i)).toBeInTheDocument();
    // Dialog stays open so the operator can react.
    expect(screen.getByRole('button', { name: /confirm write/i })).toBeInTheDocument();
  });

  it('closes the confirm dialog after a successful apply-tuning write', async () => {
    tuningRec = { data: pendingRec };
    applyTuningMock.mockResolvedValue({ ok: true });
    renderWithClient(<AiPanel controllerId={7} />);

    fireEvent.click(screen.getByRole('button', { name: /apply tuning/i }));
    expect(screen.getByRole('button', { name: /confirm write/i })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /confirm write/i }));

    await waitFor(() =>
      expect(screen.queryByRole('button', { name: /confirm write/i })).toBeNull(),
    );
  });
});
