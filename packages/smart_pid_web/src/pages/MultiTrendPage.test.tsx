import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import type { ReactNode } from 'react';

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
// uPlot needs a real canvas; stub the chart to keep this a layout test.
vi.mock('../features/multitrend/MultiTrendChart', () => ({
  MultiTrendChart: () => <div data-testid="multitrend-chart" />,
}));

import { MultiTrendPage } from './MultiTrendPage';
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

describe('MultiTrendPage', () => {
  it('renders the trend, series selector, and stats panel regions', () => {
    render(<MultiTrendPage />, { wrapper });
    expect(screen.getByTestId('multitrend-chart')).toBeInTheDocument();
    expect(screen.getByText('Séries')).toBeInTheDocument();
    expect(screen.getByLabelText(/history query/i)).toBeInTheDocument();
  });
});
