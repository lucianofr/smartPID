import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { SimulationModeBanner } from '../SimulationModeBanner';

describe('SimulationModeBanner', () => {
  it('renders persistent SIMULATION MODE label with status role', () => {
    render(<SimulationModeBanner />);
    const banner = screen.getByRole('status', { name: /simulation mode/i });
    expect(banner).toBeInTheDocument();
    expect(banner).toHaveTextContent(/MODO SIMULAÇÃO/i);
    expect(banner).toHaveTextContent(/digital twin/i);
  });
});
