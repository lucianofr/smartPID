import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import type { ReactNode } from 'react';

const stats = [
  {
    controller_id: 1, iae: 12.5, itae: 200, ise: 30, mse: 1.1, std_dev: 0.8,
    total_variation: 4.2, variability_sp: 0.03, variability_range: 0.04, sample_count: 600,
  },
  {
    controller_id: 2, iae: 7.5, itae: 100, ise: 15, mse: 0.6, std_dev: 0.5,
    total_variation: 1.8, variability_sp: 0.05, variability_range: 0.06, sample_count: 600,
  },
];
const controllers = [
  { id: 1, name: 'FIC-101', mode: 'AUTO' },
  { id: 2, name: 'TIC-202', mode: 'MAN' },
];

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
  apiGet: vi.fn((path: string) => {
    if (path === '/controllers/stats') return Promise.resolve(stats);
    if (path === '/controllers') return Promise.resolve(controllers);
    if (path === '/opcua/status') {
      return Promise.resolve({ state: 'ONLINE', endpoint: 'opc.tcp://x:4840' });
    }
    if (path === '/alarms/active') return Promise.resolve([]); // AlarmBar
    if (path.startsWith('/alarms/ai-history')) return Promise.resolve([]); // querystring
    return Promise.resolve(null); // ai-status -> '—'; tuning-rec -> null
  }),
  apiPost: vi.fn(() => Promise.resolve(null)),
  ApiError: class ApiError extends Error {},
}));

import { ExecutiveDashboardPage } from './ExecutiveDashboardPage';
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

describe('ExecutiveDashboardPage', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders aggregate KPI values equal to the values derived from mocked REST', async () => {
    render(<ExecutiveDashboardPage />, { wrapper });
    // avgIae = (12.5+7.5)/2 = 10.00 ; totalTv = 4.2+1.8 = 6.00
    // avgVariabilityRange = (0.04+0.06)/2 = 0.05 -> 5.0% ; autoPct = 1/2 = 50%
    // The KPI cards mount immediately with seeded zeros, then the /controllers/stats
    // query resolves and re-renders the real numbers; wait on that resolved value.
    expect(await screen.findByText('10.00')).toBeInTheDocument();
    expect(screen.getByTestId('kpi-iae')).toHaveTextContent('10.00');
    expect(screen.getByTestId('kpi-tv')).toHaveTextContent('6.00');
    expect(screen.getByTestId('kpi-variability')).toHaveTextContent('5.0%');
    expect(screen.getByTestId('kpi-auto')).toHaveTextContent('50.0%');
    expect(screen.getByTestId('kpi-loops')).toHaveTextContent('2');
  });

  it('shows OPC ONLINE for both loops and marks AUTO/MAN health', async () => {
    render(<ExecutiveDashboardPage />, { wrapper });
    expect(await screen.findByTestId('health-FIC-101-opc')).toHaveTextContent('ONLINE');
    expect(screen.getByTestId('health-FIC-101-state')).toHaveTextContent('running');
    expect(screen.getByTestId('health-TIC-202-state')).toHaveTextContent('running');
  });

  it('changing the period selector keeps the dashboard mounted (period-window selection)', async () => {
    render(<ExecutiveDashboardPage />, { wrapper });
    const select = await screen.findByLabelText('Aggregation period');
    fireEvent.change(select, { target: { value: '24h' } });
    expect((select as HTMLSelectElement).value).toBe('24h');
    expect(screen.getByTestId('executive-dashboard')).toBeInTheDocument();
  });
});
