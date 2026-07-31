import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { endpoints } from '@/api/endpoints';
import { queryKeys } from '@/api/queryKeys';
import type { AiStatus, Role } from '@/api/types';
import type { AiData, RealtimeEnvelope } from '@/lib/envelope';
import { makeController } from '@/test/fixtures';
import { createFakeRealtime, createQueryClient, TestProviders } from '@/test/providers';
import { AiPanel } from '../AiPanel';
import { tuningRecommendationKey } from '../useAiControls';
import type { TuningRecommendation } from '../commandApi';

const fetchMock = vi.fn();

const PENDING: TuningRecommendation = {
  controller_id: 5,
  current_kp: 1.2,
  current_ti: 30,
  current_td: 0,
  recommended_kp: 1.5,
  recommended_ti: 25,
  recommended_td: 0,
  reason: 'Fuzzy convergiu',
  timestamp: 1,
  status: 'pending',
  source: 'FUZZY',
};

function aiEvent(seq: number, overrides: Partial<AiData> = {}): RealtimeEnvelope<AiData> & {
  type: 'ai';
} {
  return {
    type: 'ai',
    loop_id: 5,
    seq,
    ts: seq,
    data: {
      controller_id: 5,
      gamma: 0.42,
      new_ki: 0.03,
      engine: 'FUZZY',
      objective: 'SP_TRACKING',
      integral_type: 'TIME_TI',
      execution_mode: 'SUPERVISORY',
      reasoning: 'erro alto, subindo Ki',
      timestamp: '2026-07-26T10:00:00Z',
      ...overrides,
    },
  };
}

/** Backend default: an engine configured but never started. */
const aiStatus = (overrides: Partial<AiStatus> = {}): AiStatus => ({
  controller_id: 5,
  engine: 'FUZZY',
  objective: 'SP_TRACKING',
  speed: 'MEDIUM',
  current_ki: 0.03,
  last_gamma: null,
  enabled: false,
  paused: false,
  ...overrides,
});

function renderAi(
  options: {
    role?: Role;
    recommendation?: TuningRecommendation;
    engine?: string;
    status?: Partial<AiStatus>;
  } = {},
) {
  const role = options.role ?? 'admin';
  sessionStorage.setItem('smart-pid-token', 'jwt');
  vi.spyOn(endpoints, 'me').mockResolvedValue({ user_id: 1, username: role, role });
  const controller = makeController({ id: 5, name: 'PIC-005' });
  controller.ai_config = { ...controller.ai_config, engine: options.engine ?? 'FUZZY' };
  const queryClient = createQueryClient();
  queryClient.setQueryData(queryKeys.controllers, [controller]);
  queryClient.setQueryData(queryKeys.aiStatus(5), { ...aiStatus(), ...options.status });
  if (options.recommendation !== undefined) {
    queryClient.setQueryData(tuningRecommendationKey(5), options.recommendation);
  }
  const realtime = createFakeRealtime();
  return {
    realtime,
    ...render(
      <TestProviders queryClient={queryClient} realtime={realtime.value}>
        <AiPanel controllerId={5} tag="PIC-005" />
      </TestProviders>,
    ),
  };
}

const postedPaths = (): string[] =>
  fetchMock.mock.calls
    .filter((call) => (call[1] as RequestInit).method === 'POST')
    .map((call) => String(call[0]));

beforeEach(() => {
  sessionStorage.clear();
  localStorage.clear();
  fetchMock.mockReset();
  fetchMock.mockResolvedValue(
    new Response(JSON.stringify({ ok: true }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }),
  );
  vi.stubGlobal('fetch', fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('AiPanel', () => {
  it('is absent entirely for the user role', async () => {
    renderAi({ role: 'user', recommendation: PENDING });
    await waitFor(() => expect(screen.queryByTestId('ai-panel')).not.toBeInTheDocument());
    expect(screen.queryByRole('button', { name: 'Start' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Apply tuning' })).not.toBeInTheDocument();
  });

  it('drives the optimizer lifecycle without touching the block mode', async () => {
    renderAi();
    fireEvent.click(await screen.findByRole('button', { name: 'Start' }));
    await waitFor(() => expect(postedPaths()).toContain('/api/controllers/5/ai/start'));

    fireEvent.click(screen.getByRole('button', { name: 'Pause' }));
    await waitFor(() => expect(postedPaths()).toContain('/api/controllers/5/ai/pause'));

    fireEvent.click(screen.getByRole('button', { name: 'Stop' }));
    await waitFor(() => expect(postedPaths()).toContain('/api/controllers/5/ai/stop'));

    // AUTO/MAN is a separate concern: no mode command may ride along.
    expect(postedPaths().some((p) => p.includes('/commands/mode'))).toBe(false);
  });

  // E2E-022. `enabled` alone cannot express three states: a paused engine is
  // still `enabled`, so `enabled ? RUN : STOP` reports PAUSE as RUN.
  it.each([
    { enabled: false, paused: false, state: 'STOP' },
    { enabled: false, paused: true, state: 'STOP' },
    { enabled: true, paused: false, state: 'RUN' },
    { enabled: true, paused: true, state: 'PAUSE' },
  ])('reads $state from enabled=$enabled paused=$paused', async ({ enabled, paused, state }) => {
    renderAi({ status: { enabled, paused } });
    const badge = await screen.findByTestId('ai-lifecycle');
    expect(badge).toHaveAttribute('data-state', state);
    // Text, not colour: the code itself must be legible in the header.
    expect(badge).toHaveTextContent(state);
    for (const other of ['RUN', 'PAUSE', 'STOP'].filter((s) => s !== state)) {
      expect(badge).not.toHaveTextContent(other);
    }
  });

  it('announces the paused hold in pt-BR, not by tone alone', async () => {
    renderAi({ status: { enabled: true, paused: true } });
    const badge = await screen.findByTestId('ai-lifecycle');
    expect(badge).toHaveAttribute('role', 'status');
    expect(badge).toHaveTextContent('otimizador pausado');
  });

  it('flips RUN → PAUSE once the status refetch lands after Pause', async () => {
    renderAi({ status: { enabled: true, paused: false } });
    expect(await screen.findByTestId('ai-lifecycle')).toHaveAttribute('data-state', 'RUN');

    // The refetch `useAiAction` triggers is the only channel the state travels on.
    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const body =
        (init?.method ?? 'GET') === 'GET' && String(input).endsWith('/ai/status')
          ? aiStatus({ enabled: true, paused: true })
          : { ok: true };
      return Promise.resolve(
        new Response(JSON.stringify(body), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      );
    });

    fireEvent.click(screen.getByRole('button', { name: 'Pause' }));
    await waitFor(() =>
      expect(screen.getByTestId('ai-lifecycle')).toHaveAttribute('data-state', 'PAUSE'),
    );
  });

  it('keeps Apply tuning inert until a recommendation is pending', async () => {
    renderAi();
    expect(await screen.findByRole('button', { name: 'Apply tuning' })).toBeDisabled();
  });

  it('writes the recommendation only after Confirm Write', async () => {
    renderAi({ recommendation: PENDING });

    fireEvent.click(await screen.findByRole('button', { name: 'Apply tuning' }));
    const dialog = await screen.findByRole('dialog');
    // The before/after table is the reason the stop exists.
    expect(within(dialog).getByText('1.5')).toBeVisible();
    expect(postedPaths()).not.toContain('/api/commands/apply-tuning/5');

    fireEvent.click(within(dialog).getByRole('button', { name: 'Confirm Write' }));
    await waitFor(() => expect(postedPaths()).toContain('/api/commands/apply-tuning/5'));
  });

  it('auto-applies a pending suggestion without the confirm dialog when the switch is on', async () => {
    renderAi({ recommendation: PENDING });

    fireEvent.click(
      await screen.findByRole('switch', { name: 'Auto-aplicar sintonia' }),
    );

    await waitFor(() => expect(postedPaths()).toContain('/api/commands/apply-tuning/5'));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    // Manual write is off while auto is on — one channel, not two.
    expect(screen.getByRole('button', { name: 'Apply tuning' })).toBeDisabled();
  });

  it('keeps the dialog open and shows why when the write is rejected', async () => {
    renderAi({ recommendation: PENDING });
    fireEvent.click(await screen.findByRole('button', { name: 'Apply tuning' }));
    const dialog = await screen.findByRole('dialog');

    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: 'malha não está em AUTO' }), {
        status: 409,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    fireEvent.click(within(dialog).getByRole('button', { name: 'Confirm Write' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('malha não está em AUTO');
    expect(screen.getByRole('dialog')).toBeVisible();
  });

  it('streams LOG.AI events into the terminal box', async () => {
    const { realtime } = renderAi();
    const log = await screen.findByRole('log', { name: 'LOG.AI' });
    expect(log).toHaveTextContent('Sem eventos de IA.');

    act(() => {
      realtime.emit(aiEvent(1));
      realtime.emit(aiEvent(2, { reasoning: 'estabilizou' }));
    });

    expect(log).toHaveTextContent('erro alto, subindo Ki');
    expect(log).toHaveTextContent('estabilizou');
  });

  it('names the auto-apply switch with its visible label', async () => {
    renderAi({ recommendation: PENDING });
    // The label is what an operator reads and what a voice-control user says,
    // so it has to BE the accessible name (WCAG 2.5.3), not sit beside a
    // separately-worded aria-label.
    const toggle = await screen.findByRole('switch', { name: 'Auto-aplicar sintonia' });
    expect(toggle).toHaveAttribute('aria-checked', 'false');
  });

  it('toggles auto-apply by clicking the label, not just the switch', async () => {
    renderAi({ recommendation: PENDING });
    const label = await screen.findByText('Auto-aplicar sintonia');

    fireEvent.click(label);

    await waitFor(() =>
      expect(screen.getByRole('switch', { name: 'Auto-aplicar sintonia' })).toHaveAttribute(
        'aria-checked',
        'true',
      ),
    );
    expect(localStorage.getItem('smartpid:autoTune:5')).toBe('1');
  });
});
