import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ExecutiveKPICard } from './ExecutiveKPICard';

describe('ExecutiveKPICard', () => {
  it('renders the exact formatted KPI value and label', () => {
    render(<ExecutiveKPICard label="Variability 2σ/RANGE" value="4.2%" testId="kpi-var" />);
    const card = screen.getByTestId('kpi-var');
    expect(card).toHaveTextContent('4.2%');
    expect(card).toHaveTextContent('Variability 2σ/RANGE');
  });

  it('marks the delta out-of-target so styling can react (data attribute, not color-only)', () => {
    render(
      <ExecutiveKPICard
        label="Variability"
        value="6.0%"
        delta={{ dir: 'up', value: '+1.0%', outOfTarget: true }}
        testId="kpi-bad"
      />,
    );
    expect(screen.getByTestId('kpi-bad-delta')).toHaveAttribute('data-out-of-target', 'true');
  });

  it('does not flag a within-target delta', () => {
    render(
      <ExecutiveKPICard
        label="Variability"
        value="4.0%"
        delta={{ dir: 'down', value: '-0.5%', outOfTarget: false }}
        testId="kpi-ok"
      />,
    );
    expect(screen.getByTestId('kpi-ok-delta')).toHaveAttribute('data-out-of-target', 'false');
  });
});
