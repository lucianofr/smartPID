import type { ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { DashboardPage } from './DashboardPage';
import { ThemeProvider } from '../theme/ThemeProvider';
import type { ControllerResponse } from '../api/controllers';
import type { StatusData } from '../realtime/envelope';

const sig = (value: number) => ({
  value,
  severity: 'GOOD',
  limit_bits: 'NONE',
  sub_status: 'NON_SPECIFIC',
});

const controller: ControllerResponse = {
  id: 9,
  name: 'TIC-009',
  description: 'Temperature',
  pv_decimals: 1,
  pv_unit: '°C',
  pid_params: { gain: 1.5, reset: 30, rate: 0, alpha: 0.1, deadband: 0 },
  pid_structure: 'ISA',
  ai_config: {
    engine: 'FUZZY',
    objective: 'SP_TRACKING',
    dead_time_l: 5,
    limit_min: 0.5,
    limit_max: 2,
    rl_fallback_kp: 1,
    rl_fallback_kd: 0,
    rl_learning_rate: 0.001,
    rl_train_interval: 100,
  },
  optimization_enabled: true,
  out_hi_lim: 100,
  out_lo_lim: 0,
  arw_hi_lim: 100,
  arw_lo_lim: 0,
  pv_ftime: 0,
  sp_ftime: 0,
  sp_rate_up: 0,
  sp_rate_dn: 0,
};

// MAN mode arrives live via the WS status frame, NOT from the REST response.
const liveStatus: StatusData = {
  pv: sig(70),
  sp: sig(72),
  co: sig(40),
  bkcal_in: sig(0),
  bkcal_out: sig(0),
  mode: 'MAN',
  kp: 1.5,
  ti: 30,
  td: 0,
  integral_val: 0,
  timestamp: '2026-06-19T00:00:00Z',
};

const lastStatus = new Map<number, StatusData>([[9, liveStatus]]);

vi.mock('../realtime/useRealtime', () => ({
  useRealtime: () => ({
    connected: true,
    lastStatus,
    lastStats: new Map(),
    subscribe: () => () => {},
    onResync: () => () => {},
  }),
}));

const cardControlsSpy = vi.fn();
vi.mock('../features/loop-config/CardControls', () => ({
  CardControls: (props: { controllerId: number; mode: string; optimizationEnabled: boolean }) => {
    cardControlsSpy(props);
    return <div data-testid={`card-controls-${props.controllerId}`} />;
  },
}));

// Keep the AiPanel out of the integration surface (it owns its own queries).
vi.mock('../features/loop-config/AiPanel', () => ({
  AiPanel: ({ controllerId }: { controllerId: number }) => (
    <div data-testid={`ai-panel-${controllerId}`} />
  ),
}));

vi.mock('../api/client', () => ({
  apiGet: vi.fn((path: string) => {
    if (path === '/controllers') return Promise.resolve([controller]);
    if (path === '/opcua/status')
      return Promise.resolve({ state: 'ONLINE', endpoint: null });
    return Promise.reject(new Error(`unexpected path ${path}`));
  }),
}));

function renderDashboard(): void {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>
      <ThemeProvider>
        <MemoryRouter>{children}</MemoryRouter>
      </ThemeProvider>
    </QueryClientProvider>
  );
  render(<DashboardPage />, { wrapper });
}

describe('DashboardPage wiring (Fatia 2)', () => {
  beforeEach(() => {
    cardControlsSpy.mockReset();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('passes the live mode and optimizationEnabled into CardControls', async () => {
    renderDashboard();
    await screen.findByText('TIC-009');
    expect(cardControlsSpy).toHaveBeenCalledWith(
      expect.objectContaining({ controllerId: 9, mode: 'MAN', optimizationEnabled: true }),
    );
  });

  it('renders an AiPanel per controller', async () => {
    renderDashboard();
    expect(await screen.findByTestId('ai-panel-9')).toBeInTheDocument();
  });

  it('opens the LoopConfigDialog for the right controller when the ⚙ is clicked', async () => {
    renderDashboard();
    await screen.findByText('TIC-009');
    expect(screen.queryByRole('dialog')).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: /config/i }));

    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByText(/Configurar Loop #9/)).toBeInTheDocument();
    // Full ai_config round-trips into the dialog: the FUZZY engine radio is checked.
    const fuzzyRadio = within(dialog).getByRole('radio', { name: 'FUZZY' }) as HTMLInputElement;
    expect(fuzzyRadio.checked).toBe(true);
  });
});
