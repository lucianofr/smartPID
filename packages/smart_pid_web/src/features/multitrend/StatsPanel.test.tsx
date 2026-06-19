import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { StatsPanel } from './StatsPanel';

describe('StatsPanel', () => {
  it('renders all eight metrics per loop with formatted values', () => {
    render(
      <StatsPanel
        rows={[
          {
            loopId: 1,
            iae: 1.5,
            itae: 2.5,
            ise: 3.5,
            mse: 0.25,
            sigma: 0.4,
            tv: 12,
            varRange: 0.08,
            varSp: 0.02,
          },
        ]}
      />,
    );
    expect(screen.getByText('IAE')).toBeInTheDocument();
    expect(screen.getByText('1.500')).toBeInTheDocument();
    expect(screen.getByText('TV')).toBeInTheDocument();
    expect(screen.getByText('8.0%')).toBeInTheDocument(); // var_range as %
    expect(screen.getByText('2.0%')).toBeInTheDocument(); // var_sp as %
  });

  it('shows an empty state when no loops have stats', () => {
    render(<StatsPanel rows={[]} />);
    expect(screen.getByText(/no statistics/i)).toBeInTheDocument();
  });
});
