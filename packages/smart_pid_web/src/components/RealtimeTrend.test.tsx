import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { RealtimeTrend } from './RealtimeTrend';

// uPlot touches canvas/measure APIs jsdom lacks; assert it mounts without throwing.
describe('RealtimeTrend', () => {
  it('mounts with empty data', () => {
    const { container } = render(<RealtimeTrend data={[[], [], [], []]} />);
    expect(container.firstChild).toBeTruthy();
  });

  // §6d: tabular hover readout. Canvas is stubbed in setup.ts so cursor pixels are
  // not assertable; assert the readout DOM node exists with the tabular-nums hook
  // (`numeric`) and the PV/SP/CO rows.
  it('renders a tabular PV/SP/CO cursor readout', () => {
    render(<RealtimeTrend data={[[], [], [], []]} />);
    const readout = screen.getByTestId('trend-readout');
    expect(readout).toBeInTheDocument();
    expect(readout.className).toContain('numeric');
    const cells = within(readout);
    for (const label of ['PV', 'SP', 'CO']) {
      expect(cells.getByText(label)).toBeInTheDocument();
    }
  });
});
