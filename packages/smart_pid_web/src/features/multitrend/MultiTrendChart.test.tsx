import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { MultiTrendChart } from './MultiTrendChart';
import type { AlignedSeries } from './multiTrendData';

// uPlot needs canvas measure APIs jsdom lacks (stubbed in setup.ts); assert the
// chart mount + §6d tabular readout DOM nodes render, not canvas pixels.
describe('MultiTrendChart', () => {
  // Empty (but shaped) data: uPlot mounts without a deferred canvas draw that would
  // hit jsdom's missing Path2D (same convention as RealtimeTrend.test).
  const series: AlignedSeries = {
    keys: [{ loopId: 1, variable: 'pv' }],
    data: [[], []],
  };

  it('preserves the multitrend-chart mount node', () => {
    render(<MultiTrendChart series={series} onPxWidth={() => {}} />);
    expect(screen.getByTestId('multitrend-chart')).toBeInTheDocument();
  });

  it('renders a tabular cursor readout node', () => {
    render(<MultiTrendChart series={series} onPxWidth={() => {}} />);
    const readout = screen.getByTestId('multitrend-readout');
    expect(readout).toBeInTheDocument();
    expect(readout.className).toContain('numeric');
    // No hover in jsdom → idle prompt is shown in the readout.
    expect(within(readout).getByText(/hover to read values/i)).toBeInTheDocument();
  });
});
