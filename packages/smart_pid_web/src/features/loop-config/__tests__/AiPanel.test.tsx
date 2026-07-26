import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { endpoints } from '@/api/endpoints';
import { queryKeys } from '@/api/queryKeys';
import type { Role } from '@/api/types';
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

function renderAi(
  options: { role?: Role; recommendation?: TuningRecommendation; engine?: string } = {},
) {
  const role = options.role ?? 'admin';
  sessionStorage.setItem('smart-pid-token', 'jwt');
  vi.spyOn(endpoints, 'me').mockResolvedValue({ user_id: 1, username: role, role });
  const controller = makeController({ id: 5, name: 'PIC-005' });
  controller.ai_config = { ...controller.ai_config, engine: options.engine ?? 'FUZZY' };
  const queryClient = createQueryClient();
  queryClient.setQueryData(queryKeys.controllers, [controller]);
  queryClient.setQueryData(queryKeys.aiStatus(5), {
    controller_id: 5,
    engine: 'FUZZY',
    objective: 'SP_TRACKING',
    speed: 'MEDIUM',
    current_ki: 0.03,
    last_gamma: null,
    enabled: false,
  });
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

  it('offers the three engines and the guardrail band', async () => {
    renderAi();
    const engine = await screen.findByLabelText('Motor');
    expect(within(engine).getAllByRole('option').map((o) => o.textContent)).toEqual([
      'NONE',
      'FUZZY',
      'RL',
    ]);
    expect(screen.getByLabelText('Tempo morto L')).toBeInTheDocument();
    expect(screen.getByLabelText('Limite mín.')).toBeInTheDocument();
    expect(screen.getByLabelText('Limite máx.')).toBeInTheDocument();
    expect(screen.getByLabelText('Velocidade do processo')).toBeInTheDocument();
  });

  it('refuses to save an inverted guardrail band', async () => {
    renderAi();
    fireEvent.change(await screen.findByLabelText('Limite mín.'), { target: { value: '500' } });
    expect(await screen.findByText('Limite mínimo deve ser menor que o máximo')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Salvar IA' })).toBeDisabled();
  });
});
