import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { AnyEnvelope, StatsData } from '@/lib/envelope';
import { createFakeRealtime, createQueryClient, TestProviders } from '@/test/providers';
import { appRoutes } from '@/app/routes';
import { ExecutiveDashboardPage } from './ExecutiveDashboardPage';

const METRICS: StatsData = {
  iae: 12.5,
  ise: 30,
  itae: 200,
  mse: 1.1,
  std_dev: 0.8,
  total_variation: 4.2,
  variability_range: 0.04,
  variability_sp: 0.03,
  sample_count: 600,
  mean_abs_error: 0,
  osc: 0,
  osc_sample_count: 0,
  overshoot: 0,
  pk_pk_error: 0,
  recent_pk_pk_error: 0,
  recent_reversals: 0,
  reversals: 0,
  sp_pk_pk: 0,
  tv_per_sample: 0,
  zero_crossings: 0,
};

const CONTROLLERS = [
  {
    id: 1,
    name: 'FIC-101',
    description: 'Flow',
    mode: 'AUTO',
    optimization_enabled: true,
    ai_config: { engine: 'FUZZY' },
  },
  {
    id: 2,
    name: 'TIC-202',
    description: 'Temp',
    mode: 'MAN',
    optimization_enabled: false,
    ai_config: { engine: 'NONE' },
  },
];

const fetchMock = vi.fn();

beforeEach(() => {
  localStorage.setItem('smart-pid-token', 'jwt');
  vi.stubGlobal('fetch', fetchMock);
  fetchMock.mockImplementation((path: string) => {
    const body =
      path.startsWith('/api/controllers/stats') ? [{ ...METRICS, controller_id: 1 }]
      : path.startsWith('/api/controllers') ? CONTROLLERS
      : path.startsWith('/api/opcua/status') ? { state: 'ONLINE', endpoint: 'opc.tcp://x' }
      : path.startsWith('/api/system/status')
        ? { status: 'running', uptime_s: 3661, active_controllers: 2, bus_active: true, api_version: '2.0.0' }
      : path.startsWith('/api/alarms/ai-history') ? []
      : path.startsWith('/api/auth/me') ? { user_id: 1, username: 'admin', role: 'admin' }
      : null;
    if (body === null) return Promise.reject(new Error(`unstubbed ${path}`));
    return Promise.resolve({ ok: true, status: 200, json: async () => body });
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
  fetchMock.mockReset();
  localStorage.clear();
  sessionStorage.clear();
});

function renderPage() {
  const realtime = createFakeRealtime();
  return {
    realtime,
    ...render(
      <TestProviders queryClient={createQueryClient()} realtime={realtime.value}>
        <ExecutiveDashboardPage />
      </TestProviders>,
    ),
  };
}

describe('ExecutiveDashboardPage', () => {
  it('answers the four buyer questions on one screen', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByTestId('kpi-iae')).toHaveTextContent('12.50'));

    expect(screen.getByTestId('kpi-auto')).toHaveTextContent('50.0%');
    expect(screen.getByTestId('kpi-ai')).toHaveTextContent('50.0%');
    expect(screen.getByTestId('kpi-variability')).toHaveTextContent('4.0%');
    expect(screen.getByRole('region', { name: 'Retorno da IA' })).toBeVisible();
    expect(screen.getByRole('region', { name: 'Saúde do backend' })).toBeVisible();
    expect(screen.getByRole('link', { name: 'FIC-101' })).toHaveAttribute('href', '/?loop=1');
  });

  it('reports OPC reachability and uptime next to each loop', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByTestId('health-FIC-101-opc')).toHaveTextContent('ONLINE'));
    expect(screen.getByTestId('health-uptime')).toHaveTextContent('1 h 1 min');
    expect(screen.getByTestId('health-cpu')).toHaveTextContent('—');
  });

  it('lets a live stats frame move the KPI without a refetch', async () => {
    const { realtime } = renderPage();
    await waitFor(() => expect(screen.getByTestId('kpi-iae')).toHaveTextContent('12.50'));

    const frame: AnyEnvelope = {
      type: 'stats',
      loop_id: 1,
      seq: 2,
      ts: 2,
      data: { ...METRICS, iae: 9 },
    };
    act(() => realtime.emit(frame));

    expect(screen.getByTestId('kpi-iae')).toHaveTextContent('9.00');
  });

  it('re-windows the AI history when the period changes', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByTestId('kpi-iae')).toHaveTextContent('12.50'));
    const before = fetchMock.mock.calls.filter((c: unknown[]) =>
      String(c[0]).includes('/alarms/ai-history'),
    ).length;

    fireEvent.change(screen.getByLabelText('Período'), { target: { value: '1h' } });

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.filter((c: unknown[]) => String(c[0]).includes('/alarms/ai-history'))
          .length,
      ).toBeGreaterThan(before),
    );
    expect(within(screen.getByRole('region', { name: 'Retorno da IA' })).getByText('Última hora')).toBeVisible();
  });

  it('says the AI window cannot be scored instead of showing zeros', async () => {
    renderPage();
    await waitFor(() =>
      expect(screen.getByText('Dados insuficientes para comparar antes e depois.')).toBeVisible(),
    );
  });
});

describe('/executive registration', () => {
  it('is reachable from the top bar, both consultative and unrestricted', () => {
    const route = appRoutes.find((r) => r.path === '/executive');
    expect(route).toBeDefined();
    expect(route?.nav).toEqual({ label: 'Executivo', order: 50 });
    expect(route?.cfg).toBeUndefined();
    expect(route?.adminOnly).toBeUndefined();
  });
});
