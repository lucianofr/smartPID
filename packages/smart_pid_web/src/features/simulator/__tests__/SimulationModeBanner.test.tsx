import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { SimulationModeBanner } from '../SimulationModeBanner';

/**
 * The banner answers one safety question: "are these numbers the plant, or a
 * model?". `role="status"` + the accessible name are frozen — e2e/simulator
 * binds to them — and the live region means the operator is told the moment the
 * twin starts stepping.
 */
describe('SimulationModeBanner', () => {
  it('is a named live region whether or not the twin is stepping', () => {
    const { rerender } = render(<SimulationModeBanner running={false} />);
    expect(screen.getByRole('status', { name: 'Simulation mode' })).toBeVisible();
    rerender(<SimulationModeBanner running />);
    expect(screen.getByRole('status', { name: 'Simulation mode' })).toBeVisible();
  });

  it('claims SIMULAÇÃO ATIVA only while the twin is actually running', () => {
    const { rerender } = render(<SimulationModeBanner running={false} />);
    expect(screen.queryByText('SIMULAÇÃO ATIVA')).toBeNull();
    expect(screen.getByText('MODO SIMULAÇÃO')).toBeVisible();
    rerender(<SimulationModeBanner running />);
    expect(screen.getByText('SIMULAÇÃO ATIVA')).toBeVisible();
  });
});
