import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import type { ReactNode } from 'react';
import * as api from '../features/simulator/api';

vi.mock('../features/simulator/api');
vi.mock('../realtime/useRealtime', () => ({
  useRealtime: () => ({
    connected: true,
    lastStatus: new Map(),
    lastStats: new Map(),
    subscribe: () => () => {},
    onResync: () => () => {},
  }),
}));
vi.mock('../api/client', () => ({
  apiGet: vi.fn(async () => []),
  apiPost: vi.fn(async () => ({})),
}));
// uPlot needs a real canvas; stub the trend to keep this a layout test.
vi.mock('../components/RealtimeTrend', () => ({
  RealtimeTrend: () => <div data-testid="twin-trend" />,
}));

import { SimulatorPage } from './SimulatorPage';
import { ThemeProvider } from '../theme/ThemeProvider';

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={qc}>
      <ThemeProvider>
        <MemoryRouter>{children}</MemoryRouter>
      </ThemeProvider>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.getSimulatorStatus).mockResolvedValue({
    enabled: true,
    running: false,
    controllers: {
      1: {
        preset: 'FLOW',
        gain: 1.2,
        tau1: 3,
        tau2: null,
        dead_time: 1,
        step_active: false,
        step_amplitude: 0,
        noise_active: false,
        noise_amplitude: 0,
        pid_mode: 0,
        co: 0,
        sp: 50,
        pv: 50,
        auto_sp: null,
        auto_disturbance: null,
      },
    },
  } as never);
});

describe('SimulatorPage', () => {
  it('shows the simulation banner, the twin trend and the controls', async () => {
    render(<SimulatorPage />, { wrapper });
    expect(screen.getByRole('status', { name: /simulation mode/i })).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByLabelText(/simulator controls/i)).toBeInTheDocument(),
    );
    expect(screen.getByTestId('twin-trend')).toBeInTheDocument();
  });
});
